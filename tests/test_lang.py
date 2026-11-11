"""Язык — один выбор на весь сайт (владелец 11.11.2026: «Я выбрал на главной русский язык, а в меню почему-то был
английский, а в уголке потребителя — казахский. Если выбран в одном любом месте язык, то он автоматически везде меняется»).

Один ключ localStorage dc_lang = ru | kk | en; скрипт seo.LANG_JS в <head> всех 9 страниц (собирает tools/seo_jsonld.py).
Проверка без браузера: настоящие скрипты страниц (скрипт языка из <head>, меню главной целиком, /ugolok, /otzyv) на
заглушке DOM в node; хранилище общее между «заходами» на страницы, как в браузере. Сценарии владельца:
выбрал ru на главной → меню ru, /ugolok ru, /otzyv ru; выбрал kk в меню → после закрытия /kk/, /ugolok kk; выбрал en на
/ugolok → / отправляет на /en/; пустое хранилище и хранилище с исключением — всё как раньше; цикла перенаправлений нет;
явная #метка языка важнее хранилища.
"""
import json, os, re, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seo_jsonld as seo  # noqa: E402
from test_perf import as_run, find_node  # noqa: E402

# путь страницы → файл; у страниц с версиями по языкам есть <link rel=alternate hreflang>
PAGES = {'/': 'index.html', '/kk/': 'kk/index.html', '/en/': 'en/index.html', '/menyu': 'menyu/index.html',
         '/kk/menyu': 'kk/menyu/index.html', '/en/menu': 'en/menu/index.html', '/ugolok/': 'ugolok/index.html',
         '/otzyv/': 'otzyv/index.html', '/404': '404.html'}
VERSIONS = ('/', '/kk/', '/en/', '/menyu', '/kk/menyu', '/en/menu')
HOME = {'ru': '/', 'kk': '/kk/', 'en': '/en/'}
MENU = {'ru': '/menyu', 'kk': '/kk/menyu', 'en': '/en/menu'}


def read(p):
    with open(os.path.join(ROOT, p), encoding='utf-8') as f:
        return f.read()


def inline_scripts(html):
    return re.findall(r'<script(?![^>]*\bsrc=)(?![^>]*ld\+json)[^>]*>([\s\S]*?)</script>', html)


def page_data(path):
    html = read(PAGES[path])
    head = html.split('</head>')[0]
    scripts = inline_scripts(html)
    if path == '/':
        run = inline_scripts(as_run(html))                         # главная — все скрипты и код assets/home.*.js: меню, глубокие ссылки
    else:                                                          # остальные — аналитика (track), скрипт языка, заставка, язык страницы
        run = [s for s in scripts if 'function track(' in s or s == seo.LANG_JS or "classList.add('intro-on')" in s or 'const I18N' in s]
    return {'lang': re.search(r'<html lang="(\w+)"', html).group(1),
            'alt': dict(re.findall(r'<link rel="alternate" hreflang="([\w-]+)" href="([^"]+)">', head)), 'scripts': run}


