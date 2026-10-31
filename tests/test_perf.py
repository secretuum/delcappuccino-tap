"""Проверка производительности главной страницы без браузера.

Запуск из корня репозитория:
    python3 -m unittest tests.test_perf -v          # проверки
    python3 tests/test_perf.py [путь/к/странице]     # отчёт о весе первого экрана (по умолчанию все PAGES)

Что считаем «первым экраном»: HTML (в gzip, как отдаёт GitHub Pages) + файлы из <link rel=preload>
+ внешние render-blocking CSS/скрипты в <head> (чужой домен — вес неизвестен, считаем по справочнику ниже)
+ все <img> без loading="lazy" — для каждого берётся кандидат из srcset, который выбрал бы браузер
при заданной ширине окна и плотности (sizes разбирается упрощённо: (max|min-width:Npx) → Npx | Nvw | calc(100vw - Npx)).
Два сценария: телефон 390px @2x и десктоп 1366px @1x.

Остальные проверки: у каждого статического <img> есть width/height и файлы из src/srcset существуют;
sw.js разбирается как JavaScript (esprima, если установлен, иначе проверка скобок/строк);
manifest.webmanifest — валидный JSON с существующими иконками; есть .nojekyll;
версия кэша в sw.js соответствует хэшу index.html (tools/sw_version.py) — иначе предупреждение.
Стратегия sw.js (TestServiceWorkerStrategy): страницы, HTML и menu/cards.json — сначала сеть с тайм-аутом, офлайн — из
кэша; картинки — из кэша с обновлением в фоне; ассеты с хэшем — только кэш. Поведение гоняется в node (если он есть).
"""
import glob, gzip, hashlib, json, os, re, shutil, subprocess, sys, tempfile, unittest
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, 'index.html')
PAGES = ['index.html', '404.html', 'ugolok/index.html']   # все страницы сайта с одинаковым критическим путём
FIRST_SCREEN_LIMIT = 300 * 1024          # цель: первый экран ≤ 300 КБ

# Вес внешних render-blocking ресурсов, которые нельзя измерить локально (типичные значения, gzip).
EXTERNAL_WEIGHT = {
    'fonts.googleapis.com': 4 * 1024 + 9 * 14 * 1024,   # CSS + ~9 woff2 (latin+cyrillic для первого экрана)
    'googletagmanager.com': 110 * 1024,
}

SCENARIOS = {'mobile 390px @2x': (390, 2.0), 'desktop 1366px @1x': (1366, 1.0)}


