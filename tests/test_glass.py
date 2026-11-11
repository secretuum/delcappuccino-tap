"""Плоские кнопки и чипы всего сайта (владелец 11.11.2026: «кнопки сделать плоскими, без стекла и т. д.»). До этого — объёмное
стекло своего тона (#54, #55 по kofe-app glass.ts); имя файла осталось от той задачи — на него ссылаются комментарии страниц.
Сторожат: одно правило :where(…) на все кнопки — сплошная заливка тона (--tone-bg), наведение и нажатие — тон --tone-p;
элемент задаёт только тон; у кнопок нет бликов, теней (box-shadow, drop-shadow), градиентов, размытия и сжатия при нажатии;
тона — в :root главной (--btn-*: зелёный, олива, WhatsApp — фирменный #25D366, решение владельца 09.11, светлый) из цветов
темы; текст на заливке ≥ 4,5:1 и при нажатии; /kk/ и /en/ (их CSS — подмножество главной, tools/seo_jsonld.py), текстовые
меню (btn_css генератора), 404.html, /ugolok и /otzyv (tools/feedback_page.py, сверяет tests/test_otzyv.py) — те же слои
дословно и те же тона. Рамка фокуса и касание — tests/test_polish_*.
Карточки, плитки акций, шапка и фото — не кнопки: их тени и размытие здесь не проверяем (владелец по ним не решал).
Запуск из корня репозитория: python3 -m unittest discover -s tests -v"""
import os, re, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import seo_jsonld as seo  # noqa: E402

PAGES = {'ru': 'index.html', 'kk': 'kk/index.html', 'en': 'en/index.html'}
TEXT_MENUS = ('menyu/index.html', 'kk/menyu/index.html', 'en/menu/index.html')
COPIES = {'404.html': ['a.btn'], 'ugolok/index.html': ['.pass-btn', '.lang-btn', '.tb-back']}
MENU_SELS = ['.pill', '.toc a', '.lang a']
OTZYV = ('otzyv/index.html', ['.fb-btn', '.fb-btn.wa', '.fb-btn.call', '.lang-btn', '.lang-btn.on', '.tb-back'])

# тон → цвет темы (основа) и наведение/нажатие: тот же тон чуть темнее, у оливы — светлее (тёмный текст на прежнем
# нажатом #748C22 давал 4,2:1). Значения нажатия — прежние «нажатые» тона стекла, кроме оливы
THEME = {'green': '--c-accent', 'olive': '--c-olive', 'wa': '--c-whatsapp', 'light': '--c-surface'}
PRESS = {'green': '#3A5A40', 'olive': '#96AD49', 'wa': '#1FBA59', 'light': '#ECEBE8'}
DARKER = {'green': True, 'olive': False, 'wa': True, 'light': True}
# цвет текста на тоне; WhatsApp — только белый логотип, контраст сознательно не проверяем (решение владельца 09.11)
TEXT = {'green': ['--c-on-accent'], 'olive': ['--c-on-olive'], 'light': ['--c-text', '--c-muted', '--c-accent']}

# кнопка → тон (главная). Зелёный — по умолчанию у слоя (.btn, .fab-menu)
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
LAYER = ('--tone-bg:var(--btn-green);--tone-p:var(--btn-green-p);border:0;background:var(--tone-bg);'
         '-webkit-tap-highlight-color:transparent;transition:background-color .15s')
PRESSED = 'background:var(--tone-p)'
LAYER_KEYS = [('', ''), ('', ':active'), ('@media(hover:hover)', ':hover')]
LIGHT = '--tone-bg:var(--btn-light);--tone-p:var(--btn-light-p)'
GREEN_ON = '--tone-bg:var(--btn-green);--tone-p:var(--btn-green-p);color:var(--c-on-accent)'
# всё, что делало кнопку объёмной: тени, блики-градиенты, размытие и фильтры, сжатие при нажатии
VOLUME = r'box-shadow|drop-shadow|text-shadow|gradient\(|backdrop-filter|(?:^|;)filter:|(?:^|;)scale:|background-image'
# лупа меню на телефоне прилипает к краю ряда вкладок: полоса цвета фона без размытия справа закрывает уходящие под неё вкладки —
# маска, не тень (единственный box-shadow у кнопок); градиент её ::before — затухание ряда слева, не поверхность кнопки
LUPA = ('@media(max-width:680px)', '.mm-search-btn', 'position:sticky;right:0;z-index:1;box-shadow:var(--s-12) 0 0 var(--c-bg)')


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
    return value.upper()


