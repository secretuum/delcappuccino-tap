#!/usr/bin/env python3
"""Собирает из данных главной всё, что читают поисковики и ИИ-боты без JavaScript: разметку schema.org (JSON-LD)
в <head> index.html, раздел «Частые вопросы» на главной, страницу меню текстом /menyu, /llms.txt и lastmod в sitemap.xml.

Запуск из корня репозитория после правки меню (массивы MENU_* / TOGO_*), точек (BRANCHES) или tools/faq.json:
    python3 tools/seo_jsonld.py && python3 tools/sw_version.py      # порядок важен: sw_version хэширует index.html
С ключом --check только сравнивает и выходит с кодом 1, если что-то устарело (tests/test_seo.py).

Источники — только сама страница и tools/faq.json, ничего не придумывается:
- JSON-LD: организация Del Cappuccino (sameAs — ссылки Instagram со страницы, заказ онлайн — OrderAction),
  5 точек из BRANCHES — 01–04 CafeOrCoffeeShop, 05 Bakery; адрес, координаты, телефон и часы — только из BRANCHES
  (город и страна — «5 точек в Алматы» из текста сайта). Юрлиц, ИП и имён людей в разметке нет и быть не должно.
  Меню кофеен с ценами в тенге — по разделам; у позиции с несколькими ценами — Offer на каждый объём из vol,
  если объёмов столько же, сколько цен, иначе AggregateOffer (от и до); позиция с only:[…] (есть не во всех
  кофейнях) — availableAtOrFrom на эти точки. В sameAs точки — только ссылка 2GIS на карточку фирмы (…/firm/<id>);
  поисковые ссылки 2GIS (…/search/…) — не карточки, их не кладём (главный, 22.10.2026). FAQPage — из tools/faq.json.
- «Частые вопросы» (#faq): <details> без JS, тот же текст, что в FAQPage. В ответах можно {часы}, {адреса}, {точек} —
  подставляются из BRANCHES, чтобы ответ не разошёлся с точками. Допустимый HTML в ответах: <a href>, <ul>, <li>.
- /menyu (menyu/index.html): всё меню текстом — кофейни (вкладки MENU_TABS) и Bakery to go (вкладки режима togo),
  разделы, объёмы, цены ₸, «только: …», старая цена зачёркнута. Путь не /menu/: там папка данных карточек menu/.
- /llms.txt: короткая справка для ИИ (ru + en) — точки, часы, ссылки; английские названия — из словаря MENU_TR.en.
Разбор не по шаблону (позиций меньше, чем {n:'…} в массиве; точка без адреса) — выход с ошибкой, а не тихий пропуск.
lastmod в sitemap.xml: дата последнего коммита страницы, а если в ней есть незакоммиченные правки — сегодня.
Только stdlib.
"""
import datetime, html as H, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, 'index.html')
SITEMAP = os.path.join(ROOT, 'sitemap.xml')
FAQ_JSON = os.path.join(ROOT, 'tools', 'faq.json')
MENU_PAGE = os.path.join(ROOT, 'menyu', 'index.html')
LLMS = os.path.join(ROOT, 'llms.txt')
SITE = 'https://tap.delcappuccino.kz/'
MENU_URL = SITE + 'menyu'
ORDER_URL = 'https://delcappuccino.kz/'      # заказ онлайн и приложение
MENU_ARRAYS = ('MENU_KITCHEN', 'MENU_BAR', 'MENU_DESSERT')
DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
MARK = '<!-- schema.org: организация, точки из BRANCHES и меню с ценами — tools/seo_jsonld.py, руками не править -->'
BLOCK_RE = re.compile(re.escape(MARK) + r'\n<script type="application/ld\+json">\n(.*?)\n</script>\n', re.S)
FAQ_MARK = '<!-- Частые вопросы: данные tools/faq.json, собирает tools/seo_jsonld.py (тот же текст — FAQPage в JSON-LD), руками не править -->'
FAQ_RE = re.compile(re.escape(FAQ_MARK) + r'\n.*?<!-- /faq -->\n', re.S)
FAQ_BEFORE = '<section class="contact shell" id="contacts">'
PAGES = {SITE: 'index.html', SITE + 'ugolok': 'ugolok/index.html', MENU_URL: 'menyu/index.html'}


