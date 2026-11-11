"""Ближайшая точка — сверху (задача владельца 11.11.2026: «по гео определялась самая ближайшая точка, и карточки с заведениями
поднимались по отдалённости: в самый верх ближайшая точка, чтобы клиент не искал»).
Сторожат:
- общий файл assets/near.<хэш>.js — ровно один, собран генератором из tools/near.js; в нём бывшие dist() и запрос геолокации
  окна выбора филиала (главная зовёт их через window.dcNear) и сортировка карточек; тег <script src defer> — только на /, /kk/,
  /en/ (за блоком #locations) и /otzyv/ (за карточками); координаты точек в файле — из BRANCHES и EXTRA_POINTS (Sputnik Mall —
  метка ТРЦ на Яндекс Картах; в BRANCHES, JSON-LD, #locations и окне выбора её по-прежнему нет — tests/test_otzyv.py);
- поведение на заглушке DOM в node (настоящая разметка карточек страниц): /otzyv спрашивает сразу; #locations — когда блок
  попал в экран (IntersectionObserver), при уже данном разрешении (Permissions API) — сразу; ближайшая — первой, расстояние
  «1,2 км» / «1.2 km» на каждой; отказ, ошибка, тайм-аут, нет геолокации — порядок прежний, в блоке ничего, на /otzyv —
  строка .fb-geo; анимации — только transform и opacity, блок не на экране или reduced-motion — без них;
- приватность: координаты человека не сохраняются (localStorage, sessionStorage, cookie, атрибуты) и не уходят (fetch, XHR,
  sendBeacon); в аналитику — только geo_sort {result}; подписи расстояний — ym-hide-content;
- окно выбора филиала главной на общем файле: порядок по близости и тот же формат расстояния; без файла — выбор вручную.
Запуск из корня репозитория: python3 -m unittest discover -s tests -v"""
import glob, json, math, os, re, shutil, subprocess, sys, tempfile, unittest
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import seo_jsonld as seo  # noqa: E402
import feedback_page as fb  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_perf import as_run  # noqa: E402  главная с кодом из assets/{home,site}.<хэш>.js, как её исполняет браузер

WITH = ['index.html', 'kk/index.html', 'en/index.html', 'otzyv/index.html']
WITHOUT = ['menyu/index.html', 'kk/menyu/index.html', 'en/menu/index.html', 'ugolok/index.html', '404.html']
SPUTNIK_GEO = (43.21216, 76.842353)       # Яндекс Карты, организация 1085318890 «Спутник Молл», Мамыр-1, 8А (curl 11.11.2026)
NEAR_03 = [43.2405, 76.9255]               # у БП Promenade (Абая, 44А), ~60 м
NEAR_SPUTNIK = [43.2125, 76.842]           # у ТРЦ Sputnik Mall


def read(p):
    with open(os.path.join(ROOT, p), encoding='utf-8') as f:
        return f.read()


def find_node():
    ver = lambda p: [int(x) for x in re.findall(r'\d+', p.split('/node/')[-1].split('/')[0])]
    return shutil.which('node') or (sorted(glob.glob(os.path.expanduser('~/.nvm/versions/node/*/bin/node')), key=ver) or [None])[-1]


def haversine(a, b):
    """та же формула, что dist() — независимая проверка в Python"""
    r = math.pi / 180
    s = math.sin((b[0] - a[0]) * r / 2) ** 2 + math.cos(a[0] * r) * math.cos(b[0] * r) * math.sin((b[1] - a[1]) * r / 2) ** 2
    return 6371 * 2 * math.atan2(math.sqrt(s), math.sqrt(1 - s))


class Tree(HTMLParser):
    """разметка → {tag, attrs, kids:[…|{'comment': …}], text}; комментарии сохраняются (маркеры генератора в #loc-grid)"""
    VOID = {'meta', 'link', 'img', 'br', 'input', 'source', 'path', 'hr', 'use', 'circle', 'rect'}

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = self.cur = {'tag': '#root', 'attrs': {}, 'kids': [], 'text': ''}
        self.stack = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        n = {'tag': tag, 'attrs': {k: (v if v is not None else '') for k, v in attrs}, 'kids': [], 'text': ''}
        self.cur['kids'].append(n)
        if tag not in self.VOID:
            self.stack.append(self.cur)
            self.cur = n

    def handle_startendtag(self, tag, attrs):
        self.cur['kids'].append({'tag': tag, 'attrs': {k: (v or '') for k, v in attrs}, 'kids': [], 'text': ''})

    def handle_endtag(self, tag):
        while self.stack and self.cur['tag'] != tag:
            self.cur = self.stack.pop()
        if self.stack:
            self.cur = self.stack.pop()

    def handle_data(self, data):
        self.cur['text'] += data

    def handle_comment(self, data):
        self.cur['kids'].append({'comment': data})

    def find(self, pred, n=None):
        n = n or self.root
        if 'tag' in n and pred(n):
            return n
        for k in n.get('kids', []):
            r = self.find(pred, k)
            if r:
                return r
        return None


