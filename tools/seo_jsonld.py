#!/usr/bin/env python3
"""Собирает из данных главной всё, что читают поисковики и ИИ-боты без JavaScript: разметку schema.org (JSON-LD)
в <head> index.html, раздел «Частые вопросы» на главной, страницу меню текстом /menyu, /llms.txt и lastmod в sitemap.xml.

Запуск из корня репозитория после правки меню (массивы MENU_* / TOGO_*), точек (BRANCHES) или tools/faq.json:
    python3 tools/seo_jsonld.py && python3 tools/sw_version.py      # порядок важен: sw_version хэширует index.html
С ключом --check только сравнивает и выходит с кодом 1, если что-то устарело (tests/test_seo.py).

Источники — только сама страница и tools/faq.json, ничего не придумывается:
- JSON-LD: организация Del Cappuccino (sameAs — Instagram, YouTube, Threads из SOCIAL, они же значками на странице, заказ онлайн — OrderAction),
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
  подставляются из BRANCHES; {детские}, {намазхана} и ответы «по точкам» ({доставка} {парковка} {wifi} {бронь} {залы}
  {работа} {животные}) — из tools/branch_facts.json (факты владельца 23.10.2026); карточка «Детская зона» на главной
  сверяется с ними. Допустимый HTML в ответах: <a href>, <ul>, <li>.
- Главная после редизайна (31.10.2026, по приложению): в блоке «акция» — карточка «кофейная подписка — скоро, в приложении»
  с видео налива кофе (грузится лениво; ссылки на сторы — константа APP_LINKS, пока пусто), подписи —
  tools/pages_i18n.json (sub); та же карточка на /kk/ и /en/. /kk/ и /en/ собираются по тому же макету, что главная:
  шапка с пилюлей точек и кругом языка, видеозона с логотипом, заставка; стили — правила <style> главной (токены v5,
  шрифт — --font-display и --font-body её :root).
- /menyu (menyu/index.html): всё меню текстом — кофейни (вкладки MENU_TABS) и Bakery to go (вкладки режима togo),
  разделы, объёмы, цены ₸, «только: …», старая цена зачёркнута. Путь не /menu/: там папка данных карточек menu/.
- /llms.txt: короткая справка для ИИ (ru + en) — точки, часы, ссылки; английские названия — из словаря MENU_TR.en.
- На /menyu — Google Analytics как на /ugolok (загрузка после load, ID — константа GA_ID): видно переходы из ИИ.
- Аналитика (блок в <head> всех страниц, включая /ugolok): gtag и единая track() — все события в Google Analytics;
  цели YM_GOALS (18 событий → 13 целей, одна цель на одно действие) ещё и в Яндекс Метрику; на /ugolok trackLinks:false;
  404.html — тот же блок и при загрузке событие page_not_found {path} (цель not_found). Включить Метрику: YM_ID = <номер счётчика> ниже,
  затем python3 tools/seo_jsonld.py && python3 tools/sw_version.py — на всех 8 собираемых страницах (с 404.html) появится ym init (вебвизор,
  карта кликов, ссылки), tag.js грузится после load. Пока YM_ID = None, кода Метрики на страницах нет (тест).
Разбор не по шаблону (позиций меньше, чем {n:'…} в массиве; точка без адреса) — выход с ошибкой, а не тихий пропуск.
lastmod в sitemap.xml: дата последнего коммита страницы, а если в ней есть незакоммиченные правки — сегодня.
Только stdlib.
"""
import datetime, html as H, json, os, re, subprocess, sys
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feature_icons  # noqa: E402  значки «Формата»

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
FACTS_JSON = os.path.join(ROOT, 'tools', 'branch_facts.json')     # факты по точкам от владельца (23.10.2026)
GA_ID = 'G-D50YPM8RMK'
YM_ID = None   # номер счётчика Яндекс Метрики (число) — пришлёт владелец; пока None, кода Метрики на страницах нет
# событие track() → цель Метрики (ym reachGoal); в Google Analytics уходят все события как есть (план владельца 23.10.2026).
# Одна цель на одно действие: menu_open шлёт само открытие меню (openMenu), поэтому кнопки «Меню» (cta_menu, loc_menu,
# modal_menu) целью не считаются; cta_wa_contact и cta_route только открывают окно выбора филиала — цель ставят modal_wa
# и modal_route (главный, 23.10.2026)
YM_GOALS = {'cta_order': 'order_app', 'cta_book': 'book_open',
            'loc_wa': 'whatsapp', 'modal_wa': 'whatsapp',
            'loc_call': 'call', 'modal_call': 'call',
            'loc_route': 'route', 'modal_route': 'route',
            'menu_open': 'menu_open',
            'menu_card': 'dish_card', 'cta_grill': 'grill_promo', 'cta_instagram': 'instagram',
            'lang_switch': 'lang_switch', 'menu_lang': 'lang_switch', 'faq_open': 'faq_open',
            'cta_ugolok': 'ugolok', 'ugolok_talon': 'ugolok',
            'page_not_found': 'not_found'}     # 404: один раз при загрузке, параметр path — путь без строки запроса
NOT_FOUND_JS = "track('page_not_found',{path:location.pathname})"

AN_MARK = '<!-- аналитика: Google Analytics и цели Яндекс Метрики — собирает tools/seo_jsonld.py, руками не править -->'
AN_RE = re.compile(r'<!-- аналитика: Google Analytics[^\n]*-->\n.*?<!-- /аналитика -->\n', re.S)
GA_LINE_RE = re.compile(r"<script>window\.dataLayer=window\.dataLayer\|\|\[\];function gtag\(\)\{dataLayer\.push\(arguments\)\}"
                        r"gtag\('js',new Date\(\)\);gtag\('config','G-[A-Z0-9]+'\);(?:function track\(n,p\)\{[^<]*\})?</script>\n")
UGOLOK = os.path.join(ROOT, 'ugolok', 'index.html')
NOT_FOUND = os.path.join(ROOT, '404.html')
FACT_TOPICS = ('tags', 'about', 'delivery', 'parking', 'wifi', 'booking', 'halls', 'business', 'pets')
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
    """(«4 кофейни работают круглосуточно, 24/7: …», [«Bakery to go · ЖК Rams City (Жандосова, 94/12) — ежедневно 07:00–22:00»])"""
    cafes = [b for b in bs if b['hours'] == '24/7']
    first = '%d %s %s круглосуточно, 24/7: %s' % (len(cafes), plural(len(cafes), 'кофейня', 'кофейни', 'кофеен'),
                                                  'работает' if len(cafes) == 1 else 'работают', ', '.join(place(b) for b in cafes))
    return first, ['%s — %s' % (place(b), b['hours']) for b in bs if b['hours'] != '24/7']


def facts():
    with open(FACTS_JSON, encoding='utf-8') as f:
        return json.load(f)


def point_facts(html):
    """{номер точки: факты} из tools/branch_facts.json — с проверкой, что номера есть в BRANCHES, а метки — в labels"""
    data, nums = facts(), [re.match(r'\d+', b['n']).group(0) for b in branches(html)]
    for num, pf in data['points'].items():
        if num not in nums:
            sys.exit('seo_jsonld: в branch_facts.json точка %s, а в BRANCHES такой нет' % num)
        unknown = [t for t in pf.get('tags', []) if t not in data['labels']]
        if unknown:
            sys.exit('seo_jsonld: у точки %s в branch_facts.json нет подписи для меток %s (labels)' % (num, ', '.join(unknown)))
        bad = [k for k in pf if k not in FACT_TOPICS]          # опечатка в теме («parkng») иначе молча выкинет факт с сайта
        if bad:
            sys.exit('seo_jsonld: у точки %s в branch_facts.json неизвестные поля %s — есть: %s' % (num, ', '.join(bad), ', '.join(FACT_TOPICS)))
        for k, v in pf.items():
            if isinstance(v, dict) and set(v) != set(LANGS):
                sys.exit('seo_jsonld: точка %s, %s — нужны ru, kk и en (есть: %s)' % (num, k, ', '.join(sorted(v))))
    for key, lab in data['labels'].items():
        if set(lab) != set(LANGS) | {'schema'}:
            sys.exit('seo_jsonld: метка %s в branch_facts.json — нужны ru, kk, en и schema' % key)
    return {n: data['points'].get(n, {}) for n in nums}