def js_array(html, name):
    """Текст литерала const NAME = [ … ]; (до парной скобки)"""
    i = html.index('const %s = [' % name) + len('const %s = ' % name)
    depth, j = 0, i
    while True:
        depth += (html[j] == '[') - (html[j] == ']')
        j += 1
        if not depth:
            return html[i:j]


def unq(s):
    return s.replace("\\'", "'")


def field(obj, key):
    m = re.search(r"\b%s:'((?:[^'\\]|\\.)*)'" % key, obj)
    return unq(m.group(1)) if m else None


def num_or_str(obj, key):
    m = re.search(r"\b%s:(?:'([^']*)'|(\d+))" % key, obj)
    return (m.group(1) or m.group(2)) if m else None


def str_list(obj, key):
    m = re.search(r"\b%s:\[([^\]]*)\]" % key, obj)
    return re.findall(r"'([^']*)'", m.group(1)) if m else []


def branches(html):
    out, src = [], js_array(html, 'BRANCHES')
    for m in re.finditer(r"\{n:'(?:[^'\\]|\\.)*'[^\n]*\}", src):
        b = m.group(0)
        geo = re.search(r"geo:\[([-\d.]+),\s*([-\d.]+)\]", b)
        out.append({'n': field(b, 'n'), 'addr': field(b, 'addr'), 'phone': field(b, 'phone'), 'hours': field(b, 'hours'),
                    'menu': field(b, 'menu'), 'route': field(b, 'route'),
                    'geo': (float(geo.group(1)), float(geo.group(2))) if geo else None})
    if len(out) != src.count("{n:'") or not all(b['geo'] and b['addr'] and b['phone'] for b in out):
        sys.exit('seo_jsonld: BRANCHES разобран не целиком (точка в несколько строк или без geo/addr/phone) — допишите разбор')
    return out


def sections(html, name):
    """[{t, p, badge, note, items:[{n, p, old, vol, note, m, only}]}] массива меню; p — число или строка «1400/1500»,
    only — номера точек, где позиция есть (['04', '02']), m — пометки (['new', 'hit'])"""
    s, out, found = js_array(html, name), [], 0
    for m in re.finditer(r"\{t:'((?:[^'\\]|\\.)*)'([^\[\]]*?)items:\[", s):
        head, i, depth, j = m.group(2), m.end(), 1, m.end()
        while depth:
            depth += (s[j] == '[') - (s[j] == ']')
            j += 1
        items = [{'n': unq(im.group(1)), 'p': num_or_str(im.group(2), 'p'), 'old': num_or_str(im.group(2), 'old'),
                  'vol': field(im.group(2), 'vol'), 'note': field(im.group(2), 'note'),
                  'm': str_list(im.group(2), 'm'), 'only': str_list(im.group(2), 'only')}
                 for im in re.finditer(r"\{n:'((?:[^'\\]|\\.)*)'([^{}]*)\}", s[i:j - 1])]
        found += len(items)
        out.append({'t': unq(m.group(1)), 'p': num_or_str(head, 'p'), 'badge': field(head, 'badge'),
                    'note': field(head, 'note'), 'items': items})
    if found != s.count("{n:'"):
        sys.exit('seo_jsonld: в %s разобрано %d позиций из %d — раздел или позиция не по шаблону, допишите разбор'
                 % (name, found, s.count("{n:'")))
    return out


def menu_sections(html):
    """[(раздел, [(название, p, vol, only)])] меню кофеен для JSON-LD: MENU_KITCHEN / MENU_BAR / MENU_DESSERT"""
    return [(s['t'], [(it['n'], it['p'], it['vol'], it['only']) for it in s['items']])
            for name in MENU_ARRAYS for s in sections(html, name)]


