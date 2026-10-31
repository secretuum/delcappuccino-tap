"""Редизайн под мобильное приложение del Cappuccino (тема v5), этап 1 — главные /, /kk/, /en/ (решение владельца 31.10.2026).
Токены v5 в одном :root; шрифт — только через --font-display (Geologica 700) и --font-body (Montserrat 400–700), прежние
Comfortaa, Golos Text и Cormorant главные не грузят; заставка «мопед въезжает в логотип» — раз за сессию, не при
reduced-motion, без JS страница видна сразу; витрина меню (чипы, подборки, плашка подписки «скоро в App Store и Google
Play» без ссылок) собирается tools/seo_jsonld.py; для поиска и аналитики всё на месте (h1, JSON-LD, hreflang, .f-legal).
Поведение скриптов (заставка, чипы, ?at=, пилюля точки) гоняется в node на заглушке DOM, если node есть.
Запуск из корня репозитория: python3 -m unittest discover -s tests -v"""
import glob, gzip, json, os, re, shutil, struct, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import seo_jsonld as seo  # noqa: E402

PAGES = {'ru': 'index.html', 'kk': 'kk/index.html', 'en': 'en/index.html'}
V5 = {   # app/src/theme/v5.ts
    '--c-bg': '#FFFFFF', '--c-surface': '#FEF1E7', '--c-raised': '#F7E7D8', '--c-border': 'rgba(66,99,73,.18)',
    '--c-text': '#241C15', '--c-muted': '#5C5245', '--c-accent': '#426349', '--c-accent-dk': '#31492F',
    '--c-olive': '#849E29', '--c-on-olive': '#1D2408', '--c-danger': '#C2140F', '--c-scrim': 'rgba(36,28,21,.4)',
    '--c-glass': 'rgba(254,241,231,.92)',
    '--r-sm': '12px', '--r-md': '16px', '--r-lg': '22px', '--r-pill': '999px',
    '--s-2': '2px', '--s-4': '4px', '--s-8': '8px', '--s-12': '12px', '--s-16': '16px', '--s-24': '24px', '--s-32': '32px',
    '--fs-caption': '12px', '--fs-small': '14px', '--fs-body': '16px', '--fs-title': '22px', '--fs-heading': '28px',
    '--h-button': '56px', '--h-touch': '48px', '--shadow-floating': '0 6px 24px rgba(49,73,47,.16)',
}
OLD_FONTS = r'Comfortaa|Golos|Cormorant'
KAZAKH = 'әғқңөұүһіӘҒҚҢӨҰҮҺІ'


def read(p):
    with open(os.path.join(ROOT, p), encoding='utf-8') as f:
        return f.read()


def style(html):
    """текст <style> без переводов строк (на /kk/ и /en/ генератор раскладывает @media по строкам)"""
    return re.sub(r'\s*\n\s*', '', re.search(r'<style>\n(.*?)</style>', html, re.S).group(1))


def root_vars(html):
    return dict(re.findall(r'(--[\w-]+):\s*([^;]+?)\s*;', re.search(r':root\{(.*?)\}', style(html), re.S).group(1)))


def find_node():
    ver = lambda p: [int(x) for x in re.findall(r'\d+', p.split('/node/')[-1].split('/')[0])]
    return shutil.which('node') or (sorted(glob.glob(os.path.expanduser('~/.nvm/versions/node/*/bin/node')), key=ver) or [None])[-1]