# Заглушка браузера: хранилище (store) и sessionStorage живут между заходами; location.replace и переходы записываются.
HARNESS = r"""
const fs = require('fs'), vm = require('vm');
const PAGES = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
let store = {}, mode = 'ok', session = {};
const localStorage = {
  getItem: k => { if (mode === 'throw') throw new Error('SecurityError'); return k in store ? store[k] : null; },
  setItem: (k, v) => { if (mode === 'throw') throw new Error('SecurityError'); store[k] = String(v); } };
const sessionStorage = { getItem: k => (k in session ? session[k] : null), setItem: (k, v) => { session[k] = String(v); } };
function el(id) { const cls = new Set(); const o = { id, innerHTML: '', textContent: '', hidden: true, dataset: {}, scrollTop: 0,
  offsetHeight: 0, offsetWidth: 0, style: { setProperty() {}, removeProperty() {} }, _l: {}, attrs: {},
  classList: { add: (...c) => c.forEach(x => cls.add(x)), remove: (...c) => c.forEach(x => cls.delete(x)),
    toggle: (c, f) => ((f === undefined ? !cls.has(c) : f) ? cls.add(c) : cls.delete(c)), contains: c => cls.has(c) },
  addEventListener(t, f) { (o._l[t] = o._l[t] || []).push(f); }, removeEventListener() {}, appendChild: x => x, insertAdjacentHTML() {},
  contains: () => false, getAttribute: k => (k in o.attrs ? o.attrs[k] : null), setAttribute(k, v) { o.attrs[k] = String(v); },
  removeAttribute(k) { delete o.attrs[k]; }, querySelector(sel) { return (o._q = o._q || {})[sel] || (o._q[sel] = el(id + ' ' + sel)); },
  querySelectorAll: () => [], getBoundingClientRect: () => ({ top: 0, bottom: 0 }), scrollTo() {}, focus() {}, closest: () => null };
  return o; }
// url — путь, ?query и #метка; served — какая страница отдана (офлайн service worker отдаёт главную вместо /kk/)
function open(url, served) {
  const u = /^([^?#]*)(\?[^#]*)?(#.*)?$/.exec(url), path = u[1], P = PAGES[served || path];
  if (!P) throw new Error('нет страницы ' + (served || path));
  const els = {}, win = {}, nav = [];
  const docEl = Object.assign(el('html'), { lang: P.lang, hidden: false });
  const document = { getElementById: id => els[id] || (els[id] = el(id)), createElement: () => el('x'),
    querySelector: s => { const m = /^link\[hreflang(?:=([\w-]+))?\]$/.exec(s);
      if (m) { const k = m[1] || Object.keys(P.alt)[0]; return k && P.alt[k] ? { href: P.alt[k], hreflang: k } : null; }
      return els['q:' + s] || (els['q:' + s] = el('q:' + s)); },
    querySelectorAll: () => [], addEventListener() {}, body: el('body'), documentElement: docEl, head: el('head'),
    readyState: 'loading', activeElement: null, title: '' };
  const location = { pathname: path, search: u[2] || '', hash: u[3] || '', origin: 'http://127.0.0.1:8090',
    replace: x => nav.push(['replace', x]), set href(x) { nav.push(['href', x]); } };
  const ctx = { document, console, localStorage, sessionStorage, location, navigator: {}, setTimeout: () => 0, clearTimeout() {},
    requestAnimationFrame: () => 0, requestIdleCallback: () => 0, IntersectionObserver: function () { return { observe() {} }; },
    matchMedia: () => ({ matches: false, addEventListener() {}, addListener() {} }), fetch: () => new Promise(() => {}),
    history: { length: 2, replaceState: (a, b, x) => nav.push(['replaceState', x]), back: () => nav.push(['back']) },
    addEventListener: (t, f) => { (win[t] = win[t] || []).push(f); }, scrollTo() {}, Image: function () {} };
  ctx.window = ctx; vm.createContext(ctx);
  P.scripts.forEach(s => vm.runInContext(s, ctx));
  const R = c => vm.runInContext(c, ctx);
  return { R, nav, els, docEl, ctx,
    // клик по ссылке переключателя языка (a[hreflang]) — как в браузере: обработчики окна, потом переход
    clickLang: l => { const a = { hreflang: l }; (win.click || []).forEach(f => f({ target: { closest: s => s === 'a[hreflang]' ? a : null } })); },
    lang: () => R('document.documentElement.lang'), go: () => nav.filter(x => x[0] === 'replace').map(x => x[1]) };
}
const out = {};
const S = (name, fn) => { store = {}; mode = 'ok'; session = {}; try { out[name] = fn(); } catch (e) { out[name] = { error: String(e.stack) }; } };
const shot = () => Object.assign({}, store);
""" + r"""
// ── каждая страница с версиями × что в хранилище: куда уходит, что запоминает ──
for (const path of %(versions)s) for (const st of ['none', 'ru', 'kk', 'en', 'throw', 'junk'])
  S('load ' + path + ' ' + st, () => { if (st === 'throw') mode = 'throw'; else if (st === 'junk') store.dc_lang = 'de"]'; else if (st !== 'none') store.dc_lang = st;
    const p = open(path); return { go: p.go(), hidden: p.docEl.hidden, store: shot(), intro: p.docEl.classList.contains('intro-on'), session: Object.assign({}, session) }; });
for (const path of ['/ugolok/', '/otzyv/', '/404']) for (const st of ['none', 'kk', 'throw'])
  S('load ' + path + ' ' + st, () => { if (st === 'throw') mode = 'throw'; else if (st !== 'none') store.dc_lang = st;
    const p = open(path); return { go: p.go(), hidden: p.docEl.hidden, store: shot(), lang: p.lang() }; });
S('query and hash kept', () => { store.dc_lang = 'en'; return [open('/?utm_source=ig#faq').go(), open('/kk/menyu?x=1#bar').go()]; });
S('offline: main served at /kk/', () => { store.dc_lang = 'kk'; const p = open('/kk/', '/'); return { go: p.go(), hidden: p.docEl.hidden, store: shot() }; });
S('offline: main served at /kk/menyu', () => { store.dc_lang = 'kk'; return open('/kk/menyu', '/').go(); });
// ── явная метка в адресе важнее хранилища и сама — выбор ──
S('hash menu-grill-kk over en', () => { store.dc_lang = 'en'; const p = open('/#menu-grill-kk');
  return { go: p.go(), store: shot(), menu: p.R('menuLang'), modal: p.els['menu-modal'].lang }; });
S('hash menu over kk', () => { store.dc_lang = 'kk'; const p = open('/#menu');
  return { go: p.go(), store: shot(), menu: p.R('menuLang'), modal: p.els['menu-modal'].lang }; });
S('hash menu-togo-en, no storage', () => { mode = 'throw'; const p = open('/#menu-togo-en'); return { go: p.go(), menu: p.R('menuLang') }; });
S('hashchange to menu-en', () => { store.dc_lang = 'ru'; const p = open('/'); p.ctx.location.hash = '#menu-en'; p.R('menuFromHash()');
  return { store: shot(), menu: p.R('menuLang') }; });
S('otzyv hash en over kk', () => { store.dc_lang = 'kk'; const p = open('/otzyv/#en'); return { store: shot(), lang: p.lang() }; });
S('ugolok hash ru over en', () => { store.dc_lang = 'en'; const p = open('/ugolok/#ru'); return { store: shot(), lang: p.lang() }; });
// ── переключатель в шапке: выбор — до перехода ──
S('header switch on /kk/ to ru', () => { const k = open('/kk/'); k.clickLang('ru'); const after = shot(); const r = open('/');
  return { after, go: r.go(), store: shot() }; });
S('header switch on / to en', () => { const r = open('/'); r.clickLang('en'); const after = shot(); return { after, go: open('/en/').go(), store: shot() }; });
S('text menu switch on /kk/menyu to en', () => { store.dc_lang = 'kk'; const m = open('/kk/menyu'); m.clickLang('en'); return { store: shot(), go: open('/en/menu').go() }; });
S('header switch, no storage', () => { mode = 'throw'; const k = open('/kk/'); k.clickLang('ru'); return { go: open('/').go(), dc: k.R('dcLang') }; });
// ── сценарии владельца ──
S('owner: ru on main → menu ru, ugolok ru, otzyv ru', () => {
  store.dc_menu_lang = 'en';                                   // старая память меню (до 11.11) — больше не действует
  const e = open('/en/'); e.clickLang('ru');                   // был на английской, выбрал РУС
  const m = open('/'); const go = m.go(); m.R('openMenu()');
  const u = open('/ugolok/'), o = open('/otzyv/');
  return { go, menu: m.R('menuLang'), modal: m.els['menu-modal'].lang, ugolok: u.lang(), otzyv: o.lang(), store: shot() }; });
S('owner: kk in menu → /kk/, ugolok kk', () => {
  const m = open('/'); m.R('openMenu()'); m.R("menuLangClick('kk')"); const picked = shot(); m.R('closeMenu()');
  const k = open('/kk/'); const u = open('/ugolok/');
  return { picked, close: m.nav, kgo: k.go(), ugolok: u.lang(), store: shot() }; });
S('owner: menu from /kk/ and back', () => {
  const k = open('/kk/'); const m = open('/#menu-kk'); const go = m.go(); m.R('closeMenu()'); return { go, menu: m.R('menuLang'), close: m.nav }; });
S('owner: ru menu closes in place', () => { const m = open('/'); m.R('openMenu()'); m.R('closeMenu()'); return m.nav; });
S('owner: closed menu not reopened by Esc', () => { const m = open('/'); m.R("menuLang='kk'"); m.R('closeMenu()'); return m.nav; });
S('owner: en on ugolok → / goes /en/', () => {
  open('/'); const u = open('/ugolok/'); u.R("setLang('en')"); const picked = shot(); const r = open('/');
  const o = open('/otzyv/'); return { picked, go: r.go(), hidden: r.docEl.hidden, otzyv: o.lang() }; });
S('owner: kk on otzyv → /menyu goes /kk/menyu', () => {
  const o = open('/otzyv/'); o.R("setLang('kk')"); return { store: shot(), go: open('/menyu').go(), back: o.nav }; });
S('owner: menu kk, storage throws', () => { mode = 'throw'; const m = open('/'); m.R('openMenu()'); m.R("menuLangClick('kk')"); m.R('closeMenu()');
  return { close: m.nav, kgo: open('/kk/').go(), ugolok: open('/ugolok/').lang() }; });
// ── заставка: при уходе на другой язык не показывается и не тратится (раз за сессию — на той странице, куда пришли) ──
S('intro on redirect', () => { store.dc_lang = 'kk'; const r = open('/'); const k = open('/kk/');
  return { r: r.docEl.classList.contains('intro-on'), k: k.docEl.classList.contains('intro-on') }; });
console.log(JSON.stringify(out));
"""