def bnum(b):
    return re.match(r'\d+', b['n']).group(0)


def tag_labels(html, b, lang):
    """короткая строка удобств точки: «детская зона · VIP-залы · Wi-Fi · парковка»"""
    labels = facts()['labels']
    return [labels[t][lang] for t in point_facts(html)[bnum(b)].get('tags', [])]


def topic_list(html, c, topic):
    """ответ «по точкам»: <ul><li>ЖК Вавилон (Розыбакиева, 247/8): через все агрегаторы доставки</li>…</ul>"""
    e = lambda s: H.escape(s, quote=False)
    pf = point_facts(html)
    rows = ['<li>%s: %s</li>' % (e(place_l(c, b)), e(pf[bnum(b)][topic][c['lang']])) for b in branches(html) if topic in pf[bnum(b)]]
    return '<ul>' + ''.join(rows) + '</ul>'


def tag_places(html, tag):
    """точки с меткой (детская зона, намазхана) — короткие названия из BRANCHES"""
    pf = point_facts(html)
    return [b for b in branches(html) if tag in pf[bnum(b)].get('tags', [])]


def kids_places(html):
    """где детская зона — из tools/branch_facts.json (метка kids); карточка «Детская зона» в «Формате» главной должна
    говорить то же самое, иначе выход с ошибкой (владелец 23.10: детская только в ЖК Вавилон, в Комфорт Сити её нет)"""
    places = [short(b) for b in tag_places(html, 'kids')]
    m = re.search(r'<h3>Детская зона</h3><p>Игровая зона в ([^<]+?)\.</p>', html)
    if not m or re.split(r',\s*|\s+и\s+', m.group(1)) != places:
        sys.exit('seo_jsonld: карточка «Детская зона» в «Формате» главной (%s) расходится с tools/branch_facts.json (%s)'
                 % (m.group(1) if m else 'не найдена', ', '.join(places)))
    return places


def and_join(xs, conj='и'):
    return xs[0] if len(xs) == 1 else '%s %s %s' % (', '.join(xs[:-1]), conj, xs[-1])


def faq_vars(html, lang='ru'):
    """подстановки в тексты: {часы} {адреса} {точек} {детские} {кофеен} {точек_n} {часы_togo} — из BRANCHES и главной"""
    e = lambda s: H.escape(s, quote=False)
    bs = branches(html)
    cafes, rest = [b for b in bs if b['hours'] == '24/7'], [b for b in bs if b['hours'] != '24/7']
    togo_h = [m.group(0) for m in (re.search(r'\d\d:\d\d\s*[–-]\s*\d\d:\d\d', b['hours']) for b in rest) if m]
    v = {'кофеен': str(len(cafes)), 'точек_n': str(len(bs)), 'часы_togo': togo_h[0] if togo_h else ''}
    c0 = lang_ctx(html, lang)
    # ответы «по точкам» из tools/branch_facts.json: {доставка} {парковка} {wifi} {бронь} {залы} {работа} {животные} {намазхана}
    for key, topic in (('доставка', 'delivery'), ('парковка', 'parking'), ('wifi', 'wifi'), ('бронь', 'booking'),
                       ('залы', 'halls'), ('работа', 'business'), ('животные', 'pets')):
        v[key] = topic_list(html, c0, topic)
    v['намазхана'] = e(and_join([place_l(c0, b) for b in tag_places(html, 'namaz')],
                                'и' if lang == 'ru' else c0['d']['phrases']['and']))
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
    """раздел «Частые вопросы» (правки владельца 31.10): по умолчанию свёрнут — видна плашка-заголовок по центру; по нажатию
    раскрывается список, каждый вопрос — свой <details>. Без JS, тексты в HTML (тот же текст — FAQPage в JSON-LD).
    Ссылка на меню текстом — под плашкой, видна и в свёрнутом виде. head — (заголовок, строка со ссылкой) для /kk/ и /en/"""
    h2, p = head or ('Частые <span>вопросы</span>', 'Всё меню с ценами текстом — <a href="/menyu">на отдельной странице</a>.')
    rows = '\n'.join('      <details ontoggle="if(this.open)track(\'faq_open\',{q:%d})"><summary>%s</summary><div class="faq-a">%s</div></details>'
                     % (i + 1, H.escape(q, quote=False), a) for i, (q, a) in enumerate(items))
    return (('' if head else FAQ_MARK + '\n') + '<section class="faq" id="faq">\n  <div class="shell">\n'
            '    <details class="faq-box" ontoggle="if(this.open)track(\'faq_list\')">\n      <summary class="faq-sum"><h2>%s</h2></summary>\n'
            '    <div class="faq-list">\n' % h2 + rows + '\n    </div>\n    </details>\n    <p class="faq-more">%s</p>\n  </div>\n</section>\n' % p +
            ('' if head else '<!-- /faq -->\n'))


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
           'logo': SITE + 'assets/icon-192.png', 'sameAs': [u for _, _, u, _ in SOCIAL],
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
        pf, labels = point_facts(html)[num], facts()['labels']
        amen = [labels[t]['ru'] for t in pf.get('tags', []) if labels[t]['schema']]
        if amen:
            node['amenityFeature'] = [{'@type': 'LocationFeatureSpecification', 'name': x[:1].upper() + x[1:], 'value': True} for x in amen]
        if 'about' in pf:
            node['description'] = pf['about']['ru']
        if 'booking' in pf:
            node['acceptsReservations'] = True
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


def tokens_css(html):
    """:root главной (токены v5, шрифты) без комментариев — текстовые меню на тех же токенах"""
    css = re.sub(r'/\*.*?\*/', '', html[html.index('<style>') + 7:html.index('</style>')], flags=re.S)
    return re.sub(r'\s*\n\s*', '', re.search(r':root\{.*?\}', css, re.S).group(0))


def social_sprite():
    """спрайт только со значками соцсетей — для текстовых меню (вся страница без JS и фото)"""
    syms = re.findall(r'<symbol id="i-(?:ig|yt|th)".*?</symbol>', ICONS)
    return '<svg class="icons" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false">%s</svg>' % ''.join(syms)


def menu_social():
    return ''.join('<a href="%s" target="_blank" rel="noopener" onclick="track(\'cta_instagram\',{net:\'%s\',src:\'menu_page\'})" '
                   'aria-label="%s" title="%s"><svg aria-hidden="true" focusable="false"><use href="#i-%s"/></svg></a>'
                   % (url, key, name, name, ic) for key, name, url, ic in SOCIAL)


def menu_lang_switch(lang):
    return ''.join('<a href="%s" lang="%s"%s>%s</a>' % (MENU[l][len(SITE) - 1:], l, ' aria-current="page"' if l == lang else
                                                      ' hreflang="%s" onclick="track(\'lang_switch\',{lang:\'%s\',src:\'menu_page\'})"' % (l, l),
                                                      {'ru': 'РУС', 'kk': 'ҚАЗ', 'en': 'ENG'}[l]) for l in LANGS)