class TestTokensAndFonts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = {l: read(p) for l, p in PAGES.items()}

    def test_v5_tokens_on_all_three(self):
        for l, html in self.pages.items():
            v = root_vars(html)
            for k, want in V5.items():
                self.assertEqual(v.get(k), want, '%s: токен %s' % (l, k))
            self.assertEqual(style(html).count(':root{'), 1, '%s: токены — в одном :root' % l)
            # прежние имена (оверлей меню) равны токенам; --forest и --sale записаны числом ради manifest и теста скидки
            self.assertEqual(v['--forest'], V5['--c-accent'])
            self.assertEqual(v['--sale'], V5['--c-danger'])

    def test_font_only_through_two_variables(self):
        for l, html in self.pages.items():
            v = root_vars(html)
            self.assertTrue(v['--font-display'].startswith("'Geologica'"), l)
            self.assertTrue(v['--font-body'].startswith("'Montserrat'"), l)
            css = re.sub(r'@font-face\{[^}]*\}', '', re.sub(r'/\*.*?\*/', '', style(html), flags=re.S))
            fams = re.findall(r'font-family:\s*([^;}]+)', css)
            self.assertTrue(fams)
            for f in fams:
                self.assertIn(f.strip(), ('var(--font-display)', 'var(--font-body)'), '%s: font-family:%s — только через переменные' % (l, f))
            for f in re.findall(r'(?<![\w-])font:\s*([^;}]+)', css):
                self.assertRegex(f, r'^(inherit|[\d./a-z ]+var\(--font-body\))$', '%s: font:%s' % (l, f))
            self.assertEqual(sorted(set(re.findall(r"@font-face\{font-family:'([^']+)'", html))), ['Geologica', 'Montserrat'], l)

    def test_old_fonts_not_loaded(self):
        for l, html in self.pages.items():
            self.assertNotRegex(html, OLD_FONTS, '%s: Comfortaa, Golos и Cormorant главные не грузят' % l)
        head = self.pages['ru'].split('</head>')[0]
        pre = re.findall(r'<link rel="preload" href="([^"]+)"', head)
        self.assertEqual(sorted(os.path.basename(p).split('-')[0] for p in pre), ['geologica', 'montserrat'])
        for p in pre:
            self.assertTrue(os.path.isfile(os.path.join(ROOT, p)), p)
        sw = read('sw.js')
        self.assertNotRegex(re.search(r'PRECACHE\s*=\s*\[(.*?)\]', sw, re.S).group(1), OLD_FONTS, 'sw.js не тянет старые шрифты')

    def test_kazakh_and_tenge_subsets(self):
        for l, html in self.pages.items():
            for fam in ('Geologica', 'Montserrat'):
                faces = re.findall(r"@font-face\{font-family:'%s'[^}]*\}" % fam, html)
                ranges = ' '.join(re.findall(r'unicode-range:([^;}]+)', ' '.join(faces)))
                for need in ('U+0460-052F', 'U+0400-045F', 'U+20B8'):     # cyrillic-ext (ә ғ қ ң ө ү һ), cyrillic (і ұ), ₸
                    self.assertIn(need, ranges, '%s: %s без %s' % (l, fam, need))
                for src in re.findall(r'url\(([^)]+)\)', ' '.join(faces)):
                    self.assertTrue(os.path.isfile(os.path.join(ROOT, src.lstrip('/'))), src)

    def test_font_files_have_kazakh_letters_and_tenge(self):
        try:
            import brotli  # noqa: F401
        except ImportError:
            self.skipTest('нет модуля brotli — woff2 не распаковать')
        html = self.pages['kk']
        for fam in ('Geologica', 'Montserrat'):
            files = [os.path.join(ROOT, u.lstrip('/')) for u in re.findall(r"@font-face\{font-family:'%s'[^}]*url\(([^)]+)\)" % fam, html)]
            have = set()
            for f in files:
                have |= woff2_cmap(f, [ord(ch) for ch in KAZAKH + '₸'])
            missing = ''.join(ch for ch in KAZAKH + '₸' if ord(ch) not in have)
            self.assertEqual(missing, '', '%s: нет глифов %s' % (fam, missing))