def grid_of(page):
    t = Tree(read(page))
    cls = lambda n: (n['attrs'].get('class') or '').split()
    grid = t.find(lambda n: 'fb-grid' in cls(n) or 'loc-grid' in cls(n))
    geo = t.find(lambda n: 'fb-geo' in cls(n))
    return grid, geo


def near_file():
    return glob.glob(os.path.join(ROOT, 'assets', 'near.*.js'))


class TestNearFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = read('index.html')
        cls.path, cls.text = seo.near_js(cls.main)
        cls.src = read('tools/near.js')

    def test_one_file_from_generator(self):
        self.assertEqual(near_file(), [self.path], 'ровно один общий файл — тот, что собирает генератор (старый — git rm)')
        with open(self.path, encoding='utf-8') as f:
            self.assertEqual(f.read(), self.text, 'python3 tools/seo_jsonld.py')
        self.assertRegex(os.path.basename(self.path), r'^near\.[0-9a-f]{8}\.js$', 'имя с хэшем — sw.js держит его в кэше навсегда')
        sw = read('sw.js')
        self.assertRegex('/assets/' + os.path.basename(self.path), re.search(r"var HASHED = new RegExp\('(.*)'\);", sw).group(1).replace('\\\\', '\\'))
        self.assertEqual(seo.stale_js(seo.outputs(self.main)), [])

    def test_tag_only_where_cards_are(self):
        tag = seo.near_tag(self.main)
        self.assertEqual(tag, '<script src="/assets/%s" defer></script>' % os.path.basename(self.path))
        for p in WITH:
            self.assertEqual(read(p).count('/assets/near.'), 1, p)
            self.assertEqual(read(p).count(tag), 1, p)
        for p in WITHOUT:
            self.assertNotIn('/assets/near.', read(p), p)

    def test_tag_right_after_the_cards(self):
        for p in ('index.html', 'kk/index.html', 'en/index.html'):
            self.assertRegex(read(p), r'(?s)<section class="locations" id="locations">(?:(?!</section>).)*</section>\n' + re.escape(seo.near_tag(self.main)),
                             '%s: за блоком #locations' % p)
        self.assertIn('</main>\n' + seo.near_tag(self.main) + '\n', read('otzyv/index.html'), '/otzyv: за карточками')

    def test_main_reuses_shared_file(self):
        """dist и геолокация окна выбора филиала вынесены — на главной их больше нет, окно зовёт window.dcNear"""
        m = as_run(self.main)            # код окна — в assets/home.<хэш>.js (tools/home.js)
        self.assertNotIn('function dist(', m)
        self.assertNotIn('getCurrentPosition', m)
        self.assertNotIn('toFixed(1)} км', m)
        body = re.search(r'function openModal\(intent\)\{(.*?)\n\}\n', m, re.S).group(1)
        self.assertIn('const N=window.dcNear;', body)
        self.assertIn('if(N&&navigator.geolocation){', body, 'нет файла или геолокации — выбор вручную, как раньше')
        self.assertIn('N.dist(here,b.geo)', body)
        self.assertIn('${N.km(b.d)}', body)
        self.assertIn('},4000);', body, 'тайм-аут окна — прежние 4 с')
        for name in ('dist', 'km', 'locate'):
            self.assertRegex(self.src, r'\bfunction %s\(' % name)
        self.assertIn('window.dcNear = { dist: dist, km: km, locate: locate };', self.src)

    def test_points_from_branches_and_extra(self):
        P = json.loads(re.search(r'var P = (\{.*?\}),\n', self.text).group(1))
        want = {b['phone']: list(b['geo']) for b in seo.branches(self.main)}
        want[fb.EXTRA_POINTS[0]['phone']] = list(SPUTNIK_GEO)
        self.assertEqual(P, want)

    def test_sputnik_from_yandex_pin(self):
        x = fb.EXTRA_POINTS[0]
        self.assertEqual((x['id'], x['geo']), ('sputnik', SPUTNIK_GEO))
        src = read('tools/feedback_page.py')
        self.assertIn('https://yandex.kz/maps/org/sputnik_moll/1085318890/', src, 'источник координат — в комментарии')
        self.assertLess(haversine(SPUTNIK_GEO, [43.220416, 76.885263]), 5, 'Мамыр-1 — недалеко от 05 Жандосова, не другой город')

    def test_bad_geo_stops_build(self):
        swapped = self.main.replace('geo:[43.20471,76.893091]', 'geo:[76.893091,43.20471]', 1)
        self.assertNotEqual(swapped, self.main)
        with self.assertRaises(SystemExit):
            seo.near_points(swapped)

    def test_builder_refuses_comment_markers_inside_code(self):
        """сборка снимает комментарии регуляркой — маркеры внутри строк и хвостовые // должны останавливать её, а не резать код"""
        ok = "/* шапка */\n(function () {\n  // строка\n  var P = __POINTS__;\n})();\n"
        self.assertIn('var P = {', seo.near_js(self.main, ok)[1])
        for bad in ("var P = __POINTS__, a = 'assets/*';", "var P = __POINTS__; // хвост", "var P = __POINTS__, u = 'https://x';",
                    "var P = __POINTS__; /* хвост */", "return /*\n*/ P;\nvar P = __POINTS__;"):
            with self.subTest(bad=bad), self.assertRaises(SystemExit):
                seo.near_js(self.main, bad)

    def test_privacy_in_source(self):
        """ни хранилищ, ни сети: координаты остаются в памяти страницы; в аналитику — одно событие с исходом"""
        code = re.sub(r'/\*.*?\*/', '', self.src, flags=re.S)
        self.assertNotRegex(code, r'\b(?:localStorage|sessionStorage|cookie|indexedDB|caches|fetch|XMLHttpRequest|sendBeacon|WebSocket|'
                                  r'setAttribute|dataset|history|location|console|gtag)\b|\bym\(')
        self.assertEqual(re.findall(r'track\([^;]*\);', code), ["track('geo_sort', { result: here ? 'ok' : why });"])
        self.assertIn("l.className = 'near-d ym-hide-content';", code, 'вебвизор Метрики подписи не пишет')

    def test_motion_only_transform_and_opacity(self):
        code = re.sub(r'/\*.*?\*/', '', self.src, flags=re.S)
        anims = re.findall(r'\.animate\(\{ (\w+):', code)
        self.assertTrue(anims)
        self.assertEqual(set(anims), {'transform', 'opacity'})
        self.assertTrue(all(int(ms) <= 320 for ms in re.findall(r'duration: (\d+)', code)), 'коротко')
        self.assertIn("matchMedia('(prefers-reduced-motion: reduce)').matches", code)
        self.assertIn("EZ = 'cubic-bezier(.2,.8,.2,1)'", code, 'кривая входа сайта (--ez-in)')

    def test_built_file_is_source_without_comments(self):
        self.assertNotIn('__POINTS__', self.text)
        self.assertEqual(self.text.count('/*'), 1, 'только заголовок')
        node = find_node()
        if not node:
            self.skipTest('нет node')
        r = subprocess.run([node, '--check', self.path], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)


