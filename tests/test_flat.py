"""Плоско везде, не только кнопки (владелец 11.11.2026 на список «объёмного вне кнопок»: «да, делай все плоским»).
Сторожат на всех страницах сайта (главная, /kk/, /en/, три текстовых меню, 404, /ugolok, /otzyv):
- ни одно правило — ни в @media любой ширины, ни при наведении, ни в печати — не задаёт тень (box-shadow, text-shadow,
  filter: drop-shadow), размытие (backdrop-filter), фильтр или градиент (фона, маски, SVG): раз объявления нет нигде,
  в каскаде его не получит ни один элемент. Исключение одно — маска у лупы меню (tests/test_glass.py, LUPA);
- при наведении ничего не поднимается и не увеличивается (без transform), тень не появляется;
- шапки (главная, /kk/, /en/, 404, /ugolok, /otzyv, шапка меню) — сплошной белый фон и линия 1px снизу;
- карточки точек и /otzyv — белые с рамкой 1px вместо тени; разделы меню — подложка surface без тени; выпадающий
  список языков, язык меню на телефоне и подсказка «!» — рамка 1px вместо тени;
- «Курица гриль»: огненная рамка — те же контуры, но сплошные заливки; без свечения окна, тени рамки и свечения строки;
  полоса «ВНИМАНИЕ» — сплошной --c-danger, жёлтый на нём ≥ 4,5:1;
- подписи плиток — ровная полупрозрачная плашка, текст ≥ 4,5:1 даже над белым кадром видео; на видеозоне нет узора
  точками, плашка первого экрана — сплошная.
Токены --shadow-floating и --c-glass остаются в :root (паритет с темой приложения, tests/test_redesign.py), но не используются.
Фото и видео не трогаем — это содержимое, не оформление.
Запуск из корня репозитория: python3 -m unittest discover -s tests -v"""
import os, re, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import seo_jsonld as seo  # noqa: E402

PAGES = ['index.html', 'kk/index.html', 'en/index.html', 'menyu/index.html', 'kk/menyu/index.html', 'en/menu/index.html',
         '404.html', 'ugolok/index.html', 'otzyv/index.html']
HOMES = ['index.html', 'kk/index.html', 'en/index.html']
LUPA = ('@media(max-width:680px)', '.mm-search-btn', 'box-shadow:var(--s-12) 0 0 var(--c-bg)')
VOLUME = r'box-shadow|text-shadow|drop-shadow|backdrop-filter|(?:^|;)-?(?:webkit-)?filter:|gradient\(|var\(--shadow-floating\)|var\(--c-glass\)'


def read(p):
    with open(os.path.join(ROOT, p), encoding='utf-8') as f:
        return f.read()


def css_of(html):
    css = html[html.index('<style>') + 7:html.index('</style>')]
    return re.sub(r'\s*\n\s*', '', re.sub(r'/\*.*?\*/', '', css, flags=re.S))


def rules(css, media=''):
    """(media, селектор, тело) — все правила, с заходом во все @media/@supports"""
    out = []
    for r in seo.css_rules(css):
        pre, body = r.split('{', 1)
        pre = pre.strip()
        if pre.startswith(('@media', '@supports')):
            out += rules(body[:-1], (media + ' ' + pre).strip())
        elif not pre.startswith('@'):
            out.append((media, pre, body[:-1]))
    return out


def rule(css, sel, media=''):
    hit = [b for m, p, b in rules(css) if p == sel and m == media]
    return hit[-1] if hit else None


def root_vars(html):
    return dict(re.findall(r'(--[\w-]+):\s*([^;]+?)\s*;', re.search(r':root\{(.*?)\}', css_of(html)).group(1)))


