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
  кофейнях) — availableAtOrFrom на эти точки. sameAs точки — поле maps в BRANCHES (карточки фирмы в 2ГИС и Яндекс
  Картах, сверенные по адресу, часам и телефону); поисковые ссылки 2GIS (route, …/search/…) — не карточки, их не кладём.
  FAQPage — из tools/faq.json.
- Карточки точек на главной (#loc-grid): та же разметка, что раньше рисовал renderLocations, но в HTML — без JS их видят
  поисковики и ИИ; кнопки (звонок, маршрут, меню, WhatsApp) работают через onclick, перерисовки нет.
- «Частые вопросы» (#faq): <details> без JS, тот же текст, что в FAQPage. В ответах можно {часы}, {адреса}, {точек} —
  подставляются из BRANCHES, {детские} — из карточки «Детские комнаты» раздела «Формат», чтобы ответ не разошёлся
  с сайтом. Допустимый HTML в ответах: <a href>, <ul>, <li>.
- /menyu (menyu/index.html): всё меню текстом — кофейни (вкладки MENU_TABS) и Bakery to go (вкладки режима togo),
  разделы, объёмы, цены ₸, «только: …», старая цена зачёркнута. Путь не /menu/: там папка данных карточек menu/.
- /llms.txt: короткая справка для ИИ (ru + en) — точки, часы, ссылки; английские названия — из словаря MENU_TR.en.
- На /menyu — Google Analytics как на /ugolok (загрузка после load, ID — из <head> главной): видно переходы из ИИ.
Разбор не по шаблону (позиций меньше, чем {n:'…} в массиве; точка без адреса) — выход с ошибкой, а не тихий пропуск.
lastmod в sitemap.xml: дата последнего коммита страницы, а если в ней есть незакоммиченные правки — сегодня.
Только stdlib.
"""
import datetime, html as H, json, os, re, subprocess, sys
from urllib.parse import quote

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
I18N_JSON = os.path.join(ROOT, 'tools', 'pages_i18n.json')
KK_REVIEW = os.path.join(ROOT, 'menu', 'kk_review.md')
LANGS = ('ru', 'kk', 'en')
HOME = {'ru': SITE, 'kk': SITE + 'kk/', 'en': SITE + 'en/'}
MENU = {'ru': MENU_URL, 'kk': SITE + 'kk/menyu', 'en': SITE + 'en/menu'}
MENU_HASH = {'ru': '#menu', 'kk': '#menu-kk', 'en': '#menu-en'}      # глубокие ссылки: меню главной сразу на этом языке
LOCALE = {'ru': 'ru_RU', 'kk': 'kk_KZ', 'en': 'en_GB'}       # английский — британское написание (flavour, favourite)
HREF_MARK = '<!-- hreflang: версии главной на ru/kk/en — tools/seo_jsonld.py -->'
HREF_RE = re.compile(re.escape(HREF_MARK) + r'\n.*?<!-- /hreflang -->\n', re.S)
PAGES = {SITE: 'index.html', SITE + 'ugolok': 'ugolok/index.html', MENU_URL: 'menyu/index.html',
         HOME['kk']: 'kk/index.html', HOME['en']: 'en/index.html', MENU['kk']: 'kk/menyu/index.html', MENU['en']: 'en/menu/index.html'}


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
                    'menu': field(b, 'menu'), 'route': field(b, 'route'), 'note': field(b, 'note'), 'wa': field(b, 'wa'),
                    'maps': [u for u in (field(b, 'gis'), field(b, 'yandex')) if u],
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
    return ui_dict(html, 'ru')


def tr_en(html):
    return tr_dict(html, 'en')


def mode_tabs(html):
    """{'cafe': [(вкладка, массив)], 'togo': [...]} — как в MENU_TABS и MENU_MODES.togo"""
    cafe = re.search(r'const MENU_TABS = \{([^}]*)\}', html).group(1)
    togo = re.search(r'togo:\{tabs:\{([^}]*)\}', html).group(1)
    return {'cafe': re.findall(r'(\w+):(\w+)', cafe), 'togo': re.findall(r'(\w+):(\w+)', togo)}


def mark_names(html, c=None):
    """пометка → слово из легенды: new → «новинка» / «жаңа» / «new item» (MK + LEGEND, переводы — MENU_TR)"""
    mk = dict(re.findall(r"(\w+):'<[^>]*>([^<]*)</[^>]*>'", obj_block(html, 'const MK = {', '};')))
    entries = re.findall(r"'(\S+ — [^']*)'", obj_block(html, 'const LEGEND = {', '};'))
    legend = dict(T(c, x).split(' — ', 1) if c else x.split(' — ', 1) for x in entries)
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


def kids_places(html):
    """где детские комнаты — из карточки «Детские комнаты» раздела «Формат»: «Игровые пространства в ЖК Вавилон и …»"""
    m = re.search(r'<h3>Детские комнаты</h3><p>Игровые пространства в ([^<]+?)\.</p>', html)
    if not m:
        sys.exit('seo_jsonld: не нашёл на главной «Детские комнаты … Игровые пространства в …» — допишите разбор')
    return re.split(r',\s*|\s+и\s+', m.group(1))


def and_join(xs, conj='и'):
    return xs[0] if len(xs) == 1 else '%s %s %s' % (', '.join(xs[:-1]), conj, xs[-1])


def faq_vars(html, lang='ru'):
    """подстановки в тексты: {часы} {адреса} {точек} {детские} {кофеен} {точек_n} {часы_togo} — из BRANCHES и главной"""
    e = lambda s: H.escape(s, quote=False)
    bs = branches(html)
    cafes, rest = [b for b in bs if b['hours'] == '24/7'], [b for b in bs if b['hours'] != '24/7']
    togo_h = [m.group(0) for m in (re.search(r'\d\d:\d\d\s*[–-]\s*\d\d:\d\d', b['hours']) for b in rest) if m]
    v = {'кофеен': str(len(cafes)), 'точек_n': str(len(bs)), 'часы_togo': togo_h[0] if togo_h else ''}
    if lang == 'ru':
        first, rest_t = hours_text(bs)
        v.update({'часы': ' '.join(e(x) + '.' for x in [first] + rest_t),
                  'детские': e(and_join(kids_places(html))),
                  'адреса': '<ul>' + ''.join('<li>%s — %s</li>' % (e(place(b)), e(hours_ru(b['hours']))) for b in bs) + '</ul>',
                  'точек': '%d %s' % (len(bs), plural(len(bs), 'точка', 'точки', 'точек'))})
        return v
    c = lang_ctx(html, lang)
    ph, kids = c['d']['phrases'], kids_places(html)
    need(c, kids)
    v.update({'часы': e(ph['cafes'].format(n=len(cafes), list=', '.join(place_l(c, b) for b in cafes)))
                      + ''.join(' %s.' % e('%s — %s' % (place_l(c, b), hours_l(c, b['hours']))) for b in rest),
              'детские': e(and_join([T(c, k) for k in kids], ph['and'])),
              'адреса': '<ul>' + ''.join('<li>%s — %s</li>' % (e(place_l(c, b)), e(hours_l(c, b['hours']))) for b in bs) + '</ul>',
              'точек': e(ph['points'].format(n=len(bs)))})
    return v


def faq(html, lang='ru'):
    """[(вопрос, ответ-HTML)] — русские из tools/faq.json, казахские и английские из tools/pages_i18n.json (те же вопросы)"""
    with open(FAQ_JSON, encoding='utf-8') as f:
        data = json.load(f)
    if lang != 'ru':
        ru_n, data = len(data), i18n()[lang]['faq']
        if len(data) != ru_n:
            sys.exit('seo_jsonld: в pages_i18n.json %s.faq %d вопросов, а в tools/faq.json %d — переведите те же вопросы' % (lang, len(data), ru_n))
    v = faq_vars(html, lang)
    out = []
    for e in data:
        a = fill(e['a'], v, 'FAQ %s: %s' % (lang, e['q']))
        bad = re.sub(r'</?(a|ul|li)\b[^>]*>', '', a)
        if '<' in bad:
            sys.exit('seo_jsonld: в ответе FAQ «%s» недопустимый тег (можно <a href>, <ul>, <li>)' % e['q'])
        out.append((e['q'], a))
    return out


def faq_block(items, head=None):
    """раздел «Частые вопросы»; head — (метка, заголовок, строка со ссылкой на меню) для /kk/ и /en/"""
    tag, h2, p = head or ('вопросы и ответы', 'Частые <span>вопросы</span>.',
                          'Всё меню с ценами текстом — <a href="/menyu">на отдельной странице</a>.')
    rows = '\n'.join('      <details><summary>%s</summary><div class="faq-a">%s</div></details>' % (H.escape(q, quote=False), a)
                     for q, a in items)
    return (('' if head else FAQ_MARK + '\n') + '<section class="faq" id="faq">\n  <div class="shell">\n    <div class="faq-head">\n'
            '      <div><p class="tag">%s</p><h2>%s</h2></div>\n      <p>%s</p>\n    </div>\n' % (tag, h2, p) +
            '    <div class="faq-list">\n' + rows + '\n    </div>\n  </div>\n</section>\n' + ('' if head else '<!-- /faq -->\n'))


def ui_dict(html, lang):
    """MENU_UI[lang]: подписи вкладок, сервисный сбор, аллергия, «Только:»"""
    i = html.index('  %s:{to_togo' % lang)
    ends = [j for j in (html.find(x, i + 1) for x in ('\n  ru:{', '\n  kk:{', '\n  en:{', '\n};')) if j > 0]
    return {k: unq(v) for k, v in re.findall(r"(\w+):'((?:[^'\\]|\\.)*)'", html[i:min(ends)])}


def tr_dict(html, lang):
    """MENU_TR[lang]: русская строка → перевод (названия, адреса, разделы, позиции, легенда)"""
    return {unq(a): unq(b) for a, b in re.findall(r"'((?:[^'\\]|\\.)*)':'((?:[^'\\]|\\.)*)'",
                                                   obj_block(html, '\n %s:{' % lang, '\n },'))}


def i18n():
    with open(I18N_JSON, encoding='utf-8') as f:
        return json.load(f)


def lang_ctx(html, lang):
    """всё, что нужно странице на языке lang: тексты из pages_i18n.json, словари MENU_TR и MENU_UI"""
    return {'lang': lang, 'd': i18n()[lang], 'tr': {} if lang == 'ru' else tr_dict(html, lang), 'ui': ui_dict(html, lang)}


def tr_units(s, lang):
    """как trUnits на странице: единицы в объёмах, которых нет в словаре"""
    if lang == 'en':
        s = re.sub(r'(\d) шт', r'\1 pcs', re.sub(r'\b1 шт', '1 pc', re.sub(r'(\d) л(?![а-яё])', r'\1 L',
                   re.sub(r'(\d) гр', r'\1 g', s.replace('мл', 'ml')))))
    elif lang == 'kk':
        s = re.sub(r'(\d) шт', r'\1 дана', re.sub(r'(\d) гр', r'\1 г', s))
    return s


def T(c, s):
    """как T() на странице: перевод из MENU_TR, иначе — единицы; по-русски — как есть"""
    if c['lang'] == 'ru' or not s:
        return s
    return c['tr'][s] if s in c['tr'] else tr_units(str(s), c['lang'])


def need(c, words):
    """факты (точки, адреса) без перевода не выводим по-русски молча — пусть допишут словарь"""
    missing = [w for w in words if c['lang'] != 'ru' and w not in c['tr']]
    if missing:
        sys.exit('seo_jsonld: нет перевода в MENU_TR.%s для %s — допишите словарь' % (c['lang'], ', '.join(missing)))


def short(b):
    return re.sub(r'^\d+\s*·\s*', '', b['n'])


def place_l(c, b):
    need(c, [short(b), b['addr']])
    return '%s (%s)' % (T(c, short(b)), T(c, b['addr']))


def hours_l(c, h):
    """часы в тексте: «круглосуточно (24/7)» / «тәулік бойы (24/7)» / «open 24/7»; «ежедневно» → «күн сайын» / «daily»"""
    ph = c['d']['phrases']
    return ph['hours_24'] if h == '24/7' else h.replace('ежедневно', ph['daily'])


def hours_card(c, h):
    """часы на карточке точки — как на русской: «24/7», «ежедневно 07:00–22:00» → «daily 07:00–22:00»"""
    return h if h == '24/7' else h.replace('ежедневно', c['d']['phrases']['daily'])


def fill(text, v, where):
    """{подстановка} → значение; неизвестная — выход с ошибкой, а не текст с фигурными скобками на сайте"""
    unknown = set(re.findall(r'\{(\w+)\}', text)) - set(v)
    if unknown:
        sys.exit('seo_jsonld: в «%s» неизвестная подстановка {%s} — есть: %s' % (where, ', '.join(sorted(unknown)), ', '.join(sorted(v))))
    return re.sub(r'\{(\w+)\}', lambda m: v[m.group(1)], text)


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
        if b['maps']:
            node['sameAs'] = b['maps']
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


def menu_page(html, lang='ru'):
    """/menyu, /kk/menyu, /en/menu — всё меню текстом: кофейни (вкладки MENU_TABS) и Bakery to go (вкладки togo)"""
    e = lambda s: H.escape(s, quote=False)
    c = lang_ctx(html, lang)
    ui, ui0, marks, bs, mp = c['ui'], ui_ru(html), mark_names(html, c if lang != 'ru' else None), branches(html), c['d']['menu_page']
    by_num = {re.match(r'\d+', b['n']).group(0): b for b in bs}
    fonts = '\n'.join(l.replace('url(assets/', 'url(/assets/') for l in re.findall(r"@font-face\{font-family:'Golos Text'[^\n]*", html))
    allergy = re.sub(r'\s*<br>\s*', ' ', ui['allergy']).rstrip('.') + '.'
    tt = lambda s: T(c, s)
    home = '/' if lang == 'ru' else '/%s/' % lang
    menu_link = '/' + MENU_HASH[lang]

    def items_html(items):
        rows = []
        for it in items:
            extra = ''.join(' <small>%s</small>' % e(tt(x)) for x in [it['vol']] if x)
            words = [marks[k] for k in it['m'] if k in marks]
            if words:
                extra += ' <i>· %s</i>' % e(', '.join(words))
            if it['only']:
                extra += ' <em>· %s %s</em>' % (e(ui['only'].lower()), e(', '.join(place_l(c, by_num[n]) for n in it['only'])))
            if it['note']:
                extra += ' <small>· %s</small>' % e(tt(it['note']))
            price = ''
            if it['p']:
                # старая цена словами («вместо»), а не только <s>: бот, вырезающий теги, иначе прочтёт «6 000 3 990 ₸»
                price = '<b class="p">%s ₸%s</b>' % (fmt_p(it['p']), ' <small>%s</small>' % mp['instead'].format(old='<s>%s</s>' % fmt_p(it['old'])) if it['old'] else '')
            rows.append('<li><span class="n">%s%s</span>%s</li>' % (e(tt(it['n'])), extra, price))
        return '<ul>\n' + '\n'.join(rows) + '\n</ul>'

    def tab_html(mode, tab, arr):
        out = ['<h3 id="%s">%s</h3>' % (tab if mode == 'cafe' else 'togo-' + tab, e(ui['tab_' + tab]))]
        for s in sections(html, arr):
            head = e(tt(s['t'])) + (' <small>%s</small>' % e(tt(s['badge'])) if s['badge'] else '')
            # раздел с тем же названием, что вкладка («Десерты» → «Десерты»), без своего заголовка — как dupT на главной
            if not (s['t'] == ui0['tab_' + tab] and not s['badge'] and not s['p']):
                out.append('<h4><span>%s</span>%s</h4>' % (head, '<b class="p">%s ₸</b>' % fmt_p(s['p']) if s['p'] else ''))
            if s['note']:
                out.append('<p class="note">%s</p>' % e(tt(s['note'])))
            out.append(items_html(s['items']))
        return '\n'.join(out)

    tabs = mode_tabs(html)
    togo = [b for b in bs if b['menu'] == 'togo']
    toc = ' · '.join('<a href="#%s">%s</a>' % (t, e(ui['tab_' + t])) for t, _ in tabs['cafe'])
    toc += ' · <a href="#togo">%s</a>' % e(ui['mode_togo'])
    cafes_note = (e(hours_text(bs)[0]) + '.' if lang == 'ru' else
                  e(c['d']['phrases']['cafes'].format(n=len([b for b in bs if b['hours'] == '24/7']),
                                                     list=', '.join(place_l(c, b) for b in bs if b['hours'] == '24/7'))))
    body = [
        '<h2 id="cafe">%s</h2>' % e(mp['cafe_h2']),
        '<p class="note">%s</p>' % cafes_note,
        '<p class="note">%s %s</p>' % (e(ui['fee']), e(allergy)),
    ] + [tab_html('cafe', t, arr) for t, arr in tabs['cafe']] + [
        '<h2 id="togo">%s</h2>' % e(tt(short(togo[0]))) if togo else '',
        ''.join('<p class="note">%s — %s</p>' % (e(tt(b['addr'])), e(hours_card(c, b['hours']) if lang != 'ru' else b['hours'])) for b in togo),
        '<p class="note">%s</p>' % e(allergy),
    ] + [tab_html('togo', t, arr) for t, arr in tabs['togo']]
    insta = instagram(html)
    return '''<!DOCTYPE html>
<html lang="%(lang)s">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<meta name="description" content="%(description)s">
<meta name="robots" content="index, follow">
<link rel="canonical" href="%(url)s">
%(hreflang)s
<meta name="theme-color" content="#426349">
<link rel="icon" type="image/png" sizes="192x192" href="/assets/icon-192.png">
<meta property="og:type" content="website">
<meta property="og:url" content="%(url)s">
<meta property="og:title" content="%(og_title)s">
<meta property="og:description" content="%(og_description)s">
<meta property="og:locale" content="%(locale)s">
<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}gtag('js',new Date());gtag('config','%(ga)s');</script>
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
<header class="wrap"><a href="%(home)s">%(back)s</a><a href="%(menu_link)s">%(photo_menu)s</a></header>
<main class="wrap">
<h1>%(h1)s</h1>
<p class="lead">%(lead)s</p>
<nav class="toc">%(toc)s</nav>
%(body)s
</main>
<footer class="wrap"><a href="%(home)s">%(f_home)s</a> · <a href="%(home)s#faq">%(f_faq)s</a> · <a href="%(order)s">%(f_order)s</a>%(insta)s · © 2026 Del Cappuccino</footer>
%(ga_loader)s
</body>
</html>
''' % {'lang': lang, 'url': MENU[lang], 'hreflang': hreflang(MENU), 'locale': LOCALE[lang], 'fonts': fonts, 'toc': toc,
       'body': '\n'.join(x for x in body if x), 'order': ORDER_URL, 'home': home, 'menu_link': menu_link,
       'title': e(mp['title']), 'description': H.escape(mp['description']), 'og_title': H.escape(mp['og_title']),
       'og_description': H.escape(mp['og_description']), 'back': e(mp['back']), 'photo_menu': e(mp['photo_menu']),
       'h1': e(mp['h1']), 'lead': mp['lead'].replace('{menu_link}', menu_link),
       'f_home': e(mp['home']), 'f_faq': e(mp['faq']), 'f_order': e(mp['order']),
       'insta': ''.join(' · <a href="%s">Instagram</a>' % u for u in insta), 'ga': ga_id(html), 'ga_loader': GA_LOADER % ga_id(html)}


# селекторы главной, которые нужны облегчённым /kk/ и /en/: шапка, hero, «О нас», «Формат», точки, вопросы, контакты, подвал
CSS_KEEP = re.compile(r'^(?::root|\*|html|body|a|h1|header|nav|footer|\.(?:shell|hbar|hbar-m|logo-d|logo-m|btn|tag|lead|actions|'
                      r'halal-badge|hero|hero-photo|hero-badge|story|story-grid|story-photo|stats|mini-stats|features|f-head|f-grid|'
                      r'locations|loc-head|loc-grid|loc-card|loc-meta|loc-links|faq|faq-head|faq-list|faq-a|contact|contact-actions|'
                      r'f-row|lang-sw|hide-mobile))(?![\w-])')


def hreflang(urls):
    """<link rel=alternate hreflang> на все версии + x-default (русская)"""
    return '\n'.join(['<link rel="alternate" hreflang="%s" href="%s">' % (l, urls[l]) for l in LANGS] +
                     ['<link rel="alternate" hreflang="x-default" href="%s">' % urls['ru']])


def ga_id(html):
    return re.search(r"gtag\('config','(G-[A-Z0-9]+)'\)", html.split('</head>')[0]).group(1)


GA_LOADER = '''<script>
/* Аналитика — после load, в простое, как на /ugolok: видно переходы на меню из поиска и ИИ-ассистентов */
(function(){
  function loadGtag(){var s=document.createElement('script');s.src='https://www.googletagmanager.com/gtag/js?id=%s';s.async=true;document.head.appendChild(s)}
  function idle(){('requestIdleCallback'in window)?requestIdleCallback(loadGtag,{timeout:4000}):setTimeout(loadGtag,1500)}
  if(document.readyState==='complete')idle();else addEventListener('load',idle);
})();
</script>'''


def css_rules(css):
    out, depth, start = [], 0, 0
    for i, ch in enumerate(css):
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if not depth:
                out.append(css[start:i + 1].strip())
                start = i + 1
    return out


def keep_rule(rule):
    pre, body = rule.split('{', 1)
    pre = pre.strip()
    if pre.startswith('@media'):
        inner = [r for r in (keep_rule(x) for x in css_rules(body[:-1])) if r]
        return pre + '{\n' + '\n'.join(inner) + '\n}' if inner else None
    if pre.startswith('@'):
        return None
    return rule if any(CSS_KEEP.match(s.strip()) for s in pre.split(',')) else None


def css_subset(html):
    """стили облегчённых страниц — правила из <style> главной (один источник вида), без меню, модалок и акций"""
    css = re.sub(r'/\*.*?\*/', '', html[html.index('<style>') + 7:html.index('</style>')], flags=re.S)
    return '\n'.join(r for r in (keep_rule(x) for x in css_rules(css)) if r)


def img_tag(html, pattern, alt, extra=''):
    """<img> с главной (srcset, размеры) с путями от корня и подписью на языке страницы"""
    m = re.search(pattern, html)
    if not m:
        sys.exit('seo_jsonld: на главной не нашёл картинку по шаблону %s — поправьте img_tag' % pattern)
    tag = m.group(0)
    tag = re.sub(r'(?<=["\s,])assets/', '/assets/', tag)
    tag = re.sub(r'alt="[^"]*"', 'alt="%s"' % H.escape(alt), tag)
    return tag.replace('<img ', '<img %s' % extra, 1) if extra else tag


def lang_jsonld(html, lang, P, items):
    data = {'@context': 'https://schema.org', '@graph': [
        {'@type': 'WebPage', '@id': HOME[lang] + '#webpage', 'url': HOME[lang], 'name': P['title'], 'description': P['description'],
         'inLanguage': lang, 'about': {'@id': SITE + '#org'},
         'isPartOf': {'@type': 'WebSite', '@id': SITE + '#website', 'url': SITE, 'name': 'Del Cappuccino'}},
        {'@type': 'Organization', '@id': SITE + '#org', 'name': 'Del Cappuccino', 'url': SITE, 'sameAs': instagram(html)},
        {'@type': 'FAQPage', '@id': HOME[lang] + '#faq', 'inLanguage': lang,
         'mainEntity': [{'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}} for q, a in items]}]}
    return dumps(data).replace('</', '<\\/')


def lang_page(html, lang):
    """/kk/ и /en/ — облегчённая главная на своём языке: текст в HTML без JS, вид — стили главной; меню — ссылкой на главную"""
    c = lang_ctx(html, lang)
    v = faq_vars(html, lang)
    P = {k: (fill(x, v, '%s.page.%s' % (lang, k)) if isinstance(x, str) else x) for k, x in c['d']['page'].items()}
    feats = [(fill(h, v, '%s.features' % lang), fill(p, v, '%s.features' % lang)) for h, p in P['features']]
    items = faq(html, lang)
    e = lambda s: H.escape(s, quote=False)
    bs = branches(html)
    home, menu_link = '/%s/' % lang, '/' + MENU_HASH[lang]
    fonts = '\n'.join(l.replace('url(assets/', 'url(/assets/') for l in re.findall(r"@font-face\{font-family:'(?:Golos Text|Comfortaa)'[^\n]*", html))
    kk_fix = ('\n/* казахские буквы (ә, ғ, қ, ң, ө, ү, һ) есть в Golos (cyrillic-ext), в Comfortaa — нет: заголовки на Golos */\n'
              "html[lang=kk] :is(h1,h2,.stats b,.mini-stats b,.hero-badge b,.loc-card small,.loc-card h3,.f-grid b)"
              "{font-family:'Golos Text',sans-serif;letter-spacing:-.01em}") if lang == 'kk' else ''
    sw = '\n'.join('      <a href="%s" lang="%s"%s>%s</a>' % ('/' if l == 'ru' else '/%s/' % l, l,
                                                            ' aria-current="page"' if l == lang else ' hreflang="%s"' % l,
                                                            {'ru': 'РУС', 'kk': 'ҚАЗ', 'en': 'ENG'}[l]) for l in LANGS)
    logo_d = img_tag(html, r'<img class="logo-d"[^>]*>', 'Del Cappuccino')
    logo_m = img_tag(html, r'<img class="logo-m"[^>]*>', 'Del Cappuccino')
    hero_img = img_tag(html, r'(?<=<div class="hero-photo">\n      )<img[^>]*>', P['hero_alt'])
    story_img = img_tag(html, r'(?<=<div class="story-photo">)<img[^>]*>', P['story_alt'])
    halal_img = img_tag(html, r'<img src="assets/halal-104\.webp"[^>]*>', P['halal_alt'])
    mono = '<img src="/assets/logo-mono-192.webp" width="192" height="192" loading="lazy" decoding="async" alt="dC">'

    def card(b):
        num = re.match(r'\d+', b['n']).group(0)
        need(c, [short(b), b['addr']] + ([b['note']] if b['note'] and b['note'] not in c['d']['branch_note'] else []))
        note = c['d']['branch_note'].get(b['note'], T(c, b['note'])) if b['note'] else ''
        wa = 'https://wa.me/%s?text=%s' % (re.sub(r'\D', '', b['phone']),
                                           quote((c['d']['wa_togo'] if b['wa'] else c['d']['wa_book']) + T(c, b['addr']), safe="-_.!~*'()"))
        links = ['<a href="tel:%s">%s</a>' % (b['phone'], e(P['call'])),
                 '<a href="%s" target="_blank" rel="noopener">%s</a>' % (H.escape(b['route']), e(P['route']))]
        if b['menu']:
            links.append('<a href="/%s-%s">%s</a>' % ('#menu-togo' if b['menu'] == 'togo' else '#menu', lang, e(P['card_menu'])))
        links.append('<a class="wa" href="%s" target="_blank" rel="noopener">WhatsApp</a>' % H.escape(wa, quote=False).replace('"', '&quot;'))
        return ('    <div class="loc-card">\n      <small>%s · %s</small>\n      <h3>%s</h3>\n      <p class="loc-meta"><b>%s</b>%s</p>\n'
                '      <div class="loc-links">\n        %s\n      </div>\n    </div>'
                % (num, e(T(c, short(b))), e(T(c, b['addr'])), e(hours_card(c, b['hours'])), ' · ' + e(note) if note else '',
                   '\n        '.join(links)))

    stats = ('<div><b>24/7</b><span>%s</span></div>\n  <div><b>%d</b><span>%s</span></div>\n  <div><b>all day</b><span>%s</span></div>'
             % (P['stat_cafes'], len(bs), P['stat_points'], P['stat_breakfast']))
    faq_html = faq_block(items, (P['faq_tag'], P['faq_h2'], P['faq_p']))
    insta = instagram(html)
    return '''<!DOCTYPE html>
<html lang="%(lang)s">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<meta name="description" content="%(description)s">
<meta name="robots" content="index, follow">
<link rel="canonical" href="%(url)s">
%(hreflang)s
<meta name="theme-color" content="#426349">
<link rel="icon" type="image/png" sizes="192x192" href="/assets/icon-192.png">
<link rel="apple-touch-icon" sizes="180x180" href="/assets/apple-touch-icon.png">
<meta property="og:type" content="website">
<meta property="og:url" content="%(url)s">
<meta property="og:title" content="%(title)s">
<meta property="og:description" content="%(description)s">
<meta property="og:locale" content="%(locale)s">
<meta property="og:image" content="%(site)sassets/photo_01.jpg">
<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}gtag('js',new Date());gtag('config','%(ga)s');</script>
<!-- Страница собрана tools/seo_jsonld.py: тексты — tools/pages_i18n.json, факты — BRANCHES и главная, стили — из <style> главной. Руками не править -->
<style>
%(fonts)s
%(css)s%(kk_fix)s
</style>
<script type="application/ld+json">
%(jsonld)s
</script>
</head>
<body>
<header>
  <div class="hbar">
    <a href="%(home)s" aria-label="%(home_label)s" style="display:inline-flex;align-items:center">
      %(logo_d)s
      %(logo_m)s
    </a>
    <nav>
      <a href="%(menu_link)s">%(nav_menu)s</a>
      <a href="#about">%(nav_about)s</a>
      <a href="#features">%(nav_features)s</a>
      <a href="#locations">%(nav_locations)s</a>
      <a href="#faq">%(nav_faq)s</a>
    </nav>
    <div class="hbar-m">
      <a href="%(menu_link)s">%(nav_menu)s</a>
    </div>
    <nav class="lang-sw" aria-label="%(lang_label)s">
%(sw)s
    </nav>
  </div>
</header>

<main>
  <section class="hero shell">
    <div>
      <p class="tag">%(hero_tag)s</p>
      <h1>%(hero_h1)s</h1>
      <p class="lead">%(hero_lead)s</p>
      <div class="actions">
        <a class="btn olive" href="#locations">%(book)s</a>
        <a class="btn ghost" href="%(menu_link)s">%(menu)s</a>
        <a class="btn" href="%(order_url)s" target="_blank" rel="noopener">%(order)s</a>
      </div>
      <div class="halal-badge">
        %(halal_img)s
        <span>%(halal)s</span>
      </div>
    </div>
    <div class="hero-photo">
      %(hero_img)s
      <div class="hero-badge">
        <b>24/7</b>
        <div><span>%(badge_cafes)s</span><span>%(badge_days)s</span></div>
      </div>
    </div>
  </section>

  <section class="story shell" id="about">
    <div class="story-grid">
      <div class="story-photo">%(story_img)s</div>
      <div>
        <h2>%(about_h2)s</h2>
        <p>%(about_p)s</p>
        <div class="stats">
  %(stats)s
        </div>
      </div>
    </div>
  </section>

  <section class="features" id="features">
    <div class="shell">
      <div class="f-head">
        <p class="tag">%(features_tag)s</p>
        <h2>%(features_h2)s</h2>
      </div>
      <div class="f-grid">
%(features)s
      </div>
    </div>
  </section>
</main>

<div class="mini-stats shell">
  %(stats)s
</div>

<section class="locations" id="locations">
  <div class="shell">
    <div class="loc-head">
      <div><p class="tag">%(loc_tag)s</p><h2>%(loc_h2)s</h2></div>
      <p>%(loc_p)s</p>
    </div>
    <div class="loc-grid">
%(cards)s
    </div>
  </div>
</section>

%(faq)s
<section class="contact shell" id="contacts">
  <a href="%(home)s" aria-label="%(home_label)s">%(mono)s</a>
  <h2>%(contact_h2)s</h2>
  <div class="contact-actions">
    <a class="btn olive" href="#locations">WhatsApp</a>
%(insta_btn)s
  </div>
</section>

<footer class="shell">
  <div class="f-row">
    <a href="%(home)s" aria-label="%(home_label)s">%(mono)s</a>
    <span>%(footer_tag)s</span>
    <a href="%(menu_page)s">%(footer_menu)s</a>
    <a class="f-ugolok" href="/ugolok/">%(footer_ugolok)s</a>
    <span>© 2026 Del Cappuccino</span>
  </div>
</footer>
%(ga_loader)s
</body>
</html>
''' % dict({k: P[k] for k in ('hero_tag', 'hero_h1', 'hero_lead', 'book', 'menu', 'order', 'halal', 'badge_cafes', 'badge_days',
                               'about_h2', 'about_p', 'features_tag', 'features_h2', 'loc_tag', 'loc_h2', 'loc_p', 'contact_h2',
                               'footer_tag', 'footer_menu', 'footer_ugolok', 'nav_menu', 'nav_about', 'nav_features',
                               'nav_locations', 'nav_faq')},
           lang=lang, title=H.escape(P['title']), description=H.escape(P['description']), url=HOME[lang], hreflang=hreflang(HOME),
           locale=LOCALE[lang], site=SITE, ga=ga_id(html), ga_loader=GA_LOADER % ga_id(html), fonts=fonts, css=css_subset(html),
           kk_fix=kk_fix, jsonld=lang_jsonld(html, lang, P, items), home=home, home_label=H.escape(P['home_label']),
           lang_label=H.escape(P['lang_label']), logo_d=logo_d, logo_m=logo_m, menu_link=menu_link, sw=sw,
           order_url=ORDER_URL, halal_img=halal_img, hero_img=hero_img, story_img=story_img, stats=stats,
           features='\n'.join('        <article><b>%02d</b><h3>%s</h3><p>%s</p></article>' % (i + 1, h, p) for i, (h, p) in enumerate(feats)),
           cards='\n'.join(card(b) for b in bs), faq=faq_html, mono=mono, menu_page='/' + MENU[lang][len(SITE):],
           insta_btn='\n'.join('    <a class="btn ghost" href="%s" target="_blank" rel="noopener">@%s</a>' % (u, u.rstrip('/').rsplit('/', 1)[1]) for u in insta))


def kk_review(html):
    """menu/kk_review.md — все казахские строки из pages_i18n.json со своим местом на сайте, для вычитки носителем"""
    where = {'phrases': 'подстановки в тексты (часы, точки, «и»)', 'branch_note': 'карточка точки 05 на /kk/',
             'wa_book': 'текст сообщения WhatsApp из карточек кофеен /kk/', 'wa_togo': 'текст сообщения WhatsApp из карточки bakery to go /kk/',
             'page': 'страница /kk/', 'faq': 'частые вопросы на /kk/ (и FAQPage в разметке)', 'menu_page': 'текстовое меню /kk/menyu',
             }
    rows = []

    def walk(x, path):
        if isinstance(x, dict):
            for k, y in x.items():
                walk(y, path + [k])
        elif isinstance(x, list):
            for i, y in enumerate(x):
                walk(y, path + [str(i + 1)])
        else:
            rows.append('| `%s` | %s | %s |' % ('.'.join(path), where.get(path[0], path[0]), str(x).replace('|', '\\|')))
    walk(i18n()['kk'], [])
    return ('# Казахские строки на вычитку носителем\n\n'
            'Собрано `tools/seo_jsonld.py` из `tools/pages_i18n.json` (раздел `kk`). Правки вносить туда и пересобрать:\n'
            '`python3 tools/seo_jsonld.py && python3 tools/sw_version.py`.\n\n'
            '- `{…}` — подстановки из данных сайта, их не переводить: `{часы}` — часы точек, `{адреса}` — список адресов,\n'
            '  `{точек}` / `{точек_n}` — число точек, `{кофеен}` — число кофеен 24/7, `{часы_togo}` — часы bakery to go,\n'
            '  `{детские}` — где детские комнаты, `{n}` / `{list}` / `{old}` — число, список, старая цена.\n'
            '- `<br>`, `<span>`, `<a href>` — разметка, её оставить.\n'
            '- Названия блюд, разделов меню и адреса точек берутся из прежнего словаря меню (`MENU_TR.kk` в `index.html`), '
            'в этот список не входят.\n\n'
            '| Ключ | Где на сайте | Текст |\n|---|---|---|\n' + '\n'.join(rows) + '\n')


def with_hreflang(html):
    new = HREF_MARK + '\n' + hreflang(HOME) + '\n<!-- /hreflang -->\n'
    m = HREF_RE.search(html)
    if m:
        return html[:m.start()] + new + html[m.end():]
    anchor = '<link rel="canonical" href="%s">\n' % SITE
    if anchor not in html:
        sys.exit('seo_jsonld: нет <link rel="canonical"> главной — некуда поставить hreflang')
    return html.replace(anchor, anchor + new, 1)


# ── /llms.txt ──

def llms(html):
    bs, en, insta = branches(html), tr_en(html), instagram(html)
    short = lambda b: re.sub(r'^\d+\s*·\s*', '', b['n'])
    hours_en = lambda h: 'open 24/7' if h == '24/7' else h.replace('ежедневно', 'daily')
    cafes = [b for b in bs if b['hours'] == '24/7']
    rest = [b for b in bs if b['hours'] != '24/7']
    ru_points = '\n'.join('- %s — %s, Алматы — %s' % (short(b), b['addr'], hours_ru(b['hours'])) for b in bs)
    kids = kids_places(html)
    missing = [x for x in [y for b in bs for y in (short(b), b['addr'])] + kids if x not in en]
    if missing:
        sys.exit('seo_jsonld: нет английского перевода в MENU_TR.en для %s — допишите словарь' % ', '.join(missing))
    en_points = '\n'.join('- %s — %s, Almaty — %s' % (en[short(b)], en[b['addr']], hours_en(b['hours']))
                          for b in bs)
    links_ru = '\n'.join([
        '- [Сайт](%s): адреса точек, бронь столика в WhatsApp или по телефону, меню с фото и составом блюд' % SITE,
        '- [Меню и цены текстом](%s): кофейни и bakery to go, цены в тенге' % MENU_URL,
        '- [Частые вопросы](%s#faq)' % SITE,
        '- [Сайт на казахском](%s) и [меню на казахском](%s)' % (HOME['kk'], MENU['kk']),
        '- [Сайт на английском](%s) и [меню на английском](%s)' % (HOME['en'], MENU['en']),
        '- [Заказ онлайн и приложение](%s)' % ORDER_URL] + ['- [Instagram](%s)' % u for u in insta])
    links_en = '\n'.join([
        '- [Website in English](%s): locations, table booking via WhatsApp or phone, FAQ' % HOME['en'],
        '- [Menu with prices](%s): cafés and bakery to go, prices in KZT' % MENU['en'],
        '- [Menu with photos](%s%s): interactive menu on the main site, in English' % (SITE, MENU_HASH['en']),
        '- Also in [Kazakh](%s) and [Russian](%s)' % (HOME['kk'], SITE),
        '- [Order online / app](%s)' % ORDER_URL] + ['- [Instagram](%s)' % u for u in insta])
    rest_ru = ''.join(', %s — %s' % (short(b).split(' · ')[0], b['hours']) for b in rest)
    rest_en = ''.join(', %s — %s' % (short(b).split(' · ')[0], hours_en(b['hours'])) for b in rest)
    return '''# Del Cappuccino

> Кофейни Del Cappuccino в Алматы: %(cafes)s круглосуточно (24/7)%(rest_ru)s. Завтраки весь день, продукция сертифицирована КМДБ Halal (halaldamu.kz).

Детские комнаты (игровые пространства) — в %(kids_ru)s. Для спокойных встреч — VIP-залы, для молитвы — намазхана. Банкеты — для компании до 40 человек. Меню на сайте — на казахском, русском и английском.

## Точки

%(ru_points)s

## Ссылки

%(links_ru)s

## English

> Del Cappuccino cafés in Almaty: %(cafes_en)d open 24/7%(rest_en)s. Breakfast all day; products certified halal by KMDB (halaldamu.kz).

Kids' rooms (play areas) at %(kids_en)s. VIP rooms for quiet meetings, a prayer room (namazkhana). Banquets for groups of up to 40 guests. The menu on the website is available in Kazakh, Russian and English.

### Locations

%(en_points)s

### Links

%(links_en)s
''' % {'cafes': '%d %s' % (len(cafes), plural(len(cafes), 'кофейня', 'кофейни', 'кофеен')), 'rest_ru': rest_ru,
       'ru_points': ru_points, 'links_ru': links_ru, 'cafes_en': len(cafes), 'rest_en': rest_en,
       'en_points': en_points, 'links_en': links_en,
       'kids_ru': and_join(kids), 'kids_en': and_join([en[k] for k in kids], 'and')}


# ── запись ──

def with_faq(html):
    new = faq_block(faq(html))
    m = FAQ_RE.search(html)
    if m:
        return html[:m.start()] + new + html[m.end():]
    if FAQ_BEFORE not in html:
        sys.exit('seo_jsonld: нет якоря %s — некуда вставить «Частые вопросы»' % FAQ_BEFORE)
    return html.replace(FAQ_BEFORE, new + '\n' + FAQ_BEFORE, 1)


LOC_MARK = '<!-- Точки: из BRANCHES собирает tools/seo_jsonld.py — видны без JS поисковикам и ИИ, руками не править -->'
LOC_RE = re.compile(re.escape(LOC_MARK) + r'\n.*?<!-- /точки -->\n', re.S)


def wa_link(html, b):
    """как branchWa/waLink на странице: wa.me/<цифры телефона>?text=<encodeURIComponent(b.wa || текст по умолчанию + адрес)>"""
    m = re.search(r"function branchWa\(b\)\{return waLink\(b\.phone,\(b\.wa\|\|'((?:[^'\\]|\\.)*)'\)\+b\.addr\)\}", html)
    if not m:
        sys.exit('seo_jsonld: branchWa на странице записан иначе — обновите wa_link, чтобы ссылки WhatsApp в карточках совпадали с модалкой')
    default = unq(m.group(1))
    return 'https://wa.me/%s?text=%s' % (re.sub(r'\D', '', b['phone']), quote((b['wa'] or default) + b['addr'], safe="-_.!~*'()"))


def loc_cards(html):
    """карточки точек — разметка один в один с бывшим renderLocations (класс, порядок ссылок, onclick-и для аналитики)"""
    a = lambda s: H.escape(s, quote=False).replace('"', '&quot;')     # атрибут в "…": одинарные кавычки onclick оставляем как есть
    t = lambda s: H.escape(s, quote=False)
    out = []
    for b in branches(html):
        links = ['<a href="tel:%s" onclick="%s">Позвонить</a>' % (a(b['phone']), a("track('loc_call',{branch:'%s'})" % b['n'])),
                 '<a href="%s" target="_blank" rel="noopener" onclick="%s">Маршрут</a>' % (a(b['route']), a("track('loc_route',{branch:'%s'})" % b['n']))]
        if b['menu']:
            links.append('<a href="#" onclick="%s">Меню</a>' % a("event.preventDefault();track('loc_menu',{branch:'%s'});openMenu('%s')" % (b['n'], b['menu'])))
        links.append('<a class="wa" href="%s" target="_blank" rel="noopener" onclick="%s">WhatsApp</a>' % (a(wa_link(html, b)), a("track('loc_wa',{branch:'%s'})" % b['n'])))
        out.append('    <div class="loc-card">\n      <small>%s</small>\n      <h3>%s</h3>\n'
                   '      <p class="loc-meta"><b>%s</b>%s</p>\n      <div class="loc-links">\n        %s\n      </div>\n    </div>'
                   % (t(b['n']), t(b['addr']), t(b['hours']), ' · ' + t(b['note']) if b['note'] else '', '\n        '.join(links)))
    return LOC_MARK + '\n' + '\n'.join(out) + '\n<!-- /точки -->\n'


def with_loc(html):
    m = LOC_RE.search(html)
    if not m:
        sys.exit('seo_jsonld: в #loc-grid нет маркеров «%s … <!-- /точки -->»' % LOC_MARK)
    return html[:m.start()] + loc_cards(html) + html[m.end():]


def with_jsonld(html):
    new = block(html)
    m = BLOCK_RE.search(html)
    return html[:m.start()] + new + html[m.end():] if m else html.replace('</head>', new + '</head>', 1)


def outputs(html):
    """{путь: ожидаемый текст} — всё, что собирает генератор"""
    page = with_hreflang(with_jsonld(with_loc(with_faq(html))))
    out = {INDEX: page, LLMS: llms(page), KK_REVIEW: kk_review(page)}
    for lang in LANGS:
        out[os.path.join(ROOT, PAGES[MENU[lang]])] = menu_page(page, lang)
        if lang != 'ru':
            out[os.path.join(ROOT, PAGES[HOME[lang]])] = lang_page(page, lang)
    return out


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
