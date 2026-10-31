"""Ролики мобильного приложения kofe-app (31.10.2026): /media/app/menu-par.mp4, napitok-kapuchino.mp4, napitok-moloko.mp4.
Адреса фиксированные (имена без хэша — их вписывает приложение). Исходники — стоковые ролики Mixkit: коммерческое
использование можно, раздавать как сток нельзя, поэтому на сайте они «невидимы»: ни одна страница, sitemap.xml, llms.txt
и JSON-LD (его собирает tools/seo_jsonld.py) на /media/app/ не ссылаются; service worker их не перехватывает (Range-запросы
видео через SW ломают iPhone). Подробности и точки вырезки — docs/COORDINATION.md, раздел «Медиа мобильного приложения».
Правило test_perf «имя видео с хэшем» касается только <video> на странице — эти файлы туда не попадают (проверка ниже).
Запуск из корня репозитория: python3 -m unittest discover -s tests -v"""
import os, re, struct, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, 'media', 'app')
FILES = ['menu-par.mp4', 'napitok-kapuchino.mp4', 'napitok-moloko.mp4']
MAX_BYTES = 3500 * 1024          # ~3,5 МБ на файл — для приложения по мобильной сети
REF = r'media/app'
SKIP_DIRS = {'tests', 'docs', 'media', 'node_modules', '__pycache__'}   # не страницы сайта (docs описывает адреса)
SKIP_FILES = {'sw.js'}           # service worker сам называет /media/app/ — чтобы их пропускать (проверка ниже)


def read(*p):
    with open(os.path.join(ROOT, *p), encoding='utf-8') as f:
        return f.read()


def atoms(data):
    """верхние блоки MP4: [(тип, начало, конец)]"""
    out, i = [], 0
    while i + 8 <= len(data):
        size, kind = struct.unpack('>I4s', data[i:i + 8])
        if size == 1:
            size = struct.unpack('>Q', data[i + 8:i + 16])[0]
        elif size == 0:
            size = len(data) - i
        if size < 8:
            break
        out.append((kind.decode('latin-1'), i, i + size))
        i += size
    return out


def site_files():
    """все страницы и текстовые файлы сайта и генераторов (tools/ собирает JSON-LD), кроме служебных папок"""
    for d, dirs, files in os.walk(ROOT):
        if d == ROOT:
            dirs[:] = [x for x in dirs if not x.startswith('.') and x not in SKIP_DIRS]
        else:
            dirs[:] = [x for x in dirs if not x.startswith('.')]
        for f in files:
            rel = os.path.relpath(os.path.join(d, f), ROOT)
            if rel not in SKIP_FILES and f.endswith(('.html', '.xml', '.txt', '.webmanifest', '.js', '.json', '.md', '.py')):
                yield rel


class TestAppMediaFiles(unittest.TestCase):
    def test_files_present_and_small(self):
        for f in FILES:
            p = os.path.join(APP, f)
            self.assertTrue(os.path.isfile(p), 'нет media/app/%s' % f)
            size = os.path.getsize(p)
            self.assertGreater(size, 100 * 1024, 'media/app/%s подозрительно мал' % f)
            self.assertLessEqual(size, MAX_BYTES, 'media/app/%s: %d байт > ~3,5 МБ' % (f, size))

    def test_mp4_faststart_video_only(self):
        # moov до mdat (+faststart: iPhone начинает играть, не дожидаясь конца файла); дорожка видео есть, звука нет
        for f in FILES:
            with open(os.path.join(APP, f), 'rb') as fh:
                data = fh.read()
            top = atoms(data)
            kinds = [k for k, _, _ in top]
            self.assertEqual(kinds[0], 'ftyp', '%s: не MP4' % f)
            self.assertIn('moov', kinds, f)
            self.assertIn('mdat', kinds, f)
            self.assertLess(kinds.index('moov'), kinds.index('mdat'), '%s: moov после mdat — нет +faststart' % f)
            _, a, b = top[kinds.index('moov')]
            handlers = re.findall(rb'hdlr.{8}(.{4})', data[a:b], re.S)
            self.assertIn(b'vide', handlers, '%s: нет видеодорожки' % f)
            self.assertNotIn(b'soun', handlers, '%s: есть звуковая дорожка (нужно -an)' % f)
            self.assertIn(b'avc1', data[a:b], '%s: не H.264 (avc1)' % f)


class TestAppMediaHidden(unittest.TestCase):
    def test_no_links_from_site(self):
        files = list(site_files())
        for must in ('index.html', 'sitemap.xml', 'llms.txt', 'tools/seo_jsonld.py'):
            self.assertIn(must, files)
        for p in files:
            self.assertNotRegex(read(p), REF, '%s ссылается на media/app/ (сток Mixkit — только прямые адреса)' % p)

    def test_not_on_page_videos(self):
        # правило test_perf «имя .mp4 с хэшем» проверяет <source> страницы — наших файлов там нет, правило не задеваем
        for p in ('index.html', 'kk/index.html', 'en/index.html'):
            for src in re.findall(r'<source[^>]*\bsrc="([^"]+\.mp4)"', read(p)):
                self.assertNotIn('media/app', src, p)

    def test_service_worker_skips_app_media(self):
        src = read('sw.js')
        handler = src[src.index("self.addEventListener('fetch'"):]
        m = re.search(r"if \(url\.pathname\.indexOf\('/media/app/'\) === 0\) return;", handler)
        self.assertIsNotNone(m, 'sw.js: в обработчике fetch нет выхода для путей /media/app/')
        self.assertLess(m.start(), handler.index('respondWith'), 'выход для /media/app/ — до любого respondWith')
        precache = src[src.index('var PRECACHE'):src.index('];', src.index('var PRECACHE'))]
        self.assertNotIn('media/app', precache, 'media/app/ не в PRECACHE')

    def test_documented(self):
        doc = read('docs', 'COORDINATION.md')
        self.assertIn('mixkit.co/license', doc)
        for f in FILES:
            self.assertIn('`/media/app/%s`' % f, doc, 'адрес %s не описан в docs/COORDINATION.md' % f)


if __name__ == '__main__':
    unittest.main()