def obj_block(html, start, stop):
    i = html.index(start)
    return html[i:html.index(stop, i)]


def ui_ru(html):
    """MENU_UI.ru: подписи вкладок, сервисный сбор, аллергия"""
    return {k: unq(v) for k, v in re.findall(r"(\w+):'((?:[^'\\]|\\.)*)'", obj_block(html, '  ru:{to_togo', '\n  kk:{'))}


def tr_en(html):
    """MENU_TR.en: русская строка → английская (названия точек, адреса)"""
    return {unq(a): unq(b) for a, b in re.findall(r"'((?:[^'\\]|\\.)*)':'((?:[^'\\]|\\.)*)'",
                                                   obj_block(html, '\n en:{', '\n },'))}


def mode_tabs(html):
    """{'cafe': [(вкладка, массив)], 'togo': [...]} — как в MENU_TABS и MENU_MODES.togo"""
    cafe = re.search(r'const MENU_TABS = \{([^}]*)\}', html).group(1)
    togo = re.search(r'togo:\{tabs:\{([^}]*)\}', html).group(1)
    return {'cafe': re.findall(r'(\w+):(\w+)', cafe), 'togo': re.findall(r'(\w+):(\w+)', togo)}


def mark_names(html):
    """пометка → слово из легенды: new → «новинка», hot → «острое блюдо» (MK + LEGEND); без легенды — не показываем"""
    mk = dict(re.findall(r"(\w+):'<[^>]*>([^<]*)</[^>]*>'", obj_block(html, 'const MK = {', '};')))
    legend = dict(re.findall(r"'(\S+) — ([^']*)'", obj_block(html, 'const LEGEND = {', '};')))
    return {k: legend[sym] for k, sym in mk.items() if sym in legend}


# ── точки: подписи и часы ──

def place(b):
    """«ЖК Вавилон (Розыбакиева, 247/8)» — как всплывашка «Только:» в меню (branchLabel)"""
    return '%s (%s)' % (re.sub(r'^\d+\s*·\s*', '', b['n']), b['addr'])


def hours_ru(h):
    return 'круглосуточно (24/7)' if h == '24/7' else h


def plural(n, one, few, many):
    n10, n100 = n % 10, n % 100
    return one if n10 == 1 and n100 != 11 else few if 2 <= n10 <= 4 and not 12 <= n100 <= 14 else many


def hours_text(bs):
    """(«4 кофейни работают круглосуточно, 24/7: …», [«Bakery to go · ЖК City (Жандосова, 94/12) — ежедневно 07:00–22:00»])"""
    cafes = [b for b in bs if b['hours'] == '24/7']
    first = '%d %s %s круглосуточно, 24/7: %s' % (len(cafes), plural(len(cafes), 'кофейня', 'кофейни', 'кофеен'),
                                                  'работает' if len(cafes) == 1 else 'работают', ', '.join(place(b) for b in cafes))
    return first, ['%s — %s' % (place(b), b['hours']) for b in bs if b['hours'] != '24/7']


def faq_vars(html):
    e = lambda s: H.escape(s, quote=False)
    bs = branches(html)
    first, rest = hours_text(bs)
    return {'часы': ' '.join(e(x) + '.' for x in [first] + rest),
            'адреса': '<ul>' + ''.join('<li>%s — %s</li>' % (e(place(b)), e(hours_ru(b['hours']))) for b in bs) + '</ul>',
            'точек': '%d %s' % (len(bs), plural(len(bs), 'точка', 'точки', 'точек'))}


def faq(html):
    """[(вопрос, ответ-HTML)] из tools/faq.json с подстановкой {часы} {адреса} {точек}"""
    with open(FAQ_JSON, encoding='utf-8') as f:
        data = json.load(f)
    v = faq_vars(html)
    out = []
    for e in data:
        a = re.sub(r'\{(\w+)\}', lambda m: v[m.group(1)], e['a'])
        bad = re.sub(r'</?(a|ul|li)\b[^>]*>', '', a)
        if '<' in bad or '{' in a:
            sys.exit('seo_jsonld: в ответе FAQ «%s» неизвестная подстановка или тег (можно <a href>, <ul>, <li>)' % e['q'])
        out.append((e['q'], a))
    return out


