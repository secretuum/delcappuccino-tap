#!/usr/bin/env python3
"""Пересобирает разметку schema.org (JSON-LD) в <head> index.html из данных самой страницы и lastmod в sitemap.xml.

Запуск из корня репозитория после правки меню (MENU_KITCHEN / MENU_BAR / MENU_DESSERT) или точек (BRANCHES):
    python3 tools/seo_jsonld.py && python3 tools/sw_version.py      # порядок важен: sw_version хэширует index.html
С ключом --check только сравнивает блок с массивами и выходит с кодом 1, если он устарел (tests/test_seo.py).

Что в разметке: организация Del Cappuccino (sameAs — ссылки Instagram со страницы, заказ онлайн — OrderAction),
5 точек из BRANCHES — 01–04 CafeOrCoffeeShop, 05 Bakery; адрес, координаты, телефон и часы — только из BRANCHES
(город и страна — «5 точек в Алматы» из текста сайта). Юрлиц, ИП и имён людей в разметке нет и быть не должно.
Меню кофеен с ценами в тенге — по разделам; у позиции с несколькими ценами — Offer на каждый объём из vol,
если объёмов столько же, сколько цен, иначе AggregateOffer (от и до). В sameAs точки — только ссылка 2GIS на карточку
фирмы (…/firm/<id>); поисковые ссылки 2GIS (…/search/…) — не карточки, их не кладём (главный, 22.10.2026).
lastmod в sitemap.xml: дата последнего коммита страницы, а если в ней есть незакоммиченные правки — сегодня.
Только stdlib.
"""
import datetime, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, 'index.html')
SITEMAP = os.path.join(ROOT, 'sitemap.xml')
SITE = 'https://tap.delcappuccino.kz/'
ORDER_URL = 'https://delcappuccino.kz/'      # заказ онлайн и приложение (Smart Restaurant)
MENU_ARRAYS = ('MENU_KITCHEN', 'MENU_BAR', 'MENU_DESSERT')
DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
MARK = '<!-- schema.org: организация, точки из BRANCHES и меню с ценами — tools/seo_jsonld.py, руками не править -->'
BLOCK_RE = re.compile(re.escape(MARK) + r'\n<script type="application/ld\+json">\n(.*?)\n</script>\n', re.S)
PAGES = {SITE: 'index.html', SITE + 'ugolok': 'ugolok/index.html'}


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


def branches(html):
    out = []
    for m in re.finditer(r"\{n:'(?:[^'\\]|\\.)*'[^\n]*\}", js_array(html, 'BRANCHES')):
        b = m.group(0)
        geo = re.search(r"geo:\[([-\d.]+),\s*([-\d.]+)\]", b)
        out.append({'n': field(b, 'n'), 'addr': field(b, 'addr'), 'phone': field(b, 'phone'), 'hours': field(b, 'hours'),
                    'menu': field(b, 'menu'), 'route': field(b, 'route'),
                    'geo': (float(geo.group(1)), float(geo.group(2))) if geo else None})
    return out


def menu_sections(html):
    """[(раздел, [(название, p, vol)])] из MENU_KITCHEN / MENU_BAR / MENU_DESSERT; p — число или строка «1400/1500»"""
    out = []
    for name in MENU_ARRAYS:
        s = js_array(html, name)
        for m in re.finditer(r"\{t:'((?:[^'\\]|\\.)*)'[^\[\]]*?items:\[", s):
            i, depth, j = m.end(), 1, m.end()
            while depth:
                depth += (s[j] == '[') - (s[j] == ']')
                j += 1
            items = []
            for im in re.finditer(r"\{n:'((?:[^'\\]|\\.)*)'([^{}]*)\}", s[i:j - 1]):
                p = re.search(r"\bp:(?:'([^']*)'|(\d+))", im.group(2))
                items.append((unq(im.group(1)), (p.group(1) or p.group(2)) if p else None, field(im.group(2), 'vol')))
            out.append((unq(m.group(1)), items))
    return out


def offers(p, vol):
    prices = [int(x.strip()) for x in str(p).split('/')]
    if len(prices) == 1:
        return {'@type': 'Offer', 'price': prices[0], 'priceCurrency': 'KZT'}
    sizes = [x.strip() for x in (vol or '').split('/')]
    unit = re.match(r'[\d.,]+\s*(.*)$', sizes[-1]) if len(sizes) == len(prices) else None
    if unit and all(re.fullmatch(r'[\d.,]+', x) for x in sizes[:-1]):
        names = [x + (' ' + unit.group(1) if unit.group(1) else '') for x in sizes[:-1]] + [sizes[-1]]
        return [{'@type': 'Offer', 'name': n, 'price': pr, 'priceCurrency': 'KZT'} for n, pr in zip(names, prices)]
    return {'@type': 'AggregateOffer', 'lowPrice': min(prices), 'highPrice': max(prices), 'offerCount': len(prices),
            'priceCurrency': 'KZT'}


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


def graph(html):
    insta = sorted(set(re.findall(r'href="(https://(?:www\.)?instagram\.com/[^"?#]+)"', html)))
    org = {'@type': 'Organization', '@id': SITE + '#org', 'name': 'Del Cappuccino', 'url': SITE,
           'logo': SITE + 'assets/icon-192.png', 'sameAs': insta,
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
                                      'hasMenuItem': [dict({'@type': 'MenuItem', 'name': n}, **({'offers': offers(p, vol)} if p else {}))
                                                      for n, p, vol in items]}
                                     for t, items in menu_sections(html)]})
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


def lastmod(path):
    """дата последнего коммита файла; есть незакоммиченные правки (или файл не в git) — сегодня"""
    try:
        dirty = subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--', path], cwd=ROOT).returncode != 0
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


def main():
    with open(INDEX, encoding='utf-8') as f:
        html = f.read()
    new = block(html)
    m = BLOCK_RE.search(html)
    if '--check' in sys.argv:
        ok = bool(m) and m.group(0) == new
        print('JSON-LD в index.html:', 'ok' if ok else 'УСТАРЕЛ — запустите python3 tools/seo_jsonld.py')
        sys.exit(0 if ok else 1)
    if m:
        out = html[:m.start()] + new + html[m.end():]
    else:
        out = html.replace('</head>', new + '</head>', 1)
    if out != html:
        with open(INDEX, 'w', encoding='utf-8') as f:
            f.write(out)
        print('index.html: JSON-LD пересобран (%d байт)' % len(new.encode('utf-8')))
    else:
        print('index.html: JSON-LD уже актуален')
    update_sitemap()


if __name__ == '__main__':
    main()