# Заглушка DOM: карточки — настоящая разметка страницы (дерево Tree), селекторы — те, что зовёт near.js
HARNESS = r"""
const fs = require('fs'), vm = require('vm');
const { code, grid, geoLine, sc } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const log = { gcp: 0, gcpOpts: null, perm: [], io: [], track: [], anim: [], touched: [], styles: [], mo: 0 };
const H_CARD = 200;
class N_ { constructor() { this.parentNode = null; }
  get nextSibling() { const p = this.parentNode; if (!p) return null; return p.childNodes[p.childNodes.indexOf(this) + 1] || null; } }
class C_ extends N_ { constructor(t) { super(); this.nodeType = 8; this.data = t; } }
class El extends N_ {
  constructor(tag, attrs, kids, text) { super(); this.nodeType = 1; this.tagName = tag.toUpperCase(); this.attrs = Object.assign({}, attrs || {});
    this.childNodes = []; this._text = text || ''; this.hidden = 'hidden' in this.attrs; (kids || []).forEach(k => this.appendChild(k)); }
  get children() { return this.childNodes.filter(n => n.nodeType === 1); }
  get className() { return this.attrs['class'] || ''; } set className(v) { this.attrs['class'] = v; }
  get textContent() { return this._text + this.children.map(c => c.textContent).join(''); } set textContent(v) { this._text = String(v); this.childNodes = []; }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  setAttribute(k, v) { log.touched.push('setAttribute ' + k + '=' + v); this.attrs[k] = String(v); }
  appendChild(n) { return this.insertBefore(n, null); }
  insertBefore(n, ref) { if (n.parentNode) { const a = n.parentNode.childNodes; a.splice(a.indexOf(n), 1); }
    const i = ref ? this.childNodes.indexOf(ref) : this.childNodes.length; if (ref && i < 0) throw new Error('ref — не ребёнок');
    this.childNodes.splice(i, 0, n); n.parentNode = this; return n; }
  matches(sel) { return sel.split(',').some(s => simple(this, s.trim())); }
  querySelector(sel) { for (const c of this.children) { if (c.matches(sel)) return c; const r = c.querySelector(sel); if (r) return r; } return null; }
  getBoundingClientRect() {          // сетка в одну колонку: карточка — по своему месту в сетке
    const g = this.parentNode && this.parentNode.attrs && /grid/.test(this.parentNode.attrs['class'] || '') ? this.parentNode : null;
    const top0 = sc.inView ? 120 : 5000;
    if (this === gridEl) return { top: top0, bottom: top0 + H_CARD * this.children.length, left: 16, width: 358, height: H_CARD * this.children.length };
    if (g) { const i = g.children.indexOf(this); return { top: top0 + i * H_CARD, bottom: top0 + (i + 1) * H_CARD, left: 16, width: 358, height: H_CARD }; }
    return { top: 0, bottom: 0, left: 0, width: 0, height: 0 }; }
  animate(kf, opts) { log.anim.push({ props: Object.keys(kf), kf, opts, el: this.className }); return {}; }
  focus() {}
}
function simple(el, s) {
  const m = /^([a-z0-9]*)((?:\.[\w-]+)*)(?:\[([\w-]+)\^="([^"]*)"\])?$/.exec(s); if (!m) throw new Error('селектор ' + s);
  if (m[1] && el.tagName.toLowerCase() !== m[1]) return false;
  const cls = (el.attrs['class'] || '').split(/\s+/);
  for (const c of m[2].split('.').filter(Boolean)) if (!cls.includes(c)) return false;
  if (m[3]) { const v = el.attrs[m[3]]; if (v == null || !v.startsWith(m[4])) return false; }
  return true;
}
const build = n => n.comment !== undefined ? new C_(n.comment) : new El(n.tag, n.attrs, n.kids.map(build), n.text);
const gridEl = build(grid), body = new El('body', {}, geoLine ? [build(geoLine), gridEl] : [gridEl]);
const html = new El('html', { lang: sc.lang }); html.lang = sc.lang;
const head = new El('head');
head.appendChild = n => { log.styles.push(n.textContent); return n; };
const spy = name => new Proxy({}, { get(t, k) { log.touched.push(name + '.' + String(k)); return () => null; },
                                    set(t, k) { log.touched.push(name + '=' + String(k)); return true; } });
const document = { documentElement: html, head, body, activeElement: null, createElement: t => new El(t),
  querySelector: s => body.querySelector(s),
  get cookie() { log.touched.push('cookie'); return ''; }, set cookie(v) { log.touched.push('cookie='); } };
const mos = [], ios = [];
const geo = sc.geo.type === 'none' ? undefined : { getCurrentPosition(ok, err, opts) { log.gcp++; log.gcpOpts = opts;
  Promise.resolve().then(() => sc.geo.type === 'ok' ? ok({ coords: { latitude: sc.geo.at[0], longitude: sc.geo.at[1], accuracy: 30 } })
                                                      : err({ code: sc.geo.code })); } };
const navigator = { geolocation: geo, sendBeacon() { log.touched.push('sendBeacon'); } };
if (sc.perm) navigator.permissions = { query(q) { log.perm.push(q.name); return Promise.resolve({ state: sc.perm }); } };
const ctx = { document, navigator, console, Promise, innerHeight: 800,
  localStorage: spy('localStorage'), sessionStorage: spy('sessionStorage'), indexedDB: spy('indexedDB'),
  fetch() { log.touched.push('fetch'); }, XMLHttpRequest: function () { log.touched.push('XMLHttpRequest'); },
  matchMedia: q => ({ matches: q.indexOf('reduce') >= 0 ? !!sc.reduce : false }),
  MutationObserver: function (cb) { this.observe = (t, o) => { log.mo++; mos.push(cb); }; },
  track(n, p) { log.track.push([n, p]); } };
if (sc.io !== false) ctx.IntersectionObserver = function (cb, o) { const me = { cb, o, targets: [], off: false }; ios.push(me); log.io.push(o);
  this.observe = t => me.targets.push(t); this.disconnect = () => { me.off = true; }; };
ctx.window = ctx;
gridEl.animate = El.prototype.animate;
vm.createContext(ctx);
const tick = () => new Promise(r => setTimeout(r, 0));
const state = () => ({
  phones: gridEl.children.map(c => (c.querySelector('a[href^="tel:"]') || { attrs: {} }).attrs.href.slice(4)),
  labels: gridEl.children.map(c => { const l = c.querySelector('.near-d'); return l ? l.textContent : null; }),
  labelClass: gridEl.children.map(c => { const l = c.querySelector('.near-d'); return l ? l.className : null; }),
  after: gridEl.children.map(c => { const l = c.querySelector('.near-d'); if (!l) return null;
    const k = l.parentNode.childNodes, p = k[k.indexOf(l) - 1]; return p.tagName.toLowerCase() + '.' + p.className; }),
  lastIsComment: gridEl.childNodes.length ? gridEl.childNodes[gridEl.childNodes.length - 1].nodeType === 8 : null,
  geoLineHidden: geoLine ? body.children[0].hidden : null, gcp: log.gcp });
(async () => {
  vm.runInContext(code, ctx);
  await tick(); await tick();
  const atLoad = state();
  for (const v of sc.view || []) { ios.forEach(me => !me.off && me.cb(me.targets.map(t => ({ isIntersecting: v, target: t })))); await tick(); await tick(); }
  const end = state();
  let relabel = null;
  if (sc.switchLang) { html.lang = sc.switchLang; mos.forEach(cb => cb([])); relabel = state().labels; }
  console.log(JSON.stringify({ atLoad, end, relabel, log, ioOff: ios.map(me => me.off), dcNear: Object.keys(ctx.dcNear || {}) }));
})();
"""

