"""Появление и уход везде (владелец 11.11: «анимация входа в раздел меню, анимация выхода из него и так на всех местах»;
затем «анимации лагают и не плавные», «анимации перехода в жалобы и предложения нет»).
Сторожат:
- главная: меню, окно выбора филиала, карточка блюда, подсказка «!», язык меню на телефоне, поле поиска, переход к разделу
  меню — у каждого и вход (.24 с, кривая --ez-in = cubic-bezier(.2,.8,.2,1)), и уход (.18 с, --ez-out = cubic-bezier(.4,0,1,1));
  состояние (.open, hidden) меняется сразу (фокус, Esc, aria-modal — как раньше); вход тяжёлых окон стартует через двойной
  requestAnimationFrame (.pre → .in) — после кадра с отрисовкой и раскладкой, а не в нём; will-change — только на время
  анимации (.anim, .closing); уход держит .closing, снимает gone() по animationend или запасному таймеру; повторное открытие
  во время ухода (stay()) — уход отменён; пока открыто меню или окно — фоновые видео и бегущая строка на паузе (.ovl);
  переход к разделу: лента гаснет, прыжок прокрутки — пока она невидима (.pre), затем въезжает; reduced-motion — сразу;
- язык в шапке (details, без JS, /, /kk/, /en/): список появляется анимацией, уходит переходом (где браузер умеет
  ::details-content); /ugolok и /otzyv: смена языка — текст сразу, страница мягко проявляется;
- переход между страницами (/, /kk/, /en/, три текстовых меню, 404, /ugolok, /otzyv): @view-transition там, где браузер
  умеет; где не умеет (Firefox) — запасной скрипт в <head> (seo.VT_JS): новая страница проявляется, клик по ссылке на
  другую страницу сайта — старая гаснет; /legal (HTML не трогаем) — только проявление стилями; reduced-motion — без;
- анимации — только opacity и transform (плоско: tests/test_flat.py); заставка, появление при прокрутке, параллакс и
  бегущая строка — прежние.
Запуск из корня репозитория: python3 -m unittest discover -s tests -v"""
import json, os, re, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seo_jsonld as seo  # noqa: E402
import test_polish_main as pm  # noqa: E402

PAGES = ['index.html', 'kk/index.html', 'en/index.html', 'menyu/index.html', 'kk/menyu/index.html', 'en/menu/index.html',
         '404.html', 'ugolok/index.html', 'otzyv/index.html']
EZ_IN, EZ_OUT = 'cubic-bezier(.2,.8,.2,1)', 'cubic-bezier(.4,0,1,1)'
ENTER, LEAVE = {'rise', 'fade-in', 'up', 'drop', 'vt-in'}, {'sink', 'down', 'out'}


def read(p):
    with open(os.path.join(ROOT, p), encoding='utf-8') as f:
        return f.read()


def css_of(html):
    css = html[html.index('<style>') + 7:html.index('</style>')]
    return re.sub(r'\s*\n\s*', '', re.sub(r'/\*.*?\*/', '', css, flags=re.S))


def rules(css, media=''):
    out = []
    for r in seo.css_rules(css):
        pre, body = r.split('{', 1)
        pre = pre.strip()
        if pre.startswith(('@media', '@supports')):
            out += rules(body[:-1], (media + ' ' + pre).strip())
        elif not pre.startswith('@'):
            out.append((media, pre, body[:-1]))
    return out


def curve(s):
    """var(--ez-in) / var(--ez-out) или само число — к кривой"""
    return {'var(--ez-in)': EZ_IN, 'var(--ez-out)': EZ_OUT}.get(s, s)


