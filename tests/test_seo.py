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
            geo = re.search(r'geo:\[([-\d.]+),([-\d.]+)\]', line)
            cls.branches.append({'n': g('n'), 'addr': g('addr'), 'phone': g('phone'), 'hours': g('hours'),
                                 'menu': g('menu'), 'route': g('route'), 'geo': [float(geo.group(1)), float(geo.group(2))]})

    def test_valid_json_in_head(self):
        self.assertIsNotNone(self.text, 'нет <script type="application/ld+json"> в <head>')
        self.assertEqual(self.data['@context'], 'https://schema.org')

    def test_up_to_date(self):
        self.assertIn(seo.block(self.html), self.html,
                      'JSON-LD разошёлся с BRANCHES/меню — запустите python3 tools/seo_jsonld.py && python3 tools/sw_version.py')

    def test_price_change_is_caught(self):
        changed = self.html.replace("{n:'Курица гриль', p:3990,", "{n:'Курица гриль', p:4990,", 1)
        self.assertNotEqual(changed, self.html)
        self.assertNotIn(seo.block(changed), changed)
        self.assertIn('"name":"Курица гриль","offers":{"@type":"Offer","price":4990', seo.block(changed))

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
        items = {it['name']: it for s in self.nodes[SITE + '#menu']['hasMenuSection'] for it in s['hasMenuItem']}
        total = sum(len(s['hasMenuItem']) for s in self.nodes[SITE + '#menu']['hasMenuSection'])
        want = 0
        for name in ('MENU_KITCHEN', 'MENU_BAR', 'MENU_DESSERT'):
            arr = re.search(r'const %s = \[(.*?)\n\];' % name, self.html, re.S).group(1)
            want += len(re.findall(r"\{n:'", arr))
        self.assertEqual(total, want)
        self.assertEqual(items['Курица гриль']['offers'], {'@type': 'Offer', 'price': 3990, 'priceCurrency': 'KZT'})
        self.assertEqual([(o['name'], o['price']) for o in items['Капучино']['offers']],
                         [('200 мл', 1400), ('300 мл', 1500), ('400 мл', 1700)])
        for it in items.values():
            for o in (it['offers'] if isinstance(it['offers'], list) else [it['offers']]):
                self.assertEqual(o['priceCurrency'], 'KZT', it['name'])


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
        for path in ('index.html', 'ugolok/index.html'):
            links = re.findall(r'<link rel="canonical" href="([^"]+)">', read(path).split('</head>')[0])
            self.assertEqual(len(links), 1, path)
            canon[path] = links[0]
        self.assertEqual(canon, {'index.html': SITE, 'ugolok/index.html': SITE + 'ugolok'})
        sm = read('sitemap.xml')
        urls = re.findall(r'<url>(.*?)</url>', sm, re.S)
        self.assertEqual(sorted(re.search(r'<loc>([^<]*)</loc>', u).group(1) for u in urls), sorted(canon.values()))
        for u in urls:
            d = re.search(r'<lastmod>(\d{4}-\d\d-\d\d)</lastmod>', u)
            self.assertIsNotNone(d, u)
            self.assertLessEqual(datetime.date.fromisoformat(d.group(1)), datetime.date.today())


if __name__ == '__main__':
    unittest.main()