def color(v, s):
    """'#RRGGBB' | 'rgba(r,g,b,a)' | 'var(--x)' → ((r, g, b), a)"""
    for _ in range(5):
        s = re.sub(r'var\((--[\w-]+)\)', lambda m: v[m.group(1)], s.strip())
    if s.startswith('#'):
        return tuple(int(s[i:i + 2], 16) for i in (1, 3, 5)), 1.0
    m = re.match(r'rgba\((\d+),(\d+),(\d+),([\d.]+)\)$', s.replace(' ', ''))
    return tuple(int(x) for x in m.groups()[:3]), float(m.group(4))


def over(top, under):
    (c, a), b = top, under
    return tuple(x * a + y * (1 - a) for x, y in zip(c, b))


def contrast(a, b):
    def lum(rgb):
        lin = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        r, g, b_ = (lin(x / 255) for x in rgb)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b_
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def decl(body, prop):
    m = re.search(r'(?:^|;)' + re.escape(prop) + r':([^;]+)', body or '')
    return m.group(1) if m else None


class TestNothingVolumetric(unittest.TestCase):
    def test_no_shadow_blur_filter_gradient_anywhere(self):
        for p in PAGES:
            html = read(p)
            for media, pre, body in rules(css_of(html)):
                if pre == ':root':
                    continue
                if (media, pre) == LUPA[:2]:
                    self.assertIn(LUPA[2], body, p)
                    body = body.replace(LUPA[2], '')
                self.assertNotRegex(body, VOLUME, '%s: %s %s' % (p, media, pre))
            self.assertNotRegex(html, r'<(?:linear|radial)Gradient|<filter\b|<feGaussianBlur', '%s: градиент или фильтр в SVG' % p)
            self.assertNotRegex(html, r'style="[^"]*(?:shadow|blur|gradient)', '%s: тень в атрибуте style' % p)
            js = ''.join(re.findall(r'<script\b[^>]*>(.*?)</script>', html, re.S))
            self.assertNotRegex(js, r'\.style\.(?:boxShadow|textShadow|filter|backdropFilter|backgroundImage)\b', '%s: тень из скрипта' % p)

    def test_no_lift_on_hover(self):
        """наведение — только цвет (кнопки, ссылки, строки меню): без подъёма, увеличения и тени"""
        for p in PAGES:
            for media, pre, body in rules(css_of(read(p))):
                if ':hover' in pre:
                    self.assertNotRegex(body, r'transform|translate|scale|shadow|filter', '%s: %s' % (p, pre))
                self.assertNotRegex(decl(body, 'transition') or '', r'box-shadow|filter', '%s: %s — переход тени' % (p, pre))

    def test_bars_solid_with_line(self):
        bars = {p: 'header' for p in HOMES + ['404.html']}
        bars.update({'ugolok/index.html': '.topbar', 'otzyv/index.html': '.topbar'})
        for p, sel in bars.items():
            body = rule(css_of(read(p)), sel)
            self.assertEqual(decl(body, 'background'), 'var(--c-bg)', '%s: шапка — сплошной белый' % p)
            self.assertEqual(decl(body, 'border-bottom'), '1px solid var(--c-border)', p)
        mm = rule(css_of(read('index.html')), '.mm-head')
        self.assertEqual(decl(mm, 'background'), 'var(--c-bg)')
        self.assertEqual(decl(mm, 'border-bottom'), '1px solid var(--c-border)')

    def test_cards_lists_and_tips_framed(self):
        line = '1px solid var(--c-border)'
        for p in HOMES:
            css = css_of(read(p))
            card = rule(css, '.loc-card')
            self.assertEqual((decl(card, 'background'), decl(card, 'border')), ('var(--c-bg)', line), '%s: карточка точки' % p)
            self.assertEqual(decl(rule(css, '.lang-list'), 'border'), line, '%s: список языков' % p)
        fb = rule(css_of(read('otzyv/index.html')), '.fb-card')
        self.assertEqual((decl(fb, 'background'), decl(fb, 'border')), ('var(--c-bg)', line), '/otzyv: карточка точки')
        css = css_of(read('index.html'))
        self.assertEqual(decl(rule(css, '.mm-pop'), 'border'), line, 'подсказка «!»')
        lang = rule(css, '.mm-lang.open', '@media(max-width:680px)')
        self.assertEqual((decl(lang, 'border'), decl(lang, 'margin')), (line, '-1px'), 'язык меню: рамка, кнопки не сдвигаются')
        self.assertEqual(decl(rule(css, '.mm-sec'), 'background'), 'var(--c-surface)')
        for p in ('menyu/index.html', 'kk/menyu/index.html', 'en/menu/index.html'):
            self.assertEqual(decl(rule(css_of(read(p)), '.sec'), 'background'), 'var(--c-surface)', p)

    def test_search_focus_ring_is_outline(self):
        """кольцо фокуса поля поиска — outline, не тень (рамку фокуса сохраняем: --c-olive-text, ≥ 4,5:1)"""
        body = rule(css_of(read('index.html')), '.mm-search:focus-within')
        self.assertEqual(decl(body, 'outline'), '1px solid var(--c-olive-text)')
        self.assertEqual(decl(body, 'border-color'), 'var(--c-olive-text)')