class TestAnimationCss(unittest.TestCase):
    def test_keyframes_only_opacity_and_transform(self):
        for p in PAGES:
            for name, body in re.findall(r'@keyframes ([\w-]+)\{((?:[^{}]*\{[^{}]*\})*)\}', css_of(read(p))):
                props = set(re.findall(r'([\w-]+):', re.sub(r'\([^)]*\)', '', body)))
                self.assertLessEqual(props, {'opacity', 'transform', 'visibility'}, '%s: @keyframes %s — %s' % (p, name, props))

    def test_curves(self):
        v = dict(re.findall(r'(--ez-(?:in|out)):\s*([^;]+?)\s*;', read('index.html')))
        self.assertEqual(v, {'--ez-in': EZ_IN, '--ez-out': EZ_OUT}, 'вход тормозит к концу, уход разгоняется')

    def test_page_transitions_everywhere(self):
        """@view-transition — где браузер умеет; запасной переход (класс в <head>, проявление и гашение body) — на всех 9"""
        for p in PAGES:
            html = read(p)
            css = css_of(html)
            self.assertIn('@media(prefers-reduced-motion:no-preference){@view-transition{navigation:auto}}', css, p)
            got = {pre: dict(re.findall(r'([\w-]+):([^;]+)', b)) for _, pre, b in rules(css) if 'view-transition' in pre or 'vt-' in pre}
            self.assertEqual(got['::view-transition-old(root)']['animation-duration'], '.18s', p)
            self.assertEqual(curve(got['::view-transition-old(root)']['animation-timing-function']), EZ_OUT, p)
            self.assertEqual(got['::view-transition-new(root)']['animation-duration'], '.24s', p)
            self.assertEqual(curve(got['::view-transition-new(root)']['animation-timing-function']), EZ_IN, p)
            name, dur, ez = got['.vt-in body']['animation'].split(' ', 2)
            self.assertEqual((name, dur, curve(ez)), ('vt-in', '.22s', EZ_IN), p)
            self.assertEqual(got['.vt-out body']['opacity'], '0', p)
            prop, dur, ez = got['.vt-out body']['transition'].split(' ', 2)
            self.assertEqual((prop, dur, curve(ez)), ('opacity', '.16s', EZ_OUT), p)
            self.assertIn('@keyframes vt-in{from{opacity:0}}', css, p)
            head = html.split('</head>')[0]
            self.assertEqual(head.count('<script>%s</script>' % seo.VT_JS), 1, '%s: запасной переход — в <head>, один раз' % p)
            self.assertLess(head.index(seo.VT_JS), head.index('<style>') if '<style>' in head else len(head), '%s: класс — до стилей и <body>' % p)
        legal = re.sub(r'\s+', ' ', read('legal/style.css'))
        self.assertIn('@media (prefers-reduced-motion: no-preference) { @view-transition { navigation: auto; } }', legal)
        self.assertIn('@supports not (view-transition-name: none) { @media (prefers-reduced-motion: no-preference) { body { animation: vt-in .22s %s; } } }' % EZ_IN, legal)

    def test_enter_and_leave_timing(self):
        """вход — 220–280 мс (--ez-in), уход — 160–200 мс (--ez-out) и остаётся в конце (forwards) до снятия .closing"""
        css = css_of(read('index.html'))
        seen = set()
        for media, pre, body in rules(css):
            if 'intro' in pre:      # заставка — прежняя анимация (fade-in .35 с), не трогаем
                continue
            for name, dur, ez, tail in re.findall(r'animation:([\w-]+) \.(\d+)s ([\w(),.-]+?)( forwards)?(?:;|$)', body):
                ms = int(dur.ljust(3, '0')[:3])
                if name in ENTER:
                    self.assertTrue(220 <= ms <= 280 and curve(ez) == EZ_IN, '%s: вход %s %d мс %s' % (pre, name, ms, ez))
                    seen.add(name)
                elif name in LEAVE:
                    self.assertTrue(160 <= ms <= 200 and curve(ez) == EZ_OUT and tail, '%s: уход %s %d мс %s' % (pre, name, ms, ez))
                    self.assertIn('closing', pre, '%s: уход — только у .closing' % pre)
                    seen.add(name)
        self.assertEqual(seen, ENTER | LEAVE)
        has = lambda sel: any(sel in [s.strip() for s in pre.split(',')] and 'animation:' in b for _, pre, b in rules(css))
        for sel in ('.menu-modal.closing', '.modal.closing .sheet', '.mm-card.closing .mm-card-box', '.modal.closing .backdrop',
                    '.mm-card.closing .mm-card-bg', '.mm-pop.closing', '#mm-cols.closing', '.mm-search.closing',
                    '.mm-lang.closing .mm-lang-btn:not(.on)'):
            self.assertTrue(has(sel), 'уход: ' + sel)
        for sel in ('.menu-modal.in', '#mm-cols.in', '.modal.in .backdrop', '.modal.in .sheet', '.mm-card.in .mm-card-box', '.mm-card.in .mm-card-bg',
                    '.mm-pop', '.mm-search', '.mm-lang.open .mm-lang-btn:not(.on)', '.lang-dd[open] .lang-list'):
            self.assertTrue(has(sel), 'вход: ' + sel)
        for sel in ('.sheet', '.mm-card-box'):
            self.assertNotIn('animation', [b for _, p, b in rules(css) if p == sel][0], '%s: вход — не в кадре смены display' % sel)

    def test_smoothness_helpers(self):
        """плавность (11.11): невидимо до старта (.pre), will-change — только на время, contain у окна и карточки, фон на паузе"""
        css = css_of(read('index.html'))
        rs = {p: b for m, p, b in rules(css) if not m}
        self.assertEqual(rs['.pre'], 'opacity:0')
        self.assertEqual(rs['.anim,.closing'], 'will-change:transform,opacity')
        self.assertEqual(rs['.modal,.mm-card'], 'contain:layout paint', 'оверлеи (у меню — нет: в нём fixed-карточка и «!»)')
        self.assertEqual(rs['.ovl .grill-ticker span'], 'animation-play-state:paused')
        self.assertNotIn('will-change', rs.get('.menu-modal', '') + rs.get('#mm-cols', ''), 'постоянного will-change на больших узлах нет')
        js = read('index.html')
        self.assertIn("RM.matches?go():requestAnimationFrame(()=>requestAnimationFrame(go))", js, 'вход — через двойной rAF')
        self.assertIn("gone(c, ()=>{ c.classList.add('pre'); scrollToMenuEl(document.getElementById(id), false); enter(c); });", js,
                      'к разделу: прыжок прокрутки — пока лента невидима')
        self.assertRegex(js, r"setTimeout\(\(\)=>\{ if\(m\.classList\.contains\('open'\)\)\{ renderFeed\(\); scheduleIdlePrefetch\(\); \} \}, 320\)",
                         'карточки пришли при открытом меню — перерисовка после въезда, не во время')
        sys.path.insert(0, os.path.join(ROOT, 'tools'))
        import flame_frame as ff
        self.assertEqual(ff.CLIP_N, 6)
        clip = re.search(r'\.grill-win\{[^}]*clip-path:polygon\(([^)]*)\)', js).group(1)
        self.assertLessEqual(clip.count('%,') + 1, 60, 'clip-path окна видео — не больше 60 точек')

    def test_closing_keeps_element_on_screen(self):
        """.closing перекрывает display:none (позже в каскаде при равной специфичности) и не ловит нажатия"""
        css = css_of(read('index.html'))
        order = [pre for _, pre, _ in rules(css)]
        self.assertIn('pointer-events:none', [b for _, p, b in rules(css) if p == '.closing'][0])
        for hidden, closing, disp in (('.mm-pop[hidden]', '.menu-modal.closing,.mm-pop.closing', 'block'),
                                      ('.mm-card[hidden]', '.modal.closing,.mm-card.closing', 'flex')):
            self.assertLess(order.index(hidden), order.index(closing))
            self.assertEqual([b for _, p, b in rules(css) if p == closing], ['display:%s' % disp])
        mob = [p for m, p, _ in rules(css) if m == '@media(max-width:680px)']
        self.assertIn('.mm-lang:not(.open):not(.closing) .mm-lang-btn:not(.on)', mob, 'язык меню виден, пока уходит')

    def test_reduced_motion(self):
        css = css_of(read('index.html'))
        rm = [(p, b) for m, p, b in rules(css) if m == '@media(prefers-reduced-motion:reduce)']
        self.assertIn(('.menu-modal,.modal *,.mm-card *,.mm-pop,#mm-cols,.mm-search,.mm-lang-btn', 'animation:none!important'), rm)
        for p in ('index.html', 'kk/index.html', 'en/index.html'):
            self.assertIn(('.lang-list', 'animation:none;transition:none'),
                          [(q, b) for m, q, b in rules(css_of(read(p))) if m == '@media(prefers-reduced-motion:reduce)'], p)
        js = read('index.html')
        self.assertIn("function gone(el,done){if(!el)return;if(RM.matches){el.classList.remove('closing');done&&done();return}", js)
        self.assertIn("matchMedia('(prefers-reduced-motion: reduce)').matches)return;", seo.VT_JS)

    def test_lang_list_light_pages(self):
        """/kk/ и /en/ без JS: список языков — те же анимации, что на главной"""
        main = css_of(read('index.html'))
        for p in ('kk/index.html', 'en/index.html'):
            css = css_of(read(p))
            for need in ('.lang-dd[open] .lang-list{animation:drop .24s var(--ez-in)}', '.lang-dd::details-content{transition:content-visibility .18s allow-discrete}',
                         '@keyframes drop{from{opacity:0;transform:translateY(-6px)}}'):
                self.assertIn(need, main)
                self.assertIn(need, css, p)

    def test_soft_language_switch(self):
        for p in ('ugolok/index.html', 'otzyv/index.html'):
            html = read(p)
            a = re.search(r'main\.lang-in\{animation:lang-in \.24s ([^}]+)\}', css_of(html))
            self.assertEqual(curve(a.group(1)), EZ_IN, p)
            self.assertIn('@media(prefers-reduced-motion:reduce){main.lang-in{animation:none}}', css_of(html), p)
            body = re.search(r'function setLang\(lang, quiet\)\{(.*?)\n\}', html, re.S).group(1)
            self.assertIn("if(mn&&mn.classList&&!quiet){mn.classList.remove('lang-in');void mn.offsetWidth;mn.classList.add('lang-in')}", body, p)