def woff2_cmap(path, cps):
    """кодовые точки из cps, которые есть в cmap woff2-файла (таблица cmap в woff2 не преобразуется — только сжата brotli)"""
    import brotli
    tags = ['cmap', 'head', 'hhea', 'hmtx', 'maxp', 'name', 'OS/2', 'post', 'cvt ', 'fpgm', 'glyf', 'loca', 'prep', 'CFF ', 'VORG', 'EBDT',
            'EBLC', 'gasp', 'hdmx', 'kern', 'LTSH', 'PCLT', 'VDMX', 'vhea', 'vmtx', 'BASE', 'GDEF', 'GPOS', 'GSUB', 'EBSC', 'JSTF', 'MATH',
            'CBDT', 'CBLC', 'COLR', 'CPAL', 'SVG ', 'sbix', 'acnt', 'avar', 'bdat', 'bloc', 'bsln', 'cvar', 'fdsc', 'feat', 'fmtx', 'fvar',
            'gvar', 'hsty', 'just', 'lcar', 'mort', 'morx', 'opbd', 'prop', 'trak', 'Zapf', 'Silf', 'Glat', 'Gloc', 'Feat', 'Sill']
    d = open(path, 'rb').read()

    def b128(o):
        v = 0
        for i in range(5):
            c = d[o + i]
            v = (v << 7) | (c & 0x7f)
            if not c & 0x80:
                return v, o + i + 1
    n, comp = struct.unpack('>H', d[12:14])[0], struct.unpack('>I', d[20:24])[0]
    o, tables = 48, []
    for _ in range(n):
        flags = d[o]
        o += 1
        tag = tags[flags & 0x3f] if flags & 0x3f != 63 else d[o:o + 4].decode('latin1')
        o += 4 if flags & 0x3f == 63 else 0
        ln, o = b128(o)
        tv, tr = (flags >> 6) & 3, ln
        if (tag in ('glyf', 'loca') and tv == 0) or (tag not in ('glyf', 'loca') and tv != 0):
            tr, o = b128(o)
        tables.append((tag, tr))
    data, off = brotli.decompress(d[o:o + comp]), 0
    for tag, tr in tables:
        if tag == 'cmap':
            cm = data[off:off + tr]
            break
        off += tr
    found = set()
    for i in range(struct.unpack('>H', cm[2:4])[0]):
        _, _, so = struct.unpack('>HHI', cm[4 + 8 * i:12 + 8 * i])
        fmt = struct.unpack('>H', cm[so:so + 2])[0]
        if fmt == 4:
            seg = struct.unpack('>H', cm[so + 6:so + 8])[0] // 2
            ends = struct.unpack('>%dH' % seg, cm[so + 14:so + 14 + 2 * seg])
            starts = struct.unpack('>%dH' % seg, cm[so + 16 + 2 * seg:so + 16 + 4 * seg])
            found |= {cp for cp in cps for a, b in zip(starts, ends) if a <= cp <= b}
        elif fmt == 12:
            for g in range(struct.unpack('>I', cm[so + 12:so + 16])[0]):
                a, b, _ = struct.unpack('>III', cm[so + 16 + 12 * g:so + 28 + 12 * g])
                found |= {cp for cp in cps if a <= cp <= b}
    return found


class TestIntro(unittest.TestCase):
    """заставка: мопед въезжает в логотип — раз за сессию, ≤ 1,5 с, не при reduced-motion, без JS её нет"""

    @classmethod
    def setUpClass(cls):
        cls.pages = {l: read(p) for l, p in PAGES.items()}
        cls.js = seo.INTRO_RE.search(cls.pages['ru'].split('</head>')[0]).group(0)

    def test_same_script_in_head_of_three(self):
        for l, html in self.pages.items():
            head = html.split('</head>')[0]
            self.assertEqual(head.count(self.js), 1, l)
            self.assertLess(head.index(self.js), head.index('<style>'), '%s: класс ставится до отрисовки — без мелькания' % l)

    def test_reduced_motion_and_storage_in_try(self):
        js = self.js
        self.assertRegex(js, r"^<script>\(function\(\)\{try\{.*\}catch\(e\)\{\}\}\)\(\);</script>$", 'всё — внутри try/catch')
        self.assertIn("matchMedia('(prefers-reduced-motion: reduce)').matches", js)
        self.assertIn("sessionStorage.getItem('dc_intro')", js)
        self.assertLess(js.index('reduced-motion'), js.index("classList.add('intro-on')"))
        delay = int(re.search(r"classList\.remove\('intro-on'\)\},(\d+)\)", js).group(1))
        self.assertLessEqual(delay, 1500, 'заставка не дольше 1,5 с')

    def test_css_hidden_without_js_and_on_reduced_motion(self):
        for l, html in self.pages.items():
            css = style(html)
            self.assertIn('.intro{display:none}', css, '%s: без класса (нет JS, повторный заход) заставки нет' % l)
            self.assertIn('@media(prefers-reduced-motion:reduce){.intro{display:none!important}}', css, l)
            self.assertIn('pointer-events:none', re.search(r'\.intro-on \.intro\{([^}]*)\}', css).group(1), '%s: клики проходят' % l)
            out = re.search(r'animation:intro-out ([\d.]+)s ease ([\d.]+)s', css)
            self.assertLessEqual(float(out.group(1)) + float(out.group(2)), 1.5, l)
            for kf in ('moped-in', 'fade-in', 'intro-out'):
                self.assertIn('@keyframes %s{' % kf, css, l)
            # мопед и надпись — файлами с хэшем (кэш навечно), не инлайном; оба есть и не тяжёлые
            for name in ('logo-text', 'moped-side'):
                srcs = set(re.findall(r'src="/?(assets/%s\.[0-9a-f]{8}\.svg)"' % name, html))
                self.assertEqual(len(srcs), 1, '%s: %s' % (l, name))
                self.assertLessEqual(os.path.getsize(os.path.join(ROOT, srcs.pop())), 40 * 1024)
            self.assertNotIn('<path', re.sub(r'<svg class="grill-fire".*?</svg>', '', html.split('</head>')[1], flags=re.S),
                             '%s: большие SVG не инлайним' % l)

    def test_intro_behaviour_in_node(self):
        node = find_node()
        if not node:
            self.skipTest('нет node')
        js = re.search(r'<script>(.*)</script>', self.js, re.S).group(1)
        harness = r"""
const vm = require('vm'); const js = %s; const out = {};
function run(name, opts) {
  const cls = new Set(), timers = [], store = {};
  const ctx = { document: { documentElement: { classList: { add: c => cls.add(c), remove: c => cls.delete(c) } } },
    matchMedia: () => ({ matches: !!opts.reduce }), setTimeout: (f, ms) => timers.push([f, ms]) };
  if (opts.storage !== 'none') ctx.sessionStorage = opts.storage === 'throw'
    ? { getItem() { throw new Error('SecurityError'); }, setItem() { throw new Error('SecurityError'); } }
    : { getItem: k => store[k] || null, setItem: (k, v) => { store[k] = v; } };
  vm.createContext(ctx);
  const res = [];
  for (let i = 0; i < (opts.times || 1); i++) {
    vm.runInContext(js, ctx); const shown = cls.has('intro-on');
    const t = timers.splice(0); t.forEach(([f]) => f());
    res.push({ shown, timers: t.map(x => x[1]), after: cls.has('intro-on') });
  }
  out[name] = res;
}
run('first_then_second', { times: 2 });
run('reduce', { reduce: true });
run('storage_throws', { storage: 'throw' });
run('no_storage', { storage: 'none' });
console.log(JSON.stringify(out));
""" % json.dumps(js)
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, 'intro.js')
            with open(f, 'w', encoding='utf-8') as fh:
                fh.write(harness)
            r = subprocess.run([node, f], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr[-800:])
        got = json.loads(r.stdout)
        first, second = got['first_then_second']
        self.assertTrue(first['shown'] and not first['after'] and first['timers'] == [1500], first)
        self.assertFalse(second['shown'], 'второй заход за сессию — без заставки')
        for k in ('reduce', 'storage_throws', 'no_storage'):
            self.assertEqual(got[k], [{'shown': False, 'timers': [], 'after': False}], k)


