"""SEO-минимум (22.10.2026): JSON-LD в <head> совпадает с BRANCHES и массивами меню (иначе — python3 tools/seo_jsonld.py),
кнопка «Заказать в приложении» в hero, глубокие ссылки #menu / #menu-togo, canonical и lastmod в sitemap.xml.
Запуск из корня репозитория: python3 -m unittest discover -s tests -v"""
import datetime, json, os, re, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import seo_jsonld as seo  # noqa: E402

SITE = 'https://tap.delcappuccino.kz/'


def read(*p):
    with open(os.path.join(ROOT, *p), encoding='utf-8') as f:
        return f.read()


def ld_text(html):
    m = re.search(r'<script type="application/ld\+json">\n(.*?)\n</script>', html.split('</head>')[0], re.S)
    return m.group(1) if m else None


class TestJsonLd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = read('index.html')
        cls.text = ld_text(cls.html)
        cls.data = json.loads(cls.text) if cls.text else None
        cls.nodes = {n['@id']: n for n in cls.data['@graph']} if cls.data else {}
        # BRANCHES — своим разбором, независимо от генератора
        arr = re.search(r'const BRANCHES = \[(.*?)\n\];', cls.html, re.S).group(1)
        cls.branches = []
        for line in re.findall(r"\{n:'.*\}", arr):
            g = lambda k: (re.search(r"\b%s:'([^']*)'" % k, line) or [None, None])[1]
            geo = re.search(r'geo:\[([-\d.]+),\s*([-\d.]+)\]', line)
            cls.branches.append({'n': g('n'), 'addr': g('addr'), 'phone': g('phone'), 'hours': g('hours'),
                                 'menu': g('menu'), 'route': g('route'), 'geo': [float(geo.group(1)), float(geo.group(2))]})

    def test_valid_json_in_head(self):
        self.assertIsNotNone(self.text, 'нет <script type="application/ld+json"> в <head>')
        self.assertEqual(self.data['@context'], 'https://schema.org')

    def test_up_to_date(self):
        stale = [os.path.relpath(p, ROOT) for p, text in seo.outputs(self.html).items() if seo.read(p) != text]
        self.assertEqual(stale, [], 'JSON-LD / FAQ / menyu / llms.txt разошлись с BRANCHES, меню или tools/faq.json — '
                                    'запустите python3 tools/seo_jsonld.py && python3 tools/sw_version.py')

    def test_price_change_is_caught(self):
        # первая позиция кухни с числовой ценой: +1000 ₸ в массиве → блок устарел, в пересобранном — новая цена
        kitchen = self.html.index('const MENU_KITCHEN = [')
        m = re.compile(r"\{n:'((?:[^'\\]|\\.)*)'[^{}]*?\bp:(\d+)").search(self.html, kitchen)
        name, price = m.group(1), int(m.group(2))
        changed = self.html[:m.start(2)] + str(price + 1000) + self.html[m.end(2):]
        self.assertNotIn(seo.block(changed), changed, 'смена цены в массиве должна делать блок устаревшим')
        self.assertIn('"name":"%s","offers":{"@type":"Offer","price":%d,' % (name, price + 1000), seo.block(changed))
        page = seo.menu_page(changed)
        self.assertNotEqual(page, read('menyu', 'index.html'), 'смена цены должна делать /menyu устаревшей')
        import html as H
        row = next(l for l in page.split('\n') if l.startswith('<li><span class="n">%s' % H.escape(name, quote=False)))
        self.assertIn('<b class="p">%s ₸' % seo.fmt_p(price + 1000), row)

    def test_five_branches_from_BRANCHES(self):
        self.assertEqual(len(self.branches), 5)
        for b in self.branches:
            num = b['n'][:2]
            node = self.nodes.get(SITE + '#branch-' + num)
            self.assertIsNotNone(node, num)
            self.assertEqual(node['@type'], 'Bakery' if b['menu'] == 'togo' else 'CafeOrCoffeeShop', num)
            self.assertEqual(node['address']['streetAddress'], b['addr'], num)
            self.assertEqual(node['telephone'], b['phone'], num)
            self.assertEqual([node['geo']['latitude'], node['geo']['longitude']], b['geo'], num)
            h = node['openingHoursSpecification']
            self.assertEqual(len(h['dayOfWeek']), 7, num)
            want = ('00:00', '23:59') if b['hours'] == '24/7' else re.search(r'(\d\d:\d\d)–(\d\d:\d\d)', b['hours']).groups()
            self.assertEqual((h['opens'], h['closes']), want, num)
            self.assertEqual(node['parentOrganization'], {'@id': SITE + '#org'}, num)
        self.assertEqual(sorted(n['@type'] for n in self.data['@graph'] if n['@type'] in ('Bakery', 'CafeOrCoffeeShop')),
                         ['Bakery'] + ['CafeOrCoffeeShop'] * 4)

    def test_no_legal_entities_or_people(self):
        for key in ('legalName', 'taxID', 'vatID', 'founder', 'employee', 'member', 'contactPoint', 'email'):
            self.assertNotIn('"%s"' % key, self.text, key)
        for word in ('ИП ', 'ТОО', 'ИИН', 'БИН'):
            self.assertNotIn(word, self.text, word)

    def test_same_as(self):
        org = self.nodes[SITE + '#org']
        self.assertTrue(org['sameAs'] and all(re.match(r'https://(www\.)?instagram\.com/', u) for u in org['sameAs']))
        for u in org['sameAs']:
            self.assertIn('href="%s"' % u, self.html, 'sameAs только со страницы')
        self.assertNotIn('2gis.kz/almaty/search', self.text, 'поисковые ссылки 2GIS — не sameAs')
        for b in self.branches:
            node = self.nodes[SITE + '#branch-' + b['n'][:2]]
            if '/firm/' in (b['route'] or ''):
                self.assertEqual(node.get('sameAs'), [b['route']])
            else:
                self.assertNotIn('sameAs', node)

    def test_order_and_menu_links(self):
        self.assertEqual(self.nodes[SITE + '#org']['potentialAction'], {'@type': 'OrderAction', 'target': 'https://delcappuccino.kz/'})
        menu = self.nodes[SITE + '#menu']
        self.assertEqual((menu['@type'], menu['url']), ('Menu', SITE + '#menu'))
        for b in self.branches:
            node = self.nodes[SITE + '#branch-' + b['n'][:2]]
            self.assertEqual(node['hasMenu'], SITE + '#menu-togo' if b['menu'] == 'togo' else {'@id': SITE + '#menu'})

    def test_menu_matches_arrays(self):
        # своим разбором массивов: (название, цены, точки only) по порядку — против того, что в разметке
        want = []
        for name in ('MENU_KITCHEN', 'MENU_BAR', 'MENU_DESSERT'):
            arr = re.search(r'const %s = \[(.*?)\n\];' % name, self.html, re.S).group(1)
            for m in re.finditer(r"\{n:'((?:[^'\\]|\\.)*)'([^{}]*)\}", arr):
                p = re.search(r"\bp:(?:'([^']*)'|(\d+))", m.group(2))
                only = re.search(r"\bonly:\[([^\]]*)\]", m.group(2))
                want.append((m.group(1).replace("\\'", "'"), sorted(int(x) for x in (p.group(1) or p.group(2)).split('/')),
                             sorted(re.findall(r"'(\d+)'", only.group(1))) if only else []))
        got = []
        for s in self.nodes[SITE + '#menu']['hasMenuSection']:
            for it in s['hasMenuItem']:
                offs = it['offers'] if isinstance(it['offers'], list) else [it['offers']]
                prices = sorted(x for o in offs for x in ((o['lowPrice'], o['highPrice']) if o['@type'] == 'AggregateOffer' else (o['price'],)))
                at = sorted({a['@id'].rsplit('-', 1)[1] for o in offs for a in o.get('availableAtOrFrom', [])})
                for o in offs:
                    self.assertEqual(o['priceCurrency'], 'KZT', it['name'])
                got.append((it['name'], prices, at))
        self.assertEqual(len(got), len(want), 'число позиций в разметке и в массивах')
        # у AggregateOffer в разметке только «от и до» — сверяем с крайними ценами массива
        want = [(n, ps if len(ps) <= 2 or len(ps) == len(g[1]) else [ps[0], ps[-1]], at) for (n, ps, at), g in zip(want, got)]
        self.assertEqual(got, want)
        self.assertTrue(any(at for _, _, at in got), 'нет ни одной позиции «только в …» — проверка availableAtOrFrom пустая')


class TestPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = read('index.html')

    def test_order_button_in_hero(self):
        actions = re.search(r'<div class="actions">(.*?)</div>', self.html, re.S).group(1)
        btn = re.search(r'<a [^>]*>Заказать в приложении</a>', actions)
        self.assertIsNotNone(btn, 'нет кнопки «Заказать в приложении» в .actions')
        tag = btn.group(0)
        for attr in ('href="https://delcappuccino.kz/"', 'target="_blank"', 'rel="noopener"', "onclick=\"track('cta_order')\""):
            self.assertIn(attr, tag)
        self.assertRegex(tag, r'class="btn"')
        self.assertNotIn('hide-mobile', tag)

    def test_city_in_titles_and_tag(self):
        # согласовано владельцем 22.10: «в Алматы» в title/og/twitter и в p.tag над H1; H1 и lead не меняются
        title = 'Del Cappuccino — кофейни 24/7 в Алматы и bakery to go'
        self.assertIn('<title>%s</title>' % title, self.html)
        self.assertIn('<meta property="og:title" content="%s">' % title, self.html)
        self.assertIn('<meta name="twitter:title" content="%s">' % title, self.html)
        self.assertIn('<p class="tag">кофейни в Алматы · coffee &amp; food</p>\n      <h1>', self.html)

    def test_menu_deep_link(self):
        f = re.search(r'function menuFromHash\(\)\{(.*?)\n\}', self.html, re.S)
        self.assertIsNotNone(f)
        self.assertIn("location.hash==='#menu')openMenu()", f.group(1))
        self.assertIn("location.hash==='#menu-togo')openMenu('togo')", f.group(1))
        self.assertIn("menuFromHash(); addEventListener('hashchange',menuFromHash);", self.html)

    def test_canonical_and_sitemap(self):
        canon = {}
        for path in ('index.html', 'ugolok/index.html', 'menyu/index.html'):
            links = re.findall(r'<link rel="canonical" href="([^"]+)">', read(path).split('</head>')[0])
            self.assertEqual(len(links), 1, path)
            canon[path] = links[0]
        self.assertEqual(canon, {'index.html': SITE, 'ugolok/index.html': SITE + 'ugolok', 'menyu/index.html': SITE + 'menyu'})
        sm = read('sitemap.xml')
        urls = re.findall(r'<url>(.*?)</url>', sm, re.S)
        self.assertEqual(sorted(re.search(r'<loc>([^<]*)</loc>', u).group(1) for u in urls), sorted(canon.values()))
        for u in urls:
            d = re.search(r'<lastmod>(\d{4}-\d\d-\d\d)</lastmod>', u)
            self.assertIsNotNone(d, u)
            # +1 день: дата коммита в поясе Алматы (+05), машина может жить в UTC
            self.assertLessEqual(datetime.date.fromisoformat(d.group(1)), datetime.date.today() + datetime.timedelta(days=1))