HARNESS_TAIL = r"""
ctx.window = ctx; vm.createContext(ctx); scripts.forEach(s => vm.runInContext(s, ctx));
const R = c => vm.runInContext(c, ctx), E = id => els[id] || document.getElementById(id);
const st = id => { const e = E(id); return ['open', 'pre', 'in', 'closing'].filter(c => e.classList.contains(c)).join(' ') + (e.hidden && /^mm-(card|pop)$/.test(id) ? ' hidden' : ''); };
const end = (id, name) => (E(id)._l.animationend || []).forEach(f => f({ animationName: name, target: E(id) }));
const flush = () => timers.splice(0).forEach(f => f());
const ovl = () => document.body.classList.contains('ovl');
const out = {};
ctx.__cards = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
// меню: вход, уход, конец анимации; повторное открытие во время ухода; запасной таймер; фон на паузе, пока открыто
R('openMenu()'); out.menuOpen = st('menu-modal'); out.ovlOpen = ovl();
R('closeMenu()'); out.menuLeaving = st('menu-modal'); out.ovlLeaving = ovl();
end('menu-modal', 'sink'); out.menuGone = st('menu-modal'); out.ovlClosed = ovl();
R('openMenu()'); R('closeMenu()'); R('openMenu()'); out.menuReopen = st('menu-modal'); flush(); out.menuReopenAfter = st('menu-modal');
R('closeMenu()'); flush(); out.menuTimer = st('menu-modal');
// окно выбора филиала
R("openModal('route')"); out.modalOpen = st('modal'); out.ovlModal = ovl();
R('closeModal()'); out.modalLeaving = st('modal'); end('modal', 'down'); out.modalGone = st('modal'); out.ovlModalClosed = ovl();
R("openModal('route')"); R('closeModal()'); R("openModal('book')"); out.modalReopen = st('modal'); flush(); out.modalReopenAfter = st('modal');
R('closeModal()'); flush();
// карточка блюда — в открытом меню
R('openMenu(); CARDS = __cards; renderFeed()');
out.cardOpened = R("openCard('Курица гриль', document.getElementById('opener'))"); out.cardOpen = st('mm-card');
R('closeCard()'); out.cardLeaving = st('mm-card'); end('mm-card', 'down'); out.cardGone = st('mm-card');
R("openCard('Курица гриль')"); R('closeCard()'); R("openCard('Курица гриль')"); out.cardReopen = st('mm-card'); flush(); out.cardReopenAfter = st('mm-card');
R('closeCard()'); flush();
// подсказка «!»
E('mm-pop').hidden = false; out.popHid = R('hidePop()'); out.popLeaving = st('mm-pop'); end('mm-pop', 'out'); out.popGone = st('mm-pop');
// переход к разделу: лента гаснет, прыжок — пока невидима, потом въезжает
R('goMenuCat(2)'); out.catLeaving = st('mm-cols'); out.cat = R('menuCat'); end('mm-cols', 'out'); out.catEntering = st('mm-cols');
R('goMenuCat(3,true)'); out.catNow = st('mm-cols');
console.log(JSON.stringify(out));
"""


