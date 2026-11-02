"""Объёмное зелёное «стекло» главной кнопки и чипы — как в мобильном приложении (решение владельца 02.11.2026).
Источник правды — kofe-app, коммит 9206813: app/src/theme/glass.ts (GLASS_BUTTON), app/src/ui/Button.tsx (порядок слоёв),
app/src/ui/Chip.tsx (чип 48 − 8 = 40, поля 16, Montserrat 500 14px). Значения glass.ts переписаны ниже (GLASS) — сверяем с :root
главной (единственное место токенов), с собранными /kk/ и /en/ и с копией в 404.html.
Под зелёной кнопкой и плавающей «меню» размытия (backdrop-filter) нет: на образце его нет, в приложении убирают.
Запуск из корня репозитория: python3 -m unittest discover -s tests -v"""
import os, re, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import seo_jsonld as seo  # noqa: E402

GLASS = {   # kofe-app 9206813, app/src/theme/glass.ts — GLASS_BUTTON
    'height': 52, 'smallHeight': 44,
    'highlight': 'linear-gradient(180deg, rgba(127,168,134,0.45) 0%, rgba(107,150,114,0.15) 45%, transparent 55%)',
    'bottom': 'linear-gradient(180deg, transparent 50%, rgba(14,26,16,0.22) 100%)',
    'base': {'photo': 'rgba(66,99,73,0.74)', 'lightPhoto': 'rgba(66,99,73,0.80)', 'plain': 'rgba(66,99,73,0.94)'},
    'basePressed': {'photo': 'rgba(58,90,64,0.85)', 'lightPhoto': 'rgba(58,90,64,0.90)', 'plain': 'rgba(58,90,64,0.96)'},
    'edge': 'rgba(158,195,164,0.35)',
    'shadow': '0px 10px 24px rgba(14,26,16,0.28), 0px 2px 4px rgba(14,26,16,0.16)',
    'inset': 'inset 0px 1px 0px rgba(169,203,174,0.55), inset 0px -2px 3px rgba(14,26,16,0.22)',
    'shadowPressed': '0px 3px 8px rgba(14,26,16,0.22)',
    'insetPressed': 'inset 0px 3px 6px rgba(0,0,0,0.25), inset 0px 1px 0px rgba(255,255,255,0.25)',
    'highlightPressed': 0.36,
    'press': {'scale': 0.97, 'inMs': 90},
}
VARIANT = {'photo': 'photo', 'lightPhoto': 'light-photo', 'plain': 'plain'}
PAGES = {'ru': 'index.html', 'kk': 'kk/index.html', 'en': 'en/index.html'}


def read(p):
    with open(os.path.join(ROOT, p), encoding='utf-8') as f:
        return f.read()


def css_of(html):
    """<style> без комментариев и переводов строк"""
    css = html[html.index('<style>') + 7:html.index('</style>')]
    return re.sub(r'\s*\n\s*', '', re.sub(r'/\*.*?\*/', '', css, flags=re.S))


def root_vars(html):
    return dict(re.findall(r'(--[\w-]+):\s*([^;]+?)\s*;', re.search(r':root\{(.*?)\}', css_of(html)).group(1)))


def resolve(v, value):
    """подставить var(--x) из :root (рекурсивно)"""
    for _ in range(10):
        value = re.sub(r'var\((--[\w-]+)\)', lambda m: v[m.group(1)], value)
    return value


def norm(s):
    return re.sub(r'\s*,\s*', ',', re.sub(r'\s+', ' ', s.strip()))


def rules(css):
    """все правила (селектор, тело), с заходом внутрь @media/@supports"""
    out = []
    for r in seo.css_rules(css):
        pre, body = r.split('{', 1)
        if pre.startswith('@media') or pre.startswith('@supports'):
            out += [(pre + ' ' + p, b) for p, b in rules(body[:-1])]
        elif not pre.startswith('@'):
            out.append((pre.strip(), body[:-1]))
    return out


def rule(css, sel):
    m = re.search(r'(?:^|\})' + re.escape(sel) + r'\{([^}]*)\}', css)
    return m.group(1) if m else None