def menu_arrays(html):
    """{массив: [(название, цена-строка|None, old|None)]} — своим разбором, для сверки со страницей /menyu"""
    out = {}
    for name in re.findall(r'const ((?:MENU|TOGO)_[A-Z]+) = \[\n \{t:', html):
        arr = re.search(r'const %s = \[(.*?)\n\];' % name, html, re.S).group(1)
        out[name] = []
        for m in re.finditer(r"\{n:'((?:[^'\\]|\\.)*)'([^{}]*)\}", arr):
            p = re.search(r"\bp:(?:'([^']*)'|(\d+))", m.group(2))
            old = re.search(r"\bold:(\d+)", m.group(2))
            out[name].append((m.group(1).replace("\\'", "'"), (p.group(1) or p.group(2)) if p else None, old.group(1) if old else None))
    return out


class TestFaq(unittest.TestCase):
    """Видимый раздел «Частые вопросы» (<details> без JS) и FAQPage в JSON-LD — один и тот же текст из tools/faq.json"""

    @classmethod
    def setUpClass(cls):
        cls.html = read('index.html')
        cls.body = cls.html.split('</head>')[1]
        cls.shown = re.findall(r'<details><summary>(.*?)</summary><div class="faq-a">(.*?)</div></details>', cls.body)
        data = json.loads(ld_text(cls.html))
        cls.ld = next(n for n in data['@graph'] if n['@type'] == 'FAQPage')

    def test_section_visible_without_js(self):
        sec = re.search(r'<section class="faq" id="faq">(.*?)</section>', self.body, re.S)
        self.assertIsNotNone(sec, 'нет <section id="faq"> в разметке страницы')
        self.assertLess(self.body.index('id="faq"'), self.body.index('id="contacts"'))
        self.assertEqual(len(self.shown), len(json.loads(read('tools', 'faq.json'))))
        self.assertNotIn('<script', sec.group(1))

    def test_faq_equals_jsonld(self):
        import html as H
        self.assertEqual([(H.unescape(q), H.unescape(a)) for q, a in self.shown],
                         [(e['name'], e['acceptedAnswer']['text']) for e in self.ld['mainEntity']])

    def test_answers_from_branches(self):
        text = ' '.join(a for _, a in self.shown)
        self.assertNotRegex(text, r'\{\w+\}', 'неподставленная переменная в ответе')
        for addr in re.findall(r"addr:'([^']*)'", re.search(r'const BRANCHES = \[(.*?)\n\];', self.html, re.S).group(1)):
            self.assertIn(addr, text)
        for hours in re.findall(r"hours:'([^']*)'", self.html):
            self.assertIn(re.sub(r'^ежедневно ', '', hours), text)
        for fact in ('КМДБ', 'весь день', 'Детские комнаты', 'VIP-залы', 'намазхана',
                     'https://delcappuccino.kz/', 'ҚАЗ'):
            self.assertIn(fact, text)

    def test_kids_rooms_where_site_says(self):
        # на сайте: «Детские комнаты — Игровые пространства в ЖК Вавилон и ЖК Комфорт Сити» — в FAQ и llms.txt так же
        places = re.search(r'<h3>Детские комнаты</h3><p>Игровые пространства в ([^<]+?)\.</p>', self.html).group(1)
        answer = next(a for q, a in self.shown if 'детская комната' in q)
        self.assertIn('игровые пространства в %s' % places, answer)
        llms = read('llms.txt')
        en = dict(re.findall(r"'([^']*)':'([^']*)'", self.html[self.html.index('\n en:{'):]))
        for p in re.split(r',\s*|\s+и\s+', places):
            self.assertIn(p, llms.split('## English')[0])
            self.assertIn(en[p], llms.split('## English')[1])

    def test_visible_link_to_menu_page(self):
        head = re.search(r'<div class="faq-head">(.*?)</div>\s*<div class="faq-list">', self.body, re.S).group(1)
        self.assertIn('<a href="/menyu">', head, 'ссылка на /menyu должна быть видна без раскрытия вопросов')