def node_or_skip(test):
    node = pm.find_node()
    if not node:
        test.skipTest('нет node')
    return node


class TestAnimationInNode(unittest.TestCase):
    """скрипты главной целиком на заглушке DOM (tests/test_polish_main.py): классы, hidden, события конца анимации, таймеры;
    requestAnimationFrame выполняется сразу (кадры в заглушке не идут)"""

    def run_page(self, reduce):
        node = node_or_skip(self)
        h = pm.FOCUS_HARNESS.split('ctx.window = ctx;')[0]
        h = h.replace('const ctx = { document, console, setTimeout: () => 0,',
                      'const timers = [];\nconst ctx = { document, console, setTimeout: f => (timers.push(f), timers.length),')
        h = h.replace('requestAnimationFrame: () => 0', 'requestAnimationFrame: f => (f(), 0)')
        # classList заглушки — по одному классу; в браузере add/remove принимают несколько
        h = h.replace('classList: { add: c => cls.add(c), remove: c => cls.delete(c),',
                      'classList: { add: (...c) => c.forEach(x => cls.add(x)), remove: (...c) => c.forEach(x => cls.delete(x)),')
        self.assertIn('(...c) => c.forEach(x => cls.delete(x))', h)
        h = h.replace('matchMedia: () => ({ matches: false,', 'matchMedia: q => ({ matches: %s && q.indexOf(\'reduce\') >= 0,' % ('true' if reduce else 'false'))
        self.assertIn('timers.push', h)
        with tempfile.TemporaryDirectory() as d:
            js, cards = os.path.join(d, 'a.js'), os.path.join(d, 'cards.json')
            with open(js, 'w', encoding='utf-8') as f:
                f.write(h + HARNESS_TAIL)
            with open(cards, 'w', encoding='utf-8') as f:
                f.write(read('menu/cards.json'))
            r = subprocess.run([node, js, os.path.join(ROOT, 'index.html'), cards], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr[-1500:])
        return json.loads(r.stdout.strip().splitlines()[-1])

    def test_enter_leave_reopen(self):
        got = self.run_page(False)
        self.assertEqual((got['menuOpen'], got['menuLeaving'], got['menuGone']), ('open in', 'closing', ''), 'меню: открыто → уходит → ушло')
        self.assertEqual((got['ovlOpen'], got['ovlLeaving'], got['ovlClosed']), (True, True, False),
                         'фоновые видео и строка — на паузе, пока меню открыто и уходит; снова — когда ушло')
        self.assertEqual((got['menuReopen'], got['menuReopenAfter']), ('open in', 'open in'), 'меню открыли снова во время ухода — уход отменён')
        self.assertEqual(got['menuTimer'], '', 'нет события конца анимации — снимает запасной таймер')
        self.assertEqual((got['modalOpen'], got['modalLeaving'], got['modalGone']), ('open in', 'closing', ''), 'окно филиалов')
        self.assertEqual((got['ovlModal'], got['ovlModalClosed']), (True, False))
        self.assertEqual((got['modalReopen'], got['modalReopenAfter']), ('open in', 'open in'))
        self.assertTrue(got['cardOpened'])
        self.assertEqual((got['cardOpen'], got['cardLeaving'], got['cardGone']), ('in', 'closing hidden', ' hidden'), 'карточка: hidden сразу, на экране — пока уходит')
        self.assertEqual((got['cardReopen'], got['cardReopenAfter']), ('in', 'in'))
        self.assertEqual((got['popHid'], got['popLeaving'], got['popGone']), (True, 'closing hidden', ' hidden'), 'подсказка «!»')
        self.assertEqual((got['catLeaving'], got['cat'], got['catEntering']), ('closing', 2, 'in'), 'раздел: гаснет, потом въезжает')
        self.assertEqual(got['catNow'], 'in', 'сразу на место (меню только открылось) — без ухода ленты')

    def test_reduced_motion_instant(self):
        got = self.run_page(True)
        self.assertEqual((got['menuOpen'], got['menuLeaving']), ('open in', ''), 'reduced-motion: меню закрывается сразу')
        self.assertEqual(got['modalLeaving'], '')
        self.assertEqual(got['cardLeaving'], ' hidden')
        self.assertEqual(got['popLeaving'], ' hidden')
        self.assertEqual((got['catLeaving'], got['cat']), ('in', 2), 'reduced-motion: к разделу — сразу')


