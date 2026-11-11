"""Шлифовка мелочей /ugolok, 404.html и legal/style.css (владелец 09.11.2026: «допиливай все детали мелкие») — сторожа,
чтобы исправленное не вернулось. Без браузера: разбор разметки на html.parser, правила CSS регулярками, контраст — по формуле
WCAG 2.1 (color-mix in srgb считаем сами), скрипт /ugolok — в node на заглушках DOM.
Токены :root и слои стекла здесь не проверяем — это tests/test_glass.py (их хозяин — polish-main).
Запуск из корня репозитория: python3 -m unittest discover -s tests -v"""
import glob, json, os, re, shutil, subprocess, tempfile, unittest
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UGOLOK, NOT_FOUND, LEGAL_CSS = 'ugolok/index.html', '404.html', 'legal/style.css'


def read(p):
    with open(os.path.join(ROOT, p), encoding='utf-8') as f:
        return f.read()


def style_of(html):
    css = html[html.index('<style>') + 7:html.index('</style>')]
    return re.sub(r'/\*.*?\*/', '', css, flags=re.S)


def top_rules(css):
    """правила верхнего уровня (селектор, тело) — без @media; и отдельно {условие @media: [(селектор, тело)]}"""
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    top, media, i = [], {}, 0
    while i < len(css):
        j = css.find('{', i)
        if j < 0:
            break
        pre = css[i:j].strip()
        depth, k = 1, j + 1
        while depth:
            depth += {'{': 1, '}': -1}.get(css[k], 0)
            k += 1
        body = css[j + 1:k - 1]
        if pre.startswith('@media'):
            media.setdefault(re.sub(r'\s+', '', pre), []).extend(top_rules(body)[0])
        elif not pre.startswith('@'):
            top.append((re.sub(r'\s+', ' ', pre), body.strip()))
        i = k
    return top, media


def sels(pre):
    return [re.sub(r'\s+', ' ', s.strip()) for s in pre.split(',')]


def decl(rules, sel, prop):
    """последнее значение свойства у селектора (как в каскаде при равной специфичности)"""
    val = None
    for pre, body in rules:
        if sel in sels(pre):
            for m in re.finditer(r'(?:^|;)\s*%s\s*:\s*([^;]+)' % re.escape(prop), body):
                val = m.group(1).strip()
    return val


def root_vars(css):
    return dict(re.findall(r'(--[\w-]+)\s*:\s*([^;]+?)\s*;', re.search(r':root\s*\{(.*?)\}', css, re.S).group(1)))


def rgb(h):
    h = h.strip().lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def color(value, v):
    """#hex, var(--x) или color-mix(in srgb, A p%, B) → (r, g, b)"""
    value = value.strip()
    m = re.fullmatch(r'var\((--[\w-]+)\)', value)
    if m:
        return color(v[m.group(1)], v)
    m = re.fullmatch(r'color-mix\(in srgb,\s*(.+?)\s+(\d+(?:\.\d+)?)%,\s*(.+)\)', value)
    if m:
        a, p, b = color(m.group(1), v), float(m.group(2)) / 100, color(m.group(3), v)
        return tuple(round(x * p + y * (1 - p)) for x, y in zip(a, b))
    return rgb(value)


def contrast(a, b):
    def lum(c):
        c = [x / 255 for x in c]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


class Markup(HTMLParser):
    """дерево тегов: незакрытые/лишние теги, дубли id"""
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr'}

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.stack, self.problems, self.ids, self.tags = [], [], [], []
        self.feed(html)
        self.close()
        self.problems += ['не закрыт <%s> (строка %d)' % t for t in self.stack]

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.tags.append((tag, a, [t for t, _ in self.stack]))
        if 'id' in a:
            self.ids.append(a['id'])
        if tag not in self.VOID:
            self.stack.append((tag, self.getpos()[0]))

    def handle_startendtag(self, tag, attrs):
        self.tags.append((tag, dict(attrs), [t for t, _ in self.stack]))

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if self.stack and self.stack[-1][0] == tag:
            self.stack.pop()
        else:
            self.problems.append('лишний или не на месте </%s> (строка %d)' % (tag, self.getpos()[0]))


