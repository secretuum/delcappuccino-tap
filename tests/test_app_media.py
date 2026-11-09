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
v4 (09.11.2026): те же 10 роликов + 10 обложек + публичный manifest.json в /media/app/v4/ (~/kofe-design-export/media/video-v4/),
байт в байт; «дизайн» пересобрал их из оригиналов стоков в 1080×1920 (владелец о v3: «слишком сжатые, пиксельные»). Стоки,
страницы и лицензии те же, что у v3. Ролик ≤ 3,2 МБ, обложка ≤ 500 КБ (как в check.py «дизайна»). v1–v3 не трогаем.
menu-media.json (06.11.2026, задача M3 kofe-app «медиа приложения без iiko»): список «позиция меню → фото / ролик» в корне
/media/app/, байт в байт из ~/kofe-design-export/media/menu-media/. Адрес постоянный, содержимое меняется — его будет читать
сервер kofe-app. Формат 1 проверяется здесь своим кодом (как check.py «дизайна», он лежит вне репозитория и из тестов не
вызывается), плюс каждый упомянутый файл лежит в media/app/ — офлайн-аналог check.py --online.
Правило kofe-app 06.11: медиафайлы (*.mp4, *.jpg) в /media/app/ под тем же именем не перезаписываются — новая версия
получает новое имя или папку v4/ (иначе телефоны и Cloudflare показывают старое). Сторож — PINNED (sha256 каждого файла).
JSON (menu-media.json, v3/manifest.json) не закрепляем: адрес постоянный, содержимое меняется.
Запуск из корня репозитория: python3 -m unittest discover -s tests -v"""
import collections, hashlib, json, os, re, struct, unittest

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
V4 = os.path.join(APP, 'v4')
LICENSE_V4 = dict(LICENSE_V3)    # v4 — те же 10 роликов из тех же стоков (страницы и лицензии сверены с manifest kofe-app 09.11)
FILES_V4 = sorted(LICENSE_V4)
POSTERS_V4 = [f[:-4] + '-poster.jpg' for f in FILES_V4]
MAX_BYTES_V4 = 3_200_000         # байт, как в check.py «дизайна»: ролик v4 1080×1920 до ~3,2 МБ (сейчас 1,01–2,59 МБ)
MAX_POSTER_V4 = 500_000          # байт, обложка 1080×1920 до ~500 КБ (сейчас 66–212 КБ)
MENU_MEDIA = 'menu-media.json'   # список медиа меню (06.11.2026), адрес https://tap.delcappuccino.kz/media/app/menu-media.json
ROOT_LIST = FILES + [MENU_MEDIA, 'v2', 'v3', 'v4']   # состав корня media/app/ (новая папка v5/ — дописать сюда)
# формат 1 menu-media.json — те же правила, что в check.py «дизайна» (~/kofe-design-export/media/menu-media/check.py)
MM_BASE = 'https://tap.delcappuccino.kz/media/app/'
MM_PATH = re.compile(r'^[a-z0-9][a-z0-9/_-]*\.(mp4|jpg)$')    # относительный путь латиницей, без «..», без пробелов
MM_MAX = {'mp4': 3_200_000, 'jpg': 500_000}                    # байт, как в check.py (с 09.11, под v4): ролик до ~3,2 МБ, фото до ~500 КБ
IMMUTABLE = ('.mp4', '.jpg', '.jpeg')   # медиа под тем же именем не перезаписываем; JSON (списки) меняются на месте
# sha256 (первые 16 hex) каждого медиафайла в media/app/ — правило kofe-app 06.11: файл под тем же именем никогда не меняется.
# Новый файл → добавить хэш сюда в том же PR. Удаление старого — только с «да» владельца (на него ссылаются старые сборки).
PINNED = {
    'menu-par.mp4': '108f640f5aeb5cb7',
    'napitok-kapuchino.mp4': '06ff2f9a67597d5e',
    'napitok-moloko.mp4': '9e7958ab2c1979ea',
    'v2/amerikano.mp4': 'd88a2813f6a224d0',
    'v2/espresso-dvoinoi.mp4': 'aa4bf734b593ea1c',
    'v2/espresso.mp4': 'aa4bf734b593ea1c',
    'v2/flet-uait.mp4': '2e56ad7e9b4bfccc',
    'v2/gruppa-dopolnitelno.mp4': '31153ea6daf704f7',
    'v2/gruppa-mod-kofe.mp4': '762cf77ef61b1540',
    'v2/gruppa-moloko.mp4': '89f0f6086e9647e1',
    'v2/gruppa-podacha.mp4': '258c39e2fba689a4',
    'v2/gruppa-siropy.mp4': '899ff525f91a2020',
    'v2/kapuchino.mp4': 'ebbab7f6f1a963b6',
    'v2/latte.mp4': '61ba32a9f6d99d11',
    'v2/raf-klassicheskii.mp4': 'f00500f7e0cc24af',
    'v2/raf-medovyi.mp4': 'f9ab464393aa50a2',
    'v3/amerikano.mp4': '6c3c600c688964f2',
    'v3/amerikano-poster.jpg': '7a2ebfb3ae37f7f8',
    'v3/espresso.mp4': '68bf0373557c7169',
    'v3/espresso-poster.jpg': 'c5273f3c60a96230',
    'v3/flet-uait.mp4': '0476d6d61c057382',
    'v3/flet-uait-poster.jpg': '0f4c6e1fb910d744',
    'v3/glavnaya-207.mp4': 'c05758206a7e0d9b',
    'v3/glavnaya-207-poster.jpg': '6584813b0b2c578b',
    'v3/glavnaya-7517.mp4': '2dd8c3bacde815ba',
    'v3/glavnaya-7517-poster.jpg': 'f164c49be149102b',
    'v3/glavnaya.mp4': '3f49c064dbe395f2',
    'v3/glavnaya-poster.jpg': '61dd7d0711c827cf',
    'v3/kapuchino.mp4': 'b8828b07d66da676',
    'v3/kapuchino-poster.jpg': '8395d8ff54252146',
    'v3/latte.mp4': '9a3c5fdcbfc4f922',
    'v3/latte-poster.jpg': 'a5295a861ad758c1',
    'v3/raf-klassicheskii.mp4': 'f00500f7e0cc24af',
    'v3/raf-klassicheskii-poster.jpg': 'cb01e0195f62b5c0',
    'v3/raf-medovyi.mp4': '733f99c7659c6f9d',
    'v3/raf-medovyi-poster.jpg': '9af4b0279db05066',
    'v4/amerikano.mp4': '9f716482a8a12028',
    'v4/amerikano-poster.jpg': '98efa092a6073c2a',
    'v4/espresso.mp4': '22c6a0d651abe8fe',
    'v4/espresso-poster.jpg': 'ae965177c21bda6e',
    'v4/flet-uait.mp4': '2a299c9b72f77de0',
    'v4/flet-uait-poster.jpg': 'b4cabb5ad45bb9de',
    'v4/glavnaya-207.mp4': '5e185dc84fd73d2a',
    'v4/glavnaya-207-poster.jpg': 'd158840617374922',
    'v4/glavnaya-7517.mp4': '23d0599044adbd89',
    'v4/glavnaya-7517-poster.jpg': 'c491206127ff95eb',
    'v4/glavnaya.mp4': '7f90b71b36879c01',
    'v4/glavnaya-poster.jpg': '2f63ca9b2c53a771',
    'v4/kapuchino.mp4': '5c6f4dd3d933b8d8',
    'v4/kapuchino-poster.jpg': 'db07a10b9f8a5812',
    'v4/latte.mp4': 'f74f792aa08c0a48',
    'v4/latte-poster.jpg': '779bd1d82f5798e7',
    'v4/raf-klassicheskii.mp4': '6e42f0b4d82c74f4',
    'v4/raf-klassicheskii-poster.jpg': 'a265a4eedeaecf4a',
    'v4/raf-medovyi.mp4': 'f02ed37ca2f91418',
    'v4/raf-medovyi-poster.jpg': 'd255b3dc58de14e9',
}
REF = r'media/app'               # подпапки media/app/v2/, v3/, v4/ ловит тот же шаблон
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


def mm_norm(name):
    """ключ позиции, как check.py и app/src/domain/covers.ts: нижний регистр, ё/э → е, дефисы → пробел, пробелы схлопнуты"""
    return re.sub(r'\s+', ' ', re.sub(r'[-‐–]', ' ', re.sub(r'[ёэ]', 'е', name.lower()))).strip()


def menu_media_errors(doc):
    """формат 1 menu-media.json (те же правила, что check.py «дизайна»): ([ошибки], [упомянутые файлы])"""
    errors, files = [], []

    def path(where, v, ext, need=True):
        if v is None and not need:
            return
        if not isinstance(v, str) or not MM_PATH.match(v) or '..' in v or not v.endswith('.' + ext):
            errors.append('%s: путь «%s» — нужен относительный путь .%s латиницей (например v3/latte.%s)' % (where, v, ext, ext))
        else:
            files.append(v)

    def dark(where, v):
        if not isinstance(v, bool):
            errors.append('%s.dark: нужно true или false' % where)

    if not isinstance(doc, dict):
        return ['корень: нужен объект'], []
    if doc.get('format') != 1:
        errors.append('format: должно быть 1')
    if doc.get('base') != MM_BASE:
        errors.append('base: должно быть ' + MM_BASE)
    if not isinstance(doc.get('updated'), str) or not re.match(r'^\d{4}-\d{2}-\d{2}$', doc['updated']):
        errors.append('updated: дата ГГГГ-ММ-ДД')
    home = doc.get('home')
    if not isinstance(home, dict):
        errors.append('home: нужен объект')
        home = {}
    else:
        path('home.video', home.get('video'), 'mp4')
        path('home.poster', home.get('poster'), 'jpg', need=False)
        dark('home', home.get('dark'))
        if home.get('drink') is not None and not isinstance(home.get('drink'), str):
            errors.append('home.drink: название напитка строкой или null')
    default = doc.get('default')
    if default is not None:
        if not isinstance(default, dict):
            errors.append('default: объект или null')
        else:
            path('default.video', default.get('video'), 'mp4')
            dark('default', default.get('dark'))
    items = doc.get('items')
    if not isinstance(items, dict) or not items:
        errors.append('items: нужен непустой объект «название → медиа»')
        items = {}
    seen = {}
    for name, m in items.items():
        key = mm_norm(name)
        if key in seen:
            errors.append('items «%s»: совпадает с «%s» после нормализации' % (name, seen[key]))
        seen[key] = name
        if not isinstance(m, dict) or not (m.get('photo') or m.get('video')):
            errors.append('items «%s»: нужен photo и/или video' % name)
            continue
        path('items «%s».photo' % name, m.get('photo'), 'jpg', need=False)
        path('items «%s».video' % name, m.get('video'), 'mp4', need=False)
        dark('items «%s»' % name, m.get('dark'))
        extra = set(m) - {'photo', 'video', 'dark'}
        if extra:
            errors.append('items «%s»: лишние поля %s' % (name, sorted(extra)))
    hd = home.get('drink')
    if isinstance(hd, str):
        rec = items.get(seen.get(mm_norm(hd)))
        if not isinstance(rec, dict) or not rec.get('video'):
            errors.append('home.drink «%s»: у напитка должна быть запись с video в items' % hd)
    return errors, sorted(set(files))


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

    def test_v4_present_and_small(self):
        self.assertEqual(sorted(os.listdir(V4)), sorted(FILES_V4 + POSTERS_V4 + ['manifest.json']),
                         'media/app/v4/: только 10 роликов, 10 обложек и manifest.json (без полного manifest, README, '
                         'contact-sheet, comparison)')
        for f in FILES_V4:
            size = os.path.getsize(os.path.join(V4, f))
            self.assertGreater(size, 300 * 1024, 'media/app/v4/%s подозрительно мал для 1080×1920' % f)
            self.assertLessEqual(size, MAX_BYTES_V4, 'media/app/v4/%s: %d байт > ~3,2 МБ' % (f, size))
        for f in POSTERS_V4:
            with open(os.path.join(V4, f), 'rb') as fh:
                data = fh.read()
            self.assertTrue(data.startswith(b'\xff\xd8\xff'), 'media/app/v4/%s: не JPEG (нет сигнатуры FFD8)' % f)
            self.assertTrue(data.endswith(b'\xff\xd9'), 'media/app/v4/%s: JPEG обрезан (нет FFD9 в конце)' % f)
            self.assertGreater(len(data), 10 * 1024, 'media/app/v4/%s подозрительно мала' % f)
            self.assertLessEqual(len(data), MAX_POSTER_V4, 'media/app/v4/%s: %d байт > ~500 КБ' % (f, len(data)))

    def check_public_manifest(self, folder, ver, files, licenses):
        # публичный manifest: {"files": [{file, poster, license}]}, по одной записи на ролик (эспрессо и эспрессо
        # двойной — один файл и одна запись); размер и звук проверяются по самим файлам (тесты выше и ниже)
        with open(os.path.join(folder, 'manifest.json'), encoding='utf-8') as fh:
            text = fh.read()
        for word in PRIVATE_V3:   # assertFalse, не assertNotIn: текст файла (с именами авторов) в сообщение не выводим
            self.assertFalse(word in text, 'media/app/%s/manifest.json: «%s» — из полного manifest kofe-app, на сайт не выкладываем' % (ver, word))
        root = json.loads(text)
        self.assertIsInstance(root, dict, 'manifest %s: корень — объект {"files": [...]}' % ver)
        self.assertEqual(sorted(root), ['files'], 'manifest %s: в корне только ключ files' % ver)
        entries = root['files']
        self.assertIsInstance(entries, list)
        counts = collections.Counter(e.get('file') for e in entries)
        self.assertEqual(sorted(counts), files, 'manifest описывает не все ролики %s (или чужие)' % ver)
        self.assertEqual({f: n for f, n in counts.items() if n > 1}, {}, 'manifest %s: ролик записан дважды' % ver)
        for e in entries:
            f = e['file']
            self.assertEqual(sorted(e), ['file', 'license', 'poster'], 'manifest %s: %s — только file, poster, license' % (ver, f))
            self.assertEqual(e['poster'], f[:-4] + '-poster.jpg', 'manifest %s: обложка %s' % (ver, f))
            self.assertTrue(os.path.isfile(os.path.join(folder, e['poster'])), 'manifest %s: обложки %s нет в папке' % (ver, e['poster']))
            stock = licenses[f]
            self.assertIn(stock, e['license'], 'manifest %s: лицензия %s не %s' % (ver, f, stock))
            self.assertIn(LICENSE_URL[stock], e['license'], 'manifest %s: у %s нет ссылки на текст лицензии %s' % (ver, f, LICENSE_URL[stock]))

    def test_v3_manifest(self):
        self.check_public_manifest(V3, 'v3', FILES_V3, LICENSE_V3)

    def test_v4_manifest(self):
        self.check_public_manifest(V4, 'v4', FILES_V4, LICENSE_V4)

    def test_mp4_faststart_video_only(self):
        # moov до mdat (+faststart: iPhone начинает играть, не дожидаясь конца файла); дорожка видео есть, звука нет
        for f in FILES + ['v2/' + x for x in FILES_V2] + ['v3/' + x for x in FILES_V3] + ['v4/' + x for x in FILES_V4]:
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

    def test_root_listing(self):
        self.assertEqual(sorted(os.listdir(APP)), sorted(ROOT_LIST),
                         'media/app/: только три ролика v1, menu-media.json и папки v2/, v3/, v4/ (новая папка v5/ — дописать в ROOT_LIST)')


class TestAppMediaImmutable(unittest.TestCase):
    """правило kofe-app 06.11.2026: медиафайл в /media/app/ под тем же именем не перезаписывается — телефоны и Cloudflare
    держат старую копию. Новая версия — новое имя (latte-2.mp4) или новая папка (v4/latte.mp4)."""

    def found(self):
        out = {}
        for d, dirs, files in os.walk(APP):
            for f in files:
                if f.lower().endswith(IMMUTABLE):
                    rel = os.path.relpath(os.path.join(d, f), APP).replace(os.sep, '/')
                    with open(os.path.join(d, f), 'rb') as fh:
                        out[rel] = hashlib.sha256(fh.read()).hexdigest()[:16]
        return out

    def test_media_not_overwritten(self):
        found = self.found()
        changed = {f: 'было %s, стало %s' % (PINNED[f], h) for f, h in found.items() if f in PINNED and h != PINNED[f]}
        self.assertEqual(changed, {}, 'media/app/: файл перезаписан под тем же именем — верните прежний; '
                                      'новая версия — новое имя или v4/ (правило kofe-app 06.11)')
        self.assertEqual(sorted(set(found) - set(PINNED)), [],
                         'media/app/: файлы без закреплённого sha256 — добавьте хэш в PINNED в том же PR '
                         '(и проверьте, что это новое имя, а не перезапись: новая версия — новое имя или v4/)')
        self.assertEqual(sorted(set(PINNED) - set(found)), [],
                         'media/app/: пропали закреплённые файлы — на них ссылаются установленные сборки и кэш; '
                         'удалять только с «да» владельца (и тогда убрать из PINNED). Новая версия — новое имя или v4/')

    def test_json_not_pinned(self):
        # списки (menu-media.json, v3/manifest.json) меняются на постоянном адресе — их сторож не держит
        for f in PINNED:
            self.assertTrue(f.endswith(IMMUTABLE), 'PINNED: %s — закрепляем только медиа (mp4/jpg), не JSON' % f)


class TestMenuMedia(unittest.TestCase):
    """menu-media.json — список «позиция меню → фото / ролик» для kofe-app (06.11.2026). Адрес постоянный, содержимое
    меняется; исходник ведёт «дизайн», перед выкладкой — их check.py --online (вручную, из тестов не вызываем)."""

    def doc(self):
        with open(os.path.join(APP, MENU_MEDIA), encoding='utf-8') as fh:
            return json.load(fh)

    def test_format_1(self):
        errors, files = menu_media_errors(self.doc())
        self.assertEqual(errors, [], 'media/app/menu-media.json: формат 1 нарушен')
        self.assertTrue(files, 'menu-media.json: ни одного файла')

    def test_files_in_repo(self):
        # офлайн-аналог check.py --online: каждый упомянутый файл лежит в media/app/, нужного типа, в пределах размера,
        # и закреплён в PINNED (значит, под этим именем уже не поменяется)
        _, files = menu_media_errors(self.doc())
        for f in files:
            p = os.path.join(APP, *f.split('/'))
            self.assertTrue(os.path.isfile(p), 'menu-media.json ссылается на %s — файла нет в media/app/' % f)
            self.assertIn(f, PINNED, 'menu-media.json: %s не закреплён в PINNED' % f)
            ext = f.rsplit('.', 1)[1]
            with open(p, 'rb') as fh:
                head = fh.read(12)
            if ext == 'jpg':
                self.assertTrue(head.startswith(b'\xff\xd8\xff'), '%s: не JPEG' % f)
            else:
                self.assertEqual(head[4:8], b'ftyp', '%s: не MP4' % f)
            self.assertLessEqual(os.path.getsize(p), MM_MAX[ext], '%s: больше, чем пропустит check.py' % f)

    def test_checker_catches_errors(self):
        # своя проверка не пустая: каждая порча находится
        good = self.doc()
        self.assertEqual(menu_media_errors(good)[0], [])
        name = next(iter(good['items']))

        def spoiled(fn):
            d = json.loads(json.dumps(good))
            fn(d)
            return menu_media_errors(d)[0]

        for why, fn in [
            ('format 2', lambda d: d.update(format=2)),
            ('чужой base', lambda d: d.update(base='https://example.com/')),
            ('дата', lambda d: d.update(updated='06.11.2026')),
            ('«..» в пути', lambda d: d['home'].update(video='../v3/latte.mp4')),
            ('кириллица в пути', lambda d: d['home'].update(video='v3/латте.mp4')),
            ('абсолютный путь', lambda d: d['home'].update(video='/media/app/v3/latte.mp4')),
            ('jpg вместо mp4', lambda d: d.update(default={'video': 'v3/latte-poster.jpg', 'dark': False})),
            ('dark строкой', lambda d: d['items'][name].update(dark='true')),
            ('лишнее поле', lambda d: d['items'][name].update(url='x')),
            ('запись без photo и video', lambda d: d['items'].update({name: {'dark': False}})),
            ('повтор после нормализации', lambda d: d['items'].update({name.upper(): d['items'][name]})),
            ('home.drink без записи', lambda d: d['home'].update(drink='нет такого')),
            ('пустые items', lambda d: d.update(items={})),
        ]:
            self.assertNotEqual(spoiled(fn), [], 'проверка menu-media.json пропустила: %s' % why)


class TestAppMediaHidden(unittest.TestCase):
    def test_no_links_from_site(self):
        files = list(site_files())
        for must in ('index.html', 'sitemap.xml', 'llms.txt', 'tools/seo_jsonld.py'):
            self.assertIn(must, files)
        for addr in ('/media/app/v2/latte.mp4', '/media/app/v3/latte.mp4', '/media/app/v3/latte-poster.jpg', 'media/app/v3/manifest.json',
                     '/media/app/v4/latte.mp4', '/media/app/v4/latte-poster.jpg', 'media/app/v4/manifest.json',
                     MM_BASE + 'v4/glavnaya.mp4', MM_BASE + MENU_MEDIA, '/media/app/menu-media.json'):
            self.assertRegex(addr, REF, 'шаблон REF должен ловить и подпапки v2/, v3/, v4/, и menu-media.json')
        # сам menu-media.json называет base …/media/app/ — он лежит в media/ (SKIP_DIRS), страницей сайта не считается
        self.assertNotIn(os.path.join('media', 'app', MENU_MEDIA), files)
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
        # v2, v3, v4 — подпапки: выход по префиксу '/media/app/' (indexOf === 0) покрывает и их, вместе с обложками .jpg и
        # manifest.json (без него SW взял бы .jpg в кэш, а .json — «сначала сеть»), и menu-media.json в корне;
        # поведение в node — test_perf, app_v2_*, app_v3_*, app_v4_*, app_menu_media
        self.assertNotRegex(src, r'media/app/v\d', 'sw.js: для v2/, v3/, v4/ отдельных правил не нужно')

    def test_documented(self):
        doc = read('docs', 'COORDINATION.md')
        self.assertIn('mixkit.co/license', doc)
        for f in FILES:
            self.assertIn('`/media/app/%s`' % f, doc, 'адрес %s не описан в docs/COORDINATION.md' % f)
        for f in FILES_V2:
            self.assertIn('`/media/app/v2/%s`' % f, doc, 'адрес v2/%s не описан в docs/COORDINATION.md' % f)
        self.assertIn('latte.mp4', doc)
        self.assertIn('права не проверены', doc, 'latte.mp4 v2 — пометка «права не проверены»')

    def test_documented_menu_media(self):
        doc = read('docs', 'COORDINATION.md')
        sec = doc[doc.index('### Список медиа меню'):doc.index('## Журнал приёмки')]
        self.assertIn('`%s%s`' % (MM_BASE, MENU_MEDIA), sec, 'постоянный адрес menu-media.json не описан')
        self.assertIn('check.py', sec)
        self.assertIn('под тем же именем никогда не перезаписывается', sec, 'правило «не перезаписывать под тем же именем» не описано')
        self.assertIn('Polish', sec, 'Cloudflare Polish для /media/app/* — решение владельца, отметка в docs')

    def check_documented(self, ver, files, posters, licenses):
        # таблица папки — одна строка на файл: адрес, лицензия (обложка — как у её ролика), заметка
        doc = read('docs', 'COORDINATION.md')
        rows = {}
        for line in doc.splitlines():
            m = re.match(r'\| `/media/app/%s/([^`]+)` \|' % ver, line)
            if m:
                self.assertNotIn(m.group(1), rows, '%s/%s описан в таблице дважды' % (ver, m.group(1)))
                rows[m.group(1)] = line
        self.assertEqual(sorted(rows), sorted(files + posters + ['manifest.json']), 'таблица %s: по строке на каждый файл папки' % ver)
        for f, lic in licenses.items():
            for name in (f, f[:-4] + '-poster.jpg'):
                self.assertIn(DOC_LICENSE[lic], rows[name], '%s/%s: в таблице не та лицензия (нужна %s)' % (ver, name, DOC_LICENSE[lic]))
        for url in LICENSE_URL.values():
            self.assertIn(url, doc)

    def test_documented_v3(self):
        self.check_documented('v3', FILES_V3, POSTERS_V3, LICENSE_V3)

    def test_documented_v4(self):
        self.check_documented('v4', FILES_V4, POSTERS_V4, LICENSE_V4)
        doc = read('docs', 'COORDINATION.md')
        self.assertIn('### v4 — `/media/app/v4/` (09.11.2026)', doc, 'подраздел v4 в docs/COORDINATION.md')
        self.assertIn('слишком сжатые, пиксельные', doc, 'причина v4 — слова владельца о v3')


if __name__ == '__main__':
    unittest.main()