VT_HARNESS = r"""
const vm = require('vm');
const run = (opts) => {
  const cls = new Set(), L = {}, timers = [], nav = [];
  const d = { classList: { add: c => cls.add(c), remove: c => cls.delete(c) } };
  const ctx = { document: { documentElement: d }, matchMedia: () => ({ matches: !!opts.reduce }), setTimeout: (f, ms) => timers.push([f, ms]),
    addEventListener: (t, f) => { L[t] = f; }, location: { origin: 'https://tap.delcappuccino.kz', pathname: '/', set href(v) { nav.push(v); } } };
  if (opts.vt) ctx.CSSViewTransitionRule = function () {};
  ctx.window = ctx; vm.createContext(ctx); vm.runInContext(process.argv[2], ctx);
  const out = { start: [...cls].join(' '), listens: Object.keys(L).sort().join(',') };
  const click = (a, ev) => { let p = false; const e = Object.assign({ button: 0, target: { closest: () => a }, preventDefault() { p = true; } }, ev || {});
    cls.delete('vt-out'); timers.length = 0; nav.length = 0; L.click(e); timers.filter(t => t[1] === 160).forEach(t => t[0]());
    return [p, cls.has('vt-out'), nav[0] || ''].join('|'); };
  const A = (href, x) => Object.assign({ href: 'https://tap.delcappuccino.kz' + href, origin: 'https://tap.delcappuccino.kz', pathname: href.split('#')[0],
    target: '', hasAttribute: n => !!(x && x[n]) }, x || {});
  if (L.click) {
    out.otzyv = click(A('/otzyv/'));
    out.hash = click(A('/#faq'));
    out.blank = click(A('/ugolok/talon.pdf', { target: '_blank' }));
    out.ctrl = click(A('/otzyv/'), { ctrlKey: true });
    out.middle = click(A('/otzyv/'), { button: 1 });
    out.handled = click(A('/otzyv/'), { defaultPrevented: true });
    out.foreign = click(Object.assign(A('/x'), { origin: 'https://wa.me' }));
    out.download = click(A('/ugolok/talon.pdf', { download: true }));
    out.safety = (() => { click(A('/kk/')); cls.add('vt-out'); const t = timers.find(t => t[1] === 3000); t && t[0](); return !cls.has('vt-out') && !!t; })();
    cls.add('vt-out'); L.pageshow({ persisted: true }); out.bfcache = !cls.has('vt-out');
  }
  return out;
};
console.log(JSON.stringify({ plain: run({}), vt: run({ vt: true }), reduce: run({ reduce: true }) }));
"""