# Окно выбора филиала главной: все встроенные скрипты index.html и код assets/home.*.js на общей заглушке (как в tests/test_analytics.py) + near.js
MODAL_HARNESS = r"""
const fs = require('fs'), vm = require('vm');
const { html, near, geo } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const scripts = [...html.matchAll(/<script(?![^>]*\bsrc=)(?![^>]*ld\+json)[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const els = {};
const el = id => ({ id, innerHTML: '', textContent: '', style: { setProperty() {}, removeProperty() {} }, dataset: {}, scrollTop: 0,
  classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } }, addEventListener() {}, removeEventListener() {},
  setAttribute() {}, getAttribute() { return null; }, removeAttribute() {}, appendChild(x) { return x; }, querySelector() { return el(); },
  querySelectorAll() { return []; }, getBoundingClientRect() { return { top: 0, left: 0, width: 360, height: 0, bottom: 0, right: 360 }; },
  scrollIntoView() {}, scrollTo() {}, focus() {}, closest() { return null; }, play() { return Promise.resolve(); }, pause() {},
  insertAdjacentHTML() {}, contains() { return false; }, offsetHeight: 0 });
const document = { getElementById: id => els[id] || (els[id] = el(id)), querySelector: s => /grid/.test(s) ? null : el(), querySelectorAll: () => [],
  addEventListener() {}, createElement: () => el(), body: el('body'), documentElement: Object.assign(el('html'), { lang: 'ru' }), head: el('head'), readyState: 'loading' };
let gcp = [];
const navigator = { language: 'ru', geolocation: geo === 'none' ? undefined : { getCurrentPosition(ok, err, o) { gcp.push(o);
  Promise.resolve().then(() => geo === 'denied' ? err({ code: 1 }) : ok({ coords: { latitude: geo[0], longitude: geo[1] } })); } } };
const ctx = { document, console, navigator, setTimeout: () => 0, clearTimeout() {}, setInterval: () => 0, clearInterval() {},
  requestAnimationFrame: () => 0, requestIdleCallback: () => 0, cancelIdleCallback() {},
  matchMedia: () => ({ matches: false, addEventListener() {}, addListener() {} }),
  IntersectionObserver: function () { return { observe() {}, disconnect() {} }; }, ResizeObserver: function () { return { observe() {} }; },
  fetch: () => new Promise(() => {}), localStorage: { getItem() { return null; }, setItem() {} }, sessionStorage: { getItem() { return null; }, setItem() {} },
  location: { hash: '', pathname: '/', search: '' }, history: { replaceState() {}, pushState() {} },
  innerWidth: 360, innerHeight: 640, scrollTo() {}, addEventListener() {}, removeEventListener() {} };
ctx.window = ctx; vm.createContext(ctx);
scripts.forEach(s => vm.runInContext(s, ctx));
if (near) vm.runInContext(near, ctx);
vm.runInContext("openModal('route')", ctx);
setTimeout(() => console.log(JSON.stringify({ list: els['branch-list'].innerHTML, status: els['modal-status'].textContent, gcp })), 5);
"""


