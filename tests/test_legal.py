"""Юридические страницы мобильного приложения (30.10.2026): /legal/offer.html, /legal/privacy.html, /legal/contacts.html
и их style.css. Файлы приходят из репозитория kofe-app и лежат как есть, байт в байт; на сайте они «невидимы»:
noindex в самих страницах, их нет в sitemap.xml и llms.txt, генератор tools/seo_jsonld.py их не собирает (нет блока
аналитики), service worker их не кэширует и не перехватывает. С 31.10.2026 (решение владельца) на три документа ссылается
только подвал главной, /kk/ и /en/ — рядом с «Уголком потребителя», событие legal_open {doc} (не цель Метрики);
в остальных страницах сайта ссылок на legal/ нет. Тексты документов — на русском на всех трёх языках сайта.
robots.txt НЕ закрывает /legal/: Disallow помешал бы Apple, Google и Meta прочитать страницы и увидеть noindex.
Запуск из корня репозитория: python3 -m unittest discover -s tests -v"""
import os, re, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import seo_jsonld as seo  # noqa: E402

LEGAL = os.path.join(ROOT, 'legal')
PAGES = ['offer.html', 'privacy.html', 'contacts.html']
FILES = PAGES + ['style.css']
SKIP_DIRS = {'legal', 'tests', 'tools', 'docs', 'node_modules', '__pycache__'}   # не страницы сайта
SKIP_FILES = {'sw.js'}   # service worker сам называет /legal/ — чтобы их пропускать (проверка ниже)


def read(*p):
    with open(os.path.join(ROOT, *p), encoding='utf-8') as f:
        return f.read()


def site_pages():
    """все страницы и текстовые файлы сайта, кроме самих legal/ (и служебных папок, скрытых каталогов)"""
    for d, dirs, files in os.walk(ROOT):
        if d == ROOT:
            dirs[:] = [x for x in dirs if not x.startswith('.') and x not in SKIP_DIRS]
        else:
            dirs[:] = [x for x in dirs if not x.startswith('.')]
        for f in files:
            rel = os.path.relpath(os.path.join(d, f), ROOT)
            if rel not in SKIP_FILES and f.endswith(('.html', '.xml', '.txt', '.webmanifest', '.js', '.json', '.md')):
                yield rel


class TestLegalFiles(unittest.TestCase):
    def test_files_present(self):
        for f in FILES:
            p = os.path.join(LEGAL, f)
            self.assertTrue(os.path.isfile(p), 'нет legal/%s' % f)
            self.assertGreater(os.path.getsize(p), 0, 'legal/%s пустой' % f)

    def test_noindex(self):
        for f in PAGES:
            html = read('legal', f)
            self.assertRegex(html, r'<meta\s+name="robots"\s+content="[^"]*noindex', 'legal/%s: нет <meta robots noindex>' % f)

    def test_no_analytics_or_generator(self):
        # страницы публикуются как есть — без блока аналитики сайта и без сборки генератором
        for f in PAGES:
            html = read('legal', f)
            for marker in ('googletagmanager', 'gtag(', 'mc.yandex', 'function track(', 'application/ld+json',
                           'tools/seo_jsonld.py'):
                self.assertNotIn(marker, html, 'legal/%s: на странице %r' % (f, marker))
        built = [os.path.relpath(p, ROOT) for p in seo.outputs(read('index.html'))]
        self.assertFalse([p for p in built if p.startswith('legal')], 'генератор не должен собирать legal/')
        self.assertFalse([p for p in seo.PAGES.values() if p.startswith('legal')], 'legal/ нет в seo_jsonld.PAGES')


FOOTER_PAGES = ['index.html', 'kk/index.html', 'en/index.html']     # подвал с документами — только здесь
DOCS = ['offer', 'privacy', 'contacts']
DOC_TITLES = {'index.html': ['Публичная оферта', 'Политика конфиденциальности', 'Контакты и реквизиты'],
              'kk/index.html': ['Жария оферта', 'Құпиялылық саясаты', 'Байланыс және деректемелер'],
              'en/index.html': ['Public offer', 'Privacy policy', 'Contacts &amp; legal details']}
LEGAL_REF = r'(?<![\w-])legal/'


def footer(html):
    m = re.search(r'<footer\b.*?</footer>', html, re.S)
    return m.group(0) if m else ''


