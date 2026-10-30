"""Юридические страницы мобильного приложения (30.10.2026): /legal/offer.html, /legal/privacy.html, /legal/contacts.html
и их style.css. Файлы приходят из репозитория kofe-app и лежат как есть, байт в байт; на сайте они «невидимы»:
noindex в самих страницах, ни одна страница сайта на них не ссылается, их нет в sitemap.xml и llms.txt, генератор
tools/seo_jsonld.py их не собирает (нет блока аналитики), service worker их не кэширует и не перехватывает.
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


class TestLegalHidden(unittest.TestCase):
    def test_site_does_not_link_legal(self):
        pages = list(site_pages())
        self.assertIn('index.html', pages)
        self.assertIn('ugolok/index.html', pages)
        for p in pages:
            self.assertNotRegex(read(p), r'(?<![\w-])legal/', '%s ссылается на legal/' % p)

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