def menu_page(html, lang='ru'):
    """/menyu, /kk/menyu, /en/menu — всё меню текстом: кофейни (вкладки MENU_TABS) и Bakery to go (вкладки togo)"""
    e = lambda s: H.escape(s, quote=False)
    c = lang_ctx(html, lang)
    ui, ui0, marks, bs, mp = c['ui'], ui_ru(html), mark_names(html, c if lang != 'ru' else None), branches(html), c['d']['menu_page']
    by_num = {re.match(r'\d+', b['n']).group(0): b for b in bs}
    fonts = font_faces(html)                  # шрифты главной: --font-display (заголовки) и --font-body (текст)
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
    toc = ' '.join('<a href="#%s">%s</a>' % (t, e(ui['tab_' + t])) for t, _ in tabs['cafe'])
    toc += ' <a href="#togo">%s</a>' % e(ui['mode_togo'])
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
%(analytics)s<!-- Страница собрана tools/seo_jsonld.py из массивов меню главной — руками не править, правьте index.html и пересоберите -->
<style>
%(fonts)s
%(tokens)s
/* меню текстом (этап 2 редизайна): токены v5 главной, Geologica — заголовки, Montserrat — текст, фон белый; без JS и фото */
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--c-bg);color:var(--c-text);font:15px/1.5 var(--font-body);-webkit-font-smoothing:antialiased}
.wrap{max-width:860px;margin:0 auto;padding:0 16px}
a{color:var(--c-accent);font-weight:600}
header{display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:12px 0}
.logo{display:inline-flex;margin-right:4px}
.logo img{display:block;height:36px;width:auto;border-radius:8px}
.pill,.toc a,.lang a{display:inline-flex;align-items:center;justify-content:center;min-height:40px;padding:0 16px;border-radius:var(--r-pill);background:var(--c-surface);color:var(--c-text);font-size:var(--fs-small);font-weight:600;text-decoration:none;white-space:nowrap}
.lang{display:flex;gap:4px;margin-left:auto}
.lang a{min-width:44px;padding:0 8px;font-size:var(--fs-caption);font-weight:700}
.lang a[aria-current]{background:var(--c-accent);color:var(--c-on-accent)}
h1,h2,h3,h4{font-family:var(--font-display);font-weight:700;text-transform:lowercase;line-height:1.2}
h1{font-size:var(--fs-heading);margin:16px 0 8px}
.lead{color:var(--c-muted)}
.toc{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0 8px}
h2{font-size:24px;margin:32px 0 8px;padding-top:16px;border-top:1px solid var(--c-border)}
h3{font-size:var(--fs-title);color:var(--c-accent);margin:24px 0 4px}
h4{display:flex;justify-content:space-between;align-items:baseline;gap:12px;font-size:20px;margin:40px 0 6px}
h4 small{display:inline-flex;align-items:center;min-height:22px;margin-left:6px;padding:0 8px;border-radius:var(--r-pill);background:var(--c-surface);font-family:var(--font-body);font-weight:600;text-transform:none;vertical-align:2px}
.note{font-size:13px;color:var(--c-muted);margin:2px 0}
ul{list-style:none}
li{display:flex;justify-content:space-between;align-items:baseline;gap:12px;padding:6px 0;border-bottom:1px solid var(--c-border);font-size:15px;line-height:1.4}
li .n{font-weight:500}
small,li i,li em{font-size:13px;color:var(--c-muted);font-style:normal;font-weight:400}
.p{white-space:nowrap;font-family:var(--font-body);font-weight:600;text-transform:none;font-variant-numeric:tabular-nums}
.p s{font-weight:400;color:var(--c-muted)}
footer{margin:40px 0 28px;padding-top:16px;border-top:1px solid var(--c-border);font-size:13px;color:var(--c-muted);line-height:1.9;text-align:center}
.social{display:flex;justify-content:center;gap:12px;margin:12px 0}
.social a{display:inline-flex;align-items:center;justify-content:center;width:48px;height:48px;border-radius:50%%;background:var(--c-surface);color:var(--c-text)}
.social svg{display:block;width:22px;height:22px}
.icons{position:absolute;width:0;height:0;overflow:hidden}
@media(min-width:700px){h1{font-size:34px}}
</style>
</head>
<body>
%(icons)s
<header class="wrap"><a class="logo" href="%(home)s" aria-label="Del Cappuccino"><img src="/assets/logo-lockup-128.webp" width="128" height="63" alt="Del Cappuccino"></a><a class="pill" href="%(home)s">%(back)s</a><a class="pill" href="%(menu_link)s" onclick="track('cta_menu',{src:'menu_page'})">%(photo_menu)s</a><nav class="lang" aria-label="%(lang_label)s">%(sw)s</nav></header>
<main class="wrap">
<h1>%(h1)s</h1>
<p class="lead">%(lead)s</p>
<nav class="toc">%(toc)s</nav>
%(body)s
</main>
<footer class="wrap">
<div class="social">%(social)s</div>
<a href="%(home)s">%(f_home)s</a> · <a href="%(home)s#faq">%(f_faq)s</a> · <a href="%(order)s" onclick="track('cta_order',{src:'menu_page'})">%(f_order)s</a> · © 2026 Del Cappuccino</footer>
%(ga_loader)s
</body>
</html>
''' % {'lang': lang, 'url': MENU[lang], 'hreflang': hreflang(MENU), 'locale': LOCALE[lang], 'fonts': fonts, 'toc': toc,
       'font_body': font_var(html, 'body'),
       'body': '\n'.join(x for x in body if x), 'order': ORDER_URL, 'home': home, 'menu_link': menu_link,
       'title': e(mp['title']), 'description': H.escape(mp['description']), 'og_title': H.escape(mp['og_title']),
       'og_description': H.escape(mp['og_description']), 'back': e(mp['back']), 'photo_menu': e(mp['photo_menu']),
       'h1': e(mp['h1']), 'lead': mp['lead'].replace('{menu_link}', menu_link),
       'f_home': e(mp['home']), 'f_faq': e(mp['faq']), 'f_order': e(mp['order']),
       'tokens': tokens_css(html), 'icons': social_sprite(), 'social': menu_social(), 'sw': menu_lang_switch(lang),
       'lang_label': H.escape(i18n()['kk' if lang == 'kk' else 'en']['page']['lang_label']) if lang != 'ru' else 'Язык',
       'analytics': analytics_head(YM_ID), 'ga_loader': GA_LOADER % GA_ID}


# селекторы главной, которые нужны облегчённым /kk/ и /en/: токены, шапка, заставка, hero, карточка подписки, «О нас», «Формат»,
# точки (кнопки-значки), вопросы, контакты, подвал (без оверлея меню, модалки, «Курицы гриль» и фото «Фирменный стиль»)
CSS_KEEP = re.compile(r'^(?::root|:focus-visible|\*|html|body|a|h1|h2|h3|header|nav|footer|\.(?:shell|disp|hbar|brand|logo-d|pill-point|top-nav|'
                      r'lang-sw|lang-dd|lang-list|btn|fab-menu|intro|intro-on|logo-art|logo-art-text|logo-art-moped|tag|lead|actions|'
                      r'halal-badge|hero|hero-zone|hero-text|hero-badge|promo|promo-grid|promo-tile|sub-tile|tile-cap|promo-t|promo-s|promo-a|row-head|sub-video|'
                      r'icons|ic|ib|pill|social|'
                      r'story|story-grid|story-photo|stats|features|f-head|f-grid|f-ic|'
                      r'locations|loc-head|loc-grid|loc-card|loc-meta|loc-about|loc-amen|loc-links|faq|faq-box|faq-sum|faq-more|faq-head|faq-list|faq-a|contact|contact-actions|'
                      r'f-row|hide-mobile))(?![\w-])')
CSS_KEYFRAMES = ('moped-in', 'fade-in', 'intro-out')     # анимации заставки


def hreflang(urls):
    """<link rel=alternate hreflang> на все версии + x-default (русская)"""
    return '\n'.join(['<link rel="alternate" hreflang="%s" href="%s">' % (l, urls[l]) for l in LANGS] +
                     ['<link rel="alternate" hreflang="x-default" href="%s">' % urls['ru']])


def analytics_head(ym_id=None, track_links=True, on_load=None):
    """<head>: gtag и track(); с номером Метрики — ещё ym init (вебвизор, карта кликов, ссылки) и цели reachGoal по YM_GOALS,
    сам tag.js — после load, в простое (как gtag). Без номера — ни строчки Метрики."""
    js = ("window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}gtag('js',new Date());"
          "gtag('config','%s');" % GA_ID)
    if not ym_id:
        js += "\nfunction track(n,p){if(typeof gtag!=='undefined')gtag('event',n,p||{})}"
    else:
        js += ("\nvar YM_ID=%d,YM_GOALS=%s;\n" % (int(ym_id), dumps(YM_GOALS)) +
               "window.ym=window.ym||function(){(ym.a=ym.a||[]).push(arguments)};ym.l=+new Date;\n"
               "ym(YM_ID,'init',{clickmap:true,trackLinks:%s,accurateTrackBounce:true,webvisor:true});\n" % ('true' if track_links else 'false') +
               "function track(n,p){if(typeof gtag!=='undefined')gtag('event',n,p||{});var g=YM_GOALS[n];if(g)ym(YM_ID,'reachGoal',g,p||{})}\n"
               "(function(){function load(){var s=document.createElement('script');s.async=true;s.src='https://mc.yandex.ru/metrika/tag.js';"
               "document.head.appendChild(s)}\nfunction idle(){('requestIdleCallback'in window)?requestIdleCallback(load,{timeout:4000}):setTimeout(load,1500)}\n"
               "if(document.readyState==='complete')idle();else addEventListener('load',idle)})();")
    if on_load:
        js += '\n' + on_load + ';'                  # событие страницы при загрузке (404 — page_not_found)
    return AN_MARK + '\n<script>' + js + '</script>\n<!-- /аналитика -->\n'


def with_analytics(html, track_links=True, on_load=None):
    """заменить блок аналитики (или прежнюю строку gtag в <head>) на analytics_head(YM_ID); track_links=False — /ugolok:
    адреса PDF-талонов с именами ИП не уходят в Метрику (главный, 23.10.2026)"""
    new, head = analytics_head(YM_ID, track_links, on_load), html.split('</head>')[0]
    m = AN_RE.search(head) or GA_LINE_RE.search(head)
    if not m:
        sys.exit('seo_jsonld: в <head> нет блока аналитики и строки gtag — некуда поставить analytics_head')
    return html[:m.start()] + new + html[m.end():]


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
    if pre.startswith(('@media', '@supports')):     # @supports — стекло плавающей кнопки «меню»
        inner = [r for r in (keep_rule(x) for x in css_rules(body[:-1])) if r]
        return pre + '{\n' + '\n'.join(inner) + '\n}' if inner else None
    if pre.startswith('@keyframes'):
        return rule if pre.split()[1] in CSS_KEYFRAMES else None
    if pre.startswith('@'):
        return None
    return rule if any(CSS_KEEP.match(s.strip()) for s in pre.split(',')) else None


def css_subset(html):
    """стили облегчённых страниц — правила из <style> главной (один источник вида: токены v5 в :root), без меню, модалок и акций"""
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
        {'@type': 'Organization', '@id': SITE + '#org', 'name': 'Del Cappuccino', 'url': SITE, 'sameAs': [u for _, _, u, _ in SOCIAL]},
        {'@type': 'FAQPage', '@id': HOME[lang] + '#faq', 'inLanguage': lang,
         'mainEntity': [{'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}} for q, a in items]}]}
    return dumps(data).replace('</', '<\\/')


def font_faces(html, which=('display', 'body')):
    """@font-face главной для семейств из переменных --font-display / --font-body её :root (пути — от корня сайта).
    Шрифт меняется в одном месте — в :root главной; /kk/, /en/ и текстовые меню берут его оттуда."""
    root = re.search(r':root\{(.*?)\}', html, re.S).group(1)
    fams = [re.search(r"--font-%s:'([^']+)'" % w, root).group(1) for w in which]
    faces = re.findall(r"@font-face\{font-family:'(?:%s)'[^\n]*" % '|'.join(re.escape(f) for f in fams), html)
    if not faces:
        sys.exit('seo_jsonld: в <style> главной нет @font-face для %s — шрифт из :root не подключён' % ', '.join(fams))
    return '\n'.join(root_paths(l) for l in faces)


def font_var(html, which):
    """значение переменной --font-<which> из :root главной: «'Montserrat',system-ui,…»"""
    return re.search(r'--font-%s:([^;]+);' % which, re.search(r':root\{(.*?)\}', html, re.S).group(1)).group(1).strip()


def root_paths(s):
    """assets/… и img/… главной → /assets/…, /img/… (страницы в подпапках)"""
    return re.sub(r'(?<=["\s,(])(assets|img)/', r'/\1/', s)


INTRO_RE = re.compile(r"<script>\(function\(\)\{try\{if\(matchMedia\('\(prefers-reduced-motion: reduce\)'\).*?</script>")


def intro_js(html):
    """скрипт заставки из <head> главной — тот же на /kk/ и /en/ (раз за сессию: общий ключ sessionStorage)"""
    m = INTRO_RE.search(html.split('</head>')[0])
    if not m:
        sys.exit('seo_jsonld: в <head> главной нет скрипта заставки (intro-on)')
    return m.group(0) + '\n'


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
    fonts = font_faces(html)        # казахские буквы — в cyrillic + cyrillic-ext обоих шрифтов (проверено), отдельный шрифт для kk не нужен
    cur = {'ru': 'РУС', 'kk': 'ҚАЗ', 'en': 'ENG'}[lang]
    sw = '\n'.join('      <a href="%s" lang="%s"%s>%s</a>' % ('/' if l == 'ru' else '/%s/' % l, l,
                                                    ' aria-current="page"' if l == lang else
                                                    ' hreflang="%s" onclick="track(\'lang_switch\',{lang:\'%s\'})"' % (l, l),
                                                    {'ru': 'РУС', 'kk': 'ҚАЗ', 'en': 'ENG'}[l]) for l in LANGS)
    logo_d = img_tag(html, r'<img class="logo-d"[^>]*>', 'Del Cappuccino')
    logo_art = root_paths(re.search(r'<div class="hero-zone">\n\s*(<div class="logo-art".*?</div>)\n', html).group(1))
    intro = root_paths(re.search(r'<div class="intro" aria-hidden="true">.*?</div></div>', html).group(0))
    preload = '\n'.join(root_paths(l) for l in re.findall(r'<link rel="preload" href="assets/fonts/[^>]*>', html))
    story_img = img_tag(html, r'(?<=<div class="story-photo">)<img[^>]*>', P['story_alt'])
    halal_img = img_tag(html, r'<img src="assets/halal-104\.webp"[^>]*>', P['halal_alt'])
    mono = '<img src="/assets/logo-mono-192.webp" width="192" height="192" loading="lazy" decoding="async" alt="dC">'

    def card(b):
        need(c, [short(b), b['addr']] + ([b['note']] if b['note'] and b['note'] not in c['d']['branch_note'] else []))
        note = c['d']['branch_note'].get(b['note'], T(c, b['note'])) if b['note'] else ''
        wa = 'https://wa.me/%s?text=%s' % (re.sub(r'\D', '', b['phone']),
                                           quote((c['d']['wa_togo'] if b['wa'] else c['d']['wa_book']) + T(c, b['addr']), safe="-_.!~*'()"))
        ev = lambda name: ' onclick="track(\'%s\',{branch:\'%s\'})"' % (name, js_attr(b['n']))
        links = [icon_link('ib route', b['route'], P['route'], ev('loc_route'), 'pin'),
                 icon_link('ib', 'tel:' + b['phone'], P['call'], ev('loc_call'), 'phone', blank=False),
                 icon_link('ib wa', wa, 'WhatsApp', ev('loc_wa'), 'wa')]
        if b['menu']:
            links.append('<a class="pill" href="/%s-%s"%s>%s</a>' % ('#menu-togo' if b['menu'] == 'togo' else '#menu', lang, ev('loc_menu'), e(P['card_menu'])))
        return ('    <div class="loc-card">\n      <small>%s</small>\n      <h3>%s</h3>\n'
                '%s%s      <div class="loc-links">\n        %s\n      </div>\n    </div>'
                % (e(T(c, short(b))), e(T(c, b['addr'])), loc_meta(e(hours_card(c, b['hours'])), e(note)),
                   card_extra(html, b, lang), '\n        '.join(links)))

    stats = ('<div><b>24/7</b><span>%s</span></div>\n  <div><b>%d</b><span>%s</span></div>\n  <div><b>all day</b><span>%s</span></div>'
             % (P['stat_cafes'], len(bs), P['stat_points'], P['stat_breakfast']))
    faq_html = faq_block(items, (P['faq_h2'], P['faq_p']))
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
%(preload)s
<meta name="theme-color" content="#426349">
<link rel="icon" type="image/png" sizes="192x192" href="/assets/icon-192.png">
<link rel="apple-touch-icon" sizes="180x180" href="/assets/apple-touch-icon.png">
<meta property="og:type" content="website">
<meta property="og:url" content="%(url)s">
<meta property="og:title" content="%(title)s">
<meta property="og:description" content="%(description)s">
<meta property="og:locale" content="%(locale)s">
<meta property="og:image" content="%(site)sassets/photo_01.jpg">
%(analytics)s%(intro_js)s
<!-- Страница собрана tools/seo_jsonld.py: тексты — tools/pages_i18n.json, факты — BRANCHES и главная, стили — из <style> главной. Руками не править -->
<style>
%(fonts)s
%(css)s
</style>
<script type="application/ld+json">
%(jsonld)s
</script>
</head>
<body>

%(intro)s
%(icons)s

<header>
  <div class="hbar">
    <a class="brand" href="%(home)s" aria-label="%(home_label)s">
      %(logo_d)s
    </a>
    <a class="pill-point" href="#locations" onclick="track('cta_route',{src:'pill'})"><b>%(pill_b)s</b><span> · %(pill_s)s</span><i aria-hidden="true">›</i></a>
    <nav class="top-nav">
      <a href="%(menu_link)s" onclick="track('cta_menu',{src:'nav'})">%(nav_menu)s</a>
      <a href="#about">%(nav_about)s</a>
      <a href="#features">%(nav_features)s</a>
      <a href="#locations">%(nav_locations)s</a>
      <a href="#faq">%(nav_faq)s</a>
    </nav>
    <nav class="lang-sw" aria-label="%(lang_label)s">
      <details class="lang-dd"><summary aria-label="%(lang_label)s">%(cur)s</summary><div class="lang-list">
%(sw)s
      </div></details>
    </nav>
  </div>
</header>

<main id="top">
  <section class="hero shell">
    <div class="hero-zone">
      %(logo_art)s
      <div class="hero-badge">
        <b>24/7</b>
        <div><span>%(badge_cafes)s</span><span>%(badge_days)s</span></div>
      </div>
    </div>
    <div class="hero-text">
      <p class="tag">%(hero_tag)s</p>
      <h1>%(hero_h1)s</h1>
      <p class="lead">%(hero_lead)s</p>
      <div class="actions">
        <a class="btn olive" href="#locations" onclick="track('cta_book')">%(book)s</a>
        <a class="btn" href="%(order_url)s" target="_blank" rel="noopener" onclick="track('cta_order')">%(order)s</a>
        <a class="btn ghost" href="%(menu_link)s" onclick="track('cta_menu')">%(menu)s</a>
      </div>
      <div class="halal-badge">
        %(halal_img)s
        <span>%(halal)s</span>
      </div>
    </div>
  </section>

  <section class="promo shell" aria-labelledby="promo-h">
    <div class="row-head"><h2 id="promo-h">%(promo_h2)s</h2></div>
    <div class="promo-grid">
%(sub)s    </div>
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
        <h2>%(features_h2)s</h2>
      </div>
      <div class="f-grid">
%(features)s
      </div>
    </div>
  </section>
</main>

<section class="locations" id="locations">
  <div class="shell">
    <div class="loc-head">
      <div><h2>%(loc_h2)s</h2></div>
      <p>%(loc_p)s</p>
    </div>
    <div class="loc-grid">
%(cards)s
    </div>
  </div>
</section>

%(faq)s
<section class="contact shell" id="contacts">
  <h2>%(contact_h2)s</h2>
%(social)s</section>

<footer class="shell">
  <div class="f-row">
    <a href="%(home)s" aria-label="%(home_label)s">%(mono)s</a>
    <span>%(footer_tag)s</span>
    <a href="%(menu_page)s">%(footer_menu)s</a>
    <span class="f-legal"><a class="f-ugolok" href="/ugolok/" onclick="track('cta_ugolok')">%(footer_ugolok)s</a> <a href="/legal/offer.%(lang)s.html" onclick="track('legal_open',{doc:'offer'})">%(footer_offer)s</a> <a href="/legal/privacy.%(lang)s.html" onclick="track('legal_open',{doc:'privacy'})">%(footer_privacy)s</a> <a href="/legal/contacts.%(lang)s.html" onclick="track('legal_open',{doc:'contacts'})">%(footer_contacts)s</a></span>
    <span>© 2026 Del Cappuccino</span>
  </div>
</footer>
<a class="fab-menu" href="%(menu_link)s" onclick="track('cta_menu',{src:'hbar_m'})"><svg class="ic" aria-hidden="true" focusable="false"><use href="#i-menu"/></svg>%(nav_menu)s</a>
%(ga_loader)s
</body>
</html>
''' % dict({k: P[k] for k in ('hero_tag', 'hero_h1', 'hero_lead', 'book', 'menu', 'order', 'halal', 'badge_cafes', 'badge_days',
                               'about_h2', 'about_p', 'features_h2', 'loc_h2', 'loc_p', 'contact_h2',
                               'footer_tag', 'footer_menu', 'footer_ugolok', 'footer_offer', 'footer_privacy', 'footer_contacts', 'nav_menu', 'nav_about', 'nav_features',
                               'nav_locations', 'nav_faq', 'pill_b', 'pill_s')},
           lang=lang, title=H.escape(P['title']), description=H.escape(P['description']), url=HOME[lang], hreflang=hreflang(HOME),
           locale=LOCALE[lang], site=SITE, analytics=analytics_head(YM_ID), ga_loader=GA_LOADER % GA_ID, fonts=fonts, css=css_subset(html),
           jsonld=lang_jsonld(html, lang, P, items), home=home, home_label=H.escape(P['home_label']),
           lang_label=H.escape(P['lang_label']), logo_d=logo_d, menu_link=menu_link, sw=sw, cur=cur,
           preload=preload, intro_js=intro_js(html), intro=intro, logo_art=logo_art,
           sub=sub_card(lang), icons=ICONS, promo_h2=H.escape(i18n()[lang]['sub']['h2'], quote=False),
           order_url=ORDER_URL, halal_img=halal_img, story_img=story_img, stats=stats,
           features='\n'.join('        <article>%s<h3>%s</h3><p>%s</p></article>' % (feature_icon(i), h, p) for i, (h, p) in enumerate(feats)),
           cards='\n'.join(card(b) for b in bs), faq=faq_html, mono=mono, menu_page='/' + MENU[lang][len(SITE):],
           social=social_row())