class TestLegalLinks(unittest.TestCase):
    def test_footer_links_on_three_pages(self):
        for p in FOOTER_PAGES:
            html, foot = read(p), footer(read(p))
            self.assertTrue(foot, '%s: нет <footer>' % p)
            m = re.search(r'<span class="f-legal">(.*?)</span>', foot, re.S)
            self.assertIsNotNone(m, '%s: в подвале нет блока f-legal' % p)
            links = re.findall(r'<a href="([^"]*)" onclick="([^"]*)">([^<]*)</a>', m.group(1))
            self.assertEqual([h for h, _, _ in links], ['/legal/%s.html' % d for d in DOCS], p)
            self.assertEqual([o for _, o, _ in links], ["track('legal_open',{doc:'%s'})" % d for d in DOCS], p)
            self.assertEqual([t for _, _, t in links], DOC_TITLES[p], '%s: названия на языке страницы' % p)
            # «Уголок потребителя» — первой ссылкой того же ряда (владелец 31.10: не кнопкой, а как документы)
            self.assertRegex(m.group(1), r'^<a class="f-ugolok" href="/ugolok/" onclick="track\(\'cta_ugolok\'\)">[^<]+</a> <a href="/legal/offer\.html"', p)
            self.assertEqual(foot.count('class="f-ugolok"'), 1, p)
            # ссылки только в подвале — ровно по одной на документ на всей странице
            self.assertEqual(len(re.findall(LEGAL_REF, html)), 3, '%s: ссылки на legal/ — только три в подвале' % p)
            self.assertEqual(len(re.findall(LEGAL_REF, foot)), 3, p)

    def test_other_pages_do_not_link_legal(self):
        pages = list(site_pages())
        self.assertIn('index.html', pages)
        self.assertIn('ugolok/index.html', pages)
        for p in pages:
            if p in FOOTER_PAGES:
                continue
            self.assertNotRegex(read(p), LEGAL_REF, '%s ссылается на legal/' % p)

    def test_generator_owns_lang_footers(self):
        # /kk/ и /en/ собирает tools/seo_jsonld.py: подписи — в tools/pages_i18n.json, kk — на вычитке в menu/kk_review.md
        d = seo.i18n()
        for lang in ('kk', 'en'):
            page = d[lang]['page']
            self.assertEqual([page['footer_' + x] for x in DOCS], DOC_TITLES['%s/index.html' % lang], lang)
        review = read('menu', 'kk_review.md')
        for x, t in zip(DOCS, DOC_TITLES['kk/index.html']):
            self.assertIn('| `page.footer_%s` | страница /kk/ | %s |' % (x, t), review)

    def test_legal_open_is_not_a_goal(self):
        self.assertNotIn('legal_open', seo.YM_GOALS, 'legal_open — событие GA, целью Метрики не делаем')
        self.assertNotIn('legal', ' '.join(seo.YM_GOALS.values()))

    def test_footer_styles_mobile(self):
        # скромно (не кнопка), на телефоне — в колонке рядом с «Уголком», переносы между ссылками, без горизонтальной прокрутки
        for p in FOOTER_PAGES:
            html = read(p)
            css = html[html.index('<style>'):html.index('</style>')]
            self.assertIn('.f-row .f-legal{display:inline-flex;flex-wrap:wrap;justify-content:center;', css, p)
            self.assertIn('max-width:100%', re.search(r'\.f-row \.f-legal\{[^}]*\}', css).group(0), p)
            self.assertNotRegex(css, r'\.f-legal[^{]*\{[^}]*(?:border|background)', '%s: ссылки на документы — не кнопки' % p)
            self.assertRegex(css, r'@media\(max-width:680px\)\{[^@]*\.f-row \.f-legal\{order:-1', '%s: на телефоне — первым в колонке' % p)
            self.assertNotRegex(css, r'\.f-ugolok[^{]*\{[^}]*(?:border|background|padding)', '%s: «Уголок» — не кнопка, как документы' % p)


class TestLegalHidden(unittest.TestCase):

    def test_not_in_sitemap_and_llms(self):
        for p in ('sitemap.xml', 'llms.txt'):
            self.assertNotIn('/legal', read(p), '%s: /legal/ в поиск не отдаём' % p)
            self.assertNotRegex(read(p), r'legal/(offer|privacy|contacts)', p)

    def test_robots_does_not_block_legal(self):
        # Disallow на /legal/ (или шире) спрятал бы noindex от Apple, Google и Meta
        for f in PAGES:
            path = '/legal/' + f
            for rule in re.findall(r'(?im)^\s*Disallow:\s*(\S*)', read('robots.txt')):
                rule = rule.split('*')[0].rstrip('$')
                self.assertFalse(rule and path.startswith(rule), 'robots.txt: Disallow %r закрывает %s' % (rule, path))

    def test_service_worker_skips_legal(self):
        src = read('sw.js')
        handler = src[src.index("self.addEventListener('fetch'"):]
        m = re.search(r"if \(url\.pathname\.indexOf\('/legal/'\) === 0\) return;", handler)
        self.assertIsNotNone(m, "sw.js: в обработчике fetch нет выхода для путей /legal/")
        self.assertLess(m.start(), handler.index('respondWith'), 'выход для /legal/ — до любого respondWith')
        self.assertNotIn('legal', src[src.index('var PRECACHE'):src.index('];', src.index('var PRECACHE'))],
                         'legal/ не в PRECACHE')


if __name__ == '__main__':
    unittest.main()
