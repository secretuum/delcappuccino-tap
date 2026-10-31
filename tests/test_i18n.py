"""Казахская и английская версии (А2, 22.10.2026): /kk/, /en/, /kk/menyu, /en/menu собирает tools/seo_jsonld.py
из tools/pages_i18n.json и данных главной. Факты — те же, что на русской; hreflang и canonical на всех версиях;
переключатель РУС / ҚАЗ / ENG; казахские строки — в menu/kk_review.md на вычитку.
Запуск из корня репозитория: python3 -m unittest discover -s tests -v"""
import html as H, json, os, re, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import seo_jsonld as seo  # noqa: E402
SITE = 'https://tap.delcappuccino.kz/'
HOME = {'ru': ('index.html', SITE), 'kk': ('kk/index.html', SITE + 'kk/'), 'en': ('en/index.html', SITE + 'en/')}
MENU = {'ru': ('menyu/index.html', SITE + 'menyu'), 'kk': ('kk/menyu/index.html', SITE + 'kk/menyu'),
        'en': ('en/menu/index.html', SITE + 'en/menu')}


def read(*p):
    with open(os.path.join(ROOT, *p), encoding='utf-8') as f:
        return f.read()


def head(s):
    return s.split('</head>')[0]


def visible(s):
    """текст, который видит человек и бот без JS: без <head>, скриптов, стилей и атрибутов"""
    body = re.sub(r'<(script|style)\b.*?</\1>', ' ', s.split('</head>')[-1], flags=re.S)
    return H.unescape(re.sub(r'<[^>]+>', ' ', body))


def tr(html, lang):
    i = html.index('\n %s:{' % lang)
    return {a.replace("\\'", "'"): b.replace("\\'", "'")
            for a, b in re.findall(r"'((?:[^'\\]|\\.)*)':'((?:[^'\\]|\\.)*)'", html[i:html.index('\n },', i)])}