class TestMenuPage(unittest.TestCase):
    """/menyu — всё меню текстом из массивов главной (кофейни + Bakery to go)"""

    @classmethod
    def setUpClass(cls):
        cls.html = read('index.html')
        cls.page = read('menyu', 'index.html')
        cls.rows = re.findall(r'<li><span class="n">(.*?)</span>(?:<b class="p">(.*?)</b>)?</li>', cls.page)

    def test_head(self):
        self.assertTrue(self.page.startswith('<!DOCTYPE html>\n<html lang="ru">'))
        head = self.page.split('</head>')[0]
        for tag in ('<meta charset="UTF-8">', 'name="viewport"', '<title>', 'name="description"'):
            self.assertIn(tag, head)
        # JS только аналитика (как на /ugolok, тот же ID, что на главной); меню — текстом, без скриптов
        scripts = re.findall(r'<script>(.*?)</script>', self.page, re.S)
        self.assertEqual(len(scripts), 2)
        self.assertEqual(len(re.findall(r'<script\b', self.page)), 2, 'других скриптов на /menyu нет')
        ga = re.search(r"gtag\('config','(G-[A-Z0-9]+)'\)", self.html.split('</head>')[0]).group(1)
        self.assertIn("gtag('config','%s')" % ga, scripts[0])
        self.assertIn('googletagmanager.com/gtag/js?id=%s' % ga, scripts[1])
        self.assertIn("addEventListener('load'", scripts[1])
        self.assertNotRegex(self.page, r'(src|href)="(?!/|https://|#)', 'пути только от корня: /menyu отдаётся без слэша')

    def test_all_items_with_prices(self):
        import html as H
        arrays = menu_arrays(self.html)
        # порядок — как вкладки на главной: MENU_TABS, затем вкладки режима togo
        order = [a for block in (re.search(r'const MENU_TABS = \{([^}]*)\}', self.html).group(1),
                                 re.search(r'togo:\{tabs:\{([^}]*)\}', self.html).group(1))
                 for a in re.findall(r'\w+:(\w+)', block)]
        self.assertEqual(sorted(arrays), sorted(order), 'на /menyu — все массивы меню обоих режимов')
        want = [it for name in order for it in arrays[name]]
        self.assertEqual(len(self.rows), len(want), 'число позиций на /menyu и в массивах')
        for (n, p, old), (cell, price) in zip(want, self.rows):
            self.assertTrue(H.unescape(cell).startswith(n), n)
            if p is None:
                self.assertEqual(price, '', n)
                continue
            digits = re.sub(r'\D', ' ', price.replace('\u00a0', '')).split()
            self.assertEqual(digits, [x.strip() for x in p.split('/')] + ([old] if old else []), n)
            if old:
                self.assertIn('вместо <s>', price, n)

    def test_only_and_sections(self):
        import html as H
        only = re.search(r"\{n:'((?:[^'\\]|\\.)*)'[^{}]*\bonly:\['(\d+)'", self.html)
        self.assertIsNotNone(only, 'в меню нет позиции с only — проверка «только: …» пустая')
        addr = re.search(r"\{n:'%s · [^\n]*addr:'([^']*)'" % only.group(2), self.html).group(1)
        row = next(c for c, _ in self.rows if H.unescape(c).startswith(only.group(1).replace("\\'", "'")))
        self.assertIn('только:', row)
        self.assertIn(addr, row)
        self.assertIn('<h2 id="togo">', self.page)
        self.assertIn('Сервисный сбор 10%', self.page)