def faq_block(items):
    rows = '\n'.join('      <details><summary>%s</summary><div class="faq-a">%s</div></details>' % (H.escape(q, quote=False), a)
                     for q, a in items)
    return (FAQ_MARK + '\n<section class="faq" id="faq">\n  <div class="shell">\n    <div class="faq-head">\n'
            '      <div><p class="tag">вопросы и ответы</p><h2>Частые <span>вопросы</span>.</h2></div>\n'
            '      <p>Всё меню с ценами текстом — <a href="/menyu">на отдельной странице</a>.</p>\n    </div>\n'
            '    <div class="faq-list">\n' + rows + '\n    </div>\n  </div>\n</section>\n<!-- /faq -->\n')


# ── JSON-LD ──

def offers(p, vol, only=()):
    """only — позиция есть не во всех кофейнях: availableAtOrFrom со ссылками на эти точки"""
    at = {'availableAtOrFrom': [{'@id': SITE + '#branch-' + n} for n in only]} if only else {}
    prices = [int(x.strip()) for x in str(p).split('/')]
    if len(prices) == 1:
        return dict({'@type': 'Offer', 'price': prices[0], 'priceCurrency': 'KZT'}, **at)
    sizes = [x.strip() for x in (vol or '').split('/')]
    unit = re.match(r'[\d.,]+\s*(.*)$', sizes[-1]) if len(sizes) == len(prices) else None
    if unit and all(re.fullmatch(r'[\d.,]+', x) for x in sizes[:-1]):
        names = [x + (' ' + unit.group(1) if unit.group(1) else '') for x in sizes[:-1]] + [sizes[-1]]
        return [dict({'@type': 'Offer', 'name': n, 'price': pr, 'priceCurrency': 'KZT'}, **at) for n, pr in zip(names, prices)]
    return dict({'@type': 'AggregateOffer', 'lowPrice': min(prices), 'highPrice': max(prices), 'offerCount': len(prices),
                 'priceCurrency': 'KZT'}, **at)


def hours_spec(hours):
    if hours == '24/7':
        opens, closes = '00:00', '23:59'
    else:
        m = re.fullmatch(r'ежедневно (\d\d:\d\d)\s*[–-]\s*(\d\d:\d\d)', hours or '')
        if not m:
            sys.exit('seo_jsonld: не понимаю часы точки %r — допишите разбор, не угадывайте' % hours)
        opens, closes = m.groups()
    return {'@type': 'OpeningHoursSpecification', 'dayOfWeek': DAYS, 'opens': opens, 'closes': closes}


def branch_name(b):
    """«01 · ЖК Вавилон» → «Del Cappuccino · ЖК Вавилон»; точка с названием «Del Cappuccino» — по адресу"""
    rest = re.sub(r'^\d+\s*·\s*', '', b['n'])
    return 'Del Cappuccino · ' + (b['addr'] if rest == 'Del Cappuccino' else rest)


def instagram(html):
    return sorted(set(re.findall(r'href="(https://(?:www\.)?instagram\.com/[^"?#]+)"', html)))


