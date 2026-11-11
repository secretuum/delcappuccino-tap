"""Сторожа шлифовки главной (polish-main, 09.11.2026: «допиливай все детали мелкие»): то, что исправили, не должно вернуться.
Контраст кнопки WhatsApp, разметка без дублей id, у картинок alt и размеры, у кнопок type, окна — диалоги с возвратом фокуса,
видимый фокус, касание, reduced-motion, неразрывный пробел перед ₸, соцсети-превью на всех страницах.
Запуск из корня репозитория: python3 -m unittest discover -s tests -v"""
import glob, json, os, re, shutil, subprocess, sys, tempfile, unittest
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_perf import as_run  # noqa: E402  главная с кодом из assets/{home,site}.<хэш>.js, как её исполняет браузер

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = ['index.html', 'kk/index.html', 'en/index.html', 'menyu/index.html', 'kk/menyu/index.html', 'en/menu/index.html']


def read(p):
    with open(os.path.join(ROOT, p), encoding='utf-8') as f:
        return f.read()


def main_run():
    """главная, как её исполняет браузер (встроенные скрипты, затем файлы кода defer)"""
    return as_run(read('index.html'))


def main_file(d):
    """путь к main_run() во временной папке — для прогонов в node"""
    path = os.path.join(d, 'index.html')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(main_run())
    return path


def css_of(html):
    css = html[html.index('<style>') + 7:html.index('</style>')]
    return re.sub(r'\s*\n\s*', '', re.sub(r'/\*.*?\*/', '', css, flags=re.S))


def root_vars(html):
    return dict(re.findall(r'(--[\w-]+):\s*([^;]+?)\s*;', re.search(r':root\{(.*?)\}', css_of(html)).group(1)))