class TestLangHead(unittest.TestCase):
    """скрипт языка — один и тот же, в <head> всех 9 страниц, до заставки и до скриптов страницы"""

    def test_everywhere_once_in_head(self):
        for path, f in PAGES.items():
            html = read(f)
            head, body = html.split('</head>')
            self.assertEqual(head.count('<script>%s</script>' % seo.LANG_JS), 1, f)
            self.assertNotIn('dcLang;', body.replace('dcLang', ''), f)
            self.assertLess(head.index(seo.VT_JS), head.index(seo.LANG_JS), '%s: сразу за переходом между страницами' % f)
            if '<style>' in head:
                self.assertLess(head.index(seo.LANG_JS), head.index('<style>'), '%s: до стилей — без вспышки' % f)
            if "classList.add('intro-on')" in head:
                self.assertLess(head.index(seo.LANG_JS), head.index("classList.add('intro-on')"), '%s: до заставки' % f)
            alt = re.findall(r'<link rel="alternate" hreflang', head)
            if path in VERSIONS:
                self.assertTrue(alt and head.rindex('<link rel="alternate" hreflang') < head.index(seo.LANG_JS), '%s: версии — раньше скрипта' % f)
            else:
                self.assertEqual(alt, [], '%s: без версий по языкам — не уводим и не запоминаем' % f)

    def test_one_key_storage_in_try(self):
        js = seo.LANG_JS
        self.assertEqual(re.findall(r"localStorage\.(\w+)\('([\w]+)'", js), [('setItem', 'dc_lang'), ('getItem', 'dc_lang')])
        for call in re.finditer(r'localStorage\.', js):
            self.assertGreater(js.rfind('try{', 0, call.start()), js.rfind('}catch(e){}', 0, call.start()), 'хранилище — только в try')
        self.assertNotIn('dc_menu_lang', read('index.html'), 'у меню больше нет своей памяти языка')
        for f in PAGES.values():
            self.assertNotIn('dc_lang', read(f).replace(seo.LANG_JS, ''), '%s: язык читают и пишут только через dcLang / dcSave' % f)

    def test_redirect_without_flash_and_animation(self):
        js = seo.LANG_JS
        self.assertIn('d.hidden=1,o.replace(', js, 'уход — location.replace (без записи в историю), страница скрыта')
        self.assertNotIn('vt-out', js, 'без анимации ухода')
        self.assertIn("'%s'" % seo.SITE[:-1], js, 'путь версии — из <link hreflang> без домена: локально и на сайте')
        intro = seo.INTRO_RE.search(read('index.html').split('</head>')[0]).group(0)
        self.assertIn('document.documentElement.hidden', intro, 'страница уходит на другой язык — без заставки')