KK_REVIEW_UI = ('search', 'search_none')       # новые строки MENU_UI.kk — тоже на вычитку


def kk_review(html):
    """menu/kk_review.md — все казахские строки из pages_i18n.json со своим местом на сайте, для вычитки носителем"""
    where = {'phrases': 'подстановки в тексты (часы, точки, «и»)', 'branch_note': 'карточка точки 05 на /kk/',
             'wa_book': 'текст сообщения WhatsApp из карточек кофеен /kk/', 'wa_togo': 'текст сообщения WhatsApp из карточки bakery to go /kk/',
             'page': 'страница /kk/', 'sub': 'карточка подписки в блоке «акция» на /kk/', 'faq': 'частые вопросы на /kk/ (и FAQPage в разметке)', 'menu_page': 'текстовое меню /kk/menyu',
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
    # строки интерфейса меню главной, добавленные при редизайне (поиск по меню, 1.11) — живут в MENU_UI.kk в index.html
    ui_kk = ui_dict(html, 'kk')
    for key in KK_REVIEW_UI:
        rows.append('| `MENU_UI.kk.%s` | поиск в меню главной (ҚАЗ) | %s |' % (key, ui_kk[key].replace('|', '\\|')))
    fw = {'labels': 'метка удобства на карточке точки /kk/', 'about': 'описание точки на карточке /kk/'}
    for key, lab in facts()['labels'].items():
        rows.append('| `branch_facts.labels.%s` | %s | %s |' % (key, fw['labels'], lab['kk']))
    for num, pf in facts()['points'].items():
        for topic, val in pf.items():
            if isinstance(val, dict):
                rows.append('| `branch_facts.points.%s.%s` | %s | %s |' % (num, topic, fw.get(topic, 'ответ «по точкам» в частых вопросах /kk/'), val['kk']))
    return ('# Казахские строки на вычитку носителем\n\n'
            'Собрано `tools/seo_jsonld.py` из `tools/pages_i18n.json` (раздел `kk`) и `tools/branch_facts.json` (поля `kk`).\n'
            'Правки вносить туда и пересобрать:\n'
            '`python3 tools/seo_jsonld.py && python3 tools/sw_version.py`.\n\n'
            '- `{…}` — подстановки из данных сайта, их не переводить: `{часы}` — часы точек, `{адреса}` — список адресов,\n'
            '  `{точек}` / `{точек_n}` — число точек, `{кофеен}` — число кофеен 24/7, `{часы_togo}` — часы bakery to go,\n'
            '  `{детские}` — где детская зона, `{намазхана}` — где намазхана, `{доставка}` `{парковка}` `{wifi}` `{бронь}`\n'
            '  `{залы}` `{работа}` `{животные}` — списки «по точкам» из branch_facts.json, `{n}` / `{list}` / `{old}` — число,\n'
            '  список, старая цена.\n'
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
    amen = lambda b, l: ''.join('; ' + ', '.join(x) for x in [tag_labels(html, b, l)] if x)
    namaz = [short(b) for b in tag_places(html, 'namaz')]
    ru_points = '\n'.join('- %s — %s, Алматы — %s%s' % (short(b), b['addr'], hours_ru(b['hours']), amen(b, 'ru')) for b in bs)
    kids = kids_places(html)
    missing = [x for x in [y for b in bs for y in (short(b), b['addr'])] + kids if x not in en]
    missing += [short(b) for b in tag_places(html, 'namaz') if short(b) not in en]
    if missing:
        sys.exit('seo_jsonld: нет английского перевода в MENU_TR.en для %s — допишите словарь' % ', '.join(missing))
    en_points = '\n'.join('- %s — %s, Almaty — %s%s' % (en[short(b)], en[b['addr']], hours_en(b['hours']), amen(b, 'en'))
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

Детская зона — в %(kids_ru)s. Для спокойных встреч — VIP-залы и кабинки, намазхана — в %(namaz_ru)s. Банкеты — для компании до 40 человек. Меню на сайте — на казахском, русском и английском.

## Точки

%(ru_points)s

## Ссылки

%(links_ru)s

## English

> Del Cappuccino cafés in Almaty: %(cafes_en)d open 24/7%(rest_en)s. Breakfast all day; products certified halal by KMDB (halaldamu.kz).

Kids' area at %(kids_en)s. VIP rooms and booths for quiet meetings; a prayer room (namazkhana) at %(namaz_en)s. Banquets for groups of up to 40 guests. The menu on the website is available in Kazakh, Russian and English.

### Locations

%(en_points)s

### Links

%(links_en)s
''' % {'cafes': '%d %s' % (len(cafes), plural(len(cafes), 'кофейня', 'кофейни', 'кофеен')), 'rest_ru': rest_ru,
       'ru_points': ru_points, 'links_ru': links_ru, 'cafes_en': len(cafes), 'rest_en': rest_en,
       'en_points': en_points, 'links_en': links_en,
       'kids_ru': and_join(kids), 'kids_en': and_join([en[k] for k in kids], 'and'),
       'namaz_ru': and_join(namaz), 'namaz_en': and_join([en[k] for k in namaz], 'and')}


# ── запись ──

def with_faq(html):
    new = faq_block(faq(html))
    m = FAQ_RE.search(html)
    if m:
        return html[:m.start()] + new + html[m.end():]
    if FAQ_BEFORE not in html:
        sys.exit('seo_jsonld: нет якоря %s — некуда вставить «Частые вопросы»' % FAQ_BEFORE)
    return html.replace(FAQ_BEFORE, new + '\n' + FAQ_BEFORE, 1)


def card_extra(html, b, lang):
    """строки карточки точки из tools/branch_facts.json: описание (у Promenade) и удобства через «·»"""
    e = lambda s: H.escape(s, quote=False)
    pf = point_facts(html)[bnum(b)]
    out = ''
    if 'about' in pf:
        out += '      <p class="loc-about">%s</p>\n' % e(pf['about'][lang])
    tags = tag_labels(html, b, lang)
    if tags:
        out += '      <p class="loc-amen">%s</p>\n' % ' · '.join('<span>%s</span>' % e(x) for x in tags)   # перенос только между метками
    return out


def js_str(s):
    """строка внутри '…' в JS: обратная косая и апостроф экранируются (название точки с ' не сломает onclick)"""
    return s.replace('\\', '\\\\').replace("'", "\\'")


def js_attr(s):
    """то же для вставки прямо в атрибут onclick="…": JS-экранирование, потом HTML (& < > ")"""
    return H.escape(js_str(s), quote=False).replace('"', '&quot;')


# Значки кнопок карточки точки (правки владельца 31.10, вторая порция): метка на карте и трубка — Lucide 0.460.0 (ISC),
# WhatsApp — Simple Icons 13.21.0 (CC0); один спрайт на страницу, кнопки ссылаются <use href="#i-…">. Лицензии — docs/LICENSES-media.md
ICONS_MARK = '<!-- значки кнопок (SVG-спрайт: Lucide ISC, Simple Icons CC0) — собирает tools/seo_jsonld.py, руками не править -->'
# Соцсети (правки владельца 31.10, третья порция): ряд круглых значков в блоке «загляните на кофе» на /, /kk/, /en/ и sameAs
# организации в JSON-LD. Событие — как у прежней ссылки на Instagram (cta_instagram) с параметром сети net.
SOCIAL = (('instagram', 'Instagram', 'https://instagram.com/del.cappuccino', 'ig'),
          ('youtube', 'YouTube', 'https://www.youtube.com/@DelCappuccino', 'yt'),
          ('threads', 'Threads', 'https://www.threads.com/@del.cappuccino', 'th'))
SOCIAL_MARK = '<!-- соцсети: значки (Simple Icons CC0) — собирает tools/seo_jsonld.py из SOCIAL, руками не править -->'
SOCIAL_RE = re.compile(re.escape(SOCIAL_MARK) + r'\n.*?<!-- /соцсети -->\n', re.S)
ICONS_RE = re.compile(re.escape(ICONS_MARK) + r'\n.*?<!-- /значки -->\n', re.S)
IG_D = 'M7.0301.084c-1.2768.0602-2.1487.264-2.911.5634-.7888.3075-1.4575.72-2.1228 1.3877-.6652.6677-1.075 1.3368-1.3802 2.127-.2954.7638-.4956 1.6365-.552 2.914-.0564 1.2775-.0689 1.6882-.0626 4.947.0062 3.2586.0206 3.6671.0825 4.9473.061 1.2765.264 2.1482.5635 2.9107.308.7889.72 1.4573 1.388 2.1228.6679.6655 1.3365 1.0743 2.1285 1.38.7632.295 1.6361.4961 2.9134.552 1.2773.056 1.6884.069 4.9462.0627 3.2578-.0062 3.668-.0207 4.9478-.0814 1.28-.0607 2.147-.2652 2.9098-.5633.7889-.3086 1.4578-.72 2.1228-1.3881.665-.6682 1.0745-1.3378 1.3795-2.1284.2957-.7632.4966-1.636.552-2.9124.056-1.2809.0692-1.6898.063-4.948-.0063-3.2583-.021-3.6668-.0817-4.9465-.0607-1.2797-.264-2.1487-.5633-2.9117-.3084-.7889-.72-1.4568-1.3876-2.1228C21.2982 1.33 20.628.9208 19.8378.6165 19.074.321 18.2017.1197 16.9244.0645 15.6471.0093 15.236-.005 11.977.0014 8.718.0076 8.31.0215 7.0301.0839m.1402 21.6932c-1.17-.0509-1.8053-.2453-2.2287-.408-.5606-.216-.96-.4771-1.3819-.895-.422-.4178-.6811-.8186-.9-1.378-.1644-.4234-.3624-1.058-.4171-2.228-.0595-1.2645-.072-1.6442-.079-4.848-.007-3.2037.0053-3.583.0607-4.848.05-1.169.2456-1.805.408-2.2282.216-.5613.4762-.96.895-1.3816.4188-.4217.8184-.6814 1.3783-.9003.423-.1651 1.0575-.3614 2.227-.4171 1.2655-.06 1.6447-.072 4.848-.079 3.2033-.007 3.5835.005 4.8495.0608 1.169.0508 1.8053.2445 2.228.408.5608.216.96.4754 1.3816.895.4217.4194.6816.8176.9005 1.3787.1653.4217.3617 1.056.4169 2.2263.0602 1.2655.0739 1.645.0796 4.848.0058 3.203-.0055 3.5834-.061 4.848-.051 1.17-.245 1.8055-.408 2.2294-.216.5604-.4763.96-.8954 1.3814-.419.4215-.8181.6811-1.3783.9-.4224.1649-1.0577.3617-2.2262.4174-1.2656.0595-1.6448.072-4.8493.079-3.2045.007-3.5825-.006-4.848-.0608M16.953 5.5864A1.44 1.44 0 1 0 18.39 4.144a1.44 1.44 0 0 0-1.437 1.4424M5.8385 12.012c.0067 3.4032 2.7706 6.1557 6.173 6.1493 3.4026-.0065 6.157-2.7701 6.1506-6.1733-.0065-3.4032-2.771-6.1565-6.174-6.1498-3.403.0067-6.156 2.771-6.1496 6.1738M8 12.0077a4 4 0 1 1 4.008 3.9921A3.9996 3.9996 0 0 1 8 12.0077'
YT_D = 'M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z'
TH_D = 'M12.186 24h-.007c-3.581-.024-6.334-1.205-8.184-3.509C2.35 18.44 1.5 15.586 1.472 12.01v-.017c.03-3.579.879-6.43 2.525-8.482C5.845 1.205 8.6.024 12.18 0h.014c2.746.02 5.043.725 6.826 2.098 1.677 1.29 2.858 3.13 3.509 5.467l-2.04.569c-1.104-3.96-3.898-5.984-8.304-6.015-2.91.022-5.11.936-6.54 2.717C4.307 6.504 3.616 8.914 3.589 12c.027 3.086.718 5.496 2.057 7.164 1.43 1.783 3.631 2.698 6.54 2.717 2.623-.02 4.358-.631 5.8-2.045 1.647-1.613 1.618-3.593 1.09-4.798-.31-.71-.873-1.3-1.634-1.75-.192 1.352-.622 2.446-1.284 3.272-.886 1.102-2.14 1.704-3.73 1.79-1.202.065-2.361-.218-3.259-.801-1.063-.689-1.685-1.74-1.752-2.964-.065-1.19.408-2.285 1.33-3.082.88-.76 2.119-1.207 3.583-1.291a13.853 13.853 0 0 1 3.02.142c-.126-.742-.375-1.332-.75-1.757-.513-.586-1.308-.883-2.359-.89h-.029c-.844 0-1.992.232-2.721 1.32L7.734 7.847c.98-1.454 2.568-2.256 4.478-2.256h.044c3.194.02 5.097 1.975 5.287 5.388.108.046.216.094.321.142 1.49.7 2.58 1.761 3.154 3.07.797 1.82.871 4.79-1.548 7.158-1.85 1.81-4.094 2.628-7.277 2.65Zm1.003-11.69c-.242 0-.487.007-.739.021-1.836.103-2.98.946-2.916 2.143.067 1.256 1.452 1.839 2.784 1.767 1.224-.065 2.818-.543 3.086-3.71a10.5 10.5 0 0 0-2.215-.221z'
_LUCIDE = ' viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"'
ICONS = ('<svg class="icons" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false">'
         '<symbol id="i-pin"%s><path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"/>'
         '<circle cx="12" cy="10" r="3"/></symbol>'
         '<symbol id="i-phone"%s><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 '
         '4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 '
         '2.81.7A2 2 0 0 1 22 16.92z"/></symbol>'
         '<symbol id="i-wa" viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 '
         '1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 '
         '0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 '
         '1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 '
         '9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 '
         '11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 '
         '11.821 0 00-3.48-8.413Z"/></symbol>'
         # Instagram, YouTube, Threads — Simple Icons 13.21.0 (CC0), ряд соцсетей в блоке «загляните на кофе»
         '<symbol id="i-ig" viewBox="0 0 24 24" fill="currentColor"><path d="%s"/></symbol>'
         '<symbol id="i-yt" viewBox="0 0 24 24" fill="currentColor"><path d="%s"/></symbol>'
         '<symbol id="i-th" viewBox="0 0 24 24" fill="currentColor"><path d="%s"/></symbol></svg>') % (_LUCIDE, _LUCIDE, IG_D, YT_D, TH_D)
# значки карточек «Место для ваших планов» — свой набор (tools/feature_icons.py), в тот же спрайт
ICONS = ICONS.replace('</svg>', feature_icons.symbols() + '</svg>')
# «три полоски» для плавающей кнопки «меню» на телефоне (свой, три линии)
ICONS = ICONS.replace('</svg>', '<symbol id="i-menu"%s><path d="M4 7h16M4 12h16M4 17h16"/></symbol></svg>' % _LUCIDE)
# лупа (поиск по меню) и «фото» (у блюда есть карточка с фото) — свои, линиями
ICONS = ICONS.replace('</svg>', '<symbol id="i-search"%s><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5 20 20"/></symbol>'
                      '<symbol id="i-photo"%s><rect x="3" y="5.5" width="18" height="14" rx="3"/><circle cx="12" cy="12.5" r="3.5"/>'
                      '<path d="M8.5 5.5 10 3.5h4l1.5 2"/></symbol></svg>' % (_LUCIDE, _LUCIDE))


def icon_link(cls, href, label, onclick, icon, blank=True):
    """круглая кнопка-значок карточки точки: aria-label и title на языке страницы, значок — <use> из спрайта ICONS"""
    a = lambda x: H.escape(x, quote=False).replace('"', '&quot;')
    return ('<a class="%s" href="%s"%s%s aria-label="%s" title="%s"><svg class="ic" aria-hidden="true" focusable="false"><use href="#i-%s"/></svg></a>'
            % (cls, a(href), ' target="_blank" rel="noopener"' if blank else '', onclick, a(label), a(label), icon))


def feature_icon(i):
    """значок i-й карточки «Формата» (порядок — как карточки: 24/7, завтраки, детская, VIP, банкеты, намазхана)"""
    return '<svg class="f-ic" aria-hidden="true" focusable="false"><use href="#%s"/></svg>' % feature_icons.FEATURE_IDS[i]


def social_row():
    """ряд круглых значков соцсетей: aria-label и title — название сети, новая вкладка, событие cta_instagram {net}"""
    return ('  <div class="social">\n' + '\n'.join(
        '    ' + icon_link('ib so', url, name, ' onclick="track(\'cta_instagram\',{net:\'%s\'})"' % key, ic) for key, name, url, ic in SOCIAL)
            + '\n  </div>\n')


def with_social(html):
    m = SOCIAL_RE.search(html)
    if not m:
        sys.exit('seo_jsonld: в блоке «загляните на кофе» нет маркеров «%s … <!-- /соцсети -->»' % SOCIAL_MARK[:40])
    return html[:m.start()] + SOCIAL_MARK + '\n' + social_row() + '<!-- /соцсети -->\n' + html[m.end():]


def with_icons(html):
    m = ICONS_RE.search(html)
    if not m:
        sys.exit('seo_jsonld: на главной нет маркеров спрайта значков «%s … <!-- /значки -->»' % ICONS_MARK[:40])
    return html[:m.start()] + ICONS_MARK + '\n' + ICONS + '\n<!-- /значки -->\n' + html[m.end():]


LOC_MARK = '<!-- Точки: из BRANCHES собирает tools/seo_jsonld.py — видны без JS поисковикам и ИИ, руками не править -->'
LOC_RE = re.compile(re.escape(LOC_MARK) + r'\n.*?<!-- /точки -->\n', re.S)


def wa_link(html, b):
    """как branchWa/waLink на странице: wa.me/<цифры телефона>?text=<encodeURIComponent(b.wa || текст по умолчанию + адрес)>"""
    m = re.search(r"function branchWa\(b\)\{return waLink\(b\.phone,\(b\.wa\|\|'((?:[^'\\]|\\.)*)'\)\+b\.addr\)\}", html)
    if not m:
        sys.exit('seo_jsonld: branchWa на странице записан иначе — обновите wa_link, чтобы ссылки WhatsApp в карточках совпадали с модалкой')
    default = unq(m.group(1))
    return 'https://wa.me/%s?text=%s' % (re.sub(r'\D', '', b['phone']), quote((b['wa'] or default) + b['addr'], safe="-_.!~*'()"))


def loc_meta(hours, note):
    """строка часов карточки — только у точек не 24/7 (владелец 31.10: «24/7» в каждой карточке не нужно — это сказано
    в шапке, hero и «Формате»); у bakery — «ежедневно 07:00–22:00 · описание»"""
    if hours == '24/7':
        return ''
    return '      <p class="loc-meta"><b>%s</b>%s</p>\n' % (hours, ' · ' + note if note else '')


def loc_cards(html):
    """карточки точек: название (без номера — номер нужен только данным), адрес, часы, удобства; кнопки-значки — маршрут
    (главная, forest), звонок, WhatsApp; у bakery ещё текстовая пилюля «Меню»"""
    a = lambda s: H.escape(s, quote=False).replace('"', '&quot;')     # атрибут в "…": одинарные кавычки onclick оставляем как есть
    t = lambda s: H.escape(s, quote=False)
    out = []
    for b in branches(html):
        n = js_str(b['n'])
        ev = lambda name: ' onclick="%s"' % a("track('%s',{branch:'%s'})" % (name, n))
        links = [icon_link('ib route', b['route'], 'Маршрут', ev('loc_route'), 'pin'),
                 icon_link('ib', 'tel:' + b['phone'], 'Позвонить', ev('loc_call'), 'phone', blank=False),
                 icon_link('ib wa', wa_link(html, b), 'WhatsApp', ev('loc_wa'), 'wa')]
        if b['menu']:
            links.append('<a class="pill" href="#" onclick="%s">Меню</a>' % a("event.preventDefault();track('loc_menu',{branch:'%s'});openMenu('%s')" % (n, b['menu'])))
        out.append('    <div class="loc-card">\n      <small>%s</small>\n      <h3>%s</h3>\n'
                   '%s%s      <div class="loc-links">\n        %s\n      </div>\n    </div>'
                   % (t(short(b)), t(b['addr']), loc_meta(t(b['hours']), t(b['note']) if b['note'] else ''), card_extra(html, b, 'ru'),
                      '\n        '.join(links)))
    return LOC_MARK + '\n' + '\n'.join(out) + '\n<!-- /точки -->\n'


def with_loc(html):
    m = LOC_RE.search(html)
    if not m:
        sys.exit('seo_jsonld: в #loc-grid нет маркеров «%s … <!-- /точки -->»' % LOC_MARK)
    return html[:m.start()] + loc_cards(html) + html[m.end():]


# ── Плитка подписки в блоке «акции»: видео, где наливают кофе (решение владельца 1.11.2026 — вместо анимации-чашки) ──
# Видео — Mixkit «Latte art» (https://mixkit.co/free-stock-video/latte-art-810/), Mixkit Stock Video Free License
# (бесплатно, коммерция разрешена, атрибуция не нужна); клип собирает tools/build_sub_video.py из исходника вне репозитория:
# весь налив 0–31 с ×2, петля с перетеканием конца в начало, 960×654 под плитку, webm VP9 + mp4 H.264, постер webp.
# Грузится и играет, только когда плитка на экране (IntersectionObserver, после load), вне экрана — пауза; без JS и при
# reduced-motion — постер; в preload и PRECACHE sw.js видео нет (sw.js пропускает mp4/webm). Лицензии — docs/LICENSES-media.md.
# Подписи — tools/pages_i18n.json (раздел sub у ru/kk/en).

# Мобильное приложение: ссылок на сторы пока нет (аккаунты ждут D-U-N-S, выпуск — примерно середина ноября 2026).
# Появятся — вписать сюда (одна правка) и пересобрать: вместо «скоро, в приложении» встанут ссылки, событие app_store {store}.
APP_LINKS = {'App Store': None, 'Google Play': None}
SUB_VIDEO = {'webm': '/assets/latte-pour.0aa34e2d.webm', 'mp4': '/assets/latte-pour.eaff9eed.mp4',
             'poster': '/assets/latte-pour-poster.eace987c.webp', 'w': 960, 'h': 654}
SUB_MARK = '<!-- Плитка подписки (видео налива кофе) — собирает tools/seo_jsonld.py, руками не править -->'
SUB_RE = re.compile(re.escape(SUB_MARK) + r'\n.*?<!-- /подписка -->\n', re.S)
# загрузчик видео: после load, по IntersectionObserver — play, вне экрана — pause; reduced-motion или нет IO — постер
SUB_JS = ("<script>(function(){var v=document.querySelector('.sub-video');if(!v||!('IntersectionObserver'in window))return;"
          "try{if(matchMedia('(prefers-reduced-motion: reduce)').matches)return}catch(e){return;}v.muted=true;"
          "function play(){var p=v.play();if(p&&p.catch)p.catch(function(){})}"
          "function start(){new IntersectionObserver(function(es){es[es.length-1].isIntersecting?play():v.pause()},{threshold:.25}).observe(v)}"
          "if(document.readyState==='complete')start();else addEventListener('load',start)})();</script>")


def sub_card(lang):
    """плитка «кофейная подписка — скоро, в приложении» с видео (постер без JS) и загрузчиком"""
    S = i18n()[lang]['sub']
    e = lambda x: H.escape(x, quote=False)
    links = [(n, u) for n, u in APP_LINKS.items() if u]
    line = ('<span class="promo-s">%s</span>' % e(S['soon']) if not links else
            '<span class="promo-s">%s</span> <span class="promo-a">%s</span>' % (e(S['now']), ' · '.join(
                '<a href="%s" target="_blank" rel="noopener" onclick="track(\'app_store\',{store:\'%s\'})">%s</a>' % (H.escape(u), js_str(n), e(n))
                for n, u in links)))
    V = SUB_VIDEO
    # плитка пары к огненной рамке «Курицы гриль»: та же форма 910×620, видео во всю плитку, подпись внизу на затемнении
    return ('    <div class="promo-tile sub-tile">\n'
            '      <!-- видео: Mixkit «Latte art» (https://mixkit.co/free-stock-video/latte-art-810/), Mixkit Stock Video Free License; '
            'клип — tools/build_sub_video.py; docs/LICENSES-media.md -->\n'
            '      <video class="sub-video" poster="%s" width="%d" height="%d" muted loop playsinline preload="none" tabindex="-1" aria-hidden="true">\n'
            '        <source src="%s" type="video/webm">\n        <source src="%s" type="video/mp4">\n      </video>\n'
            '      <p class="tile-cap"><b class="promo-t">%s</b> %s</p>\n    </div>\n%s\n'
            % (V['poster'], V['w'], V['h'], V['webm'], V['mp4'], e(S['title']), line, SUB_JS))


def with_sub(html):
    m = SUB_RE.search(html)
    if not m:
        sys.exit('seo_jsonld: в блоке «акция» главной нет маркеров «%s … <!-- /подписка -->»' % SUB_MARK[:40])
    return html[:m.start()] + SUB_MARK + '\n' + sub_card('ru') + '<!-- /подписка -->\n' + html[m.end():]


def with_jsonld(html):
    new = block(html)
    m = BLOCK_RE.search(html)
    return html[:m.start()] + new + html[m.end():] if m else html.replace('</head>', new + '</head>', 1)


def outputs(html):
    """{путь: ожидаемый текст} — всё, что собирает генератор"""
    page = with_analytics(with_hreflang(with_jsonld(with_loc(with_social(with_icons(with_sub(with_faq(html))))))))
    out = {INDEX: page, LLMS: llms(page), KK_REVIEW: kk_review(page), UGOLOK: with_analytics(read(UGOLOK), track_links=False),
           NOT_FOUND: with_analytics(read(NOT_FOUND), on_load=NOT_FOUND_JS)}
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