# ── контраст по WCAG 2.x ──
def _lin(c):
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def lum(rgb):
    r, g, b = (_lin(x) for x in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def over(fg, a, bg):
    return tuple(f * a + b * (1 - a) for f, b in zip(fg, bg))


def rgba(s):
    m = re.match(r'rgba\((\d+),(\d+),(\d+),([\d.]+)\)', s)
    return tuple(int(x) for x in m.groups()[:3]), float(m.group(4))


def hexrgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


class TestWhatsAppTone(unittest.TestCase):
    """09.11: при шлифовке тон WhatsApp меняли на #128C7E (белый логотип на #25D366 — ~1,9:1); владелец посмотрел на сайте:
    «кнопка ватсапа стала неестественной, цвет лучше оставить тот который был» — вернули фирменный #25D366.
    Контраст логотипа здесь сознательно не проверяем: это решение владельца, не недосмотр"""

    def test_brand_green(self):
        v = root_vars(read('index.html'))
        self.assertEqual(v['--c-whatsapp'], '#25D366', 'WhatsApp — фирменный зелёный (решение владельца 09.11)')
        self.assertEqual(v['--btn-wa'], 'var(--c-whatsapp)', 'кнопка WhatsApp — того же тона (плоская заливка с 11.11)')


VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr', 'param'}
SVG_LEAF = {'path', 'circle', 'rect', 'use', 'stop', 'line', 'polyline', 'polygon', 'ellipse'}


class Page(HTMLParser):
    """теги с атрибутами, id, незакрытые теги, текст вне script/style"""

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.tags, self.ids, self.stack, self.problems, self.text = [], [], [], [], []
        self.feed(html)
        self.close()
        self.problems += ['не закрыт <%s> (строка %d)' % t for t in self.stack]

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.tags.append((tag, a, self.getpos()[0]))
        if 'id' in a:
            self.ids.append(a['id'])
        if tag not in VOID and tag not in SVG_LEAF:
            self.stack.append((tag, self.getpos()[0]))

    def handle_startendtag(self, tag, attrs):
        a = dict(attrs)
        self.tags.append((tag, a, self.getpos()[0]))
        if 'id' in a:
            self.ids.append(a['id'])

    def handle_endtag(self, tag):
        if tag in VOID or tag in SVG_LEAF:
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                self.problems += ['<%s> (строка %d) закрыт по </%s>' % (t, l, tag) for t, l in self.stack[i + 1:] if t not in ('p', 'li')]
                del self.stack[i:]
                return
        self.problems.append('лишний </%s> (строка %d)' % (tag, self.getpos()[0]))

    def handle_data(self, d):
        if not (self.stack and self.stack[-1][0] in ('script', 'style')):
            self.text.append(d)


class TestMarkup(unittest.TestCase):
    """главная, /kk/, /en/ и три текстовых меню: валидное дерево, уникальные id, alt и размеры у картинок, type у кнопок,
    href у ссылок, рабочие внутренние ссылки и якоря"""

    @classmethod
    def setUpClass(cls):
        cls.pages = {p: Page(read(p)) for p in PAGES}

    def test_tree_and_ids(self):
        for p, pg in self.pages.items():
            self.assertEqual(pg.problems, [], p)
            dup = sorted({i for i in pg.ids if pg.ids.count(i) > 1})
            self.assertEqual(dup, [], '%s: дубли id' % p)

    def test_images_buttons_links(self):
        for p, pg in self.pages.items():
            for tag, a, line in pg.tags:
                where = '%s:%d' % (p, line)
                if tag == 'img':
                    self.assertIn('alt', a, where)
                    self.assertTrue(a.get('width') and a.get('height'), '%s: у картинки нет width/height — вёрстка прыгает' % where)
                if tag == 'button':
                    self.assertIn(a.get('type'), ('button', 'submit', 'reset'), '%s: кнопка без type' % where)
                if tag == 'a':
                    self.assertIn('href', a, where)
            self.assertRegex(read(p), r'<html lang="(ru|kk|en)">', p)

    def test_buttons_drawn_by_script_have_type(self):
        js = ''.join(re.findall(r'<script>(.*?)</script>', main_run(), re.S))
        for b in re.findall(r'<button\b[^>]*>', js):
            self.assertIn('type="button"', b, b)

    def test_internal_links_resolve(self):
        for p, pg in self.pages.items():
            base = os.path.dirname(os.path.join(ROOT, p))
            for tag, a, line in pg.tags:
                for key in ('href', 'src', 'poster'):
                    h = a.get(key)
                    if not h or tag == 'use' or re.match(r'(https?:|mailto:|tel:|data:)', h):
                        continue
                    if h.startswith('#'):
                        if h != '#' and not h.startswith('#menu'):     # #menu… — глубокие ссылки меню (скрипт)
                            self.assertIn(h[1:], pg.ids, '%s:%d: якорь %s' % (p, line, h))
                        continue
                    path = h.split('#')[0].split('?')[0]
                    f = os.path.join(ROOT, path.lstrip('/')) if path.startswith('/') else os.path.join(base, path)
                    ok = any(os.path.isfile(x) for x in (f, f + '.html', os.path.join(f, 'index.html')))
                    self.assertTrue(ok, '%s:%d: битая ссылка %s' % (p, line, h))

    def test_tenge_not_torn_off(self):
        """перед ₸ — неразрывный пробел (в тексте страниц; подписи aria-label не в счёт)"""
        for p, pg in self.pages.items():
            self.assertNotRegex(''.join(pg.text), r'\d[ \t\n]₸', p)
        self.assertIn('}&nbsp;₸</div>`', main_run(), 'цена в карточке блюда')

    def test_social_preview(self):
        from PIL import Image
        with Image.open(os.path.join(ROOT, 'assets', 'photo_01.jpg')) as im:
            w, h = im.size
        for p in PAGES:
            head = read(p).split('</head>')[0]
            self.assertIn('<meta property="og:image" content="https://tap.delcappuccino.kz/assets/photo_01.jpg">', head, p)
            self.assertIn('<meta property="og:image:width" content="%d">' % w, head, p)
            self.assertIn('<meta property="og:image:height" content="%d">' % h, head, p)
            self.assertIn('<meta name="twitter:card" content="summary_large_image">', head, p)


class TestFocusAndMotion(unittest.TestCase):
    def test_focus_ring_contrast(self):
        """рамка фокуса — --c-olive-text (им же мелкий оливковый текст в 404 и /ugolok): ≥ 4,5:1 на белом и сером
        (светлая олива давала 3,0 и 2,8:1); копии токена в 404 и /ugolok равны главной"""
        main = root_vars(read('index.html'))
        for p in ('index.html', 'kk/index.html', 'en/index.html'):
            css = css_of(read(p))
            self.assertIn(':focus-visible{outline:2px solid var(--c-olive-text);', css, p)
            self.assertNotRegex(css, r'focus-visible\{outline:[^}]*var\(--(?:c-)?olive\)', '%s: старая олива в рамке фокуса' % p)
        ring = hexrgb(main['--c-olive-text'])
        for back in ('--c-bg', '--c-surface', '--c-raised'):
            self.assertGreaterEqual(contrast(ring, hexrgb(main[back])), 4.5, back)
        for p in ('404.html', 'ugolok/index.html'):
            self.assertEqual(root_vars(read(p))['--c-olive-text'], main['--c-olive-text'], '%s: копия токена' % p)

    def test_touch_targets(self):
        css = css_of(read('index.html'))
        self.assertIn('.sheet .x,.mm-x,.mm-card-x{display:inline-flex;align-items:center;justify-content:center;width:44px;height:44px;', css)
        self.assertIn(".mm-only::after{content:'';position:absolute;inset:-15px}", css, '15 + 2 × 15 = 45')
        self.assertIn(".mm-search-btn::after{content:'';position:absolute;inset:-4px -2px}", css, 'лупа 40 → касание 44 × 48')

    def test_reduced_motion(self):
        for p in ('index.html', 'kk/index.html', 'en/index.html'):
            media = ''.join(re.findall(r'@media\(prefers-reduced-motion:reduce\)\{(.*?)\}\}', css_of(read(p))))
            self.assertIn('html{scroll-behavior:auto', media, p)
        css = css_of(read('index.html'))
        self.assertIn('@media(prefers-reduced-motion:reduce){.mm-tabs,.mm-cats{scroll-behavior:auto}.sheet,.mm-card-box{animation:none}}', css)
        js = ''.join(re.findall(r'<script>(.*?)</script>', main_run(), re.S))
        for line in js.split('\n'):
            if "'smooth'" in line:
                self.assertIn('RM.matches', line, 'прокрутка скриптом смотрит на reduced-motion: ' + line.strip()[:120])


def find_node():
    ver = lambda p: [int(x) for x in re.findall(r'\d+', p.split('/node/')[-1].split('/')[0])]
    return shutil.which('node') or (sorted(glob.glob(os.path.expanduser('~/.nvm/versions/node/*/bin/node')), key=ver) or [None])[-1]


FOCUS_HARNESS = r"""
const fs = require('fs'), vm = require('vm');
const html = fs.readFileSync(process.argv[2], 'utf8');
const scripts = [...html.matchAll(/<script(?![^>]*\bsrc=)(?![^>]*ld\+json)[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const els = {}, docL = {}; let active = null;
const el = id => { const cls = new Set(); const o = { id, innerHTML: '', textContent: '', hidden: true, dataset: {}, scrollTop: 0, offsetHeight: 0,
  style: { setProperty() {}, removeProperty() {} }, _l: {},
  classList: { add: c => cls.add(c), remove: c => cls.delete(c), toggle: (c, f) => ((f === undefined ? !cls.has(c) : f) ? cls.add(c) : cls.delete(c)), contains: c => cls.has(c) },
  addEventListener(t, f) { (o._l[t] = o._l[t] || []).push(f); }, removeEventListener() {}, appendChild: x => x, insertAdjacentHTML() {},
  contains: () => false, getAttribute: () => null, querySelector(sel) { return (o._q = o._q || {})[sel] || (o._q[sel] = el(id + ' ' + sel)); },
  querySelectorAll: () => [], getBoundingClientRect: () => ({ top: 0, bottom: 0 }), scrollTo() {}, setAttribute() {}, removeAttribute() {},
  focus() { active = o; }, closest: () => null }; return o; };
const document = { getElementById: id => els[id] || (els[id] = el(id)), querySelector: s => els['q:' + s] || (els['q:' + s] = el('q:' + s)),
  querySelectorAll: () => [], addEventListener(t, f) { (docL[t] = docL[t] || []).push(f); }, createElement: () => el('x'),
  body: el('body'), documentElement: el('html'), head: el('head'), readyState: 'loading', get activeElement() { return active; } };
const ctx = { document, console, setTimeout: () => 0, clearTimeout() {}, requestAnimationFrame: () => 0, requestIdleCallback: () => 0,
  matchMedia: () => ({ matches: false, addEventListener() {}, addListener() {} }), IntersectionObserver: function () { return { observe() {} }; },
  fetch: () => new Promise(() => {}), localStorage: { getItem() { return null; }, setItem() {} }, navigator: {},
  location: { hash: '', pathname: '/', search: '' }, history: { replaceState() {} }, addEventListener() {}, scrollTo() {}, Image: function () {} };
ctx.window = ctx; vm.createContext(ctx); scripts.forEach(s => vm.runInContext(s, ctx));
const R = c => vm.runInContext(c, ctx), out = {}, opener = el('opener');
opener.focus(); R("openModal('book')"); out.modalOpen = active.id;
R('closeModal()'); out.modalClosed = active.id;
opener.focus(); R('openMenu()'); out.menuOpen = active.id;
docL.keydown.forEach(f => f({ key: 'Escape' })); out.menuEsc = [els['menu-modal'].classList.contains('open'), active.id];
opener.focus(); R("openModal('route')"); R("closeModal();openMenu('togo')"); R('closeMenu()'); out.modalToMenu = active.id;
const items = [{ n: 'a', offsetParent: {}, tabIndex: 0 }, { n: 'b', offsetParent: null, tabIndex: 0 }, { n: 'c', offsetParent: {}, tabIndex: 0 }];
items.forEach(x => { x.focus = () => { active = x; }; });
const box = { querySelectorAll: () => items }, ev = s => ({ key: 'Tab', shiftKey: s, preventDefault() { this.p = true; } });
active = items[2]; let e = ev(false); R('trapTab')(e, box); out.tabLast = [!!e.p, active.n];
active = items[0]; e = ev(true); R('trapTab')(e, box); out.shiftFirst = [!!e.p, active.n];
active = items[0]; e = ev(false); R('trapTab')(e, box); out.tabMiddle = [!!e.p, active.n];
console.log(JSON.stringify(out));
"""


class TestDialogFocus(unittest.TestCase):
    """окно выбора филиала и меню (поручение: Esc и Tab): фокус внутрь, Tab по кругу, после закрытия — на место"""

    def test_dialog_markup(self):
        pg = Page(read('index.html'))
        attrs = {a.get('id'): a for _, a, _ in pg.tags if a.get('id')}
        for i in ('modal', 'menu-modal'):
            self.assertEqual((attrs[i].get('role'), attrs[i].get('aria-modal')), ('dialog', 'true'), i)
        self.assertIn(attrs['modal']['aria-labelledby'], attrs, 'имя окна — его заголовок')
        back = [a for t, a, _ in pg.tags if t == 'button' and 'backdrop' in a.get('class', '')][0]
        self.assertEqual((back.get('tabindex'), back.get('aria-hidden')), ('-1', 'true'), 'подложка — не кнопка без имени в порядке Tab')

    def test_focus_in_node(self):
        node = find_node()
        if not node:
            self.skipTest('нет node')
        with tempfile.TemporaryDirectory() as d:
            h = os.path.join(d, 'f.js')
            with open(h, 'w', encoding='utf-8') as f:
                f.write(FOCUS_HARNESS)
            r = subprocess.run([node, h, main_file(d)], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr[-1500:])
        got = json.loads(r.stdout)
        self.assertEqual(got['modalOpen'], 'modal .x', 'окно филиалов: фокус на «закрыть»')
        self.assertEqual(got['modalClosed'], 'opener', 'после закрытия — на кнопку, которой открыли')
        self.assertEqual(got['menuOpen'], 'mm-x', 'меню: фокус на «закрыть»')
        self.assertEqual(got['menuEsc'], [False, 'opener'], 'Esc закрывает меню и возвращает фокус')
        self.assertEqual(got['modalToMenu'], 'opener', '«Меню» в окне филиалов → меню → закрыть: фокус на исходной кнопке')
        self.assertEqual(got['tabLast'], [True, 'a'], 'Tab с последнего — на первый')
        self.assertEqual(got['shiftFirst'], [True, 'c'], 'Shift+Tab с первого — на последний (скрытые пропускаем)')
        self.assertEqual(got['tabMiddle'], [False, 'a'], 'внутри — обычный порядок')


if __name__ == '__main__':
    unittest.main()
