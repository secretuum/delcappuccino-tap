"""Появление и уход везде (владелец 11.11: «анимация входа в раздел меню, анимация выхода из него и так на всех местах»).
Сторожат:
- главная: меню, окно выбора филиала, карточка блюда, подсказка «!», язык меню на телефоне, поле поиска, переход к разделу
  меню — у каждого и вход (.24 с ease-out), и уход (.18 с ease-in); состояние (.open, hidden) меняется сразу (фокус, Esc,
  aria-modal — как раньше), а .closing держит элемент на экране, пока он уходит: снимает его gone() по animationend или
  по запасному таймеру; повторное открытие во время ухода (stay()) — уход отменён; reduced-motion — без .closing и анимаций;
- язык в шапке (details, без JS, /, /kk/, /en/): список появляется анимацией, уходит переходом (где браузер умеет
  ::details-content); /ugolok и /otzyv: смена языка — текст сразу, страница мягко проявляется;
- переход между страницами (/, /kk/, /en/, три текстовых меню, 404, /ugolok, /otzyv, /legal): @view-transition, без JS,
  при reduced-motion — нет; старая страница гаснет .18 с, новая проявляется .24 с;
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
VT = ['@media(prefers-reduced-motion:no-preference){@view-transition{navigation:auto}}',
      '::view-transition-old(root){animation-duration:.18s;animation-timing-function:ease-in}',
      '::view-transition-new(root){animation-duration:.24s;animation-timing-function:ease-out}']
ENTER, LEAVE = {'rise', 'fade-in', 'up', 'drop'}, {'sink', 'down', 'out'}


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


class TestAnimationCss(unittest.TestCase):
    def test_keyframes_only_opacity_and_transform(self):
        for p in PAGES:
            for name, body in re.findall(r'@keyframes ([\w-]+)\{((?:[^{}]*\{[^{}]*\})*)\}', css_of(read(p))):
                props = set(re.findall(r'([\w-]+):', re.sub(r'\([^)]*\)', '', body)))
                self.assertLessEqual(props, {'opacity', 'transform', 'visibility'}, '%s: @keyframes %s — %s' % (p, name, props))

    def test_view_transition_everywhere(self):
        for p in PAGES:
            css = css_of(read(p))
            for need in VT:
                self.assertIn(need, css, p)
        legal = re.sub(r'\s+', ' ', read('legal/style.css'))
        self.assertIn('@media (prefers-reduced-motion: no-preference) { @view-transition { navigation: auto; } }', legal)
        self.assertIn('::view-transition-old(root) { animation-duration: .18s; animation-timing-function: ease-in; }', legal)

    def test_enter_and_leave_timing(self):
        """вход — 220–280 мс ease-out, уход — 160–200 мс ease-in и остаётся в конце (forwards) до снятия .closing"""
        css = css_of(read('index.html'))
        seen = set()
        for media, pre, body in rules(css):
            if 'intro' in pre:      # заставка — прежняя анимация (fade-in .35 с), не трогаем
                continue
            for name, dur, ease, tail in re.findall(r'animation:([\w-]+) \.(\d+)s ([\w-]+)( forwards)?', body):
                ms = int(dur.ljust(3, '0')[:3])
                if name in ENTER:
                    self.assertTrue(220 <= ms <= 280 and ease == 'ease-out', '%s: вход %s %d мс %s' % (pre, name, ms, ease))
                    seen.add(name)
                elif name in LEAVE:
                    self.assertTrue(160 <= ms <= 200 and ease == 'ease-in' and tail, '%s: уход %s %d мс %s' % (pre, name, ms, ease))
                    self.assertIn('closing', pre, '%s: уход — только у .closing' % pre)
                    seen.add(name)
        self.assertEqual(seen, ENTER | LEAVE)
        for sel in ('.menu-modal.closing', '.modal.closing .sheet', '.mm-card.closing .mm-card-box', '.modal.closing .backdrop',
                    '.mm-card.closing .mm-card-bg', '.mm-pop.closing', '#mm-cols.closing', '.mm-search.closing',
                    '.mm-lang.closing .mm-lang-btn:not(.on)'):
            self.assertTrue(any(sel in [s.strip() for s in pre.split(',')] and 'animation:' in b for _, pre, b in rules(css)), 'уход: ' + sel)
        for sel in ('.menu-modal.open', '#mm-cols.entering', '.modal.open .backdrop', '.mm-card-bg', '.mm-pop', '.mm-search',
                    '.mm-lang.open .mm-lang-btn:not(.on)', '.sheet', '.mm-card-box', '.lang-dd[open] .lang-list'):
            self.assertTrue(any(sel in [s.strip() for s in pre.split(',')] and 'animation:' in b for _, pre, b in rules(css)), 'вход: ' + sel)

    def test_closing_keeps_element_on_screen(self):
        """.closing перекрывает display:none (позже в каскаде при равной специфичности) и не ловит нажатия"""
        css = css_of(read('index.html'))
        order = [pre for _, pre, _ in rules(css)]
        self.assertIn('.closing', order)
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
        self.assertIn(('.sheet,.mm-card-box', 'animation:none'), rm)
        for p in ('index.html', 'kk/index.html', 'en/index.html'):
            self.assertIn(('.lang-list', 'animation:none;transition:none'),
                          [(q, b) for m, q, b in rules(css_of(read(p))) if m == '@media(prefers-reduced-motion:reduce)'], p)
        js = read('index.html')
        self.assertIn("function gone(el,done){if(!el)return;if(RM.matches){el.classList.remove('closing');done&&done();return}", js)

    def test_lang_list_light_pages(self):
        """/kk/ и /en/ без JS: список языков — те же анимации, что на главной"""
        main = css_of(read('index.html'))
        for p in ('kk/index.html', 'en/index.html'):
            css = css_of(read(p))
            for need in ('.lang-dd[open] .lang-list{animation:drop .24s ease-out}', '.lang-dd::details-content{transition:content-visibility .18s allow-discrete}',
                         '@keyframes drop{from{opacity:0;transform:translateY(-6px)}}'):
                self.assertIn(need, main)
                self.assertIn(need, css, p)

    def test_soft_language_switch(self):
        for p in ('ugolok/index.html', 'otzyv/index.html'):
            html = read(p)
            self.assertIn('main.lang-in{animation:lang-in .24s ease-out}', css_of(html), p)
            self.assertIn('@media(prefers-reduced-motion:reduce){main.lang-in{animation:none}}', css_of(html), p)
            body = re.search(r'function setLang\(lang, quiet\)\{(.*?)\n\}', html, re.S).group(1)
            self.assertIn("if(mn&&mn.classList&&!quiet){mn.classList.remove('lang-in');void mn.offsetWidth;mn.classList.add('lang-in')}", body, p)


HARNESS_TAIL = r"""
ctx.window = ctx; vm.createContext(ctx); scripts.forEach(s => vm.runInContext(s, ctx));
const R = c => vm.runInContext(c, ctx), E = id => els[id] || document.getElementById(id);
const st = id => { const e = E(id); return ['open', 'closing', 'entering'].filter(c => e.classList.contains(c)).join(' ') + (e.hidden && /^mm-(card|pop)$/.test(id) ? ' hidden' : ''); };   // hidden — состояние карточки и «!»
const end = (id, name) => (E(id)._l.animationend || []).forEach(f => f({ animationName: name, target: E(id) }));
const flush = () => timers.splice(0).forEach(f => f());
const out = {};
ctx.__cards = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
// меню: вход, уход, конец анимации; повторное открытие во время ухода; запасной таймер
R('openMenu()'); out.menuOpen = st('menu-modal');
R('closeMenu()'); out.menuLeaving = st('menu-modal');
end('menu-modal', 'sink'); out.menuGone = st('menu-modal');
R('openMenu()'); R('closeMenu()'); R('openMenu()'); out.menuReopen = st('menu-modal'); flush(); out.menuReopenAfter = st('menu-modal');
R('closeMenu()'); flush(); out.menuTimer = st('menu-modal');
// окно выбора филиала
R("openModal('route')"); out.modalOpen = st('modal');
R('closeModal()'); out.modalLeaving = st('modal'); end('modal', 'down'); out.modalGone = st('modal');
R("openModal('route')"); R('closeModal()'); R("openModal('book')"); out.modalReopen = st('modal'); flush(); out.modalReopenAfter = st('modal');
// карточка блюда — в открытом меню
R('openMenu(); CARDS = __cards; renderFeed()');
out.cardOpened = R("openCard('Курица гриль', document.getElementById('opener'))"); out.cardOpen = st('mm-card');
R('closeCard()'); out.cardLeaving = st('mm-card'); end('mm-card', 'down'); out.cardGone = st('mm-card');
R("openCard('Курица гриль')"); R('closeCard()'); R("openCard('Курица гриль')"); out.cardReopen = st('mm-card'); flush(); out.cardReopenAfter = st('mm-card');
R('closeCard()'); flush();
// подсказка «!»
E('mm-pop').hidden = false; out.popHid = R('hidePop()'); out.popLeaving = st('mm-pop'); end('mm-pop', 'out'); out.popGone = st('mm-pop');
// переход к разделу: лента гаснет, потом въезжает
R('goMenuCat(2)'); out.catLeaving = st('mm-cols'); out.cat = R('menuCat'); end('mm-cols', 'out'); out.catEntering = st('mm-cols');
R('goMenuCat(3,true)'); out.catNow = st('mm-cols');
console.log(JSON.stringify(out));
"""


class TestAnimationInNode(unittest.TestCase):
    """скрипты главной целиком на заглушке DOM (tests/test_polish_main.py): классы, hidden, события конца анимации, таймеры"""

    def run_page(self, reduce):
        node = pm.find_node()
        if not node:
            self.skipTest('нет node')
        h = pm.FOCUS_HARNESS.split('ctx.window = ctx;')[0]
        h = h.replace('const ctx = { document, console, setTimeout: () => 0,',
                      'const timers = [];\nconst ctx = { document, console, setTimeout: f => (timers.push(f), timers.length),')
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
        self.assertEqual((got['menuOpen'], got['menuLeaving'], got['menuGone']), ('open', 'closing', ''), 'меню: открыто → уходит → ушло')
        self.assertEqual((got['menuReopen'], got['menuReopenAfter']), ('open', 'open'), 'меню открыли снова во время ухода — уход отменён')
        self.assertEqual(got['menuTimer'], '', 'нет события конца анимации — снимает запасной таймер')
        self.assertEqual((got['modalOpen'], got['modalLeaving'], got['modalGone']), ('open', 'closing', ''), 'окно филиалов')
        self.assertEqual((got['modalReopen'], got['modalReopenAfter']), ('open', 'open'))
        self.assertTrue(got['cardOpened'])
        self.assertEqual((got['cardOpen'], got['cardLeaving'], got['cardGone']), ('', 'closing hidden', ' hidden'), 'карточка: hidden сразу, на экране — пока уходит')
        self.assertEqual((got['cardReopen'], got['cardReopenAfter']), ('', ''))
        self.assertEqual((got['popHid'], got['popLeaving'], got['popGone']), (True, 'closing hidden', ' hidden'), 'подсказка «!»')
        self.assertEqual((got['catLeaving'], got['cat'], got['catEntering']), ('closing', 2, 'entering'), 'раздел: гаснет, потом въезжает')
        self.assertEqual(got['catNow'], 'entering', 'сразу на место (меню только открылось) — без ухода ленты')

    def test_reduced_motion_instant(self):
        got = self.run_page(True)
        self.assertEqual((got['menuOpen'], got['menuLeaving']), ('open', ''), 'reduced-motion: меню закрывается сразу')
        self.assertEqual(got['modalLeaving'], '')
        self.assertEqual(got['cardLeaving'], ' hidden')
        self.assertEqual(got['popLeaving'], ' hidden')
        self.assertEqual((got['catLeaving'], got['cat']), ('', 2), 'reduced-motion: к разделу — сразу, без въезда')


if __name__ == '__main__':
    unittest.main()