@unittest.skipUnless(find_node(), 'нет node')
class TestNearInNode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = read('index.html')
        cls.code = seo.near_js(cls.main)[1]
        cls.points = {b['phone']: b['geo'] for b in seo.branches(cls.main)}
        cls.points[fb.EXTRA_POINTS[0]['phone']] = SPUTNIK_GEO
        cls.tmp = tempfile.TemporaryDirectory()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_js(self, harness, data):
        h = os.path.join(self.tmp.name, 'h%d.js' % abs(hash(harness)))
        if not os.path.exists(h):
            with open(h, 'w', encoding='utf-8') as f:
                f.write(harness)
        d = os.path.join(self.tmp.name, 'd.json')
        with open(d, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        r = subprocess.run([find_node(), h, d], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def page(self, page, **sc):
        grid, geo = grid_of(page)
        sc.setdefault('lang', {'kk/index.html': 'kk', 'en/index.html': 'en'}.get(page, 'ru'))
        sc.setdefault('inView', True)
        return self.run_js(HARNESS, {'code': self.code, 'grid': grid, 'geoLine': geo if 'otzyv' in page else None, 'sc': sc})

    def by_distance(self, phones, here):
        return sorted(phones, key=lambda p: (haversine(here, self.points[p]), phones.index(p)))

    def label(self, here, phone, lang):
        s = '%.1f' % haversine(here, self.points[phone])      # toFixed(1): здесь нет ровно-половинок
        return s + ' km' if lang == 'en' else s.replace('.', ',') + ' км'

    def assert_private(self, out):
        self.assertEqual(out['log']['touched'], [], 'ни хранилищ, ни cookie, ни атрибутов, ни сети')
        for name, params in out['log']['track']:
            self.assertEqual(name, 'geo_sort')
            self.assertEqual(list(params), ['result'], 'без координат и расстояний')
            self.assertIn(params['result'], ('ok', 'denied', 'error'))
        self.assertLessEqual(len(out['log']['track']), 1, 'одно событие за заход')

    # ── /otzyv: спросить сразу ──
    def test_otzyv_near_03(self):
        out = self.page('otzyv/index.html', geo={'type': 'ok', 'at': NEAR_03})
        before = list(self.points)                                 # порядок разметки: BRANCHES, затем Sputnik
        self.assertEqual(out['atLoad']['gcp'], 1, 'спросили при открытии, без прокрутки')
        self.assertEqual(out['log']['io'], [], '/otzyv не ждёт блок')
        self.assertEqual(out['atLoad']['phones'], self.by_distance(before, NEAR_03))
        self.assertEqual(out['atLoad']['phones'][0], '+77770355617', '03 Promenade — первой')
        self.assertEqual(out['atLoad']['labels'], [self.label(NEAR_03, p, 'ru') for p in out['atLoad']['phones']])
        self.assertTrue(all(c == 'near-d ym-hide-content' for c in out['atLoad']['labelClass']))
        self.assertEqual(set(out['atLoad']['after']), {'p.fb-addr'}, 'расстояние — под адресом')
        self.assertTrue(out['atLoad']['geoLineHidden'], 'строка «не определили» — только при неудаче')
        self.assertEqual(out['log']['track'], [['geo_sort', {'result': 'ok'}]])
        self.assertEqual(out['log']['gcpOpts'], {'timeout': 10000, 'maximumAge': 300000})
        self.assertEqual(out['dcNear'], ['dist', 'km', 'locate'])
        self.assert_private(out)

    def test_otzyv_near_sputnik(self):
        out = self.page('otzyv/index.html', geo={'type': 'ok', 'at': NEAR_SPUTNIK})
        self.assertEqual(out['atLoad']['phones'][0], fb.EXTRA_POINTS[0]['phone'], 'Sputnik Mall — первым')
        self.assertEqual(out['atLoad']['phones'], self.by_distance(list(self.points), NEAR_SPUTNIK))
        self.assertEqual(out['atLoad']['labels'][0], self.label(NEAR_SPUTNIK, fb.EXTRA_POINTS[0]['phone'], 'ru'))
        self.assertLess(haversine(NEAR_SPUTNIK, SPUTNIK_GEO), 0.2)
        self.assert_private(out)

    def test_otzyv_refusals_keep_order(self):
        markup = list(self.points)
        for geo, result in (({'type': 'denied', 'code': 1}, 'denied'), ({'type': 'error', 'code': 3}, 'error'),
                            ({'type': 'error', 'code': 2}, 'error'), ({'type': 'none'}, 'error')):
            with self.subTest(geo=geo):
                out = self.page('otzyv/index.html', geo=geo)
                self.assertEqual(out['end']['phones'], markup, 'порядок прежний')
                self.assertEqual(out['end']['labels'], [None] * len(markup), 'без подписей')
                self.assertFalse(out['end']['geoLineHidden'], 'одна спокойная строка')
                self.assertEqual(out['log']['track'], [['geo_sort', {'result': result}]])
                self.assertEqual(out['log']['styles'], [], 'страницу не трогали')
                self.assert_private(out)

    def test_otzyv_language_switch_relabels(self):
        out = self.page('otzyv/index.html', geo={'type': 'ok', 'at': NEAR_03}, switchLang='en')
        self.assertEqual(out['log']['mo'], 1)
        self.assertEqual(out['relabel'], [self.label(NEAR_03, p, 'en') for p in out['end']['phones']], '«км» → «km», запятая → точка')

    # ── #locations на /, /kk/, /en/: только когда блок в экране, при разрешении — сразу ──
    def test_locations_wait_for_block(self):
        for page in ('index.html', 'kk/index.html', 'en/index.html'):
            with self.subTest(page=page):
                markup = [p for p in self.points if p != fb.EXTRA_POINTS[0]['phone']]
                out = self.page(page, perm='prompt', geo={'type': 'ok', 'at': NEAR_03}, view=[False, True])
                self.assertEqual(out['atLoad']['gcp'], 0, 'при входе не спрашиваем')
                self.assertEqual(out['atLoad']['phones'], markup)
                self.assertEqual(out['log']['perm'], ['geolocation'])
                self.assertEqual(out['log']['io'], [{'rootMargin': '0px 0px -25% 0px'}])
                self.assertEqual(out['end']['gcp'], 1, 'блок в экране — спросили один раз')
                self.assertEqual(out['ioOff'], [True], 'наблюдатель снят')
                self.assertEqual(out['end']['phones'], self.by_distance(markup, NEAR_03))
                self.assertEqual(out['end']['phones'][0], '+77770355617')
                lang = {'kk/index.html': 'kk', 'en/index.html': 'en'}.get(page, 'ru')
                self.assertEqual(out['end']['labels'], [self.label(NEAR_03, p, lang) for p in out['end']['phones']])
                self.assertEqual(set(out['end']['after']), {'h3.'}, 'расстояние — под адресом карточки')
                if page == 'index.html':
                    self.assertTrue(out['end']['lastIsComment'], 'карточки остаются между маркерами генератора')
                self.assertNotIn('Sputnik', json.dumps(out, ensure_ascii=False))
                self.assert_private(out)

    def test_locations_granted_sorts_at_once(self):
        out = self.page('index.html', perm='granted', geo={'type': 'ok', 'at': NEAR_03}, inView=False)
        self.assertEqual(out['atLoad']['gcp'], 1, 'разрешение уже дано — сразу, без ожидания блока')
        self.assertEqual(out['log']['io'], [])
        self.assertEqual(out['atLoad']['phones'][0], '+77770355617')
        self.assertEqual(out['log']['anim'], [], 'блок не на экране — без анимации')

    def test_locations_without_permissions_api_or_io(self):
        out = self.page('kk/index.html', perm=None, geo={'type': 'ok', 'at': NEAR_03}, view=[True])
        self.assertEqual((out['atLoad']['gcp'], out['end']['gcp']), (0, 1), 'нет Permissions API — ждём блок')
        out = self.page('kk/index.html', perm='prompt', io=False, geo={'type': 'ok', 'at': NEAR_03})
        self.assertEqual(out['end']['gcp'], 0, 'нет IntersectionObserver — не спрашиваем вовсе')
        self.assertEqual(out['log']['track'], [])

    def test_locations_refusal_silent(self):
        for geo in ({'type': 'denied', 'code': 1}, {'type': 'error', 'code': 3}, {'type': 'none'}):
            with self.subTest(geo=geo):
                out = self.page('en/index.html', perm='prompt', geo=geo, view=[True])
                self.assertEqual(out['end']['phones'], [p for p in self.points if p != fb.EXTRA_POINTS[0]['phone']])
                self.assertEqual(out['end']['labels'], [None] * 5, 'в блоке ничего')
                self.assertEqual(out['log']['styles'], [])
                self.assertEqual(out['log']['anim'], [])
                self.assert_private(out)

    def test_motion(self):
        out = self.page('index.html', perm='granted', geo={'type': 'ok', 'at': NEAR_03}, inView=True)
        anim = out['log']['anim']
        self.assertTrue(anim, 'блок на экране — перестановка видна')
        self.assertEqual({p for a in anim for p in a['props']}, {'transform', 'opacity'})
        moves = [a for a in anim if a['props'] == ['transform']]
        self.assertTrue(moves)
        for a in moves:
            self.assertRegex(a['kf']['transform'][0], r'^translate\(-?\d+(\.\d+)?px,-?\d+(\.\d+)?px\)$')
            self.assertEqual(a['kf']['transform'][1], 'none')
        for a in anim:
            self.assertLessEqual(a['opts']['duration'], 320)
            self.assertEqual(a['opts']['easing'], 'cubic-bezier(.2,.8,.2,1)')
        reduce = self.page('index.html', perm='granted', geo={'type': 'ok', 'at': NEAR_03}, inView=True, reduce=True)
        self.assertEqual(reduce['log']['anim'], [], 'reduced-motion — мгновенно')
        self.assertEqual(reduce['end']['phones'], out['end']['phones'])

    # ── окно выбора филиала главной — на общем файле ──
    def test_modal_uses_shared_file(self):
        bn = [b['phone'] for b in seo.branches(self.main)]
        out = self.run_js(MODAL_HARNESS, {'html': as_run(self.main), 'near': self.code, 'geo': NEAR_03})
        order = re.findall(r'href="tel:([^"]+)"', out['list'])
        self.assertEqual(order, sorted(bn, key=lambda p: haversine(NEAR_03, self.points[p])))
        self.assertEqual(re.findall(r'<span class="dist ym-hide-content">([^<]*)</span>', out['list']),
                         [self.label(NEAR_03, p, 'ru') for p in order], 'тот же формат, что на карточках')
        self.assertTrue(out['status'].startswith('Ближайший к вам филиал — сверху.'))
        self.assertEqual(out['gcp'], [{'timeout': 4000, 'maximumAge': 300000}], 'тайм-аут окна — прежние 4 с')
        self.assertNotIn(fb.EXTRA_POINTS[0]['phone'], out['list'], 'Sputnik в окне выбора нет')
        out = self.run_js(MODAL_HARNESS, {'html': as_run(self.main), 'near': self.code, 'geo': 'denied'})
        self.assertEqual(re.findall(r'href="tel:([^"]+)"', out['list']), bn)
        self.assertTrue(out['status'].startswith('Не удалось определить геолокацию — выберите филиал вручную.'))
        self.assertNotIn('class="dist', out['list'])
        out = self.run_js(MODAL_HARNESS, {'html': as_run(self.main), 'near': None, 'geo': NEAR_03})
        self.assertEqual(re.findall(r'href="tel:([^"]+)"', out['list']), bn, 'общий файл не загрузился — окно работает, как без геолокации')
        self.assertTrue(out['status'].startswith('Выберите филиал вручную.'))
        self.assertEqual(out['gcp'], [])


if __name__ == '__main__':
    unittest.main()