class TestLangInNode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        node = find_node()
        if not node:
            raise unittest.SkipTest('нет node')
        pages = {p: page_data(p) for p in PAGES}
        with tempfile.TemporaryDirectory() as d:
            h, data = os.path.join(d, 'h.js'), os.path.join(d, 'pages.json')
            with open(h, 'w', encoding='utf-8') as f:
                f.write(HARNESS % {'versions': json.dumps(list(VERSIONS))})
            with open(data, 'w', encoding='utf-8') as f:
                json.dump(pages, f, ensure_ascii=False)
            r = subprocess.run([node, h, data], capture_output=True, text=True, timeout=120)
        if r.returncode:
            raise AssertionError(r.stderr[-2000:])
        cls.out = json.loads(r.stdout)
        errors = {k: v['error'] for k, v in cls.out.items() if isinstance(v, dict) and 'error' in v}
        if errors:
            raise AssertionError(json.dumps(errors, ensure_ascii=False, indent=1)[-3000:])

    def test_versions_follow_choice(self):
        for path in VERSIONS:
            own = {'/': 'ru', '/kk/': 'kk', '/en/': 'en', '/menyu': 'ru', '/kk/menyu': 'kk', '/en/menu': 'en'}[path]
            urls = HOME if path in HOME.values() else MENU
            for st in ('ru', 'kk', 'en'):
                got = self.out['load %s %s' % (path, st)]
                if st == own:
                    self.assertEqual((got['go'], got['hidden'], got['store']), ([], False, {'dc_lang': st}), '%s, выбран %s — остаёмся' % (path, st))
                else:
                    self.assertEqual((got['go'], got['hidden']), ([urls[st]], True), '%s, выбран %s — сразу на свою версию, страница скрыта' % (path, st))
                    self.assertEqual(got['store'], {'dc_lang': st}, 'выбор не меняется')

    def test_empty_or_broken_storage_as_before(self):
        for path in VERSIONS:
            own = {'/': 'ru', '/kk/': 'kk', '/en/': 'en', '/menyu': 'ru', '/kk/menyu': 'kk', '/en/menu': 'en'}[path]
            got = self.out['load %s none' % path]
            self.assertEqual((got['go'], got['hidden']), ([], False), '%s: новый посетитель и робот — остаются' % path)
            self.assertEqual(got['store'], {'dc_lang': own}, '%s: открыл — значит, это его язык' % path)
            got = self.out['load %s throw' % path]
            self.assertEqual((got['go'], got['hidden'], got['store']), ([], False, {}), '%s: хранилище бросает — по-старому' % path)
            got = self.out['load %s junk' % path]
            self.assertEqual((got['go'], got['store']), ([], {'dc_lang': own}), '%s: в хранилище не язык — как пустое' % path)
        for path, default in (('/ugolok/', 'kk'), ('/otzyv/', 'ru'), ('/404', 'ru')):
            for st in ('none', 'throw'):
                got = self.out['load %s %s' % (path, st)]
                self.assertEqual((got['go'], got['store'], got['lang']), ([], {}, default), '%s: открытие — не выбор, язык по умолчанию' % path)
        self.assertEqual(self.out['load /ugolok/ kk']['lang'], 'kk')
        self.assertEqual(self.out['load /otzyv/ kk']['lang'], 'kk', '/otzyv — за выбором')
        self.assertEqual((self.out['load /404 kk']['go'], self.out['load /404 kk']['store']), ([], {'dc_lang': 'kk'}), '404 — не уводим')

    def test_query_and_hash_kept(self):
        self.assertEqual(self.out['query and hash kept'], [['/en/?utm_source=ig#faq'], ['/en/menu?x=1#bar']])

    def test_no_redirect_loop(self):
        # офлайн service worker отдаёт главную из кэша вместо /kk/: она не уводит на тот же адрес и не перезаписывает выбор
        got = self.out['offline: main served at /kk/']
        self.assertEqual((got['go'], got['hidden'], got['store']), ([], False, {'dc_lang': 'kk'}))
        self.assertEqual(self.out['offline: main served at /kk/menyu'], ['/kk/'], 'один шаг, дальше — тот же случай выше')
        # любой выбор: со страницы уходим не больше одного раза, и там, куда пришли, — остаёмся
        for path in VERSIONS:
            for st in ('ru', 'kk', 'en'):
                go = self.out['load %s %s' % (path, st)]['go']
                if go:
                    self.assertEqual(self.out['load %s %s' % (go[0], st)]['go'], [], '%s → %s → дальше никуда' % (path, go[0]))

    def test_hash_mark_wins_and_becomes_choice(self):
        got = self.out['hash menu-grill-kk over en']
        self.assertEqual((got['go'], got['store'], got['menu'], got['modal']), ([], {'dc_lang': 'kk'}, 'kk', 'kk'))
        got = self.out['hash menu over kk']
        self.assertEqual((got['go'], got['store'], got['menu'], got['modal']), ([], {'dc_lang': 'kk'}, 'kk', 'kk'),
                         '/#menu без языка — меню на выбранном языке, страницу не уводим')
        self.assertEqual(self.out['hash menu-togo-en, no storage'], {'go': [], 'menu': 'en'}, 'без хранилища метка всё равно работает')
        self.assertEqual(self.out['hashchange to menu-en'], {'store': {'dc_lang': 'en'}, 'menu': 'en'})
        self.assertEqual(self.out['otzyv hash en over kk'], {'store': {'dc_lang': 'en'}, 'lang': 'en'})
        self.assertEqual(self.out['ugolok hash ru over en'], {'store': {'dc_lang': 'ru'}, 'lang': 'ru'})

    def test_header_switch_is_choice(self):
        self.assertEqual(self.out['header switch on /kk/ to ru'], {'after': {'dc_lang': 'ru'}, 'go': [], 'store': {'dc_lang': 'ru'}},
                         'РУС на /kk/: выбор до перехода, иначе / вернул бы на /kk/')
        self.assertEqual(self.out['header switch on / to en'], {'after': {'dc_lang': 'en'}, 'go': [], 'store': {'dc_lang': 'en'}})
        self.assertEqual(self.out['text menu switch on /kk/menyu to en'], {'store': {'dc_lang': 'en'}, 'go': []})
        self.assertEqual(self.out['header switch, no storage'], {'go': [], 'dc': 'ru'})

    def test_owner_ru_on_main(self):
        got = self.out['owner: ru on main → menu ru, ugolok ru, otzyv ru']
        self.assertEqual((got['go'], got['menu'], got['modal'], got['ugolok'], got['otzyv']), ([], 'ru', 'ru', 'ru', 'ru'))
        self.assertEqual(got['store']['dc_lang'], 'ru')

    def test_owner_kk_in_menu(self):
        got = self.out['owner: kk in menu → /kk/, ugolok kk']
        self.assertEqual(got['picked'], {'dc_lang': 'kk'})
        self.assertEqual(got['close'], [['replace', '/kk/']], 'закрыли меню на ҚАЗ — главная /kk/')
        self.assertEqual((got['kgo'], got['ugolok']), ([], 'kk'))
        got = self.out['owner: menu from /kk/ and back']
        self.assertEqual((got['go'], got['menu'], got['close']), ([], 'kk', [['replace', '/kk/']]), 'с /kk/ в меню и обратно — на /kk/, не на русскую')
        self.assertEqual(self.out['owner: ru menu closes in place'], [], 'меню на РУС — закрывается на месте, как раньше')
        self.assertEqual(self.out['owner: closed menu not reopened by Esc'], [], 'Esc без открытого меню — никуда не уводит')
        got = self.out['owner: menu kk, storage throws']
        self.assertEqual((got['close'], got['kgo'], got['ugolok']), ([['replace', '/kk/']], [], 'kk'))

    def test_owner_en_on_ugolok(self):
        got = self.out['owner: en on ugolok → / goes /en/']
        self.assertEqual(got['picked'], {'dc_lang': 'en'})
        self.assertEqual((got['go'], got['hidden'], got['otzyv']), (['/en/'], True, 'en'))
        got = self.out['owner: kk on otzyv → /menyu goes /kk/menyu']
        self.assertEqual((got['store'], got['go'], got['back']), ({'dc_lang': 'kk'}, ['/kk/menyu'], [['replaceState', '#kk']]))

    def test_intro_not_lost_on_redirect(self):
        self.assertEqual(self.out['intro on redirect'], {'r': False, 'k': True}, 'заставка — на /kk/, куда пришли, а не на скрытой /')
        got = self.out['load / kk']
        self.assertEqual((got['intro'], got['session']), (False, {}), 'уходящая страница не тратит «раз за сессию»')


if __name__ == '__main__':
    unittest.main()