class TestPageTransitionFallback(unittest.TestCase):
    """запасной переход между страницами (seo.VT_JS) на заглушке окна: Firefox и старые браузеры, с view transitions — ничего"""

    def test_fallback_in_node(self):
        node = node_or_skip(self)
        with tempfile.TemporaryDirectory() as d:
            h = os.path.join(d, 'vt.js')
            with open(h, 'w', encoding='utf-8') as f:
                f.write(VT_HARNESS)
            r = subprocess.run([node, h, seo.VT_JS], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr[-1500:])
        got = json.loads(r.stdout)
        p = got['plain']
        self.assertEqual((p['start'], p['listens']), ('vt-in', 'click,pageshow'), 'новая страница проявляется')
        self.assertEqual(p['otzyv'], 'true|true|https://tap.delcappuccino.kz/otzyv/', 'другая страница сайта: гаснет, затем переход')
        for k in ('hash', 'blank', 'ctrl', 'middle', 'handled', 'foreign', 'download'):
            self.assertEqual(p[k], 'false|false|', k)
        self.assertTrue(p['safety'], 'переход не случился — страница возвращается через 3 с')
        self.assertTrue(p['bfcache'], '«Назад» из bfcache — страница не остаётся пустой')
        for k in ('vt', 'reduce'):
            self.assertEqual((got[k]['start'], got[k]['listens']), ('', ''), '%s: скрипт ничего не делает' % k)


if __name__ == '__main__':
    unittest.main()
