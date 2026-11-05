"""Ролики мобильного приложения kofe-app (31.10.2026): /media/app/menu-par.mp4, napitok-kapuchino.mp4, napitok-moloko.mp4.
Адреса фиксированные (имена без хэша — их вписывает приложение). Исходники — стоковые ролики Mixkit: коммерческое
использование можно, раздавать как сток нельзя, поэтому на сайте они «невидимы»: ни одна страница, sitemap.xml, llms.txt
и JSON-LD (его собирает tools/seo_jsonld.py) на /media/app/ не ссылаются; service worker их не перехватывает (Range-запросы
видео через SW ломают iPhone). Подробности и точки вырезки — docs/COORDINATION.md, раздел «Медиа мобильного приложения».
Правило test_perf «имя видео с хэшем» касается только <video> на странице — эти файлы туда не попадают (проверка ниже).
v2 (01.11.2026): 13 роликов напитков и групп в /media/app/v2/ — готовые файлы «дизайна» (~/kofe-design-export/media/video-v2/),
скопированы байт в байт; те же правила (без звука, H.264, +faststart, ссылок со страниц нет, SW не трогает), бюджет ~1,5 МБ.
v3 (05.11.2026): 10 роликов + 10 обложек *-poster.jpg + manifest.json в /media/app/v3/ (~/kofe-design-export/media/video-v3/),
байт в байт; стоки Mixkit / Coverr / Pexels (у каждого файла своя лицензия — таблица в COORDINATION и поле license в manifest).
Ролик ≤ ~1 МБ, обложка ≤ ~200 КБ. manifest.json на сайте — публичный (manifest.public.json kofe-app, замена 05.11 по их
просьбе): {"files": [...]}, по записи на ролик, только file / poster / license (название + ссылка на текст лицензии);
полный manifest (авторы, исходники, заметки) — у kofe-app локально. espresso.mp4 — и «эспрессо», и «эспрессо двойной».
Запуск из корня репозитория: python3 -m unittest discover -s tests -v"""
import collections, json, os, re, struct, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, 'media', 'app')
FILES = ['menu-par.mp4', 'napitok-kapuchino.mp4', 'napitok-moloko.mp4']
MAX_BYTES = 3500 * 1024          # ~3,5 МБ на файл — для приложения по мобильной сети
V2 = os.path.join(APP, 'v2')
FILES_V2 = ['amerikano.mp4', 'espresso.mp4', 'espresso-dvoinoi.mp4', 'flet-uait.mp4', 'kapuchino.mp4', 'latte.mp4',
            'raf-klassicheskii.mp4', 'raf-medovyi.mp4', 'gruppa-dopolnitelno.mp4', 'gruppa-mod-kofe.mp4',
            'gruppa-moloko.mp4', 'gruppa-podacha.mp4', 'gruppa-siropy.mp4']
MAX_BYTES_V2 = 1536 * 1024       # ~1,5 МБ на ролик v2 (сейчас 0,14–0,8 МБ)
V3 = os.path.join(APP, 'v3')
LICENSE_V3 = {                   # ролик → сток (подтверждено kofe-app 05.11); обложка — кадр того же ролика
    'espresso.mp4': 'Mixkit', 'kapuchino.mp4': 'Mixkit', 'latte.mp4': 'Mixkit', 'flet-uait.mp4': 'Mixkit',
    'raf-medovyi.mp4': 'Mixkit', 'glavnaya-207.mp4': 'Mixkit',
    'amerikano.mp4': 'Coverr', 'glavnaya.mp4': 'Coverr', 'glavnaya-7517.mp4': 'Coverr',
    'raf-klassicheskii.mp4': 'Pexels'}