class TestVersions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = read('index.html')
        cls.pages = {(kind, l): read(f) for kind, d in (('home', HOME), ('menu', MENU)) for l, (f, _) in d.items()}
        cls.data = json.loads(read('tools', 'pages_i18n.json'))
        arr = re.search(r'const BRANCHES = \[(.*?)\n\];', cls.main, re.S).group(1)
        cls.branches = [dict(re.findall(r"\b(n|addr|hours|phone|note|menu):'([^']*)'", line)) for line in re.findall(r"\{n:'.*\}", arr)]

    def test_hreflang_and_canonical(self):
        for kind, d in (('home', HOME), ('menu', MENU)):
            want = sorted([(l, url) for l, (_, url) in d.items()] + [('x-default', d['ru'][1])])
            for l, (f, url) in d.items():
                h = head(self.pages[(kind, l)])
                self.assertEqual(sorted(re.findall(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)">', h)), want, f)
                self.assertEqual(re.findall(r'<link rel="canonical" href="([^"]+)">', h), [url], f)
                self.assertIn('<html lang="%s">' % l, self.pages[(kind, l)], f)

    def test_titles_on_own_language(self):
        for kind in ('home', 'menu'):
            titles = {l: re.search(r'<title>(.*?)</title>', self.pages[(kind, l)]).group(1) for l in HOME}
            descs = {l: re.search(r'<meta name="description" content="([^"]+)">', self.pages[(kind, l)]).group(1) for l in HOME}
            self.assertEqual(len(set(titles.values())), 3, titles)
            self.assertEqual(len(set(descs.values())), 3, descs)
            self.assertRegex(titles['kk'], r'[әғқңөұүһі]', 'казахский title — на казахском')
            self.assertNotRegex(titles['en'] + descs['en'], r'[А-Яа-яЁё]', 'английский title/description — без кириллицы')

    def test_jsonld_faq_on_own_language(self):
        faq_ru = json.loads(read('tools', 'faq.json'))
        for l in ('kk', 'en'):
            page = self.pages[('home', l)]
            data = json.loads(re.search(r'<script type="application/ld\+json">\n(.*?)\n</script>', page, re.S).group(1))
            nodes = {n['@type']: n for n in data['@graph']}
            self.assertEqual(nodes['WebPage']['inLanguage'], l)
            self.assertEqual(nodes['FAQPage']['inLanguage'], l)
            shown = re.findall(r'<details[^>]*><summary>(.*?)</summary><div class="faq-a">(.*?)</div></details>', page)
            self.assertEqual(len(shown), len(faq_ru), 'те же вопросы, что на русской')
            self.assertEqual([(H.unescape(q), H.unescape(a)) for q, a in shown],
                             [(e['name'], e['acceptedAnswer']['text']) for e in nodes['FAQPage']['mainEntity']])
            self.assertNotRegex(page, r'\{\w+\}', 'неподставленная переменная')

    def test_facts_same_as_russian(self):
        kids = re.split(r',\s*|\s+и\s+', re.search(r'<h3>Детская зона</h3><p>Игровая зона в ([^<]+?)\.</p>', self.main).group(1))
        for l in ('kk', 'en'):
            page, d = H.unescape(self.pages[('home', l)]), tr(self.main, l)
            for b in self.branches:
                self.assertIn(d[b['addr']], page, '%s: адрес %s' % (l, b['addr']))
                self.assertIn(d[re.sub(r'^\d+\s*·\s*', '', b['n'])], page)
                self.assertIn('href="tel:%s"' % b['phone'], page)
                hours = re.search(r'\d\d:\d\d–\d\d:\d\d', b['hours'])
                self.assertIn(hours.group(0) if hours else '24/7', page)
            faq_ru = json.loads(read('tools', 'faq.json'))
            i = next(n for n, e in enumerate(faq_ru) if 'детская зона' in e['q'])
            answer = H.unescape(re.findall(r'<div class="faq-a">(.*?)</div></details>', self.pages[('home', l)])[i])
            for k in kids:
                self.assertIn(d[k], answer, '%s: детская зона — там же, где на русской' % l)
            self.assertNotIn(d['ЖК Комфорт Сити'], answer, '%s: в Комфорт Сити детской нет' % l)
            # строки удобств и описание Promenade — на языке страницы, из tools/branch_facts.json
            facts = json.loads(read('tools', 'branch_facts.json'))
            for num, pf in facts['points'].items():
                if pf.get('tags'):
                    self.assertIn(' · '.join('<span>%s</span>' % facts['labels'][t][l] for t in pf['tags']), page, '%s: удобства %s' % (l, num))
                if 'about' in pf:
                    self.assertIn(pf['about'][l], page)
            # чисел, которых нет на русской главной, на kk/en быть не должно (часы, «40 человек», число точек, адреса)
            ru_numbers = set(re.findall(r'\d+', visible(self.main)))
            self.assertEqual(set(re.findall(r'\d+', visible(self.pages[('home', l)]))) - ru_numbers, set(), l)
            self.assertIn('40', re.findall(r'\d+', visible(self.pages[('home', l)])))
            self.assertRegex(page, r'ҚМДБ|KMDB')
            self.assertIn('halaldamu.kz', page)

    def test_light_page_without_js(self):
        for l in ('kk', 'en'):
            page = self.pages[('home', l)]
            scripts = re.findall(r'<script(?: type="application/ld\+json")?>(.*?)</script>', page, re.S)
            # редизайн 31.10: + скрипт заставки из <head> главной (тот же текст, раз за сессию) и ленивый загрузчик анимации
            # кофе в карточке подписки (тот же, что на главной) — страница без них видна целиком, вместо анимации постер
            self.assertEqual(len(re.findall(r'<script\b', page)), 5, 'аналитика (2), JSON-LD, заставка и видео подписки — других скриптов нет')
            self.assertTrue(all('gtag' in s or '"@context"' in s or "classList.add('intro-on')" in s or "querySelector('.sub-video')" in s for s in scripts))
            self.assertIn(seo.SUB_JS, page)
            self.assertIn(seo.SUB_JS, self.main, 'видео подписки — тот же загрузчик, что на главной')
            intro = [s for s in scripts if 'intro-on' in s]
            self.assertEqual(len(intro), 1)
            self.assertIn('<script>%s</script>' % intro[0], self.main.split('</head>')[0], 'заставка — тот же скрипт, что на главной')
            # обработчики на кнопках — только события аналитики (те же, что на главной), без логики страницы
            for h in re.findall(r'\son(?:click|toggle)="([^"]*)"', page):
                self.assertRegex(h, r"^(?:if\(this\.open\))?track\('[a-z_]+'(?:,\{[^}]*\})?\)$", h)
            self.assertNotRegex(page, r'(src|href|srcset)="(?!/|https://|#|tel:)', 'пути только от корня')
            css = re.search(r'<style>(.*?)</style>', page, re.S).group(1)
            self.assertNotRegex(css, r'\.(mm-|grill|modal|strip|showcase)', 'в стилях только нужное странице')
            self.assertIn('.lang-sw', css)
            # казахские буквы — в cyrillic/cyrillic-ext шрифтов из :root главной (tests/test_redesign.py), подмена шрифта для kk не нужна
            self.assertNotIn('html[lang=kk]', css)

    def test_links_to_menu_and_order(self):
        for l in ('kk', 'en'):
            page = self.pages[('home', l)]
            self.assertIn('href="/#menu-%s"' % l, page, 'меню главной на этом языке')
            self.assertIn('href="/#menu-togo-%s"' % l, page, 'меню bakery to go на этом языке')
            self.assertIn('href="https://delcappuccino.kz/"', page)
            self.assertIn('href="/%s"' % MENU[l][1][len(SITE):], page, 'ссылка на текстовое меню')
            # каждая ссылка на меню главной проходит через MENU_HASH из её JS — иначе меню не откроется
            js_re = re.search(r'const MENU_HASH=/(.*?)/;', self.main).group(1)
            for h in re.findall(r'href="/(#menu[^"]*)"', page):
                self.assertRegex(h, js_re, '%s: %s' % (l, h))
            for wa in re.findall(r'href="(https://wa\.me/[^"]+)"', page):
                self.assertRegex(wa, r'^https://wa\.me/\d+\?text=[^\s"<>]+$')

    def test_language_switcher(self):
        for l, page in [('ru', self.main), ('kk', self.pages[('home', 'kk')]), ('en', self.pages[('home', 'en')])]:
            sw = re.search(r'<nav class="lang-sw" aria-label="[^"]+">(.*?)</nav>', page.split('</header>')[0], re.S)
            self.assertIsNotNone(sw, '%s: переключатель в шапке' % l)
            links = re.findall(r'<a href="([^"]+)" lang="(\w+)"([^>]*)>([^<]+)</a>', sw.group(1))
            self.assertEqual([(h, x, t) for h, x, _, t in links], [('/', 'ru', 'РУС'), ('/kk/', 'kk', 'ҚАЗ'), ('/en/', 'en', 'ENG')])
            self.assertEqual([x for _, x, a, _ in links if 'aria-current="page"' in a], [l])
        self.assertIn('<link rel="alternate" hreflang="kk" href="%skk/">' % SITE, head(self.main))

    def test_text_menus(self):
        ru_rows = re.findall(r'<li><span class="n">', self.pages[('menu', 'ru')])
        for l in ('kk', 'en'):
            page, d = self.pages[('menu', l)], tr(self.main, l)
            rows = re.findall(r'<li><span class="n">(.*?)</span>(?:<b class="p">(.*?)</b>)?</li>', page)
            self.assertEqual(len(rows), len(ru_rows), '%s: все позиции, как на /menyu' % l)
            ru_prices = re.findall(r'<b class="p">([\d\u00a0 /]+) ₸', self.pages[('menu', 'ru')])
            self.assertEqual(re.findall(r'<b class="p">([\d\u00a0 /]+) ₸', page), ru_prices, '%s: цены как на /menyu' % l)
            self.assertIn('<html lang="%s">' % l, page)
            translated = [H.unescape(c) for c, _ in rows]
            for name in ('Капучино', 'Мясо'):
                self.assertIn(name, d, '%s: в MENU_TR нет «%s» — возьмите для проверки другую позицию' % (l, name))
                self.assertIn(d[name], ' '.join(translated) + page, '%s: %s → %s' % (l, name, d[name]))

    def test_kk_review_lists_all_kazakh_strings(self):
        review = read('menu', 'kk_review.md')

        def strings(x):
            if isinstance(x, dict):
                return [s for y in x.values() for s in strings(y)]
            if isinstance(x, list):
                return [s for y in x for s in strings(y)]
            return [x]
        for s in strings(self.data['kk']):
            self.assertIn(s.replace('|', '\\|'), review)

    def test_sitemap_and_llms(self):
        sm = read('sitemap.xml')
        for d in (HOME, MENU):
            for _, url in d.values():
                self.assertIn('<loc>%s</loc>' % url, sm)
        llms = read('llms.txt')
        for url in (SITE + 'kk/', SITE + 'en/', SITE + 'kk/menyu', SITE + 'en/menu'):
            self.assertIn('](%s)' % url, llms)


if __name__ == '__main__':
    unittest.main()