def graph(html):
    org = {'@type': 'Organization', '@id': SITE + '#org', 'name': 'Del Cappuccino', 'url': SITE,
           'logo': SITE + 'assets/icon-192.png', 'sameAs': instagram(html),
           'potentialAction': {'@type': 'OrderAction', 'target': ORDER_URL}}
    nodes = [org]
    for b in branches(html):
        num = re.match(r'\d+', b['n']).group(0)
        togo = b['menu'] == 'togo'
        node = {'@type': 'Bakery' if togo else 'CafeOrCoffeeShop', '@id': SITE + '#branch-' + num, 'name': branch_name(b),
                'url': SITE, 'telephone': b['phone'],
                'address': {'@type': 'PostalAddress', 'streetAddress': b['addr'], 'addressLocality': 'Алматы',
                            'addressCountry': 'KZ'},
                'geo': {'@type': 'GeoCoordinates', 'latitude': b['geo'][0], 'longitude': b['geo'][1]},
                'openingHoursSpecification': hours_spec(b['hours']),
                'hasMenu': SITE + '#menu-togo' if togo else {'@id': SITE + '#menu'},
                'parentOrganization': {'@id': SITE + '#org'}}
        if re.match(r'https://2gis\.kz/[^/]+/firm/\d+$', b['route'] or ''):
            node['sameAs'] = [b['route']]
        nodes.append(node)
    nodes.append({'@type': 'Menu', '@id': SITE + '#menu', 'url': SITE + '#menu', 'name': 'Меню кофеен Del Cappuccino',
                  'inLanguage': 'ru',
                  'hasMenuSection': [{'@type': 'MenuSection', 'name': t,
                                      'hasMenuItem': [dict({'@type': 'MenuItem', 'name': n},
                                                           **({'offers': offers(p, vol, only)} if p else {}))
                                                      for n, p, vol, only in items]}
                                     for t, items in menu_sections(html)]})
    nodes.append({'@type': 'FAQPage', '@id': SITE + '#faq', 'inLanguage': 'ru',
                  'mainEntity': [{'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}}
                                 for q, a in faq(html)]})
    return {'@context': 'https://schema.org', '@graph': nodes}


def dumps(o):
    return json.dumps(o, ensure_ascii=False, separators=(',', ':'))


def render(data):
    """Компактный JSON, но строка на узел, раздел и позицию меню — чтобы смена цены была видна в diff одной строкой"""
    parts = []
    for node in data['@graph']:
        if node['@type'] != 'Menu':
            parts.append(dumps(node))
            continue
        head = dict(node)
        secs = head.pop('hasMenuSection')
        body = []
        for s in secs:
            sec = dict(s)
            items = sec.pop('hasMenuItem')
            body.append(dumps(sec)[:-1] + ',"hasMenuItem":[\n' + ',\n'.join(dumps(i) for i in items) + ']}')
        parts.append(dumps(head)[:-1] + ',"hasMenuSection":[\n' + ',\n'.join(body) + ']}')
    text = '{"@context":"https://schema.org","@graph":[\n' + ',\n'.join(parts) + '\n]}'
    assert json.loads(text) == data
    return text.replace('</', '<\\/')


def block(html):
    return MARK + '\n<script type="application/ld+json">\n' + render(graph(html)) + '\n</script>\n'


# ── /menyu: меню текстом ──

def fmt_p(p):
    """«1400/1500» → «1 400 / 1 500» (неразрывный пробел в тысячах, как fmtP на странице)"""
    return ' / '.join('{:,}'.format(int(x.strip())).replace(',', '\u00a0') for x in str(p).split('/'))


def menu_page(html):
    e = lambda s: H.escape(s, quote=False)
    ui, marks, bs = ui_ru(html), mark_names(html), branches(html)
    by_num = {re.match(r'\d+', b['n']).group(0): b for b in bs}
    fonts = '\n'.join(l.replace('url(assets/', 'url(/assets/') for l in re.findall(r"@font-face\{font-family:'Golos Text'[^\n]*", html))
    allergy = re.sub(r'\s*<br>\s*', ' ', ui['allergy']).rstrip('.') + '.'

    def items_html(items):
        rows = []
        for it in items:
            extra = ''.join(' <small>%s</small>' % e(x) for x in [it['vol']] if x)
            words = [marks[k] for k in it['m'] if k in marks]
            if words:
                extra += ' <i>· %s</i>' % e(', '.join(words))
            if it['only']:
                extra += ' <em>· %s %s</em>' % (e(ui['only'].lower()), e(', '.join(place(by_num[n]) for n in it['only'])))
            if it['note']:
                extra += ' <small>· %s</small>' % e(it['note'])
            price = ''
            if it['p']:
                price = '<b class="p">%s%s ₸</b>' % ('<s>%s</s> ' % fmt_p(it['old']) if it['old'] else '', fmt_p(it['p']))
            rows.append('<li><span class="n">%s%s</span>%s</li>' % (e(it['n']), extra, price))
        return '<ul>\n' + '\n'.join(rows) + '\n</ul>'

    def tab_html(mode, tab, arr):
        out = ['<h3 id="%s">%s</h3>' % (tab if mode == 'cafe' else 'togo-' + tab, e(ui['tab_' + tab]))]
        for s in sections(html, arr):
            head = e(s['t']) + (' <small>%s</small>' % e(s['badge']) if s['badge'] else '')
            out.append('<h4><span>%s</span>%s</h4>' % (head, '<b class="p">%s ₸</b>' % fmt_p(s['p']) if s['p'] else ''))
            if s['note']:
                out.append('<p class="note">%s</p>' % e(s['note']))
            out.append(items_html(s['items']))
        return '\n'.join(out)

    tabs = mode_tabs(html)
    cafes = [b for b in bs if b['menu'] != 'togo']
    togo = [b for b in bs if b['menu'] == 'togo']
    toc = ' · '.join('<a href="#%s">%s</a>' % (t, e(ui['tab_' + t])) for t, _ in tabs['cafe'])
    toc += ' · <a href="#togo">%s</a>' % e(ui['mode_togo'])
    body = [
        '<h2 id="cafe">Меню кофеен</h2>',
        '<p class="note">%s.</p>' % e(hours_text(bs)[0]),
        '<p class="note">%s %s</p>' % (e(ui['fee']), e(allergy)),
    ] + [tab_html('cafe', t, arr) for t, arr in tabs['cafe']] + [
        '<h2 id="togo">%s</h2>' % e(re.sub(r'^\d+\s*·\s*', '', togo[0]['n'])) if togo else '',
        ''.join('<p class="note">%s — %s</p>' % (e(b['addr']), e(b['hours'])) for b in togo),
        '<p class="note">%s</p>' % e(allergy),
    ] + [tab_html('togo', t, arr) for t, arr in tabs['togo']]
    insta = instagram(html)
    return '''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Меню и цены — Del Cappuccino, кофейни 24/7 в Алматы</title>
<meta name="description" content="Меню Del Cappuccino с ценами в тенге: кухня, бар, десерты, полуфабрикаты и bakery to go. Кофейни 24/7 в Алматы, завтраки весь день.">
<meta name="robots" content="index, follow">
<link rel="canonical" href="%(url)s">
<meta name="theme-color" content="#426349">
<link rel="icon" type="image/png" sizes="192x192" href="/assets/icon-192.png">
<meta property="og:type" content="website">
<meta property="og:url" content="%(url)s">
<meta property="og:title" content="Меню и цены — Del Cappuccino">
<meta property="og:description" content="Всё меню кофеен Del Cappuccino и bakery to go с ценами в тенге.">
<!-- Страница собрана tools/seo_jsonld.py из массивов меню главной — руками не править, правьте index.html и пересоберите -->
<style>
%(fonts)s
:root{--forest:#426349;--forest-dk:#31492F;--cream:#FEF1E7;--olive:#849E29;--ink:#241C15;--ink-2:#5C5245;--line:rgba(66,99,73,.18)}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--cream);color:var(--ink);font:15px/1.5 'Golos Text',-apple-system,sans-serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:860px;margin:0 auto;padding:0 16px}
header{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:14px 0;border-bottom:1px solid var(--line)}
a{color:var(--forest);font-weight:600}
header a{text-decoration:none}
h1{font-size:28px;line-height:1.15;color:var(--forest-dk);margin:22px 0 8px}
.lead{color:var(--ink-2)}
.toc{margin:12px 0 4px;font-size:14px;line-height:1.9}
h2{font-size:22px;color:var(--forest-dk);margin:30px 0 6px;padding-top:10px;border-top:2px solid var(--forest)}
h3{font-size:18px;color:var(--olive);margin:22px 0 2px}
h4{display:flex;justify-content:space-between;gap:12px;font-size:15px;margin:16px 0 2px}
.note{font-size:13px;color:var(--ink-2);margin:2px 0}
ul{list-style:none}
li{display:flex;justify-content:space-between;align-items:baseline;gap:12px;padding:7px 0;border-bottom:1px solid var(--line)}
small,li i,li em{font-size:12.5px;color:var(--ink-2);font-style:normal;font-weight:400}
.p{white-space:nowrap;font-weight:600;font-variant-numeric:tabular-nums}
.p s{font-weight:400;color:var(--ink-2);margin-right:2px}
footer{margin:34px 0 26px;padding-top:14px;border-top:1px solid var(--line);font-size:13px;color:var(--ink-2);line-height:1.9}
@media(min-width:700px){h1{font-size:34px}}
</style>
</head>
<body>
<header class="wrap"><a href="/">← Del Cappuccino</a><a href="/#menu">Меню с фото</a></header>
<main class="wrap">
<h1>Меню Del Cappuccino</h1>
<p class="lead">Цены в тенге (₸). Меню с фото и составом блюд — <a href="/#menu">на главной</a>, заказ онлайн — <a href="%(order)s">delcappuccino.kz</a>.</p>
<nav class="toc">%(toc)s</nav>
%(body)s
</main>
<footer class="wrap"><a href="/">Главная</a> · <a href="/#faq">Частые вопросы</a> · <a href="%(order)s">Заказать в приложении</a>%(insta)s · © 2026 Del Cappuccino</footer>
</body>
</html>
''' % {'url': MENU_URL, 'fonts': fonts, 'toc': toc, 'body': '\n'.join(x for x in body if x), 'order': ORDER_URL,
       'insta': ''.join(' · <a href="%s">Instagram</a>' % u for u in insta)}


# ── /llms.txt ──

def llms(html):
    bs, en, insta = branches(html), tr_en(html), instagram(html)
    short = lambda b: re.sub(r'^\d+\s*·\s*', '', b['n'])
    hours_en = lambda h: 'open 24/7' if h == '24/7' else h.replace('ежедневно', 'daily')
    cafes = [b for b in bs if b['hours'] == '24/7']
    rest = [b for b in bs if b['hours'] != '24/7']
    ru_points = '\n'.join('- %s — %s, Алматы — %s' % (short(b), b['addr'], hours_ru(b['hours'])) for b in bs)
    en_points = '\n'.join('- %s — %s, Almaty — %s' % (en.get(short(b), short(b)), en.get(b['addr'], b['addr']), hours_en(b['hours']))
                          for b in bs)
    links_ru = '\n'.join([
        '- [Сайт](%s): адреса точек, бронь столика в WhatsApp или по телефону, меню с фото и составом блюд' % SITE,
        '- [Меню и цены текстом](%s): кофейни и bakery to go, цены в тенге' % MENU_URL,
        '- [Частые вопросы](%s#faq)' % SITE,
        '- [Заказ онлайн и приложение](%s)' % ORDER_URL] + ['- [Instagram](%s)' % u for u in insta])
    links_en = '\n'.join([
        '- [Website](%s): locations, table booking via WhatsApp or phone, menu with photos (Kazakh, Russian, English)' % SITE,
        '- [Menu with prices, text](%s): cafés and bakery to go, prices in KZT (in Russian)' % MENU_URL,
        '- [Order online / app](%s)' % ORDER_URL] + ['- [Instagram](%s)' % u for u in insta])
    rest_ru = ''.join(', %s — %s' % (short(b).split(' · ')[0], b['hours']) for b in rest)
    rest_en = ''.join(', %s — %s' % (short(b).split(' · ')[0], hours_en(b['hours'])) for b in rest)
    return '''# Del Cappuccino

> Кофейни Del Cappuccino в Алматы: %(cafes)s круглосуточно (24/7)%(rest_ru)s. Завтраки весь день, продукция сертифицирована КМДБ Halal (halaldamu.kz).

Для семейных визитов есть детские комнаты, для спокойных встреч — VIP-залы, для молитвы — намазхана. Банкеты — для компании до 40 человек. Меню на сайте — на казахском, русском и английском.

## Точки

%(ru_points)s

## Ссылки

%(links_ru)s

## English

> Del Cappuccino cafés in Almaty: %(cafes_en)d open 24/7%(rest_en)s. Breakfast all day; products certified halal by KMDB (halaldamu.kz).

Kids' rooms for family visits, VIP rooms for quiet meetings, a prayer room (namazkhana). Banquets for groups of up to 40 guests. The menu on the website is available in Kazakh, Russian and English.

### Locations

%(en_points)s

### Links

%(links_en)s
''' % {'cafes': '%d %s' % (len(cafes), plural(len(cafes), 'кофейня', 'кофейни', 'кофеен')), 'rest_ru': rest_ru,
       'ru_points': ru_points, 'links_ru': links_ru, 'cafes_en': len(cafes), 'rest_en': rest_en,
       'en_points': en_points, 'links_en': links_en}


# ── запись ──

def with_faq(html):
    new = faq_block(faq(html))
    m = FAQ_RE.search(html)
    if m:
        return html[:m.start()] + new + html[m.end():]
    return html.replace(FAQ_BEFORE, new + '\n' + FAQ_BEFORE, 1)


def with_jsonld(html):
    new = block(html)
    m = BLOCK_RE.search(html)
    return html[:m.start()] + new + html[m.end():] if m else html.replace('</head>', new + '</head>', 1)


def outputs(html):
    """{путь: ожидаемый текст} — всё, что собирает генератор"""
    page = with_jsonld(with_faq(html))
    return {INDEX: page, MENU_PAGE: menu_page(page), LLMS: llms(page)}


def lastmod(path):
    """дата последнего коммита файла; есть незакоммиченные правки (или файл не в git) — сегодня"""
    try:
        dirty = subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--', path], cwd=ROOT,
                               capture_output=True).returncode != 0
        date = subprocess.run(['git', 'log', '-1', '--format=%cs', '--', path], cwd=ROOT,
                              capture_output=True, text=True).stdout.strip()
    except OSError:
        dirty, date = True, ''
    return datetime.date.today().isoformat() if dirty or not date else date


