"""Редизайн под мобильное приложение del Cappuccino (тема v5), этап 1 — главные /, /kk/, /en/ (решение владельца 31.10.2026).
Токены v5 в одном :root; шрифт — только через --font-display (Geologica 700) и --font-body (Montserrat 400–700), прежние
Comfortaa, Golos Text и Cormorant главные не грузят; заставка «мопед въезжает в логотип» — раз за сессию, не при
reduced-motion, без JS страница видна сразу; для поиска и аналитики всё на месте (h1, JSON-LD, hreflang, .f-legal).
Правки владельца 31.10: без чипов и лент блюд, «Формат» без цифр; в блоке «акция» — карточка «кофейная подписка — скоро,
в приложении» (с 1.11 — видео налива кофе, лениво, без JS — постер); шапка оверлея меню — одна строка и пилюли.
Поведение скриптов (заставка, загрузчик видео, пилюля точки, заметка меню) гоняется в node на заглушке DOM, если node есть.
Запуск из корня репозитория: python3 -m unittest discover -s tests -v"""
import glob, gzip, json, os, re, shutil, struct, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import seo_jsonld as seo  # noqa: E402

PAGES = {'ru': 'index.html', 'kk': 'kk/index.html', 'en': 'en/index.html'}
V5 = {   # app/src/theme/v5.ts
    '--c-bg': '#FFFFFF', '--c-surface': '#F5F5F3', '--c-raised': '#ECEBE8', '--c-disabled': '#E5E3DF',   # без крема (владелец 31.10)
    '--c-border': 'rgba(66,99,73,.18)', '--c-brand-cream': '#FEF1E7', '--c-input-border': '#8C7E6E',
    '--c-text': '#241C15', '--c-muted': '#5C5245', '--c-accent': '#426349', '--c-accent-dk': '#31492F',
    '--c-olive': '#849E29', '--c-on-olive': '#1D2408', '--c-danger': '#C2140F', '--c-scrim': 'rgba(36,28,21,.4)',
    '--c-glass': 'rgba(255,255,255,.92)',
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

    def test_no_cream_in_interface(self):
        """владелец 31.10: крем (#FEF1E7, #F7E7D8) — только цвет бренда (--c-brand-cream: логотип, мопед, светлое на зелёном),
        в токенах интерфейса и в правилах его нет; manifest — белый фон"""
        cream = r'(?i)#FEF1E7|#F7E7D8|#F7EFE2|#E9DDD0|254,\s*241,\s*231'
        for l, html in self.pages.items():
            v = root_vars(html)
            ui = {k: x for k, x in v.items() if k != '--c-brand-cream'}
            self.assertEqual([k for k, x in ui.items() if re.search(cream, x)], [], '%s: крем в токенах интерфейса' % l)
            rules = re.sub(r':root\{.*?\}', '', style(html), count=1, flags=re.S)
            self.assertNotRegex(rules, cream, '%s: крем числом в правилах' % l)
            for use in re.findall(r'[^;{}]*var\(--c-brand-cream\)[^;{}]*', rules):
                sel = re.search(r'([^{}]*)\{[^{}]*' + re.escape(use), rules).group(1)
                self.assertRegex(sel, r'hero-zone|tile-cap', '%s: крем — только на зелёном (видеозона, плитка подписки): %s' % (l, use))
        self.assertEqual(json.loads(read('manifest.webmanifest'))['background_color'], '#FFFFFF')

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
            body = re.sub(r'<svg class="(?:grill-fire|icons)".*?</svg>', '', html.split('</head>')[1], flags=re.S)
            self.assertNotIn('<path', body, '%s: большие SVG не инлайним (кроме огня акции и спрайта значков кнопок)' % l)

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


class TestPage(unittest.TestCase):
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

    def test_owner_cuts_31_10(self):
        """правки владельца 31.10: без чипов и лент блюд, «Формат» без цифр и надзаголовка; кнопки hero остаются"""
        for l, html in self.pages.items():
            self.assertNotRegex(html, r'class="(?:chips?|rail[^"]*|dish|feed[^"]*)"', '%s: чипов и лент блюд нет' % l)
            self.assertNotRegex(html, r'openMenuAt|[?&]at=|menu_chip|menu_pick', l)
            feats = re.search(r'<section class="features" id="features">(.*?)</section>', html, re.S).group(1)
            self.assertNotIn('<p class="tag">', feats, '%s: без надзаголовка «больше, чем кофейня»' % l)
            self.assertNotRegex(feats, r'<b>\d+</b>', '%s: без цифр 01–06' % l)
            self.assertEqual(len(re.findall(r'<article><h3>', feats)), 6, l)
            actions = re.search(r'<div class="actions">(.*?)</div>', html, re.S).group(1)
            for ev in ('cta_book', 'cta_order', 'cta_menu'):
                self.assertIn("track('%s')" % ev, actions, l)
        self.assertNotIn('больше, чем кофейня', self.pages['ru'])

    def test_subscription_card_soon_without_links(self):
        if any(seo.APP_LINKS.values()):
            self.skipTest('ссылки на сторы уже вписаны в APP_LINKS')
        for l, html in self.pages.items():
            S = self.i18n[l]['sub']
            promo = re.search(r'<section class="promo shell"[^>]*>(.*?)</section>', html, re.S)
            self.assertIsNotNone(promo, '%s: блок акции' % l)
            card = re.search(r'<div class="promo-tile sub-tile">(.*?)\n    </div>', promo.group(1), re.S)
            self.assertIsNotNone(card, '%s: плитка подписки — в блоке акций' % l)
            self.assertIn('<p class="tile-cap"><b class="promo-t">%s</b> <span class="promo-s">%s</span></p>' % (S['title'], S['soon']), card.group(1), l)
            self.assertNotRegex(html, r'apps\.apple\.com|itunes\.apple|play\.google\.com|app_store', '%s: ссылок на сторы пока нет' % l)
            self.assertEqual(html.count('sub-tile"'), 1, '%s: подписка — один раз' % l)
            self.assertNotRegex(html, r'class="sub"|кофе каждый день|30 чашек|күн сайын кофе|coffee every day', '%s: отдельной плашки нет' % l)
        self.assertEqual((self.i18n['ru']['sub']['title'], self.i18n['ru']['sub']['soon']), ('кофейная подписка', 'скоро, в приложении'))
        promo = re.search(r'<section class="promo shell"[^>]*>(.*?)</section>', self.pages['ru'], re.S).group(1)
        self.assertLess(promo.index('class="promo-tile grill-promo"'), promo.index('class="promo-tile sub-tile"'), '«Курица гриль» остаётся первой')
        review = read('menu/kk_review.md')
        for k, v in self.i18n['kk']['sub'].items():
            self.assertIn('| `sub.%s` |' % k, review)
            self.assertIn(v, review)

    def test_promo_tiles(self):
        """акции (владелец 31.10): две плитки делят ширину контейнера пополам с зазором колонок hero, без серых подложек;
        «Курица гриль» — сама огненная рамка, подпись (название, цена, адреса, кнопка-пилюля) внутри окна с видео внизу на
        затемнении; подписка — та же форма 910×620 на фирменном зелёном. Ширины по CSS: 2000 и 1280 → (1112 − 32) / 2 = 540;
        ≤ 900 (как hero) — одна под другой: 768 → 720, 360 → 328"""
        for l, html in self.pages.items():
            promo = re.search(r'<section class="promo shell"[^>]*>(.*?)</section>', html, re.S).group(1)
            self.assertIn('<div class="row-head"><h2 id="promo-h">%s</h2></div>' % self.i18n[l]['sub']['h2'], promo, '%s: «акции» — множественное' % l)
            self.assertNotIn('promo-card', promo)
            self.assertIn('<div class="promo-tile sub-tile">', promo)
        self.assertEqual([self.i18n[l]['sub']['h2'] for l in ('ru', 'kk', 'en')], ['акции', 'акциялар', 'offers'])
        html = self.pages['ru']
        promo = re.search(r'<section class="promo shell"[^>]*>(.*?)</section>', html, re.S).group(1)
        self.assertEqual(re.findall(r'\n\s*<div class="promo-tile ([\w-]+)"', promo), ['grill-promo', 'sub-tile'])
        css = re.sub(r'/\*.*?\*/', '', style(html), flags=re.S)
        rule = lambda sel: re.search(r'(?:^|\})' + re.escape(sel) + r'\{([^}]*)\}', css).group(1)
        hero = rule('.hero')
        self.assertIn('grid-template-columns:1fr 1fr;gap:var(--s-32)', rule('.promo-grid'))
        self.assertIn('grid-template-columns:1fr 1fr;gap:var(--s-32)', hero, 'тот же зазор, что у колонок hero')
        self.assertIn('padding:var(--s-8) var(--s-24)', rule('.promo'), 'край контейнера — как у hero (отступ 24)')
        self.assertIn('aspect-ratio:910/620', rule('.promo-tile'))
        self.assertIn('aspect-ratio:910/620', rule('.grill-frame'))
        self.assertNotRegex(rule('.promo-tile'), r'background|padding', 'у плитки нет подложки — огненная рамка и есть плитка')
        self.assertIn('background:var(--c-accent)', rule('.sub-tile'))
        cap = rule('.grill-cap')
        self.assertIn('position:absolute', cap)
        self.assertIn('bottom:0', cap)
        self.assertIn('linear-gradient(to top', cap, 'затемнение для читаемости')
        # 1.11 (владелец): «смотреть в меню» — простая светлая ссылка, без плашки; подпись — по центру у низа окна
        link = rule('.promo-a')
        self.assertNotRegex(link, r'background|border-radius', 'ссылка без плашки-пилюли')
        self.assertIn('text-decoration:underline', link)
        self.assertIn('color:#FFFFFF', link)
        self.assertIn('text-align:center', cap)
        self.assertIn('align-items:center', cap)
        self.assertIn('bottom:0', cap)
        # пламя целиком (с языками) — во весь бокс SVG 910×620, рамка = плитка: края, верх и низ — как у плитки подписки
        sys.path.insert(0, os.path.join(ROOT, 'tools'))
        import flame_frame as ff
        xs = [p[0] for seg in ff.OUTER for p in seg[1:]]
        ys = [p[1] for seg in ff.OUTER for p in seg[1:]]
        self.assertEqual((min(xs), max(xs), min(ys), max(ys)), (0, ff.W, 0, ff.H), 'габарит пламени = бокс')
        self.assertNotIn('.grill-promo .grill-frame', css, 'без сдвигов и растяжек рамки — она сама по плитке')
        self.assertIn('position:relative;aspect-ratio:910/620', rule('.grill-frame'))
        # кайма прежней толщины: окно отстоит от края пламени на 30 ед. с боков и снизу (как до правки)
        wx = [p[0] for p in ff.flatten(ff.WINDOW)]
        wy = [p[1] for p in ff.flatten(ff.WINDOW)]
        self.assertEqual((round(min(wx)), round(ff.W - max(wx)), round(ff.H - max(wy))), (30, 30, 30))
        for cell in (540, 358):                                                         # 2000 px и 390 px
            self.assertEqual(round(cell * 620 / 910), round(cell * ff.H / ff.W), 'пламя = плитка подписки по высоте')
        mid = re.search(r'@media\(max-width:900px\)\{(.*?)\}\}', css, re.S).group(1)
        self.assertIn('.promo-grid{grid-template-columns:1fr', mid, 'на телефоне и планшете — одна под другой, как hero')

    def test_grill_text_inside_fire_frame(self):
        html = self.pages['ru']
        i = html.index('<div class="grill-win">')
        win_end = html.index('\n          </div>\n        </div>\n      </div>', i)
        win = html[i:win_end]
        cap = re.search(r'<p class="grill-cap">(.*?)</p>', win, re.S)
        self.assertIsNotNone(cap, 'подпись — внутри окна огненной рамки')
        for need in ('<b class="promo-t">Курица гриль</b>', '<s>6000</s>&nbsp;<span class="sale">3990 ₸</span>', 'Толе Би, 64', 'Серкебаева, 146',
                     '<a class="promo-a" href="#"', 'смотреть в меню'):
            self.assertIn(need, cap.group(1))
        self.assertNotIn('grill-ticker', win, 'бегущая строка — не в огне')
        # строка — полосой под обеими плитками на всю ширину контейнера, только там, где есть «Курица гриль»
        promo = re.search(r'<section class="promo shell"[^>]*>(.*?)</section>', html, re.S).group(1)
        self.assertRegex(promo, r'</div>\n    <div class="promo-run" onclick="openGrill\(\)"><div class="grill-ticker" aria-hidden="true">')
        self.assertGreater(promo.index('class="promo-run"'), promo.index('<!-- /подписка -->'))
        for l in ('kk', 'en'):
            self.assertNotIn('grill-ticker', self.pages[l])
        css = style(html)
        self.assertIn('@media(prefers-reduced-motion:reduce){.grill-ticker span{animation:none}}', css)

    def test_no_247_and_numbers_in_cards_and_modal(self):
        for l, html in self.pages.items():
            loc = re.search(r'<section class="locations" id="locations">(.*?)</section>', html, re.S).group(1)
            self.assertNotIn('<p class="tag">', loc, '%s: без надзаголовка «алматы · 5 точек»' % l)
            cards = re.findall(r'<div class="loc-card">(.*?)\n    </div>', loc, re.S)
            self.assertEqual(len(cards), 5)
            for c in cards:
                vis = re.sub(r'<[^>]+>', ' ', c)
                self.assertNotIn('24/7', vis, '%s: «24/7» в карточке не пишем' % l)
                self.assertNotRegex(re.search(r'<small>([^<]*)</small>', c).group(1), r'^\d')
            self.assertEqual(len(re.findall(r'<p class="loc-meta"><b>[^<]*07:00–22:00</b>', loc)), 1, '%s: у bakery часы остались' % l)
        css = style(self.pages['ru'])
        self.assertIn('background:var(--c-bg)', re.search(r'\.locations\{([^}]*)\}', css).group(1), 'фон секции — белый')
        card = re.search(r'\.loc-card\{([^}]*)\}', css).group(1)
        self.assertIn('box-shadow:var(--shadow-floating)', card)
        self.assertIn('text-align:center', card)
        self.assertIn('justify-content:center', re.search(r'\.loc-links\{([^}]*)\}', css).group(1))
        draw = re.search(r'function draw\(arr,showDist\)\{(.*?)\n  \}\n', self.pages['ru'], re.S).group(1)
        self.assertIn("<small>${b.n.replace(/^\\d+\\s*·\\s*/,'')}</small>", draw, 'окно выбора филиала — без номеров')
        self.assertIn("${b.hours!=='24/7'?", draw, 'окно — без «24/7»')
        for cls, ev, ic in (('ib route', 'modal_route', 'pin'), ('ib', 'modal_call', 'phone'), ('ib wa', 'modal_wa', 'wa')):
            self.assertRegex(draw, r'<a class="%s" [^>]*onclick="track\(\'%s\'[^>]*aria-label="[^"]+" title="[^"]+">\$\{ic\(\'%s\'\)\}</a>' % (cls, ev, ic))
        self.assertNotIn('br-btn', self.pages['ru'], 'старых кнопок окна нет')

    def test_whatsapp_green(self):
        css = style(self.pages['ru'])
        self.assertEqual(root_vars(self.pages['ru'])['--c-whatsapp'], '#25D366')
        for l, html in self.pages.items():
            wa = re.search(r'\.ib\.wa\{([^}]*)\}', style(html)).group(1)
            self.assertEqual(wa, 'background:var(--c-whatsapp);color:#FFFFFF', l)
            self.assertNotRegex(html, r'class="btn[^"]*"[^>]*>WhatsApp<', '%s: текстовых кнопок WhatsApp нет' % l)

    def test_contacts_social_icons(self):
        want = [('instagram', 'Instagram', 'https://instagram.com/del.cappuccino', 'ig'),
                ('youtube', 'YouTube', 'https://www.youtube.com/@DelCappuccino', 'yt'),
                ('threads', 'Threads', 'https://www.threads.com/@del.cappuccino', 'th')]
        for l, html in self.pages.items():
            sec = re.search(r'<section class="contact shell" id="contacts">(.*?)</section>', html, re.S).group(1)
            self.assertNotIn('<img', sec, '%s: без логотипа dC над заголовком' % l)
            self.assertNotRegex(sec, r'WhatsApp|cta_wa_contact', '%s: без кнопки WhatsApp' % l)
            got = re.findall(r'<a class="ib so" href="([^"]+)" target="_blank" rel="noopener" onclick="track\(\'cta_instagram\',\{net:\'(\w+)\'\}\)" '
                             r'aria-label="([^"]+)" title="([^"]+)"><svg class="ic" aria-hidden="true" focusable="false"><use href="#i-(\w+)"/></svg></a>', sec)
            self.assertEqual([(net, lab, url, ic) for url, net, lab, tit, ic in got], want, l)
            self.assertTrue(all(lab == tit for _, _, lab, tit, _ in got))
            self.assertNotIn('?hl=', sec)
            for _, _, _, ic in want:
                self.assertIn('<symbol id="i-%s"' % ic, html)
            self.assertIn('<footer', html)
            self.assertRegex(re.search(r'<footer\b.*?</footer>', html, re.S).group(0), r'logo-mono-192\.webp', '%s: логотип в подвале остался' % l)
            ld = json.loads(re.search(r'<script type="application/ld\+json">\n(.*?)\n</script>', html, re.S).group(1))
            org = next(n for n in ld['@graph'] if n['@type'] == 'Organization')
            self.assertEqual(org['sameAs'], [u for _, _, u, _ in want], '%s: sameAs — Instagram, YouTube, Threads' % l)
        lic = read('docs/LICENSES-media.md')
        for need in ('instagram', 'youtube', 'threads', 'CC0'):
            self.assertIn(need, lic)

    def test_location_names_without_numbers(self):
        for l, html in self.pages.items():
            names = re.findall(r'<div class="loc-card">\n      <small>([^<]+)</small>', html)
            self.assertEqual(len(names), 5, l)
            for n in names:
                self.assertNotRegex(n, r'^\d', '%s: номер в видимом названии точки: %s' % (l, n))
        self.assertIn("track('loc_call',{branch:'01 · ЖК Вавилон'})", self.pages['ru'], 'события — с номером, как были')

    def test_location_icon_buttons(self):
        emoji = re.compile('[\U0001F300-\U0001FAFF☀-➿☎\U0001F4DE\U0001F4CD]')
        labels = {'ru': ('Маршрут', 'Позвонить'), 'kk': (self.i18n['kk']['page']['route'], self.i18n['kk']['page']['call']),
                  'en': (self.i18n['en']['page']['route'], self.i18n['en']['page']['call'])}
        for l, html in self.pages.items():
            self.assertEqual(html.count('<svg class="icons"'), 1, '%s: один спрайт значков' % l)
            for sym in ('i-pin', 'i-phone', 'i-wa'):
                self.assertIn('<symbol id="%s"' % sym, html, l)
            cards = re.findall(r'<div class="loc-card">(.*?)\n    </div>', html, re.S)
            for c in cards:
                links = re.search(r'<div class="loc-links">(.*?)</div>', c, re.S).group(1)
                self.assertNotRegex(links, emoji, '%s: без эмодзи' % l)
                btns = re.findall(r'<a class="ib( route| wa)?" href="([^"]+)"[^>]*onclick="track\(\'(loc_\w+)\'[^"]*" aria-label="([^"]+)" title="([^"]+)">'
                                  r'<svg class="ic" aria-hidden="true" focusable="false"><use href="#i-(\w+)"/></svg></a>', links)
                self.assertEqual([(cl, ev, lab, tit, ic) for cl, _, ev, lab, tit, ic in btns],
                                 [(' route', 'loc_route', labels[l][0], labels[l][0], 'pin'), ('', 'loc_call', labels[l][1], labels[l][1], 'phone'),
                                  (' wa', 'loc_wa', 'WhatsApp', 'WhatsApp', 'wa')], l)
                self.assertTrue(btns[1][1].startswith('tel:') and btns[2][1].startswith('https://wa.me/'))
            self.assertEqual(len(re.findall(r'<a class="pill" [^>]*>[^<]+</a>', html)), 1, '%s: «Меню» у bakery — текстовой пилюлей' % l)
        css = style(self.pages['ru'])
        ib = re.search(r'\}\.ib\{([^}]*)\}', css).group(1)
        self.assertIn('width:var(--h-touch);height:var(--h-touch)', ib, 'касание 48 px')
        self.assertIn('background:var(--c-surface)', ib)
        self.assertIn('background:var(--c-accent);color:var(--c-on-accent)', re.search(r'\.ib\.route\{([^}]*)\}', css).group(1))
        lic = read('docs/LICENSES-media.md')
        for need in ('Lucide', 'ISC', 'Simple Icons', 'CC0', 'map-pin', 'phone', 'whatsapp'):
            self.assertIn(need, lic)

    def test_faq_collapsed_details(self):
        faq = json.loads(read('tools/faq.json'))
        for l, html in self.pages.items():
            sec = re.search(r'<section class="faq" id="faq">(.*?)</section>', html, re.S).group(1)
            box = re.search(r'<details class="faq-box"([^>]*)>\n\s*<summary class="faq-sum"><h2>([^\n]+)</h2></summary>(.*?)</details>\n\s*<p class="faq-more">', sec, re.S)
            self.assertIsNotNone(box, '%s: вопросы — в свёрнутой плашке <details>' % l)
            self.assertNotRegex(box.group(1), r'(?:^|\s)open(?:[\s=>]|$)', '%s: по умолчанию свёрнуто' % l)
            self.assertEqual(len(re.findall(r'<details ontoggle="if\(this\.open\)track\(\'faq_open\'', box.group(3))), len(faq), l)
            self.assertNotIn('<script', sec)
        css = style(self.pages['ru'])
        self.assertIn('max-width:760px;margin:0 auto', re.search(r'\.faq-box\{([^}]*)\}', css).group(1))
        self.assertIn('justify-content:center', re.search(r'\.faq-sum\{([^}]*)\}', css).group(1))

    def test_subscription_video_files_and_credits(self):
        """плитка подписки — видео налива кофе (владелец 1.11, вместо Lottie): файлы с хэшем, webm первым, постер маленький,
        источник и лицензия Mixkit в разметке и docs; анимация, плеер и tools/lottie_brand.py удалены"""
        V = seo.SUB_VIDEO
        for k in ('webm', 'mp4', 'poster'):
            self.assertRegex(V[k], r'^/assets/latte-pour(?:-poster)?\.[0-9a-f]{8}\.(webm|mp4|webp)$', k)
            self.assertTrue(os.path.isfile(os.path.join(ROOT, V[k].lstrip('/'))), V[k])
        self.assertLessEqual(os.path.getsize(os.path.join(ROOT, V['mp4'].lstrip('/'))), 1.2 * 1024 * 1024, 'mp4 ≤ 1,2 МБ')
        self.assertLessEqual(os.path.getsize(os.path.join(ROOT, V['webm'].lstrip('/'))), 1.2 * 1024 * 1024)
        self.assertLessEqual(os.path.getsize(os.path.join(ROOT, V['poster'].lstrip('/'))), 30 * 1024, 'постер маленький')
        for l, html in self.pages.items():
            tile = re.search(r'<div class="promo-tile sub-tile">(.*?)\n    </div>', html, re.S).group(1)
            self.assertIn('<!-- видео: Mixkit «Latte art» (https://mixkit.co/free-stock-video/latte-art-810/), Mixkit Stock Video Free License', tile)
            vid = re.search(r'<video class="sub-video" ([^>]*)>\s*<source src="([^"]+)" type="video/webm">\s*<source src="([^"]+)" type="video/mp4">\s*</video>', tile)
            self.assertIsNotNone(vid, '%s: видео во всю плитку, webm первым' % l)
            attrs = vid.group(1)
            for a in ('muted', 'loop', 'playsinline', 'preload="none"', 'poster="%s"' % V['poster']):
                self.assertIn(a, attrs, l)
            self.assertNotIn('autoplay', attrs, '%s: играет только на экране — через IntersectionObserver' % l)
            self.assertEqual((vid.group(2), vid.group(3)), (V['webm'], V['mp4']))
            self.assertIn(seo.SUB_JS, html, l)
            self.assertNotRegex(html, r'<link[^>]+latte-pour', '%s: видео не в preload' % l)
            self.assertNotRegex(html, r'(?i)lottie|brewing-coffee|sub-anim', '%s: от Lottie ничего не осталось' % l)
        css = style(self.pages['ru'])
        self.assertIn('.sub-video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover', css)
        self.assertIn('linear-gradient(to top', re.search(r'\.tile-cap\{([^}]*)\}', css).group(1), 'затемнение под подписью')
        self.assertNotIn('latte-pour', re.search(r'PRECACHE\s*=\s*\[(.*?)\]', read('sw.js'), re.S).group(1))
        for gone in ('assets/lottie_light.23cd2c01.js', 'assets/brewing-coffee.df6fc172.json', 'assets/brewing-coffee-poster.b7411dfe.webp',
                     'assets/brewing-coffee.2e74c5d9.json', 'assets/brewing-coffee-poster.f762aef7.webp', 'tools/lottie_brand.py'):
            self.assertFalse(os.path.exists(os.path.join(ROOT, gone)), 'удалено: ' + gone)
        lic = read('docs/LICENSES-media.md')
        for need in ('Mixkit', 'Mixkit Stock Video Free License', 'https://mixkit.co/free-stock-video/latte-art-810/', V['mp4'].lstrip('/'),
                     V['webm'].lstrip('/'), V['poster'].lstrip('/'), 'tools/build_sub_video.py'):
            self.assertIn(need, lic)
        tool = read('tools/build_sub_video.py')
        self.assertIn('xfade', tool, 'петля без рывка')
        self.assertIn('-an', tool.split('X264')[0] + tool, 'без звука')

    def test_subscription_video_loader_in_node(self):
        node = find_node()
        if not node:
            self.skipTest('нет node')
        js = re.search(r'<script>(.*)</script>', seo.SUB_JS, re.S).group(1)
        harness = r"""
const vm = require('vm'); const js = %s; const out = {};
function run(opts) {
  const log = [], loadL = [];
  const v = { muted: false, play() { log.push(['play', this.muted]); return Promise.resolve(); }, pause() { log.push(['pause']); } };
  const ctx = { document: { querySelector: s => s === '.sub-video' ? v : null, readyState: opts.ready || 'complete' },
    matchMedia: () => ({ matches: !!opts.reduce }), addEventListener: (t, f) => loadL.push([t, f]) };
  if (!opts.noIO) ctx.IntersectionObserver = function (cb, o) { this.observe = el => log.push(['observe', el === v, o.threshold]); ctx.__cb = cb; };
  ctx.window = ctx; vm.createContext(ctx); vm.runInContext(js, ctx);
  if (opts.ready === 'loading') { log.push(['before load']); loadL.forEach(([t, f]) => t === 'load' && f()); }
  const fire = on => ctx.__cb && ctx.__cb([{ isIntersecting: on }]);
  fire(true); fire(false); fire(true);
  return log;
}
out.normal = run({}); out.before_load = run({ ready: 'loading' }); out.reduce = run({ reduce: true }); out.no_io = run({ noIO: true });
console.log(JSON.stringify(out));
""" % json.dumps(js)
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, 'v.js')
            with open(f, 'w', encoding='utf-8') as fh:
                fh.write(harness)
            r = subprocess.run([node, f], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr[-800:])
        got = json.loads(r.stdout)
        want = [['observe', True, .25], ['play', True], ['pause'], ['play', True]]
        self.assertEqual(got['normal'], want, 'на экране — play (muted), вне экрана — pause')
        self.assertEqual(got['before_load'], [['before load']] + want, 'до load ничего не грузим')
        self.assertEqual(got['reduce'], [], 'reduced-motion — только постер')
        self.assertEqual(got['no_io'], [])

    def test_menu_overlay_header(self):
        """шапка меню: одна строка «Кофейни / Bakery to go · язык · закрыть», ниже вкладки и разделы — пилюлями;
        кнопки «Меню Жандосова» и блока «ME / NU» с адресами нет; аллергия и сервисный сбор — одной строкой"""
        html = self.pages['ru']
        head = re.search(r'<div class="mm-head">(.*?)\n  </div>\n  <div class="mm-body">', html, re.S).group(1)
        top = re.search(r'<div class="mm-top">(.*?)\n    </div>\n', head, re.S).group(1)
        self.assertEqual(re.findall(r'\n      <(?:div|button) class="([\w-]+)"', top), ['mm-mode', 'mm-lang-wrap', 'mm-x'])
        self.assertLess(head.index('id="mm-tabs"'), head.index('id="mm-cats"'))
        self.assertGreater(head.index('id="mm-tabs"'), head.index('class="mm-x"'), 'вкладки — под верхней строкой')
        self.assertNotRegex(html, r'mm-where|whereHTML|mm-mark|ME<br>NU|mm-logo|to_togo\}|to_cafe\}')
        self.assertIn("function openMenu(mode){", html, 'сигнатура openMenu(mode) — прежняя')
        css = style(html)
        on = re.search(r'\.mm-tab\.on,\.mm-cat\.on\{([^}]*)\}', css).group(1)
        self.assertEqual(on, 'background:var(--c-accent);color:var(--c-on-accent)', 'одна схема: активная — forest, текст белый')
        base = re.search(r'\.mm-tab,\.mm-cat\{([^}]*)\}', css).group(1)
        self.assertIn('background:var(--c-surface)', base)
        self.assertIn('border:0', base)
        self.assertNotRegex(base, r'width:\d', 'по ширине текста')
        self.assertNotRegex(css, r'\.mm-(?:tab|cat)[^{]*\{[^}]*(?:olive|border:1)', 'без оливы и обводок у вкладок и разделов')

    def test_weight(self):
        sizes = {l: len(html.encode('utf-8')) for l, html in self.pages.items()}
        self.assertLessEqual(sizes['ru'], 230 * 1024, 'главная была ~215 КБ — не раздувать')
        self.assertLessEqual(len(gzip.compress(self.pages['ru'].encode('utf-8'), 9)), 56 * 1024)
        for l in ('kk', 'en'):
            self.assertLessEqual(sizes[l], 70 * 1024, l)

    def test_scripts_in_node(self):
        """пилюля точки и заметка меню — на заглушке DOM: скрипты главной целиком"""
        node = find_node()
        if not node:
            self.skipTest('нет node')
        html = self.pages['ru']
        harness = r"""
const fs = require('fs'), vm = require('vm');
const { html } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
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
  return { ctx, els, raf, listeners, log, store };
}
const out = {};
let p;
for (const [name, h] of [['open', 10], ['closed', 20]]) {     // UTC 10:00 = 15:00 в Алматы, UTC 20:00 = 01:00
  p = page({ store: { dc_point: '05' }, utcHour: h }); const pill = p.els['pill-point'];
  out['pill_' + name] = [pill.querySelector('b').textContent, pill.querySelector('span').textContent];
}
p = page({});
const addr = { textContent: 'Абая, 44А' }, card = { querySelector: s => s === 'h3,.bn b' ? addr : null };
const target = { closest: s => s === 'a,button' ? {} : (s === '.branch-row,.loc-card' ? card : null) };
p.listeners.click.forEach(f => f({ target }));
out.pill_click = [p.store.dc_point, p.els['pill-point'].querySelector('b').textContent, p.els['pill-point'].querySelector('span').textContent];
for (const mode of ['cafe', 'togo']) {
  p = page({}); vm.runInContext("openMenu(" + (mode === 'togo' ? "'togo'" : '') + ")", p.ctx);
  out['menu_' + mode] = (p.els['mm-cols'].innerHTML.match(/<div class="mm-intro">(.*?)<\/div>/) || [])[1];
}
console.log(JSON.stringify(out));
"""
        with tempfile.TemporaryDirectory() as d:
            h, data = os.path.join(d, 'h.js'), os.path.join(d, 'data.json')
            with open(h, 'w', encoding='utf-8') as f:
                f.write(harness)
            with open(data, 'w', encoding='utf-8') as f:
                json.dump({'html': html}, f)
            r = subprocess.run([node, h, data], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr[-1500:])
        got = json.loads(r.stdout)
        self.assertEqual(got['pill_open'], ['Жандосова, 94/12', ' · открыто до 22:00'])
        self.assertEqual(got['pill_closed'], ['Жандосова, 94/12', ' · откроется в 07:00'])
        self.assertEqual(got['pill_click'], ['03', 'Абая, 44А', ' · открыто 24/7'])
        self.assertEqual(got['menu_cafe'], '<p class="mm-notice">Предупредите официанта об аллергии на продукты · Сервисный сбор 10% добавляется к счёту.</p>')
        self.assertEqual(got['menu_togo'], '<p class="mm-notice">Предупредите официанта об аллергии на продукты</p>', 'bakery — без сервисного сбора')


if __name__ == '__main__':
    unittest.main()