class TestPageAndFeed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = {l: read(p) for l, p in PAGES.items()}
        cls.i18n = seo.i18n()

    def test_seo_and_analytics_kept(self):
        for l, html in self.pages.items():
            self.assertEqual(len(re.findall(r'<h1>', html)), 1, l)
            self.assertIn('<script type="application/ld+json">', html.split('</head>')[0], l)
            self.assertEqual(len(re.findall(r'<link rel="alternate" hreflang="(?:ru|kk|en|x-default)"', html)), 4, l)
            self.assertEqual(len(re.findall(r'<link rel="canonical"', html)), 1, l)
            self.assertIn('<meta property="og:title"', html, l)
            self.assertIn(seo.AN_MARK, html.split('</head>')[0], l)
            foot = re.search(r'<footer\b.*?</footer>', html, re.S).group(0)
            self.assertIn('<span class="f-legal"><a class="f-ugolok" href="/ugolok/" onclick="track(\'cta_ugolok\')">', foot, l)
        self.assertIn('<h1>Вкус,<br>который<br>собирает <span>близких</span>.</h1>', self.pages['ru'], 'h1 главной — прежний текст')

    def test_app_stores_soon_without_links(self):
        if any(seo.APP_LINKS.values()):
            self.skipTest('ссылки на сторы уже вписаны в APP_LINKS')
        for l, html in self.pages.items():
            f = self.i18n[l]['feed']
            sub = re.search(r'<div class="sub"><p class="sub-t">([^<]+)</p><p class="sub-s">([^<]+)</p></div>\n\s*<p class="stores">([^<]*)</p>', html)
            self.assertIsNotNone(sub, '%s: плашка подписки и подпись под ней' % l)
            self.assertEqual(sub.groups(), (f['sub_t'], f['sub_s'], f['stores_soon']), l)
            self.assertNotRegex(html, r'apps\.apple\.com|itunes\.apple|play\.google\.com|app_store', '%s: ссылок на сторы пока нет' % l)
        self.assertEqual(self.i18n['ru']['feed']['stores_soon'], 'скоро в App Store и Google Play')
        self.assertEqual(self.i18n['ru']['feed']['sub_t'], 'кофе каждый день')

    def test_chips_lead_to_sections(self):
        tabs = dict(seo.mode_tabs(self.pages['ru'])['cafe'])
        want = []
        for key, tab, title in seo.FEED_CHIPS:
            want.append((key, tab, [s['t'] for s in seo.sections(self.pages['ru'], tabs[tab])].index(title)))
        ru = re.findall(r"<a class=\"chip\" href=\"/menyu#(\w+)\" onclick=\"event\.preventDefault\(\);track\('menu_chip',\{chip:'(\w+)'\}\);"
                        r"openMenuAt\('(\w+)',(\d+)\)\">([^<]+)</a>", self.pages['ru'])
        self.assertEqual([(k, t, int(i)) for _, k, t, i, _ in ru], want)
        self.assertEqual([x[4] for x in ru], ['Кофе', 'Не кофе', 'Еда'])
        for l in ('kk', 'en'):
            got = re.findall(r'<a class="chip" href="/\?at=(\w+)\.(\d+)#menu-%s" onclick="track\(\'menu_chip\',\{chip:\'(\w+)\'\}\)">' % l, self.pages[l])
            self.assertEqual([(k, t, int(i)) for t, i, k in got], want, l)

    def test_feed_cards_from_menu_with_site_photos(self):
        items = seo.feed_items(self.pages['ru'])
        self.assertTrue(items['popular'] and items['desserts'] and items['novelties'])
        self.assertTrue(all('hit' in r[2]['m'] for r in items['popular']))
        self.assertTrue(all('new' in r[2]['m'] for r in items['novelties']))
        for l, html in self.pages.items():
            cards = re.findall(r'<a class="dish"[^>]*><img src="([^"]+)" width="\d+" height="\d+" loading="lazy" decoding="async" alt="[^"]+">', html)
            self.assertEqual(len(cards), sum(len(v) for v in items.values()), l)
            for src in cards:
                self.assertTrue(src.lstrip('/').startswith('img/menu/'), '%s: фото блюд — сайтовые: %s' % (l, src))
                self.assertTrue(os.path.isfile(os.path.join(ROOT, src.lstrip('/'))), src)
            self.assertNotRegex(html, r'class="dish"[^>]*>[^<]*\+', '%s: сайт не продаёт — без «+»' % l)
        self.assertIn('<b class="dish-n">Капучино</b><span class="dish-p"><small>200 мл · </small>1 400 ₸</span>', self.pages['ru'])

    def test_weight(self):
        sizes = {l: len(html.encode('utf-8')) for l, html in self.pages.items()}
        self.assertLessEqual(sizes['ru'], 250 * 1024, 'главная была ~215 КБ — не раздувать')
        self.assertLessEqual(len(gzip.compress(self.pages['ru'].encode('utf-8'), 9)), 64 * 1024)
        for l in ('kk', 'en'):
            self.assertLessEqual(sizes[l], 90 * 1024, l)

    def test_scripts_in_node(self):
        """чипы, ?at= с /kk/ и /en/, пилюля точки — на заглушке DOM: скрипты главной целиком, функции меню подменены записью"""
        node = find_node()
        if not node:
            self.skipTest('нет node')
        html = self.pages['ru']
        chip = next(x for x in re.findall(r'<a class="chip"[^>]*onclick="([^"]*)"', html) if "chip:'notcoffee'" in x)
        harness = r"""
const fs = require('fs'), vm = require('vm');
const { html, chip } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const scripts = [...html.matchAll(/<script(?![^>]*\bsrc=)(?![^>]*ld\+json)[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]);
function page(opts) {
  const els = {}, raf = [], listeners = {}, log = [], store = Object.assign({}, opts.store || {});
  const el = id => ({ id, innerHTML: '', textContent: '', style: { setProperty() {}, removeProperty() {} }, dataset: {}, scrollTop: 0, offsetHeight: 0,
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } }, addEventListener() {}, removeEventListener() {},
    appendChild(x) { return x; }, insertAdjacentHTML() {}, contains() { return false; }, getAttribute() { return null; }, scrollIntoView() {},
    querySelector(sel) { return (this._q = this._q || {})[sel] || (this._q[sel] = el(sel)); }, querySelectorAll() { return []; },
    getBoundingClientRect() { return { top: 0, bottom: 0 }; }, scrollTo() {}, setAttribute() {}, removeAttribute() {}, focus() {},
    closest() { return null; }, play() { return Promise.resolve(); }, pause() {} });
  const document = { getElementById: id => els[id] || (els[id] = el(id)), querySelector: () => el('q'), querySelectorAll: () => [],
    addEventListener: (t, f) => { (listeners[t] = listeners[t] || []).push(f); }, createElement: () => el('x'),
    body: el('body'), documentElement: el('html'), head: el('head'), readyState: 'loading' };
  const H = opts.utcHour == null ? 12 : opts.utcHour;
  class FakeDate extends Date { getUTCHours() { return H; } getUTCMinutes() { return 0; } }
  const ctx = { document, console, Date: FakeDate, setTimeout: () => 0, clearTimeout() {}, requestAnimationFrame: f => raf.push(f),
    requestIdleCallback: () => 0, matchMedia: () => ({ matches: false, addEventListener() {}, addListener() {} }),
    IntersectionObserver: function () { return { observe() {} }; }, fetch: () => new Promise(() => {}),
    localStorage: { getItem: k => store[k] || null, setItem: (k, v) => { store[k] = v; } }, navigator: {},
    location: { hash: opts.hash || '', pathname: '/', search: opts.search || '' },
    history: { replaceState: (a, b, u) => log.push(['replaceState', u]) }, addEventListener() {}, scrollTo() {} };
  ctx.window = ctx; vm.createContext(ctx);
  scripts.forEach(s => vm.runInContext(s, ctx));
  vm.runInContext("openMenu=function(m){__log.push(['openMenu',m===undefined?null:m])};" +
                  "setActive=function(t,i){__log.push(['setActive',t,i])};scrollToMenuEl=function(e){__log.push(['scroll',e&&e.id])}", Object.assign(ctx, { __log: log }));
  return { ctx, els, raf, listeners, log, store };
}
const out = {};
let p = page({}); p.ctx.__code = chip; vm.runInContext('(function(event){ eval(__code) })({ preventDefault() {} })', p.ctx);
p.raf.splice(0).forEach(f => f()); out.chip = p.log;
p = page({ search: '?at=bar.2', hash: '#menu-kk' }); const before = p.log.slice(); p.raf.splice(0).forEach(f => f()); out.at = p.log;
p = page({ search: '?at=bar.2', hash: '' }); p.raf.splice(0).forEach(f => f()); out.at_nohash = p.log;
for (const [name, h] of [['open', 10], ['closed', 20]]) {     // UTC 10:00 = 15:00 в Алматы, UTC 20:00 = 01:00
  p = page({ store: { dc_point: '05' }, utcHour: h }); const pill = p.els['pill-point'];
  out['pill_' + name] = [pill.querySelector('b').textContent, pill.querySelector('span').textContent];
}
p = page({});
const small = { textContent: '03 · БП Promenade' }, card = { querySelector: s => s === 'small' ? small : null };
const target = { closest: s => s === 'a,button' ? {} : (s === '.branch-row,.loc-card' ? card : null) };
p.listeners.click.forEach(f => f({ target }));
out.pill_click = [p.store.dc_point, p.els['pill-point'].querySelector('b').textContent, p.els['pill-point'].querySelector('span').textContent];
console.log(JSON.stringify(out));
"""
        with tempfile.TemporaryDirectory() as d:
            h, data = os.path.join(d, 'h.js'), os.path.join(d, 'data.json')
            with open(h, 'w', encoding='utf-8') as f:
                f.write(harness)
            with open(data, 'w', encoding='utf-8') as f:
                json.dump({'html': html, 'chip': chip.replace('&quot;', '"')}, f)
            r = subprocess.run([node, h, data], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr[-1500:])
        got = json.loads(r.stdout)
        self.assertEqual(got['chip'], [['openMenu', None], ['setActive', 'bar', 2], ['scroll', 'mm-sec-bar-2']])
        self.assertEqual(got['at'], [['replaceState', '/#menu-kk'], ['setActive', 'bar', 2], ['scroll', 'mm-sec-bar-2']])
        self.assertEqual(got['at_nohash'], [['replaceState', '/']], 'без #menu меню не открываем, ?at= убираем')
        self.assertEqual(got['pill_open'], ['Жандосова, 94/12', ' · открыто до 22:00'])
        self.assertEqual(got['pill_closed'], ['Жандосова, 94/12', ' · откроется в 07:00'])
        self.assertEqual(got['pill_click'], ['03', 'Абая, 44А', ' · открыто 24/7'])


if __name__ == '__main__':
    unittest.main()