def find_node():
    ver = lambda p: [int(x) for x in re.findall(r'\d+', p.split('/node/')[-1].split('/')[0])]
    return shutil.which('node') or (sorted(glob.glob(os.path.expanduser('~/.nvm/versions/node/*/bin/node')), key=ver) or [None])[-1]


class TestMarkup(unittest.TestCase):
    def test_valid_tree_and_unique_ids(self):
        for p in (UGOLOK, NOT_FOUND):
            m = Markup(read(p))
            self.assertEqual(m.problems, [], p)
            self.assertEqual(len(m.ids), len(set(m.ids)), '%s: дубли id' % p)

    def test_buttons_have_type(self):
        for p in (UGOLOK, NOT_FOUND):
            for tag, a, _ in Markup(read(p)).tags:
                if tag == 'button':
                    self.assertEqual(a.get('type'), 'button', '%s: <button> без type="button"' % p)

    def test_images_have_alt_and_size(self):
        for p in (UGOLOK, NOT_FOUND):
            for tag, a, _ in Markup(read(p)).tags:
                if tag == 'img':
                    for k in ('alt', 'width', 'height'):
                        self.assertIn(k, a, '%s: у <img %s> нет %s' % (p, a.get('src'), k))

    def test_icons_inside_links_hidden(self):
        # значок рядом с подписью — украшение: экранный диктор читает подпись, а не «изображение»
        for p in (UGOLOK, NOT_FOUND):
            for tag, a, parents in Markup(read(p)).tags:
                if tag == 'svg' and ('a' in parents or 'button' in parents):
                    self.assertEqual(a.get('aria-hidden'), 'true', '%s: svg в ссылке без aria-hidden' % p)
        self.assertIn('<span class="ic" aria-hidden="true">ℹ️</span>', read(UGOLOK))

    def test_local_links_exist(self):
        for p in (UGOLOK, NOT_FOUND):
            for tag, a, _ in Markup(read(p)).tags:
                url = a.get('href') if tag in ('a', 'link') else a.get('src') if tag == 'img' else None
                if not url or not url.startswith('/') or url.startswith('//'):
                    continue
                path = os.path.join(ROOT, url.split('#')[0].split('?')[0].lstrip('/'))
                if path.endswith('/'):
                    path += 'index.html'
                self.assertTrue(os.path.isfile(path), '%s: нет файла для %s' % (p, url))
        pdfs = re.findall(r'href="(/ugolok/talon-[\w-]+\.pdf)"', read(UGOLOK))
        self.assertEqual(len(pdfs), 5, 'талон у каждой из 5 точек')