class TestRootFiles(unittest.TestCase):
    def test_llms_txt(self):
        txt = read('llms.txt')
        self.assertTrue(txt.startswith('# Del Cappuccino\n\n> '))
        self.assertIn('\n## English\n', txt)
        for addr in re.findall(r"addr:'([^']*)'", re.search(r'const BRANCHES = \[(.*?)\n\];', read('index.html'), re.S).group(1)):
            self.assertIn(addr, txt)
        for url in (SITE, SITE + 'menyu', 'https://delcappuccino.kz/', 'https://instagram.com/'):
            self.assertIn('](' + url, txt)

    def test_robots_allows_ai_bots(self):
        robots = read('robots.txt')
        self.assertNotIn('Disallow', robots)
        groups = [g for g in re.split(r'\n\s*\n', robots) if 'User-agent' in g]
        agents = {}
        for g in groups:
            allow = re.findall(r'^Allow: (\S+)', g, re.M)
            for a in re.findall(r'^User-agent: (\S+)', g, re.M):
                agents[a] = allow
        for bot in ('*', 'GPTBot', 'OAI-SearchBot', 'ChatGPT-User', 'PerplexityBot', 'ClaudeBot', 'Claude-SearchBot',
                    'Google-Extended', 'Applebot-Extended', 'YandexBot', 'Bingbot'):
            self.assertEqual(agents.get(bot), ['/'], bot)
        self.assertIn('Sitemap: %ssitemap.xml' % SITE, robots)

    def test_indexnow_key_and_payload(self):
        import indexnow  # без сети: только сборка запроса
        keys = [f for f in os.listdir(ROOT) if re.fullmatch(r'[0-9a-f]{32}\.txt', f)]
        self.assertEqual(len(keys), 1)
        self.assertEqual(read(keys[0]).strip(), keys[0][:-4])
        body = indexnow.payload()
        self.assertEqual(body['host'], 'tap.delcappuccino.kz')
        self.assertEqual(body['keyLocation'], SITE + keys[0])
        self.assertEqual(body['urlList'], re.findall(r'<loc>([^<]+)</loc>', read('sitemap.xml')))


if __name__ == '__main__':
    unittest.main()