def rules(css):
    """все правила (media, селектор, тело), с заходом внутрь @media/@supports"""
    out = []
    for r in seo.css_rules(css):
        pre, body = r.split('{', 1)
        if pre.startswith('@media') or pre.startswith('@supports'):
            out += [(pre.strip(), p, b) for _, p, b in rules(body[:-1])]
        elif not pre.startswith('@'):
            out.append(('', pre.strip(), body[:-1]))
    return out


def rule(css, sel):
    m = re.search(r'(?:^|\})' + re.escape(sel) + r'\{([^}]*)\}', css)
    return m.group(1) if m else None


def split_sel(pre):
    return [s.strip() for s in pre.split(',')]


def layer_rules(css):
    """{(media, ':active' | ':hover' | ''): (список селекторов, тело)} — правила :where(…) общего слоя кнопок"""
    out = {}
    for media, pre, body in rules(css):
        m = re.match(r':where\((.*)\)(:\w+)?$', pre)
        if m:
            out[(media, m.group(2) or '')] = (split_sel(m.group(1)), body)
    return out


def tone_of(css, sel):
    """тон селектора: правило (не слой), где он в списке и задан --tone-bg"""
    hit = [b for _, p, b in rules(css) if ':where(' not in p and sel in split_sel(p) and '--tone-bg:' in b]
    return re.search(r'--tone-bg:var\(--btn-(\w+)\)', hit[-1]).group(1) if hit else None


def hexrgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def lum(h):
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(x) for x in hexrgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def all_pages():
    return [*PAGES.values(), *TEXT_MENUS, *COPIES, OTZYV[0]]