class TestPromoAndHero(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = read('index.html')
        cls.css = css_of(cls.html)
        cls.v = root_vars(cls.html)

    def test_flame_shape_kept_fills_solid(self):
        svg = re.search(r'<svg class="grill-fire"[^>]*>(.*?)</svg>', self.html, re.S).group(1)
        fills = re.findall(r'<path class="grill-fire-(\w+)" fill="([^"]+)" d="[^"]*C[^"]*"', svg)
        self.assertEqual([k for k, _ in fills], ['outer', 'inner'], 'контур пламени и кромка — прежние кривые')
        for _, f in fills:
            self.assertRegex(f, r'^#[0-9A-F]{6}$', 'сплошной цвет, не url(#градиент)')
        self.assertNotIn('<defs', svg)
        self.assertNotIn('grill-glow', self.html)
        self.assertIsNone(decl(rule(self.css, '.grill-frame'), 'filter'))

    def test_attention_strip_solid(self):
        run = rule(self.css, '.promo-run')
        self.assertEqual(decl(run, 'background'), 'var(--c-danger)')
        ticker = rule(self.css, '.grill-ticker')
        self.assertIsNone(decl(ticker, 'text-shadow'))
        self.assertIsNone(decl(ticker, 'mask-image'))
        c = contrast(color(self.v, decl(ticker, 'color'))[0], color(self.v, 'var(--c-danger)')[0])
        self.assertGreaterEqual(c, 4.5, 'жёлтый на красной полосе: %.2f' % c)

    def test_caption_plates_readable_over_any_frame(self):
        """подпись на ровной плашке поверх видео: худший случай — белый кадр под плашкой; каждый цвет текста подписи ≥ 4,5:1"""
        texts = {'.tile-cap': ['.tile-cap .promo-t', '.promo-s', '.promo-s s'], '.grill-cap': ['.promo-t', '.promo-s', '.promo-s s', '.promo-s .sale', '.promo-a']}
        for cap, sels in texts.items():
            bg = decl(rule(self.css, cap), 'background')
            self.assertRegex(bg, r'^rgba\(\d+,\d+,\d+,[\d.]+\)$', '%s: ровная плашка, не градиент' % cap)
            for frame in ((255, 255, 255), (0, 0, 0)):
                plate = over(color(self.v, bg), frame)
                for sel in sels:
                    fg = over(color(self.v, decl(rule(self.css, sel), 'color')), plate)
                    c = contrast(fg, plate)
                    self.assertGreaterEqual(c, 4.5, '%s %s над кадром %s: %.2f' % (cap, sel, frame, c))

    def test_hero_plain(self):
        for p in HOMES:
            css = css_of(read(p))
            self.assertIsNone(rule(css, '.hero-zone::before'), '%s: узора точками нет' % p)
            self.assertEqual(decl(rule(css, '.hero-badge'), 'background'), 'var(--c-bg)', '%s: плашка первого экрана — сплошная' % p)


if __name__ == '__main__':
    unittest.main()