class Page(HTMLParser):
    """Собирает <img>, <link>, <script> из HTML (всё, что внутри <script>/<style>, не разбирается)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.imgs, self.links, self.scripts, self.videos, self.sources = [], [], [], [], []
        self.in_head = False
        self._skip = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'head':
            self.in_head = True
        elif tag == 'img':
            a['_line'] = self.getpos()[0]
            self.imgs.append(a)
        elif tag == 'link':
            a['_head'] = self.in_head
            self.links.append(a)
        elif tag == 'script':
            a['_head'] = self.in_head
            self.scripts.append(a)
        elif tag == 'video':
            a['_line'] = self.getpos()[0]
            self.videos.append(a)
        elif tag == 'source':
            self.sources.append(a)

    def handle_endtag(self, tag):
        if tag == 'head':
            self.in_head = False


def parse(path=INDEX):
    with open(path, encoding='utf-8') as f:
        html = f.read()
    p = Page()
    p.feed(html)
    return html, p


def local(url):
    """Локальный путь для относительного URL страницы (или None для внешних/data:)."""
    if not url or re.match(r'^(https?:)?//|^data:|^mailto:|^tel:', url):
        return None
    url = url.split('?')[0].split('#')[0]
    return os.path.join(ROOT, url.lstrip('/'))


def size_of(url):
    path = local(url)
    return os.path.getsize(path) if path and os.path.isfile(path) else None


def parse_srcset(srcset):
    out = []
    for part in srcset.split(','):
        bits = part.strip().split()
        if not bits:
            continue
        w = None
        if len(bits) > 1 and bits[1].endswith('w'):
            w = int(bits[1][:-1])
        out.append((bits[0], w))
    return out


def eval_length(expr, vw):
    expr = expr.strip()
    m = re.match(r'^calc\(\s*100vw\s*-\s*(\d+(?:\.\d+)?)px\s*\)$', expr)
    if m:
        return vw - float(m.group(1))
    m = re.match(r'^(\d+(?:\.\d+)?)px$', expr)
    if m:
        return float(m.group(1))
    m = re.match(r'^(\d+(?:\.\d+)?)vw$', expr)
    if m:
        return vw * float(m.group(1)) / 100
    return vw  # неизвестная запись — считаем во всю ширину


def eval_sizes(sizes, vw):
    """Ширина отображения в CSS-пикселях по атрибуту sizes для окна шириной vw."""
    if not sizes:
        return vw
    for item in sizes.split(','):
        item = item.strip()
        m = re.match(r'^\((.*?)\)\s+(.+)$', item)
        if not m:
            return eval_length(item, vw)
        cond_ok = True
        for cond in re.split(r'\)\s*and\s*\(', m.group(1)):
            cm = re.match(r'^(max|min)-width:\s*(\d+(?:\.\d+)?)px$', cond.strip())
            if not cm:
                cond_ok = False
                break
            if cm.group(1) == 'max' and vw > float(cm.group(2)):
                cond_ok = False
            if cm.group(1) == 'min' and vw < float(cm.group(2)):
                cond_ok = False
        if cond_ok:
            return eval_length(m.group(2), vw)
    return vw


def pick_candidate(img, vw, dpr):
    """Файл, который выберет браузер: наименьший кандидат с шириной ≥ ширина отображения × dpr."""
    srcset = img.get('srcset')
    if not srcset:
        return img.get('src')
    cands = parse_srcset(srcset)
    if any(w is None for _, w in cands):
        return cands[0][0]
    need = eval_sizes(img.get('sizes'), vw) * dpr
    fitting = [c for c in cands if c[1] >= need]
    return (min(fitting, key=lambda c: c[1]) if fitting else max(cands, key=lambda c: c[1]))[0]


def first_screen(html, page, vw, dpr):
    """Список (описание, байты) ресурсов первого экрана."""
    items = [('index.html (gzip)', len(gzip.compress(html.encode('utf-8'), 9)))]
    for l in page.links:
        rel = (l.get('rel') or '').lower()
        href = l.get('href', '')
        if rel == 'preload':
            s = size_of(href)
            items.append(('preload ' + href, s if s is not None else 0))
        elif rel == 'stylesheet' and local(href) is None:
            host = re.sub(r'^(https?:)?//', '', href).split('/')[0]
            items.append(('external css ' + host, EXTERNAL_WEIGHT.get(host, 50 * 1024)))
    for s in page.scripts:
        src = s.get('src')
        if src and s.get('_head') and local(src) is None and 'defer' not in s:
            host = re.sub(r'^(https?:)?//', '', src).split('/')[0]
            items.append(('head script ' + host, EXTERNAL_WEIGHT.get(host, 50 * 1024)))
    for img in page.imgs:
        if (img.get('loading') or '').lower() == 'lazy':
            continue
        url = pick_candidate(img, vw, dpr)
        s = size_of(url)
        items.append(('img ' + (url or '?'), s if s is not None else 0))
    return items


def report(path=INDEX):
    html, page = parse(path)
    print('Страница:', os.path.relpath(path, ROOT), '—', len(html.encode('utf-8')) // 1024, 'КБ raw')
    for name, (vw, dpr) in SCENARIOS.items():
        items = first_screen(html, page, vw, dpr)
        total = sum(b for _, b in items)
        print(f'\n[{name}] первый экран: {total / 1024:.0f} КБ')
        for d, b in items:
            print(f'  {b / 1024:7.1f} КБ  {d}')
    print()


def js_syntax_error(src):
    """None, если sw.js разбирается; иначе строка с ошибкой. esprima — если установлен, иначе баланс скобок."""
    try:
        import esprima  # type: ignore
        try:
            esprima.parseScript(src)
            return None
        except Exception as e:  # esprima.Error
            return 'esprima: %s' % e
    except ImportError:
        pass
    # Запасной вариант: снимаем строки и комментарии, проверяем парность скобок.
    i, n, stack = 0, len(src), []
    pairs = {')': '(', ']': '[', '}': '{'}
    line = 1
    while i < n:
        c = src[i]
        if c == '\n':
            line += 1
        if c in '\'"`':
            q, j = c, i + 1
            while j < n and src[j] != q:
                if src[j] == '\\':
                    j += 1
                if src[j] == '\n':
                    if q != '`':
                        return 'незакрытая строка, строка %d' % line
                    line += 1
                j += 1
            if j >= n:
                return 'незакрытая строка, строка %d' % line
            i = j + 1
            continue
        if src.startswith('//', i):
            i = src.find('\n', i)
            i = n if i < 0 else i
            continue
        if src.startswith('/*', i):
            j = src.find('*/', i + 2)
            if j < 0:
                return 'незакрытый комментарий, строка %d' % line
            line += src.count('\n', i, j)
            i = j + 2
            continue
        if c in '([{':
            stack.append((c, line))
        elif c in ')]}':
            if not stack or stack[-1][0] != pairs[c]:
                return 'лишняя %r, строка %d' % (c, line)
            stack.pop()
        i += 1
    if stack:
        return 'незакрытая %r со строки %d' % stack[-1]
    return None


def index_hash(path=INDEX):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()[:10]


class TestFirstScreen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = {name: parse(os.path.join(ROOT, name)) for name in PAGES}
        cls.html, cls.page = cls.pages['index.html']

    def each(self):
        for name, (html, page) in self.pages.items():
            with self.subTest(page=name):
                yield html, page

    def test_first_screen_under_limit(self):
        for html, page in self.each():
            for name, (vw, dpr) in SCENARIOS.items():
                items = first_screen(html, page, vw, dpr)
                total = sum(b for _, b in items)
                self.assertLessEqual(total, FIRST_SCREEN_LIMIT,
                                     f'{name}: {total // 1024} КБ > {FIRST_SCREEN_LIMIT // 1024} КБ\n' +
                                     '\n'.join(f'  {b // 1024} КБ {d}' for d, b in items))

    def test_img_have_dimensions(self):
        for _, page in self.each():
            bad = [f"строка {i['_line']}: {i.get('src')}" for i in page.imgs
                   if not (i.get('width') and i.get('height'))]
            self.assertEqual(bad, [], 'у <img> нет width/height:\n' + '\n'.join(bad))

    def test_img_files_exist(self):
        for _, page in self.each():
            missing = []
            for img in page.imgs:
                urls = [img.get('src')] + [u for u, _ in parse_srcset(img.get('srcset', ''))]
                for u in urls:
                    p = local(u)
                    if p and not os.path.isfile(p):
                        missing.append(f"строка {img['_line']}: {u}")
            self.assertEqual(missing, [], 'файлов нет:\n' + '\n'.join(missing))

    def test_below_fold_imgs_lazy(self):
        # всё после героя — lazy + async; герой и шапка — без lazy
        lazy = [i for i in self.page.imgs if (i.get('loading') or '').lower() == 'lazy']
        self.assertTrue(lazy, 'ни одной lazy-картинки')
        for i in lazy:
            self.assertEqual((i.get('decoding') or '').lower(), 'async', f"строка {i['_line']}: lazy без decoding=async")
        self.assertTrue(any((i.get('fetchpriority') or '').lower() == 'high' for i in self.page.imgs),
                        'у героя нет fetchpriority=high')

    def test_preloads_exist(self):
        for _, page in self.each():
            for l in page.links:
                if (l.get('rel') or '').lower() == 'preload':
                    p = local(l.get('href'))
                    self.assertTrue(p and os.path.isfile(p), 'preload без файла: %s' % l.get('href'))

    def test_no_render_blocking_external(self):
        for html, page in self.each():
            for l in page.links:
                if (l.get('rel') or '').lower() == 'stylesheet':
                    self.assertIsNotNone(local(l.get('href')), 'внешний render-blocking CSS: %s' % l.get('href'))
            for s in page.scripts:
                if s.get('src') and s.get('_head') and local(s['src']) is None:
                    self.fail('внешний скрипт в <head>: %s' % s['src'])
            self.assertNotIn('fonts.googleapis.com', html, 'остались Google Fonts')
            self.assertIn('serviceWorker', html, 'нет регистрации service worker')

    def test_head_order(self):
        head = self.html.split('</head>')[0]
        pos = lambda pat: head.find(pat)
        self.assertLess(pos('charset'), pos('viewport'))
        self.assertLess(pos('viewport'), pos('rel="preload"'))
        self.assertLess(pos('rel="preload"'), pos('<style>'))
        self.assertIn('theme-color', head)
        self.assertIn('rel="manifest"', head)


def polygon_area_pct(clip):
    """Площадь clip-path: polygon(x% y%, ...) в долях бокса (формула шнурков)."""
    nums = [float(x) for x in re.findall(r'(-?\d+(?:\.\d+)?)%', clip)]
    pts = list(zip(nums[0::2], nums[1::2]))
    return abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
                   for i in range(len(pts)))) / 2 / (100 * 100)


class TestGrillPromo(unittest.TestCase):
    """Акция «Курица гриль» в hero: видео не тяжелит первый экран, в окне огня его видно ≥ 75% бокса (владелец, 19.10)."""
    VIDEO_MIN = 0.75

    @classmethod
    def setUpClass(cls):
        cls.html, cls.page = parse()
        cls.video = next((v for v in cls.page.videos if 'grill-video' in (v.get('class') or '')), None)

    def test_video_not_on_first_screen(self):
        v = self.video
        self.assertIsNotNone(v, 'нет <video class="grill-video">')
        self.assertIn(v.get('preload'), ('none', 'metadata'), 'видео должно быть preload=none|metadata')
        self.assertNotIn('autoplay', v, 'autoplay заставит грузить видео сразу — запуск через IntersectionObserver')
        for attr in ('muted', 'loop', 'playsinline', 'poster', 'width', 'height'):
            self.assertIn(attr, v, 'у видео нет ' + attr)
        poster = local(v['poster'])
        self.assertTrue(poster and os.path.isfile(poster), 'постера нет')
        self.assertLessEqual(os.path.getsize(poster), 40 * 1024, 'постер > 40 КБ')
        srcs = [x['src'] for x in self.page.sources if (x.get('src') or '').endswith('.mp4')]
        self.assertTrue(srcs, 'нет <source> mp4')
        for u in srcs:
            self.assertTrue(os.path.isfile(local(u)), 'видео нет: ' + u)
            self.assertRegex(u, r'\.[0-9a-f]{8}\.mp4$', 'имя видео без хэша')
        for l in self.page.links:
            if (l.get('rel') or '').lower() == 'preload':
                self.assertNotIn('.mp4', l.get('href', ''), 'видео в preload')
        with open(os.path.join(ROOT, 'sw.js'), encoding='utf-8') as f:
            sw = f.read()
        m = re.search(r'PRECACHE\s*=\s*\[(.*?)\]', sw, re.S)
        self.assertNotIn('.mp4', m.group(1), 'видео в PRECACHE sw.js')
        self.assertIn('mp4', sw.split('addEventListener(\'fetch\'')[1], 'sw.js должен пропускать видео мимо кэша')
        self.assertIn('IntersectionObserver', self.html)
        self.assertIn('prefers-reduced-motion', self.html)

    def test_fire_window_shows_video(self):
        """Огонёк — SVG с плавными кривыми, видео в окне-языке видно не меньше половины своего бокса."""
        m = re.search(r'<svg class="grill-fire"[^>]*viewBox="0 0 (\d+) (\d+)"[^>]*>(.*?)</svg>', self.html, re.S)
        self.assertIsNotNone(m, 'нет <svg class="grill-fire">')
        paths = re.findall(r'<path[^>]*\sd="([^"]+)"', m.group(3))
        self.assertGreaterEqual(len(paths), 2, 'нужны внешнее пламя и внутренний язык')
        for d in paths:
            self.assertRegex(d, r'[CQ]', 'контур пламени должен быть плавным (кривые C/Q)')
        self.assertNotIn('<image', m.group(3), 'рамка — только CSS/SVG, без растров')
        self.assertIn('#FFE500', m.group(3).upper(), 'внутри пламени нет жёлтого')
        clip = re.search(r'\.grill-win\{[^}]*clip-path:polygon\(([^)]+)\)', self.html)
        self.assertIsNotNone(clip, 'у окна .grill-win нет clip-path: polygon(...)')
        visible = polygon_area_pct(clip.group(1))
        self.assertGreaterEqual(visible, self.VIDEO_MIN, f'окно оставляет {visible:.0%} бокса видео < {self.VIDEO_MIN:.0%}')

    def test_video_layer_above_fire(self):
        """Заявка 20992 вернулась: svg лежал поверх видео. Окно с видео должно рисоваться над пламенем,
        а тикер и виньетка — внутри окна (режутся его контуром, на кремовом фоне текста нет)."""
        def z(sel):
            m = re.search(r'\n' + re.escape(sel) + r'\{([^}]*)\}', self.html)
            self.assertIsNotNone(m, 'нет правила ' + sel)
            zi = re.search(r'z-index:(-?\d+)', m.group(1))
            return int(zi.group(1)) if zi else 0
        self.assertGreater(z('.grill-win'), z('.grill-fire'), 'окно .grill-win должно быть над svg .grill-fire')
        def inner(tag_start):
            # содержимое <div …> до парного </div> (с 31.10 в окне ещё и подпись <p class="grill-cap"> — по уровню вложенности,
            # а не по отступам)
            i = self.html.index(tag_start) + len(tag_start)
            depth, j = 1, i
            while depth:
                m = re.compile(r'<div\b|</div>').search(self.html, j)
                depth += 1 if m.group(0) == '<div' else -1
                j = m.end()
            return self.html[i:m.start()]
        frame = inner('<div class="grill-frame">')
        self.assertLess(frame.index('<svg class="grill-fire"'), frame.index('<div class="grill-win">'),
                        'svg пламени должен идти в DOM раньше окна с видео')
        win = inner('<div class="grill-win">')
        # редизайн 31.10 (владелец): название, цена, адреса и кнопка «смотреть в меню» — тоже внутри окна, поверх видео
        for part in ('<video class="grill-video"', '<div class="grill-glow"', '<div class="grill-ticker"', '<p class="grill-cap">'):
            self.assertIn(part, win, part + ' должен быть внутри окна .grill-win')
        self.assertNotIn('z-index:1', re.search(r'\n\.grill-fire\{([^}]*)\}', self.html).group(1))
        glow = re.search(r'\n\.grill-glow\{([^}]*)\}', self.html).group(1)
        self.assertIn('transparent', glow, 'центр виньетки должен быть прозрачным')

    def test_ticker_seamless_and_static_on_reduced_motion(self):
        spans = re.findall(r'<div class="grill-ticker"[^>]*>(.*?)</div>', self.html, re.S)
        self.assertTrue(spans)
        parts = re.findall(r'<span>(.*?)</span>', spans[0])
        self.assertEqual(len(parts), 2, 'бесшовный повтор — два одинаковых span')
        self.assertEqual(parts[0], parts[1])
        self.assertIn('ВНИМАНИЕ', parts[0])
        self.assertRegex(self.html, r'@keyframes grill-run\{to\{transform:translateX\(-100%\)\}\}')
        self.assertRegex(self.html, r'prefers-reduced-motion:reduce\)\{\.grill-ticker span\{animation:none\}')
        ticker_css = re.search(r'\.grill-ticker\{([^}]*)\}', self.html).group(1)
        self.assertIn('color:#FFE500', ticker_css, 'бегущая строка должна быть чисто-жёлтой')
        self.assertGreaterEqual(int(re.search(r'font-weight:(\d+)', ticker_css).group(1)), 800)
        self.assertIn('text-shadow', ticker_css, 'нужно свечение, чтобы читалось на красном')


class TestServiceWorker(unittest.TestCase):
    SW = os.path.join(ROOT, 'sw.js')
    MANIFEST = os.path.join(ROOT, 'manifest.webmanifest')

    def test_sw_syntax(self):
        with open(self.SW, encoding='utf-8') as f:
            src = f.read()
        self.assertIsNone(js_syntax_error(src))

    def test_sw_precache_files_exist(self):
        with open(self.SW, encoding='utf-8') as f:
            src = f.read()
        m = re.search(r'PRECACHE\s*=\s*\[(.*?)\]', src, re.S)
        self.assertIsNotNone(m, 'в sw.js нет списка PRECACHE')
        urls = re.findall(r'[\'"]([^\'"]+)[\'"]', m.group(1))
        self.assertTrue(urls)
        for u in urls:
            if u in ('./', '/'):
                continue
            p = local(u)
            self.assertTrue(p and os.path.isfile(p), 'precache без файла: %s' % u)

    def test_sw_version_matches_index(self):
        with open(self.SW, encoding='utf-8') as f:
            src = f.read()
        m = re.search(r'VERSION\s*=\s*[\'"]([^\'"]+)[\'"]', src)
        self.assertIsNotNone(m, 'в sw.js нет VERSION')
        if m.group(1) != index_hash():
            sys.stderr.write('\nПРЕДУПРЕЖДЕНИЕ: VERSION в sw.js (%s) не совпадает с хэшем index.html (%s) — '
                             'запусти python3 tools/sw_version.py\n' % (m.group(1), index_hash()))

    def test_sw_registered(self):
        html, _ = parse()
        self.assertIn('serviceWorker', html)
        self.assertIn("register('sw.js')", html)

    def test_manifest(self):
        with open(self.MANIFEST, encoding='utf-8') as f:
            m = json.load(f)
        for k in ('name', 'short_name', 'start_url', 'display', 'theme_color', 'background_color', 'icons'):
            self.assertIn(k, m)
        self.assertEqual(m['display'], 'browser')
        sizes = set()
        for ic in m['icons']:
            p = local(ic['src'])
            self.assertTrue(p and os.path.isfile(p), 'иконки нет: %s' % ic['src'])
            sizes.add(ic['sizes'])
        self.assertTrue({'192x192', '512x512'} <= sizes, 'нужны иконки 192 и 512')
        html, _ = parse()
        theme = re.search(r'--forest:\s*(#[0-9A-Fa-f]{6})', html).group(1)
        self.assertEqual(m['theme_color'].lower(), theme.lower(), 'theme_color ≠ --forest из :root')

    def test_nojekyll(self):
        self.assertTrue(os.path.isfile(os.path.join(ROOT, '.nojekyll')))


def find_node():
    """node из PATH или из ~/.nvm (на ноутбуке владельца node только там); нет — тест поведения SW пропускается"""
    ver = lambda p: [int(x) for x in re.findall(r'\d+', p.split('/node/')[-1].split('/')[0])]   # v9 < v24 по числам, не по строке
    return shutil.which('node') or (sorted(glob.glob(os.path.expanduser('~/.nvm/versions/node/*/bin/node')), key=ver) or [None])[-1]


# Прогон sw.js в node с подставными caches / fetch / таймерами: какой ответ получает страница и что остаётся в кэше.
SW_HARNESS = r"""
const fs = require('fs'), vm = require('vm');
const ORIGIN = 'https://tap.delcappuccino.kz';
const tick = () => new Promise(r => setImmediate(r));
class Res { constructor(body, status) { this.body = body; this.status = status || 200; this.ok = this.status >= 200 && this.status < 300; }
  clone() { return new Res(this.body, this.status); } static error() { return { error: true }; } }