class TestGlassTokens(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = {l: read(p) for l, p in PAGES.items()}

    def test_tokens_equal_glass_ts(self):
        for l, html in self.pages.items():
            v = root_vars(html)
            rgb, rgbp = v['--glass-rgb'].split(), v['--glass-rgb-pressed'].split()
            for key, name in VARIANT.items():
                self.assertEqual('rgba(%s,%s)' % (','.join(rgb), v['--glass-base-' + name]), GLASS['base'][key], '%s: основа %s' % (l, key))
                self.assertEqual('rgba(%s,%s)' % (','.join(rgbp), v['--glass-pressed-' + name]), GLASS['basePressed'][key], '%s: нажатая %s' % (l, key))
            for var, key in (('--glass-highlight', 'highlight'), ('--glass-bottom', 'bottom'), ('--glass-edge', 'edge'),
                             ('--glass-shadow', 'shadow'), ('--glass-inset', 'inset'), ('--glass-shadow-pressed', 'shadowPressed'),
                             ('--glass-inset-pressed', 'insetPressed')):
                self.assertEqual(norm(resolve(v, v[var])), norm(GLASS[key]), '%s: %s' % (l, var))
            self.assertEqual(float(v['--glass-highlight-pressed']), GLASS['highlightPressed'])
            self.assertEqual(float(v['--glass-press-scale']), GLASS['press']['scale'])
            self.assertEqual(v['--glass-press-in'], '%dms' % GLASS['press']['inMs'])
            self.assertEqual(v['--glass-press-out'], '300ms', 'назад ~300 мс')
            y1 = float(re.match(r'cubic-bezier\(([\d.]+),([\d.]+),([\d.]+),([\d.]+)\)', v['--glass-press-spring']).group(2))
            self.assertTrue(1 < y1 <= 1.4, 'лёгкая пружина: перелёт есть, но небольшой')
            self.assertEqual(v['--h-glass'], '%dpx' % GLASS['height'])
            self.assertEqual(v['--h-glass-small'], '%dpx' % GLASS['smallHeight'])

    def test_base_photo_and_btn_font(self):
        for l, html in self.pages.items():
            v = root_vars(html)
            self.assertEqual(v.get('--glass-base-photo'), '0.74', '%s: --glass-base-photo — отдельной переменной, 0.74' % l)
            self.assertEqual(v.get('--btn-font'), 'var(--font-display)', l)

    def test_pressed_highlight_is_layer_opacity(self):
        """блик при нажатии — тот же градиент, прозрачность слоя 0,36 (Button.tsx: opacity highlightPressed)"""
        v = root_vars(self.pages['ru'])
        dim = v['--glass-highlight-dim']
        self.assertEqual(dim.count('calc(var(--glass-highlight-pressed)*100%)'), 2, 'обе цветные точки блика — через 0,36')
        self.assertIn('var(--glass-hl-top)', dim)
        self.assertIn('var(--glass-hl-mid)', dim)
        self.assertTrue(norm(dim).endswith('transparent 55%)'))

    def test_comment_links_to_kofe_app(self):
        root = re.search(r':root\{(.*?)\n\}', read('index.html'), re.S).group(1)
        self.assertRegex(root, r'kofe-app 9206813 app/src/theme/glass\.ts')


class TestGlassButtons(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = {l: read(p) for l, p in PAGES.items()}
        cls.css = {l: css_of(h) for l, h in cls.pages.items()}

    def test_no_backdrop_filter_under_green_buttons(self):
        for l, css in self.css.items():
            for sel, body in rules(css):
                if re.search(r'\.(?:btn|fab-menu)(?![\w-])', sel):
                    self.assertNotIn('backdrop-filter', body, '%s: %s' % (l, sel))
        nf = css_of(read('404.html'))
        for sel, body in rules(nf):
            if '.btn' in sel:
                self.assertNotIn('backdrop-filter', body, '404: %s' % sel)

    def test_btn_glass_plain(self):
        for l, css in self.css.items():
            btn = rule(css, '.btn')
            self.assertIn('min-height:var(--h-glass)', btn, '%s: высота 52' % l)
            glass = rule(css, '.btn,.fab-menu')
            for need in ('--glass-a:var(--glass-base-plain)', '--glass-ap:var(--glass-pressed-plain)', 'border:1px solid var(--glass-edge)',
                         'background-color:rgb(var(--glass-rgb) / var(--glass-a))', 'background-image:var(--glass-highlight),var(--glass-bottom)',
                         'box-shadow:var(--glass-shadow),var(--glass-inset)', 'color:var(--c-on-accent)', 'font-family:var(--btn-font)',
                         'transition:scale var(--glass-press-out) var(--glass-press-spring)'):
                self.assertIn(need, glass, '%s: %s' % (l, need))
            act = rule(css, '.btn:active,.fab-menu:active')
            for need in ('background-color:rgb(var(--glass-rgb-pressed) / var(--glass-ap))', 'background-image:var(--glass-highlight-dim),var(--glass-bottom)',
                         'box-shadow:var(--glass-shadow-pressed),var(--glass-inset-pressed)', 'scale:var(--glass-press-scale)',
                         'transition:scale var(--glass-press-in) ease-out'):
                self.assertIn(need, act, '%s: нажатие %s' % (l, need))
            self.assertIn('--glass-a:var(--glass-base-photo);--glass-ap:var(--glass-pressed-photo)', rule(css, '.btn.on-photo'))
            self.assertIn('--glass-a:var(--glass-base-light-photo);--glass-ap:var(--glass-pressed-light-photo)', rule(css, '.btn.on-light-photo'))
            hover = [b for s, b in rules(css) if s.startswith('@media(hover:hover)') and s.endswith('.btn:hover,.fab-menu:hover')]
            self.assertEqual(hover, ['background-color:rgb(var(--glass-rgb-pressed) / var(--glass-ap))'], '%s: наведение — основа pressed' % l)
            self.assertNotRegex(''.join(b for s, b in rules(css) if re.search(r'\.btn(?:[:,]|$)', s)), r'#31492F|--c-accent-dk', 'без плоского #31492F')
            rm = [b for s, b in rules(css) if s.startswith('@media(prefers-reduced-motion:reduce)') and '.btn:active' in s]
            self.assertEqual(rm, ['scale:none'], '%s: reduced-motion — без сжатия' % l)

    def test_ghost_and_olive_flat(self):
        for l, css in self.css.items():
            flat = rule(css, '.btn.ghost,.btn.olive')
            for need in ('border-color:transparent', 'background-image:none', 'box-shadow:none'):
                self.assertIn(need, flat, l)
            self.assertIn('background-color:var(--c-surface);color:var(--c-text)', rule(css, '.btn.ghost'))
            self.assertIn('background-color:var(--c-olive);color:var(--c-on-olive)', rule(css, '.btn.olive'))
        # главная, вторичная и выделенная — в одном ряду героя
        self.assertRegex(self.pages['ru'], r'<button class="btn olive"[^>]*>[^<]+</button>\s*<a class="btn" href')

    def test_404_button_same_glass(self):
        nf, main = read('404.html'), root_vars(self.pages['ru'])
        v = root_vars(nf)
        glass = {k: x for k, x in v.items() if k.startswith('--glass-') or k in ('--h-glass', '--btn-font')}
        self.assertGreaterEqual(len(glass), 20)
        for k, x in glass.items():
            self.assertEqual(x, main[k], '404: %s — как на главной' % k)
        btn = rule(css_of(nf), 'a.btn')
        for need in ('min-height:var(--h-glass)', 'background-color:rgb(var(--glass-rgb) / var(--glass-base-plain))',
                     'background-image:var(--glass-highlight),var(--glass-bottom)', 'box-shadow:var(--glass-shadow),var(--glass-inset)',
                     'font-family:var(--btn-font)'):
            self.assertIn(need, btn)


class TestChips(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = read('index.html')
        cls.css = css_of(cls.html)

    def test_chip_size_font_touch(self):
        """Chip.tsx: высота 48 − 8, поля 16, Montserrat 500 14px; касание 48 — псевдоэлемент по 4px сверху и снизу"""
        for sel in ('.pill', '.mm-tab,.mm-cat'):
            r = rule(self.css, sel)
            for need in ('calc(var(--h-touch) - var(--s-8))', 'padding:0 var(--s-16)', 'font-size:var(--fs-small)', 'font-weight:500', 'position:relative'):
                self.assertIn(need, r, '%s: %s' % (sel, need))
        for sel in ('.pill::after', '.mm-tab::after,.mm-cat::after'):
            self.assertEqual(rule(self.css, sel), "content:'';position:absolute;inset:calc(var(--s-8) / -2) 0", sel)
        self.assertIn('font-family:var(--font-body)', rule(self.css, '.mm-tab,.mm-cat'))
        self.assertEqual(rule(self.css, '.mm-tab.on,.mm-cat.on'), 'background:var(--c-accent);color:var(--c-on-accent)')

    def test_rows_leave_room_for_touch(self):
        """ряды вкладок и разделов прокручиваются (overflow-x) — касание чипа (4px сверху и снизу) должно лечь в поля ряда"""
        rows = rule(self.css, '.mm-tabs,.mm-cats')
        self.assertIn('padding:var(--s-4) var(--s-24)', rows)
        mob = ''.join(re.findall(r'@media\(max-width:680px\)\{(.*?)\}\}', self.css))
        self.assertIn('.mm-tabs,.mm-cats{padding:var(--s-4) var(--s-12)', mob)
        self.assertNotRegex(mob, r'\.mm-tab\{padding', 'поля чипа на телефоне — тоже 16')

    def test_mode_and_lang_like_chips(self):
        r = rule(self.css, '.mm-mode-btn,.mm-lang-btn')
        for need in ('height:44px', 'border:2px solid transparent', 'background-clip:padding-box', 'font-weight:500', 'font-family:var(--font-body)'):
            self.assertIn(need, r, need)
        self.assertIn('font-size:var(--fs-small)', rule(self.css, '.mm-mode-btn'))
        self.assertNotIn('font-weight:700', rule(self.css, '.mm-lang-btn'))
        self.assertEqual(rule(self.css, '.mm-mode-btn.on,.mm-lang-btn.on'), 'background:var(--c-accent);color:var(--c-on-accent)')

    def test_pill_point_untouched(self):
        self.assertIn('min-height:var(--h-touch);padding:0 var(--s-16)', rule(self.css, '.pill-point'))

    def test_text_menus_chips(self):
        for p in ('menyu/index.html', 'kk/menyu/index.html', 'en/menu/index.html'):
            css = css_of(read(p))
            r = rule(css, '.pill,.toc a,.lang a')
            self.assertIn('min-height:40px', r, p)
            self.assertIn('font-weight:500', r, p)
            self.assertEqual(rule(css, '.pill::after,.toc a::after,.lang a::after'), "content:'';position:absolute;inset:-4px 0", p)


if __name__ == '__main__':
    unittest.main()