DOC_LICENSE = {'Mixkit': 'Mixkit Free License', 'Coverr': 'Coverr License', 'Pexels': 'Pexels License'}   # как в таблице COORDINATION
LICENSE_URL = {'Mixkit': 'mixkit.co/license', 'Coverr': 'coverr.co/license', 'Pexels': 'pexels.com/license'}   # текст лицензии
PRIVATE_V3 = ('author', 'kandidaty', 'source', 'note')   # из полного manifest kofe-app — на сайт не выкладываем
FILES_V3 = sorted(LICENSE_V3)
POSTERS_V3 = [f[:-4] + '-poster.jpg' for f in FILES_V3]
MAX_BYTES_V3 = 1024 * 1024       # ~1 МБ на ролик v3 (сейчас 224–464 КБ)
MAX_POSTER_V3 = 200 * 1024       # ~200 КБ на обложку (сейчас 33–109 КБ)
REF = r'media/app'               # подпапки media/app/v2/, v3/ ловит тот же шаблон
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

    def test_v2_present_and_small(self):
        self.assertEqual(sorted(os.listdir(V2)), sorted(FILES_V2), 'media/app/v2/: только 13 роликов (без постеров, json, _staroe, zapas)')
        for f in FILES_V2:
            p = os.path.join(V2, f)
            size = os.path.getsize(p)
            self.assertGreater(size, 50 * 1024, 'media/app/v2/%s подозрительно мал' % f)
            self.assertLessEqual(size, MAX_BYTES_V2, 'media/app/v2/%s: %d байт > ~1,5 МБ' % (f, size))

    def test_v3_present_and_small(self):
        self.assertEqual(sorted(os.listdir(V3)), sorted(FILES_V3 + POSTERS_V3 + ['manifest.json']),
                         'media/app/v3/: только 10 роликов, 10 обложек и manifest.json (без contact-sheet, README, MENU_HERO, EXPO_*)')
        for f in FILES_V3:
            size = os.path.getsize(os.path.join(V3, f))
            self.assertGreater(size, 50 * 1024, 'media/app/v3/%s подозрительно мал' % f)
            self.assertLessEqual(size, MAX_BYTES_V3, 'media/app/v3/%s: %d байт > ~1 МБ' % (f, size))
        for f in POSTERS_V3:
            with open(os.path.join(V3, f), 'rb') as fh:
                data = fh.read()
            self.assertTrue(data.startswith(b'\xff\xd8\xff'), 'media/app/v3/%s: не JPEG (нет сигнатуры FFD8)' % f)
            self.assertTrue(data.endswith(b'\xff\xd9'), 'media/app/v3/%s: JPEG обрезан (нет FFD9 в конце)' % f)
            self.assertGreater(len(data), 10 * 1024, 'media/app/v3/%s подозрительно мала' % f)
            self.assertLessEqual(len(data), MAX_POSTER_V3, 'media/app/v3/%s: %d байт > ~200 КБ' % (f, len(data)))

    def test_v3_manifest(self):
        # публичный manifest: {"files": [{file, poster, license}]}, по одной записи на ролик (эспрессо и эспрессо
        # двойной — один файл и одна запись); размер и звук проверяются по самим файлам (тесты выше и ниже)
        path = os.path.join(V3, 'manifest.json')
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        for word in PRIVATE_V3:   # assertFalse, не assertNotIn: текст файла (с именами авторов) в сообщение не выводим
            self.assertFalse(word in text, 'media/app/v3/manifest.json: «%s» — из полного manifest kofe-app, на сайт не выкладываем' % word)
        root = json.loads(text)
        self.assertIsInstance(root, dict, 'manifest: корень — объект {"files": [...]}')
        self.assertEqual(sorted(root), ['files'], 'manifest: в корне только ключ files')
        entries = root['files']
        self.assertIsInstance(entries, list)
        counts = collections.Counter(e.get('file') for e in entries)
        self.assertEqual(sorted(counts), FILES_V3, 'manifest описывает не все ролики v3 (или чужие)')
        self.assertEqual({f: n for f, n in counts.items() if n > 1}, {}, 'manifest: ролик записан дважды')
        for e in entries:
            f = e['file']
            self.assertEqual(sorted(e), ['file', 'license', 'poster'], 'manifest: %s — только file, poster, license' % f)
            self.assertEqual(e['poster'], f[:-4] + '-poster.jpg', 'manifest: обложка %s' % f)
            self.assertTrue(os.path.isfile(os.path.join(V3, e['poster'])), 'manifest: обложки %s нет в папке' % e['poster'])
            stock = LICENSE_V3[f]
            self.assertIn(stock, e['license'], 'manifest: лицензия %s не %s' % (f, stock))
            self.assertIn(LICENSE_URL[stock], e['license'], 'manifest: у %s нет ссылки на текст лицензии %s' % (f, LICENSE_URL[stock]))

    def test_mp4_faststart_video_only(self):
        # moov до mdat (+faststart: iPhone начинает играть, не дожидаясь конца файла); дорожка видео есть, звука нет
        for f in FILES + ['v2/' + x for x in FILES_V2] + ['v3/' + x for x in FILES_V3]:
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
        for addr in ('/media/app/v2/latte.mp4', '/media/app/v3/latte.mp4', '/media/app/v3/latte-poster.jpg', 'media/app/v3/manifest.json'):
            self.assertRegex(addr, REF, 'шаблон REF должен ловить и подпапки v2/, v3/')
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
        # v2, v3 — подпапки: выход по префиксу '/media/app/' (indexOf === 0) покрывает и их, вместе с обложками .jpg и
        # manifest.json (без него SW взял бы .jpg в кэш, а .json — «сначала сеть»); поведение в node — test_perf, app_v2_*, app_v3_*
        self.assertNotRegex(src, r'media/app/v\d', 'sw.js: для v2/, v3/ отдельных правил не нужно')

    def test_documented(self):
        doc = read('docs', 'COORDINATION.md')
        self.assertIn('mixkit.co/license', doc)
        for f in FILES:
            self.assertIn('`/media/app/%s`' % f, doc, 'адрес %s не описан в docs/COORDINATION.md' % f)
        for f in FILES_V2:
            self.assertIn('`/media/app/v2/%s`' % f, doc, 'адрес v2/%s не описан в docs/COORDINATION.md' % f)
        self.assertIn('latte.mp4', doc)
        self.assertIn('права не проверены', doc, 'latte.mp4 v2 — пометка «права не проверены»')

    def test_documented_v3(self):
        # таблица v3 — одна строка на файл: адрес, лицензия (обложка — как у её ролика), заметка
        doc = read('docs', 'COORDINATION.md')
        rows = {}
        for line in doc.splitlines():
            m = re.match(r'\| `/media/app/v3/([^`]+)` \|', line)
            if m:
                self.assertNotIn(m.group(1), rows, 'v3/%s описан в таблице дважды' % m.group(1))
                rows[m.group(1)] = line
        self.assertEqual(sorted(rows), sorted(FILES_V3 + POSTERS_V3 + ['manifest.json']), 'таблица v3: по строке на каждый файл папки')
        for f, lic in LICENSE_V3.items():
            for name in (f, f[:-4] + '-poster.jpg'):
                self.assertIn(DOC_LICENSE[lic], rows[name], 'v3/%s: в таблице не та лицензия (нужна %s)' % (name, DOC_LICENSE[lic]))
        for url in LICENSE_URL.values():
            self.assertIn(url, doc)


if __name__ == '__main__':
    unittest.main()