def update_sitemap():
    with open(SITEMAP, encoding='utf-8') as f:
        src = f.read()

    def one(m):
        url = m.group(0)
        loc = re.search(r'<loc>([^<]*)</loc>', url).group(1)
        if loc not in PAGES:
            return url
        tag = '<lastmod>%s</lastmod>' % lastmod(PAGES[loc])
        if '<lastmod>' in url:
            return re.sub(r'<lastmod>[^<]*</lastmod>', tag, url)
        return url.replace('</loc>', '</loc>\n    ' + tag, 1)
    new = re.sub(r'<url>.*?</url>', one, src, flags=re.S)
    if new != src:
        with open(SITEMAP, 'w', encoding='utf-8') as f:
            f.write(new)
        print('sitemap.xml: lastmod обновлён')


def read(path):
    try:
        with open(path, encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return None


def main():
    want = outputs(read(INDEX))
    stale = [os.path.relpath(p, ROOT) for p, text in want.items() if read(p) != text]
    if '--check' in sys.argv:
        print('seo_jsonld:', 'ok' if not stale else 'УСТАРЕЛО: %s — запустите python3 tools/seo_jsonld.py' % ', '.join(stale))
        sys.exit(1 if stale else 0)
    for p, text in want.items():
        if read(p) != text:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'w', encoding='utf-8') as f:
                f.write(text)
            print('%s: пересобран (%d байт)' % (os.path.relpath(p, ROOT), len(text.encode('utf-8'))))
    if not stale:
        print('всё уже актуально')
    update_sitemap()


if __name__ == '__main__':
    main()
