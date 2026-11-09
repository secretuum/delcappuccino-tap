"""Объёмное «стекло» всех кнопок сайта — как главная кнопка мобильного приложения (решения владельца 02.11.2026: сначала
зелёная кнопка, затем «все кнопки — стекло своего цвета», включая меню и переключатели).
Источник правды — kofe-app, коммит 9206813: app/src/theme/glass.ts (GLASS_BUTTON), app/src/ui/Button.tsx (порядок слоёв:
основа, низ, блик, кромка 1px с внутренними тенями), app/src/ui/Chip.tsx (чип 48 − 8 = 40, поля 16, Montserrat 500 14px).
Значения glass.ts переписаны ниже (GLASS) — сверяем с :root главной (единственное место токенов), /kk/, /en/, текстовыми
меню и копиями в 404.html и /ugolok. Тона: зелёный (glass.ts), олива, WhatsApp, светлое (значения сайта — в приложении
светлого объёмного стекла нет, там матовая панель с размытием). Слои — одно правило :where(…) на все кнопки, элемент задаёт
только тон --tone-*. Размытия (backdrop-filter) под кнопками нет.
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
TEXT_MENUS = ('menyu/index.html', 'kk/menyu/index.html', 'en/menu/index.html')

# кнопка → тон (главная). Зелёный — по умолчанию у слоёв (.btn, .fab-menu)
TONES = {
    'light': ['.btn.ghost', '.ib', '.pill', '.pill-point', '.lang-dd summary', '.mm-tab', '.mm-cat', '.mm-mode-btn', '.mm-lang-btn',
              '.mm-search-btn', '.mm-search-x', '.mm-x', '.mm-card-x', '.sheet .x', '.mm-only'],
    'green': ['.ib.route', '.lang-dd[open] summary', '.mm-tab.on', '.mm-cat.on', '.mm-mode-btn.on', '.mm-lang-btn.on', '.mm-only:hover',
              '.mm-only[aria-expanded="true"]'],
    'wa': ['.ib.wa'],
    'olive': ['.btn.olive'],
}
LAYERED = ['.btn', '.fab-menu', '.ib', '.pill', '.pill-point', '.lang-dd summary', '.mm-tab', '.mm-cat', '.mm-mode-btn', '.mm-lang-btn',
           '.mm-search-btn', '.mm-search-x', '.mm-x', '.mm-card-x', '.sheet .x', '.mm-only']
TONE_VARS = {'green': 'glass', 'light': 'glass-light', 'wa': 'glass-wa', 'olive': 'glass-olive'}
BASE = ('background-color:rgb(var(--tone-rgb) / var(--tone-a))', 'background-image:linear-gradient(180deg,var(--tone-hl1) 0%,var(--tone-hl2) 45%,transparent 55%),var(--tone-bot)',
        'box-shadow:var(--tone-sh),var(--tone-in),inset 0 0 0 1px var(--tone-edge)', 'transition:scale var(--glass-press-out) var(--glass-press-spring)')


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


def split_sel(pre):
    return [s.strip() for s in pre.split(',')]


def layer_rules(css):
    """{'' | ':active' | ':hover' | 'reduce': (список селекторов, тело)} — правила :where(…) слоёв стекла"""
    out = {}
    for pre, body in rules(css):
        m = re.match(r'(@media\([^)]*\) )?:where\((.*)\)(:\w+)?$', pre)
        if m:
            key = 'reduce' if m.group(1) and 'reduced-motion' in m.group(1) else (m.group(3) or '')
            out[key] = (split_sel(m.group(2)), body)
    return out


def tone_of(css, sel):
    """тон селектора: правило, где он в списке и задан --tone-rgb"""
    hit = [b for p, b in rules(css) if ':where(' not in p and sel in split_sel(p) and '--tone-rgb:' in b]
    if not hit:
        return None
    rgb = re.search(r'--tone-rgb:var\(--([\w-]+)-rgb\)', hit[-1]).group(1)
    return {v: k for k, v in TONE_VARS.items()}[rgb]


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
            hl = 'linear-gradient(180deg,%s 0%%,%s 45%%,transparent 55%%)' % (v['--glass-hl-top'], v['--glass-hl-mid'])
            self.assertEqual(norm(hl), norm(GLASS['highlight']), '%s: блик' % l)
            for var, key in (('--glass-bottom', 'bottom'), ('--glass-edge', 'edge'), ('--glass-shadow', 'shadow'), ('--glass-inset', 'inset'),
                             ('--glass-shadow-pressed', 'shadowPressed'), ('--glass-inset-pressed', 'insetPressed')):
                self.assertEqual(norm(resolve(v, v[var])), norm(GLASS[key]), '%s: %s' % (l, var))
            self.assertEqual(float(v['--glass-highlight-pressed']), GLASS['highlightPressed'])
            self.assertEqual(float(v['--glass-press-scale']), GLASS['press']['scale'])
            self.assertEqual(v['--glass-press-in'], '%dms' % GLASS['press']['inMs'])
            self.assertEqual(v['--glass-press-out'], '300ms', 'назад ~300 мс')
            y1 = float(re.match(r'cubic-bezier\(([\d.]+),([\d.]+),([\d.]+),([\d.]+)\)', v['--glass-press-spring']).group(2))
            self.assertTrue(1 < y1 <= 1.4, 'лёгкая пружина: перелёт есть, но небольшой')
            self.assertEqual(v['--h-glass'], '%dpx' % GLASS['height'])
            self.assertEqual(v['--h-glass-small'], '%dpx' % GLASS['smallHeight'])

    def test_tone_tokens(self):
        """на каждый тон — rgb основы и нажатой, блик (две точки), кромка; цвета основ — из токенов v5; у светлого свои низ и тени"""
        hexrgb = lambda h: ' '.join(str(int(h[i:i + 2], 16)) for i in (1, 3, 5))
        for l, html in self.pages.items():
            v = root_vars(html)
            for pre in TONE_VARS.values():
                for suf in ('rgb', 'rgb-pressed', 'hl-top', 'hl-mid', 'edge'):
                    self.assertIn('--%s-%s' % (pre, suf), v, l)
            self.assertEqual(v['--glass-olive-rgb'], hexrgb(v['--c-olive']), 'олива = #849E29')
            self.assertEqual(v['--glass-wa-rgb'], hexrgb(v['--c-whatsapp']), 'WhatsApp = --c-whatsapp (#128C7E)')
            self.assertEqual(v['--glass-light-rgb'], hexrgb(v['--c-surface']))
            self.assertEqual(v['--glass-light-rgb-pressed'], hexrgb(v['--c-raised']))
            for suf in ('bottom', 'shadow', 'inset', 'shadow-pressed', 'inset-pressed'):
                self.assertIn('--glass-light-' + suf, v, l)
            # блик светлее основы: у оливы и WhatsApp — светлый вариант своего цвета
            for pre in ('glass-olive', 'glass-wa', 'glass-light'):
                top = [int(x) for x in re.match(r'rgba\((\d+),(\d+),(\d+),', v['--%s-hl-top' % pre]).groups()]
                self.assertGreater(sum(top), sum(int(x) for x in v['--%s-rgb' % pre].split()), pre)

    def test_base_photo_and_btn_font(self):
        for l, html in self.pages.items():
            v = root_vars(html)
            self.assertEqual(v.get('--glass-base-photo'), '0.74', '%s: --glass-base-photo — отдельной переменной, 0.74' % l)
            self.assertEqual(v.get('--btn-font'), 'var(--font-display)', l)

    def test_comment_links_to_kofe_app(self):
        root = re.search(r':root\{(.*?)\n\}', read('index.html'), re.S).group(1)
        self.assertRegex(root, r'kofe-app 9206813 app/src/theme/glass\.ts')


class TestGlassButtons(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = {l: read(p) for l, p in PAGES.items()}
        cls.css = {l: css_of(h) for l, h in cls.pages.items()}

    def test_layers_for_every_button(self):
        """одно правило слоёв на все кнопки: основа, блик, низ, тень + inset, кромка 1px; нажатие; наведение; reduced-motion"""
        lr = layer_rules(self.css['ru'])
        self.assertEqual(sorted(lr), ['', ':active', ':hover', 'reduce'])
        for key, (sels, body) in lr.items():
            self.assertEqual(sels, LAYERED, key)
        base = lr[''][1]
        for need in BASE + ('--tone-a:var(--glass-base-plain)', '--tone-ap:var(--glass-pressed-plain)', 'border:0'):
            self.assertIn(need, base)
        act = lr[':active'][1]
        for need in ('background-color:rgb(var(--tone-rgbp) / var(--tone-ap))', 'box-shadow:var(--tone-shp),var(--tone-inp),inset 0 0 0 1px var(--tone-edge)',
                     'scale:var(--glass-press-scale)', 'transition:scale var(--glass-press-in) ease-out'):
            self.assertIn(need, act)
        self.assertEqual(act.count('calc(var(--glass-highlight-pressed)*100%)'), 2, 'блик при нажатии — прозрачность слоя 0,36')
        self.assertEqual(lr[':hover'][1], 'background-color:rgb(var(--tone-rgbp) / var(--tone-ap))', 'наведение — основа нажатой')
        self.assertEqual(lr['reduce'][1], 'scale:none')
        for l in ('kk', 'en'):     # облегчённые: те же тела, в списке — только то, что есть на странице
            lk = layer_rules(self.css[l])
            for key in ('', ':active', ':hover', 'reduce'):
                self.assertEqual(lk[key][1], lr[key][1], '%s %s' % (l, key))
            self.assertEqual(lk[''][0], ['.btn', '.fab-menu', '.ib', '.pill', '.pill-point', '.lang-dd summary'], l)

    def test_button_tones(self):
        css = self.css['ru']
        for t, sels in TONES.items():
            for sel in sels:
                self.assertEqual(tone_of(css, sel), t, sel)
        for sel in ('.btn', '.fab-menu'):
            self.assertIsNone(tone_of(css, sel), '%s — зелёный по умолчанию (тон слоёв)' % sel)
        layer = layer_rules(css)[''][1]
        self.assertIn('--tone-rgb:var(--glass-rgb)', layer)
        self.assertIn('color:var(--c-on-olive)', rule(css, '.btn.olive'))
        self.assertIn('color:#FFFFFF', rule(css, '.ib.wa'))
        self.assertIn('--tone-a:var(--glass-base-photo);--tone-ap:var(--glass-pressed-photo)', rule(css, '.fab-menu'), 'плавающая «меню» — основа photo')
        self.assertIn('--tone-a:var(--glass-base-photo);--tone-ap:var(--glass-pressed-photo)', rule(css, '.btn.on-photo'))
        self.assertIn('--tone-a:var(--glass-base-light-photo);--tone-ap:var(--glass-pressed-light-photo)', rule(css, '.btn.on-light-photo'))
        for l in ('kk', 'en'):
            for sel, t in (('.btn.ghost', 'light'), ('.ib', 'light'), ('.pill-point', 'light'), ('.lang-dd summary', 'light'),
                           ('.ib.route', 'green'), ('.ib.wa', 'wa'), ('.btn.olive', 'olive')):
                self.assertEqual(tone_of(self.css[l], sel), t, '%s %s' % (l, sel))
            self.assertNotRegex(self.css[l], r'\.mm-|\.sheet', l)

    def test_no_flat_overrides_and_no_blur(self):
        """у кнопок нет своих плоских заливок, теней и размытия поверх слоёв (кроме липкой лупы: её тень — слои + подложка)"""
        for l, css in self.css.items():
            for pre, body in rules(css):
                parts = [re.sub(r'^@media\([^)]*\) ', '', s) for s in split_sel(pre)]
                if not any(re.sub(r':(?:hover|active)$', '', p) in LAYERED + sum(TONES.values(), []) for p in parts):
                    continue
                self.assertNotIn('backdrop-filter', body, '%s: %s' % (l, pre))
                self.assertNotRegex(body, r'(?:^|;)background:', '%s: %s — плоская заливка' % (l, pre))
                if 'box-shadow' in body and not pre.startswith(':where') and ':where(' not in pre:
                    self.assertIn('var(--tone-sh),var(--tone-in),inset 0 0 0 1px var(--tone-edge)', body, '%s: %s' % (l, pre))

    def test_404_and_ugolok_same_glass(self):
        main = root_vars(self.pages['ru'])
        lr = layer_rules(self.css['ru'])
        light = rule(self.css['ru'], ','.join(TONES['light']))
        for path, sels in (('404.html', ['a.btn']), ('ugolok/index.html', ['.pass-btn', '.lang-btn', '.tb-back'])):
            html = read(path)
            v, css = root_vars(html), css_of(html)
            glass = {k: x for k, x in v.items() if k.startswith('--glass-') or k in ('--h-glass', '--btn-font')}
            self.assertGreaterEqual(len(glass), 18, path)
            for k, x in glass.items():
                self.assertEqual(x, main[k], '%s: %s — как на главной' % (path, k))
            lk = layer_rules(css)
            for key in ('', ':active', ':hover', 'reduce'):
                self.assertEqual(lk[key], (sels, lr[key][1]), '%s: слои %s — дословно как на главной' % (path, key))
            for pre, body in rules(css):
                self.assertNotIn('backdrop-filter', body if any(s in pre for s in sels) else '', path)
        ug = css_of(read('ugolok/index.html'))
        self.assertEqual(rule(ug, '.lang-btn,.tb-back'), light, '/ugolok: языки и «на главную» — светлое стекло')
        self.assertTrue(rule(ug, '.lang-btn.on').startswith('--tone-rgb:var(--glass-rgb);'), 'выбранный язык — зелёный')
        for sel in ('.pass-btn', '.lang-btn', '.tb-back'):
            self.assertNotRegex(rule(ug, sel), r'(?:^|;)background:', sel)
        self.assertIn('min-height:var(--h-glass)', rule(ug, '.pass-btn'))
        self.assertIn('min-height:var(--h-glass)', rule(css_of(read('404.html')), 'a.btn'))

    def test_text_menus_glass(self):
        lr = layer_rules(self.css['ru'])
        light = rule(self.css['ru'], ','.join(TONES['light']))
        sels = ['.pill', '.toc a', '.lang a']
        for p in TEXT_MENUS:
            css = css_of(read(p))
            lk = layer_rules(css)
            for key in ('', ':active', ':hover', 'reduce'):
                self.assertEqual(lk[key], (sels, lr[key][1]), '%s %s' % (p, key))
            self.assertIn('{' + light + '}', css, '%s: светлый тон — как у главной' % p)
            self.assertTrue(rule(css, '.lang a[aria-current]').startswith('--tone-rgb:var(--glass-rgb);'), p)
            self.assertNotRegex(rule(css, '.pill,.toc a,.lang a'), r'(?:^|;)background:', p)


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

    def test_rows_leave_room_for_touch_and_shadow(self):
        """ряды вкладок и разделов прокручиваются (overflow-x): касание (4px) и тень чипа должны лечь в поля ряда"""
        rows = rule(self.css, '.mm-tabs,.mm-cats')
        self.assertIn('padding:var(--s-4) var(--s-24) var(--s-8)', rows)
        mob = ''.join(re.findall(r'@media\(max-width:680px\)\{(.*?)\}\}', self.css))
        self.assertIn('.mm-tabs,.mm-cats{padding:var(--s-4) var(--s-12) var(--s-8)', mob)
        self.assertNotRegex(mob, r'\.mm-tab\{padding', 'поля чипа на телефоне — тоже 16')
        v = root_vars(self.html)
        self.assertEqual(v['--glass-light-shadow'], '0px 2px 6px rgba(36,28,21,0.12),0px 1px 2px rgba(36,28,21,0.1)', 'тень светлого — в 8px')

    def test_mode_and_lang_like_chips(self):
        r = rule(self.css, '.mm-mode-btn,.mm-lang-btn')
        for need in ('height:calc(var(--h-touch) - var(--s-8))', 'font-weight:500', 'font-family:var(--font-body)', 'position:relative'):
            self.assertIn(need, r, need)
        self.assertEqual(rule(self.css, '.mm-mode-btn::after,.mm-lang-btn::after'), "content:'';position:absolute;inset:-2px 0", 'касание 44')
        self.assertIn('font-size:var(--fs-small)', rule(self.css, '.mm-mode-btn'))
        self.assertNotIn('font-weight:700', rule(self.css, '.mm-lang-btn'))
        mob = ''.join(re.findall(r'@media\(max-width:680px\)\{(.*?)\}\}', self.css))
        self.assertNotRegex(re.search(r'\.mm-mode-btn\{[^}]*\}', mob).group(0), r'overflow:hidden', 'обрезка срезала бы касание')

    def test_pill_point_size_untouched(self):
        self.assertIn('min-height:var(--h-touch);padding:0 var(--s-16)', rule(self.css, '.pill-point'))

    def test_text_menus_chips(self):
        for p in TEXT_MENUS:
            css = css_of(read(p))
            r = re.search(r'\}\.pill,\.toc a,\.lang a\{(position[^}]*)\}', css).group(1)
            self.assertIn('min-height:40px', r, p)
            self.assertIn('font-weight:500', r, p)
            self.assertEqual(rule(css, '.pill::after,.toc a::after,.lang a::after'), "content:'';position:absolute;inset:-4px 0", p)


if __name__ == '__main__':
    unittest.main()