class TestTones(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vars = {l: root_vars(read(p)) for l, p in PAGES.items()}

    def test_tones_are_theme_colors(self):
        """основа тона — цвет темы (одно место смены), нажатие — свой оттенок; WhatsApp — фирменный #25D366"""
        for l, v in self.vars.items():
            self.assertEqual(v['--c-whatsapp'], '#25D366', l)
            for t, theme in THEME.items():
                self.assertEqual(v['--btn-' + t], 'var(%s)' % theme, '%s: %s' % (l, t))
                self.assertEqual(resolve(v, v['--btn-%s-p' % t]), PRESS[t], '%s: нажатие %s' % (l, t))
            self.assertEqual(v['--btn-light-p'], 'var(--c-raised)', l)

    def test_press_is_a_shade(self):
        """наведение и нажатие — тот же тон «чуть» темнее (у оливы — светлее): заметно, но не другой цвет"""
        v = self.vars['ru']
        for t in THEME:
            base, press = resolve(v, v['--btn-' + t]), resolve(v, v['--btn-%s-p' % t])
            self.assertEqual(lum(press) < lum(base), DARKER[t], t)
            self.assertTrue(1.05 <= contrast(base, press) <= 1.35, '%s: %.2f' % (t, contrast(base, press)))

    def test_text_contrast(self):
        """текст на заливке и на нажатой заливке ≥ 4,5:1 (WhatsApp — только логотип, решение владельца)"""
        v = self.vars['ru']
        for t, fgs in TEXT.items():
            for fill in (resolve(v, v['--btn-' + t]), resolve(v, v['--btn-%s-p' % t])):
                for fg in fgs:
                    c = contrast(resolve(v, v[fg]), fill)
                    self.assertGreaterEqual(c, 4.5, '%s на %s (%s): %.2f' % (fg, t, fill, c))

    def test_heights_and_font(self):
        for l, v in self.vars.items():
            self.assertEqual(v['--h-btn'], '52px', l)
            self.assertEqual(v['--h-btn-sm'], '44px', l)
            self.assertEqual(v['--btn-font'], 'var(--font-display)', l)
            self.assertIn('min-height:var(--h-btn)', rule(css_of(read(PAGES[l])), '.btn'), l)

    def test_no_glass_left(self):
        """от стекла не осталось ни токенов --glass-*, ни прежних переменных тона (блик, низ, тени, прозрачность основы)"""
        for p in all_pages():
            css = css_of(read(p))
            self.assertNotIn('--glass-', css, p)
            self.assertNotRegex(css, r'--tone-(?!bg\b|p\b)', p)
            self.assertNotRegex(css, r'\.on-(?:light-)?photo', p)


class TestFlatButtons(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.css = {l: css_of(read(p)) for l, p in PAGES.items()}
        cls.layer = layer_rules(cls.css['ru'])

    def test_one_layer_for_all_buttons(self):
        """одно правило на все кнопки: заливка тона, нажатие и наведение (только при мыши) — тон -p; без reduced-motion — движения нет"""
        self.assertEqual(sorted(self.layer), sorted(LAYER_KEYS))
        for key, (sels, body) in self.layer.items():
            self.assertEqual(sels, LAYERED, key)
        self.assertEqual(self.layer[('', '')][1], LAYER)
        self.assertEqual(self.layer[('', ':active')][1], PRESSED)
        self.assertEqual(self.layer[('@media(hover:hover)', ':hover')][1], PRESSED)
        for l in ('kk', 'en'):     # облегчённые: те же тела, в списке — только то, что есть на странице
            lk = layer_rules(self.css[l])
            self.assertEqual(sorted(lk), sorted(LAYER_KEYS), l)
            for key in LAYER_KEYS:
                self.assertEqual(lk[key], (['.btn', '.fab-menu', '.ib', '.pill', '.pill-point', '.lang-dd summary'], self.layer[key][1]), '%s %s' % (l, key))

    def test_button_tones(self):
        css = self.css['ru']
        for t, sels in TONES.items():
            for sel in sels:
                self.assertEqual(tone_of(css, sel), t, sel)
        for sel in ('.btn', '.fab-menu'):
            self.assertIsNone(tone_of(css, sel), '%s — зелёный по умолчанию (тон слоя)' % sel)
        self.assertEqual(rule(css, ','.join(TONES['light'])), LIGHT)
        self.assertIn('color:var(--c-on-olive)', rule(css, '.btn.olive'))
        self.assertIn('color:#FFFFFF', rule(css, '.ib.wa'))
        # «!» у позиций меню лежит на подложке раздела (surface) — светлая заливка с ней сливается: тонкий контур, как до стекла
        self.assertIn('border:1.3px solid var(--c-accent)', rule(css, '.mm-only'))
        for l in ('kk', 'en'):
            for sel, t in (('.btn.ghost', 'light'), ('.ib', 'light'), ('.pill-point', 'light'), ('.lang-dd summary', 'light'),
                           ('.ib.route', 'green'), ('.ib.wa', 'wa'), ('.btn.olive', 'olive')):
                self.assertEqual(tone_of(self.css[l], sel), t, '%s %s' % (l, sel))
            self.assertNotRegex(self.css[l], r'\.mm-|\.sheet', l)

    def test_no_volume_on_buttons(self):
        """у кнопок (и их наведения/нажатия) на всех страницах — ни теней, ни градиентов, ни размытия, ни своей заливки
        мимо тона, ни снятой рамки фокуса; псевдоэлементы кнопок (касание, крестики) — тоже без теней и размытия"""
        menu_light = MENU_SELS
        buttons = set(LAYERED + sum(TONES.values(), []) + sum(COPIES.values(), []) + menu_light + OTZYV[1] + ['.lang a[aria-current]'])
        checked = 0
        for p in all_pages():
            for media, pre, body in rules(css_of(read(p))):
                if pre.startswith(':where('):
                    self.assertNotRegex(body, VOLUME, '%s: слой %s' % (p, pre))
                    continue
                for part in split_sel(pre):
                    base = re.sub(r':(?:hover|active|focus-visible|focus)$', '', part)
                    pseudo = re.match(r'(.*?)::?(before|after)$', base)
                    if pseudo and pseudo.group(1) in buttons:
                        self.assertNotRegex(body, r'box-shadow|backdrop-filter|(?:^|;)filter:', '%s: %s' % (p, part))
                        if (pseudo.group(1), pseudo.group(2)) != ('.mm-search-btn', 'before'):
                            self.assertNotIn('gradient(', body, '%s: %s' % (p, part))
                        continue
                    if base not in buttons:
                        continue
                    checked += 1
                    where = '%s: %s %s' % (p, media, part)
                    if (media, part) == LUPA[:2]:
                        self.assertEqual(body, LUPA[2], where)
                    else:
                        self.assertNotRegex(body, VOLUME, where)
                    self.assertNotRegex(body, r'(?:^|;)background(?:-color)?:', '%s — своя заливка мимо тона' % where)
                    self.assertNotRegex(body, r'outline:\s*(?:none|0)', '%s — рамку фокуса не снимать' % where)
        self.assertGreater(checked, 90)

    def test_lupa_mask_present(self):
        mob = [b for m, p, b in rules(self.css['ru']) if m == LUPA[0] and p == LUPA[1]]
        self.assertEqual(mob, [LUPA[2]])

    def test_404_and_ugolok_same_as_main(self):
        main = root_vars(read('index.html'))
        for path, sels in COPIES.items():
            html = read(path)
            v, css = root_vars(html), css_of(html)
            need = ['--btn-green', '--btn-green-p', '--h-btn', '--btn-font'] + (['--btn-light', '--btn-light-p'] if '.lang-btn' in sels else [])
            own = sorted(k for k in v if k.startswith('--btn-') or k.startswith('--h-btn'))
            self.assertEqual(own, sorted(need), '%s: копия только нужных токенов' % path)
            for k in need:
                self.assertEqual(v[k], main[k], '%s: %s — дословно как на главной' % (path, k))
                if k.startswith('--btn-') and k != '--btn-font':
                    self.assertEqual(resolve(v, v[k]), resolve(main, main[k]), '%s: %s — тот же цвет' % (path, k))
            lk = layer_rules(css)
            self.assertEqual(sorted(lk), sorted(LAYER_KEYS), path)
            for key in LAYER_KEYS:
                self.assertEqual(lk[key], (sels, self.layer[key][1]), '%s: слой %s — дословно как на главной' % (path, key))
        ug = css_of(read('ugolok/index.html'))
        self.assertEqual(rule(ug, '.lang-btn,.tb-back'), LIGHT, '/ugolok: языки и «на главную» — светлые')
        self.assertEqual(rule(ug, '.lang-btn.on'), GREEN_ON, 'выбранный язык — зелёный')
        self.assertIn('min-height:var(--h-btn)', rule(ug, '.pass-btn'))
        self.assertIn('min-height:var(--h-btn)', rule(css_of(read('404.html')), 'a.btn'))

    def test_text_menus_same_as_main(self):
        for p in TEXT_MENUS:
            css = css_of(read(p))
            lk = layer_rules(css)
            self.assertEqual(sorted(lk), sorted(LAYER_KEYS), p)
            for key in LAYER_KEYS:
                self.assertEqual(lk[key], (MENU_SELS, self.layer[key][1]), '%s %s' % (p, key))
            self.assertEqual(rule(css, ','.join(MENU_SELS)), LIGHT, '%s: светлый тон — как у главной' % p)
            self.assertEqual(rule(css, '.lang a[aria-current]'), GREEN_ON, p)
            self.assertEqual(root_vars(read(p))['--btn-light'], 'var(--c-surface)', '%s: токены — из :root главной' % p)


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

    def test_rows_leave_room_for_touch(self):
        """ряды вкладок и разделов прокручиваются (overflow-x): касание чипа (4px сверху) должно лечь в поля ряда"""
        rows = rule(self.css, '.mm-tabs,.mm-cats')
        self.assertIn('padding:var(--s-4) var(--s-24) var(--s-8)', rows)
        mob = ''.join(re.findall(r'@media\(max-width:680px\)\{(.*?)\}\}', self.css))
        self.assertIn('.mm-tabs,.mm-cats{padding:var(--s-4) var(--s-12) var(--s-8)', mob)
        self.assertNotRegex(mob, r'\.mm-tab\{padding', 'поля чипа на телефоне — тоже 16')

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