function setup(state) {
  const store = {}, handlers = {}, timers = [], fetches = [];
  const norm = k => new URL(k, ORIGIN + '/').href;               // как Cache API: './' и ORIGIN + '/' — один ключ
  const cacheObj = name => (store[name] = store[name] || new Map(), {
    match: k => Promise.resolve(store[name].get(norm(k))), put: (k, r) => (store[name].set(norm(k), r), Promise.resolve()) });
  const ctx = { console, URL, Promise, Response: Res, Request: function (u, o) { return { url: new URL(u, ORIGIN).href, mode: 'cors' }; },
    setTimeout: fn => timers.push(fn), caches: { open: n => Promise.resolve(cacheObj(n)), keys: () => Promise.resolve(Object.keys(store)),
      delete: n => Promise.resolve(delete store[n]) },
    fetch: req => { fetches.push(req.url); return state.net(req.url); } };
  ctx.self = { location: { origin: ORIGIN }, addEventListener: (t, f) => handlers[t] = f, skipWaiting() {}, clients: { claim() {} } };
  vm.createContext(ctx); vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), ctx);
  const SHELL = vm.runInContext('SHELL', ctx), RT = vm.runInContext('RT', ctx);
  return { store, handlers, timers, fetches, SHELL, RT, put: (n, k, body) => cacheObj(n).put(k, new Res(body)) };
}
async function run(name, { url, mode, cache, net, slow }) {   // net: {body, status} | 'offline'; slow — сеть ответит после тайм-аута
  let release;
  const state = { net: () => net === 'offline' ? Promise.reject(new TypeError('offline'))
    : slow ? new Promise(r => release = () => r(new Res(net.body, net.status))) : Promise.resolve(new Res(net.body, net.status)) };
  const sw = setup(state);
  for (const [n, k, body] of cache) await sw.put(n === 'SHELL' ? sw.SHELL : sw.RT, k, body);
  // как в браузере: waitUntil после того, как ответ отдан и других ожиданий нет, — InvalidStateError
  const ev = { request: { url: ORIGIN + url, mode, method: 'GET', headers: { get: () => null } }, waits: [], pending: 0, settled: false,
    respondWith(p) { this.resp = p; this.pending++; p.finally(() => { this.pending--; this.settled = true; }); },
    waitUntil(p) { if (this.settled && !this.pending) throw new Error('InvalidStateError'); this.pending++; this.waits.push(p);
                   p.finally(() => this.pending--); } };
  sw.handlers.fetch(ev);
  if (!ev.resp) return { name, passthrough: true, fetched: sw.fetches.length, waits: ev.waits.length };   // мимо SW — в сеть сам браузер
  let answered = null; ev.resp.then(r => answered = r);
  for (let i = 0; i < 20; i++) await tick();
  const beforeTimer = answered;
  sw.timers.forEach(f => f());                                   // прошло NET_TIMEOUT
  for (let i = 0; i < 20; i++) await tick();
  if (!answered && release) release();                           // в кэше не было — сеть отвечает позже
  const res = await ev.resp;
  if (release) release();
  await Promise.all(ev.waits.map(p => p.catch(() => {})));       // кэш снимаем сразу после ожиданий, без лишних тактов:
  const dump = {}; for (const n of [sw.SHELL, sw.RT]) for (const [k, v] of (sw.store[n] || new Map())) dump[k] = v.body;
  return { name, body: res && res.body, status: res && res.status, error: !!(res && res.error), fetched: sw.fetches.length,
           answered_before_timeout: !!beforeTimer, waits: ev.waits.length, cache: dump };
}
(async () => {
  const S = 'SHELL', R = 'RT', fresh = { body: 'new' };
  const out = await Promise.all([
    run('nav_fresh', { url: '/', mode: 'navigate', cache: [[S, './', 'old']], net: fresh }),
    run('nav_offline', { url: '/', mode: 'navigate', cache: [[S, './', 'old']], net: 'offline' }),
    run('nav_slow', { url: '/kk/', mode: 'navigate', cache: [[S, ORIGIN + '/kk/', 'old']], net: fresh, slow: true }),
    run('nav_offline_uncached', { url: '/en/', mode: 'navigate', cache: [[S, './', 'home']], net: 'offline' }),
    run('nav_404', { url: '/nope', mode: 'navigate', cache: [], net: { body: 'nf', status: 404 } }),
    run('nav_5xx_cached', { url: '/kk/', mode: 'navigate', cache: [[S, ORIGIN + '/kk/', 'old']], net: { body: 'bad', status: 502 } }),
    run('nav_5xx_uncached', { url: '/x', mode: 'navigate', cache: [], net: { body: 'bad', status: 502 } }),
    run('nav_slow_uncached', { url: '/en/', mode: 'navigate', cache: [], net: fresh, slow: true }),
    run('json_offline_uncached', { url: '/menu/cards.json', mode: 'cors', cache: [], net: 'offline' }),
    run('cards_json', { url: '/menu/cards.json', mode: 'cors', cache: [[S, ORIGIN + '/menu/cards.json', 'old']], net: fresh }),
    run('image_swr', { url: '/img/menu/a.webp', mode: 'no-cors', cache: [[R, ORIGIN + '/img/menu/a.webp', 'old']], net: fresh }),
    run('hashed', { url: '/assets/x.1a2b3c4d.webp', mode: 'no-cors', cache: [[R, ORIGIN + '/assets/x.1a2b3c4d.webp', 'old']], net: fresh }),
    run('legal_nav', { url: '/legal/offer.html', mode: 'navigate', cache: [[S, ORIGIN + '/legal/offer.html', 'old']], net: fresh }),
    run('legal_css', { url: '/legal/style.css', mode: 'no-cors', cache: [[R, ORIGIN + '/legal/style.css', 'old']], net: fresh }),
  ]);
  console.log(JSON.stringify(out));
})();
"""


class TestServiceWorkerStrategy(unittest.TestCase):
    """sw.js: страницы, HTML и menu/cards.json — сначала сеть (тайм-аут NET_TIMEOUT), офлайн — из кэша; картинки — из кэша
    с обновлением в фоне; ассеты с хэшем — только кэш. Раньше страницы шли stale-while-revalidate: после выкладки все,
    кто уже заходил, видели прошлую версию (23.10.2026)."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, 'sw.js'), encoding='utf-8') as f:
            cls.src = f.read()
        node = find_node()
        cls.res = None
        if node:
            with tempfile.TemporaryDirectory() as d:
                h = os.path.join(d, 'harness.js')
                with open(h, 'w', encoding='utf-8') as f:
                    f.write(SW_HARNESS)
                out = subprocess.run([node, h, os.path.join(ROOT, 'sw.js')], capture_output=True, text=True, timeout=60)
                if out.returncode or not out.stdout.strip():
                    raise AssertionError('стенд sw.js упал или завис (ответ не пришёл ни из сети, ни из кэша): '
                                         + (out.stderr[-2000:] or 'пустой вывод'))
                cls.res = {r['name']: r for r in json.loads(out.stdout)}

    def test_navigation_routed_network_first(self):
        # без node: в обработчике fetch навигация и оболочка идут в networkFirst, а он начинает с fetch(req)
        fetch_handler = self.src[self.src.index("self.addEventListener('fetch'"):]
        self.assertRegex(fetch_handler, r"req\.mode === 'navigate' \|\| isShell\(url\)[^}]*networkFirst\(")
        nf = re.search(r'function networkFirst\([^)]*\) \{(.*?)\n\}', self.src, re.S)
        self.assertIsNotNone(nf, 'в sw.js нет function networkFirst(...)')
        nf = nf.group(1)
        self.assertLess(nf.index('fetch(req)'), nf.index('c.match(key)'), 'networkFirst: сначала сеть, потом кэш')
        self.assertRegex(self.src, r'var NET_TIMEOUT = \d{3,5};')

    def need(self):
        if self.res is None:
            self.skipTest('нет node — поведение sw.js не прогнать (статическая проверка выше всё равно идёт)')

    def test_navigation_network_first(self):
        self.need()
        r = self.res['nav_fresh']
        self.assertEqual((r['body'], r['fetched']), ('new', 1), 'страница — свежая из сети, не прошлая из кэша')
        self.assertEqual(r['cache']['https://tap.delcappuccino.kz/'], 'new', 'свежая страница записана в кэш')
        self.assertTrue(r['answered_before_timeout'])

    def test_offline_from_cache(self):
        self.need()
        self.assertEqual(self.res['nav_offline']['body'], 'old', 'без сети — страница из кэша')
        self.assertEqual(self.res['nav_offline_uncached']['body'], 'home', 'страницы нет в кэше — главная из кэша')

    def test_slow_network_falls_back_after_timeout(self):
        self.need()
        r = self.res['nav_slow']
        self.assertFalse(r['answered_before_timeout'], 'до тайм-аута ждём сеть')
        self.assertEqual(r['body'], 'old', 'после тайм-аута — из кэша')
        self.assertEqual(r['cache']['https://tap.delcappuccino.kz/kk/'], 'new', 'запоздавший ответ сети дописан в кэш')
        self.assertGreater(r['waits'], 0, 'запись в кэш продлевает жизнь события (waitUntil)')
        r = self.res['nav_slow_uncached']
        self.assertEqual(r['body'], 'new', 'в кэше нет — ждём сеть и после тайм-аута')

    def test_errors_not_cached(self):
        self.need()
        r = self.res['nav_404']
        self.assertEqual(r['status'], 404)
        self.assertEqual(r['cache'], {}, 'ответы не 2xx в кэш не попадают')
        self.assertEqual(self.res['nav_5xx_cached']['body'], 'old', 'сбой хостинга (5xx) при живом кэше — из кэша')
        r = self.res['nav_5xx_uncached']
        self.assertEqual((r['status'], r['cache']), (502, {}), '5xx без кэша — как есть, и не в кэш')
        self.assertTrue(self.res['json_offline_uncached']['error'], 'офлайн, не страница и нет в кэше — сетевая ошибка')

    def test_cards_json_network_first(self):
        self.need()
        self.assertEqual(self.res['cards_json']['body'], 'new', 'menu/cards.json — свежий из сети')

    def test_images_and_hashed_unchanged(self):
        self.need()
        r = self.res['image_swr']
        self.assertEqual((r['body'], r['fetched']), ('old', 1), 'картинка — из кэша, обновление в фоне')
        self.assertEqual(r['cache']['https://tap.delcappuccino.kz/img/menu/a.webp'], 'new')
        r = self.res['hashed']
        self.assertEqual((r['body'], r['fetched']), ('old', 0), 'файл с хэшем в имени — только кэш, без сети')

    def test_legal_not_intercepted(self):
        # /legal/ (оферта, политика, контакты приложения, 30.10.2026) — мимо SW: без respondWith, не из кэша и не в кэш
        self.need()
        for name in ('legal_nav', 'legal_css'):
            r = self.res[name]
            self.assertTrue(r.get('passthrough'), '%s: /legal/ не перехватывается (fetch-обработчик выходит без respondWith)' % name)
            self.assertEqual((r['fetched'], r['waits']), (0, 0), '%s: SW сам не ходит в сеть и не пишет в кэш' % name)
        self.assertFalse(self.res['nav_fresh'].get('passthrough'), 'обычные страницы SW по-прежнему перехватывает')


if __name__ == '__main__':
    for arg in (sys.argv[1:] or PAGES):
        report(os.path.join(ROOT, arg) if not os.path.isabs(arg) else arg)