class TestNotFound(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = read(NOT_FOUND)
        cls.rules, cls.media = top_rules(style_of(cls.html))

    def test_noindex_lang_and_way_home(self):
        head = self.html.split('</head>')[0]
        self.assertRegex(head, r'<meta name="robots" content="noindex">', '404 в поиск не отдаём')
        self.assertIn('<html lang="ru">', self.html)
        hrefs = re.findall(r'<a [^>]*href="([^"]*)"', self.html)
        self.assertEqual(set(hrefs), {'/'}, 'все ссылки 404 — на главную')
        self.assertIn('<a class="btn" href="/">На главную</a>', self.html)

    def test_touch_targets(self):
        self.assertEqual(decl(self.rules, '.hbar a', 'min-height'), '44px', 'логотип в шапке — касание 44')
        for prop in ('min-width', 'min-height'):
            self.assertEqual(decl(self.rules, '.f-row a', prop), '44px', 'логотип 28 px в подвале — касание 44')
        self.assertEqual(decl(self.rules, 'a.btn', 'min-height'), 'var(--h-btn)')

    def test_full_height_on_phone(self):
        body = [b for p, b in self.rules if p == 'body'][0]
        self.assertIn('min-height:100vh;min-height:100dvh', body, '100dvh — без лишней прокрутки под панелью Safari')


class TestContrast(unittest.TestCase):
    """мелкий текст ≥4,5:1, рамка фокуса ≥3:1 — на белом и на подложке surface"""
    PAGES = {UGOLOK: ('--c-bg', '--c-surface', '--c-olive'), NOT_FOUND: ('--c-bg', '--c-surface', '--c-olive'),
             LEGAL_CSS: ('--bg', '--surface', '--olive')}

    def css(self, p):
        return read(p) if p.endswith('.css') else style_of(read(p))

    def test_focus_ring(self):
        for p, (bg, surface, _) in self.PAGES.items():
            css = self.css(p)
            v, (rules, _) = root_vars(css), top_rules(css)
            ring = decl(rules, ':focus-visible', 'outline-color') or decl(rules, ':focus-visible', 'outline').split()[-1]
            for back in (bg, surface):
                self.assertGreaterEqual(contrast(color(ring, v), color(v[back], v)), 3, '%s: рамка фокуса на %s' % (p, back))

    def test_olive_text(self):
        # каждый селектор, у которого где-то задан текст светлой оливой, в итоге (последнее правило) читается ≥4,5:1
        for p, (bg, surface, olive) in self.PAGES.items():
            css = self.css(p)
            v, (rules, _) = root_vars(css), top_rules(css)
            hit = [s for pre, body in rules if re.search(r'(?:^|;)\s*color\s*:\s*var\(%s\)' % olive, body) for s in sels(pre)]
            if p != LEGAL_CSS:
                self.assertTrue(hit, '%s: проверять нечего — сторож устарел?' % p)
            for s in hit:
                c = color(decl(rules, s, 'color'), v)
                for back in (bg, surface):
                    self.assertGreaterEqual(contrast(c, color(v[back], v)), 4.5, '%s: %s на %s' % (p, s, back))

    def test_checker_itself(self):
        # формула: светлая олива на подложке — 2,8:1 (было), олива 65% + текст — 5,0:1 (стало)
        v = root_vars(style_of(read(UGOLOK)))
        self.assertAlmostEqual(contrast(color('var(--c-olive)', v), color('var(--c-surface)', v)), 2.79, delta=0.02)
        self.assertAlmostEqual(contrast(color('color-mix(in srgb,var(--c-olive) 65%,var(--c-text))', v),
                                        color('var(--c-surface)', v)), 4.98, delta=0.02)


class TestUgolok(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = read(UGOLOK)
        cls.rules, cls.media = top_rules(style_of(cls.html))

    def test_lang_buttons(self):
        btns = [a for tag, a, _ in Markup(self.html).tags if tag == 'button']
        self.assertEqual([b['data-lang'] for b in btns], ['kk', 'ru', 'en'])
        for b in btns:
            self.assertEqual(b.get('lang'), b['data-lang'], 'ҚАЗ / РУС / ENG читаются на своём языке')
            self.assertEqual(b.get('aria-pressed'), 'true' if 'on' in b['class'].split() else 'false', b['data-lang'])

    def test_numbers_do_not_break(self):
        # «Талон №» и номер — неразрывно; телефон не рвётся посередине
        for label in ('lbl_talon', 'lbl_incoming'):
            self.assertEqual(len(re.findall(r'<span data-i18n="%s">[^<]*</span>&nbsp;<b>KZ\w+</b>' % label, self.html)), 5, label)
        self.assertNotRegex(self.html, r'class="talon-line">.*</span> <b>')
        self.assertEqual(decl(self.rules, '.row .v a', 'white-space'), 'nowrap')

    def test_touch_targets(self):
        for s in ('.tb-back', '.tb-brand'):
            self.assertEqual(decl(self.rules, s, 'min-height'), '44px', s)
        for prop in ('min-width', 'min-height'):
            self.assertEqual(decl(self.rules, '.f-row a', prop), '44px', 'подвал: логотип 28 px и ссылка 12 px — касание 44')
        self.assertEqual(decl(self.rules, '.lang-btn', 'min-height'), '40px')
        self.assertEqual(decl(self.rules, '.lang-btn::after', 'inset'), '-2px 0', 'языки: 40 + 2 × 2 = 44 по высоте')

    def test_back_link_press_like_other_glass(self):
        # своя transition у .tb-back перебивала пружину нажатия из слоёв стекла (:where — нулевая специфичность)
        self.assertIsNone(decl(self.rules, '.tb-back', 'transition'))

    def test_reduced_motion(self):
        self.assertEqual(decl(self.media.get('@media(prefers-reduced-motion:reduce)', []), 'html', 'scroll-behavior'), 'auto')

    def test_print(self):
        pr = self.media.get('@mediaprint')
        self.assertTrue(pr, '/ugolok: нет @media print')
        for s in ('.topbar', 'footer', '.pass-btn'):
            self.assertEqual(decl(pr, s, 'display'), 'none', 'печать без %s' % s)
        self.assertEqual(decl(pr, '.cards', 'grid-template-columns'), '1fr 1fr')
        for s in ('.pass', '.info', '.note'):
            self.assertEqual(decl(pr, s, 'break-inside'), 'avoid', s)
        for s in ('.pass-num', '.steps li::before', '.info li::before'):
            self.assertEqual(decl(pr, s, 'print-color-adjust'), 'exact', '%s: цифры и маркеры нарисованы фоном — фон печатаем' % s)
        for s in ('.row .k', '.talon-line'):
            size = decl(pr, s, 'font-size')
            self.assertRegex(size, r'^\d+pt$')
            self.assertGreaterEqual(int(size[:-2]), 8, s)

    def test_og_image(self):
        m = re.search(r'<meta property="og:image" content="https://tap\.delcappuccino\.kz/([^"]+)">', self.html)
        self.assertIsNotNone(m, 'превью ссылки в мессенджерах')
        self.assertTrue(os.path.isfile(os.path.join(ROOT, m.group(1))))
        self.assertIn('<meta property="og:locale" content="kk_KZ">', self.html)

    def test_i18n_keys_same_in_three_languages(self):
        keys = {}
        for lang in ('kk', 'ru', 'en'):
            block = re.search(r'\b%s:\s*\{(.*?)\n  \}' % lang, self.html, re.S).group(1)
            keys[lang] = dict(re.findall(r'(\w+):"((?:[^"\\]|\\.)*)"', block))
            for k, t in keys[lang].items():
                self.assertEqual(t, re.sub(r'\s+', ' ', t).strip(), '%s.%s: лишние пробелы' % (lang, k))
        self.assertEqual(set(keys['kk']), set(keys['ru']))
        self.assertEqual(set(keys['kk']), set(keys['en']))
        used = set(re.findall(r'data-i18n="(\w+)"', self.html))
        self.assertEqual(used - set(keys['kk']), set(), 'в разметке ключ, которого нет в словаре')
        for k, t in re.findall(r'data-i18n="(\w+)"[^>]*>([^<]*)<', self.html):
            self.assertEqual(t, keys['kk'][k], 'текст в разметке = казахский словарь (страница открывается на ҚАЗ): %s' % k)

    def test_lang_switch_in_node(self):
        node = find_node()
        if not node:
            self.skipTest('нет node')
        script = [s for s in re.findall(r'<script>([\s\S]*?)</script>', self.html) if 'const I18N' in s][0]
        harness = r"""
const vm = require('vm'), fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');
const mk = (attrs) => { const a = Object.assign({}, attrs), cls = new Set((a['class'] || '').split(' ').filter(Boolean));
  return { textContent: '', getAttribute: k => (k in a ? a[k] : null), setAttribute: (k, x) => { a[k] = String(x); },
    classList: { toggle: (c, on) => { on ? cls.add(c) : cls.delete(c); }, contains: c => cls.has(c) }, attrs: a, cls }; };
const btns = ['kk', 'ru', 'en'].map((l, i) => mk({ 'data-lang': l, 'class': 'lang-btn' + (i ? '' : ' on'), 'aria-pressed': i ? 'false' : 'true' }));
const back = [mk({ 'data-i18n': 'back' }), mk({ 'data-i18n': 'back' })];
const events = [];
const document = { documentElement: { lang: 'kk' }, title: '',
  querySelectorAll: q => q === '.lang-btn' ? btns : q === '[data-i18n]' ? back : [] };
const ctx = { document, track: (n, p) => events.push([n, p]) };
vm.createContext(ctx); vm.runInContext(src, ctx);
const state = () => ({ lang: document.documentElement.lang, title: document.title, back: back.map(b => b.textContent),
  pressed: btns.map(b => b.attrs['aria-pressed']), on: btns.map(b => b.cls.has('on')), events: events.slice() });
const out = { load: state() };
ctx.setLang('ru'); out.ru = state();
console.log(JSON.stringify(out));
"""
        with tempfile.TemporaryDirectory() as d:
            h, s = os.path.join(d, 'h.js'), os.path.join(d, 's.js')
            with open(h, 'w', encoding='utf-8') as f:
                f.write(harness)
            with open(s, 'w', encoding='utf-8') as f:
                f.write(script)
            r = subprocess.run([node, h, s], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr[-1500:])
        out = json.loads(r.stdout)
        load, ru = out['load'], out['ru']
        self.assertEqual(load['events'], [], 'открытие страницы — не выбор языка: ugolok_lang не шлём')
        self.assertEqual((load['lang'], load['back'], load['pressed']), ('kk', ['Басты бетке'] * 2, ['true', 'false', 'false']))
        self.assertEqual(ru['events'], [['ugolok_lang', {'lang': 'ru'}]], 'выбор языка посетителем — одно событие')
        self.assertEqual((ru['lang'], ru['title'], ru['back']), ('ru', 'Уголок потребителя — Del Cappuccino', ['На главную'] * 2))
        self.assertEqual((ru['pressed'], ru['on']), (['false', 'true', 'false'], [False, True, False]))


class TestLegalStyle(unittest.TestCase):
    """legal/style.css (HTML документов — kofe-app, байт в байт; правим только стиль)"""
    @classmethod
    def setUpClass(cls):
        cls.rules, cls.media = top_rules(read(LEGAL_CSS))

    def test_touch_targets(self):
        self.assertEqual(decl(self.rules, '.langs a', 'min-height'), '44px', 'языки — касание 44')
        self.assertEqual(decl(self.rules, '.top a', 'min-height'), '44px')
        # «← На главную»: касание 44, а строка в ряду — прежние 32 (поля −6 px)
        self.assertEqual(decl(self.rules, '.top a.home', 'min-height'), '44px')
        self.assertEqual(decl(self.rules, '.top a.home', 'margin'), '-6px 0')
        self.assertEqual(decl(self.rules, '.langs', 'align-items'), 'center', 'логотип 40 и пилюли 44 — по центру строки')

    def test_print(self):
        pr = self.media.get('@mediaprint')
        self.assertTrue(pr, 'legal/style.css: нет @media print')
        for s in ('.langs', '.top', '.bottom', 'footer'):
            self.assertEqual(decl(pr, s, 'display'), 'none', 'печать без %s' % s)
        self.assertEqual(decl(pr, 'body', 'font-size'), '12pt')
        self.assertEqual(decl(pr, 'main', 'margin'), '0', 'без боковых полей телефона на листе')
        self.assertEqual(decl(pr, 'h2', 'break-after'), 'avoid')
        self.assertEqual(decl(pr, 'tr', 'break-inside'), 'avoid')

    def test_no_fixed_widths_wider_than_phone(self):
        for p, css in ((LEGAL_CSS, read(LEGAL_CSS)), (UGOLOK, style_of(read(UGOLOK))), (NOT_FOUND, style_of(read(NOT_FOUND)))):
            for w in re.findall(r'(?<![\w-])(?:min-)?width\s*:\s*(\d+)px', css):
                self.assertLessEqual(int(w), 288, '%s: ширина %s px не влезет в телефон 320 px' % (p, w))


if __name__ == '__main__':
    unittest.main()
