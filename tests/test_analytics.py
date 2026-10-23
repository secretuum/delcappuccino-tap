"""Аналитика (план владельца 23.10.2026): единая track() во всех страницах — каждое событие в Google Analytics, 12 целей
ещё и в Яндекс Метрику (ym reachGoal). Номер счётчика — константа YM_ID в tools/seo_jsonld.py; пока его нет, кода
Метрики на страницах нет. Параметры событий обезличены: на /ugolok — номера точек 01–05, без имён ИП.
Запуск из корня репозитория: python3 -m unittest discover -s tests -v"""
import glob, json, os, re, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import seo_jsonld as seo  # noqa: E402

PAGES = ['index.html', 'ugolok/index.html', 'menyu/index.html', 'kk/index.html', 'en/index.html',
         'kk/menyu/index.html', 'en/menu/index.html']
# сопоставление из плана владельца (лист «Статистика сайтов»), 12 целей
# одна цель на одно действие (главный, 23.10): кнопки «Меню» и открытие окна выбора филиала целью не считаются
PLAN = {'order_app': ['cta_order'], 'book_open': ['cta_book'], 'whatsapp': ['loc_wa', 'modal_wa'],
        'call': ['loc_call', 'modal_call'], 'route': ['loc_route', 'modal_route'],
        'menu_open': ['menu_open'], 'dish_card': ['menu_card'],
        'grill_promo': ['cta_grill'], 'instagram': ['cta_instagram'], 'lang_switch': ['lang_switch', 'menu_lang'],
        'faq_open': ['faq_open'], 'ugolok': ['cta_ugolok', 'ugolok_talon']}


def read(p):
    with open(os.path.join(ROOT, p), encoding='utf-8') as f:
        return f.read()


def find_node():
    ver = lambda p: [int(x) for x in re.findall(r'\d+', p.split('/node/')[-1].split('/')[0])]
    return shutil.which('node') or (sorted(glob.glob(os.path.expanduser('~/.nvm/versions/node/*/bin/node')), key=ver) or [None])[-1]


# Главная в node с пробным номером Метрики: клики выполняются кодом из onclick/ontoggle разметки, считаются ym reachGoal
GOALS_HARNESS = r"""
const fs = require('fs'), vm = require('vm');
const { html, actions, hashActions } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const scripts = [...html.matchAll(/<script(?![^>]*\bsrc=)(?![^>]*ld\+json)[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]);
function page(hash) {
  const els = {};
  const el = id => ({ id, innerHTML: '', textContent: '', style: { setProperty() {}, removeProperty() {} }, dataset: {}, scrollTop: 0,
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } }, addEventListener() {}, removeEventListener() {},
    setAttribute() {}, getAttribute() { return null; }, removeAttribute() {}, appendChild(x) { return x; }, querySelector() { return el(); },
    querySelectorAll() { return []; }, getBoundingClientRect() { return { top: 0, left: 0, width: 360, height: 0, bottom: 0, right: 360 }; },
    scrollIntoView() {}, scrollTo() {}, focus() {}, closest() { return null; }, play() { return Promise.resolve(); }, pause() {},
    insertAdjacentHTML() {}, contains() { return false; }, offsetHeight: 0 });
  const document = { getElementById: id => els[id] || (els[id] = el(id)), querySelector: () => el(), querySelectorAll: () => [],
    addEventListener() {}, createElement: () => el(), body: el('body'), documentElement: el('html'), head: el('head'), readyState: 'loading' };
  const ctx = { document, console, setTimeout: () => 0, clearTimeout() {}, setInterval: () => 0, clearInterval() {},
    requestAnimationFrame: () => 0, requestIdleCallback: () => 0, cancelIdleCallback() {},
    matchMedia: () => ({ matches: false, addEventListener() {}, addListener() {} }),
    IntersectionObserver: function () { return { observe() {}, disconnect() {} }; }, ResizeObserver: function () { return { observe() {} }; },
    fetch: () => new Promise(() => {}), localStorage: { getItem() { return null; }, setItem() {} }, navigator: { language: 'ru' },
    location: { hash: hash || '', pathname: '/', search: '' }, history: { replaceState() {}, pushState() {} },
    innerWidth: 360, innerHeight: 640, scrollTo() {}, addEventListener() {}, removeEventListener() {} };
  ctx.window = ctx; vm.createContext(ctx);
  scripts.forEach(s => vm.runInContext(s, ctx));
  return { ctx, els };
}
const goals = ctx => (ctx.ym.a || []).filter(a => a[1] === 'reachGoal').map(a => a[2]);
const out = {};
for (const [name, steps] of Object.entries(actions)) {
  const { ctx, els } = page('');
  ctx.ym.a = [];
  for (const step of steps) {
    let code = step;
    if (step.startsWith('MODAL:')) {                          // кнопка в окне выбора филиала (его рисует openModal)
      const ev = step.slice(6);
      code = (els['branch-list'].innerHTML.match(new RegExp('onclick="([^"]*track\\(\'' + ev + '\'[^"]*)"')) || [])[1];
      if (!code) { out[name] = 'нет кнопки ' + ev + ' в окне выбора филиала'; break; }
    }
    ctx.__code = code;
    vm.runInContext('(function(event){ eval(__code) }).call({ open: true }, { preventDefault() {} })', ctx);
  }
  if (!out[name]) out[name] = goals(ctx);
}
for (const [name, hash] of Object.entries(hashActions)) out[name] = goals(page(hash).ctx);   // заход по глубокой ссылке
console.log(JSON.stringify(out));
"""


class TestAnalytics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = {p: read(p) for p in PAGES}

    def test_one_block_in_head_everywhere(self):
        want = seo.analytics_head(seo.YM_ID)
        for p, html in self.pages.items():
            head = html.split('</head>')[0]
            self.assertEqual(head.count(seo.AN_MARK), 1, p)
            self.assertIn(want, head, '%s: блок аналитики разошёлся с генератором — python3 tools/seo_jsonld.py' % p)
            self.assertEqual(len(re.findall(r'function track\(', html)), 1, '%s: одна track() на странице' % p)
            self.assertIn("gtag('config','%s')" % seo.GA_ID, head, p)

    def test_no_metrika_without_counter(self):
        if seo.YM_ID:
            self.skipTest('номер счётчика задан — проверяется test_metrika_block')
        for p, html in self.pages.items():
            self.assertNotRegex(html, r'\bym\(|mc\.yandex|YM_ID|YM_GOALS|reachGoal', '%s: без номера Метрики её кода нет' % p)

    def test_goals_as_planned(self):
        self.assertEqual(sorted(set(seo.YM_GOALS.values())), sorted(PLAN), '12 целей')
        self.assertEqual(seo.YM_GOALS, {ev: goal for goal, evs in PLAN.items() for ev in evs})

    def test_every_goal_event_fires_somewhere(self):
        site = ' '.join(self.pages.values())
        for ev in seo.YM_GOALS:
            self.assertRegex(site, r"track\('%s'" % ev, 'событие %s нигде не отправляется' % ev)

    def test_metrika_block(self):
        block = seo.analytics_head(12345678)      # пробный номер: как будет выглядеть блок, когда владелец пришлёт номер
        for opt in ('clickmap:true', 'trackLinks:true', 'webvisor:true'):
            self.assertIn(opt, block)
        self.assertIn("ym(YM_ID,'init'", block)
        self.assertIn("ym(YM_ID,'reachGoal',g", block)
        self.assertIn("addEventListener('load',idle)", block, 'tag.js — после load, в простое, как gtag')
        self.assertNotIn('<script src=', block, 'tag.js не грузится в <head> синхронно')
        node = find_node()
        if not node:
            self.skipTest('нет node — поведение track() не прогнать')
        js = re.search(r'<script>(.*?)</script>', block, re.S).group(1)
        # блок исполняется как в браузере (вне модуля); gtag складывает события в dataLayer, ym-заглушка — в ym.a
        harness = ("const vm=require('vm');const ctx={document:{readyState:'loading',createElement(){return {}},head:{appendChild(){}}},"
                   "addEventListener(){}};ctx.window=ctx;vm.createContext(ctx);vm.runInContext(%s,ctx);"
                   "vm.runInContext(\"track('loc_wa',{branch:'01'});track('cta_locations')\",ctx);"
                   "const calls=[...ctx.dataLayer.map(a=>['gtag',...Array.from(a)]),...(ctx.ym.a||[]).map(a=>['ym',...Array.from(a)])];"
                   "console.log(JSON.stringify(calls))") % json.dumps(js)
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, 't.js')
            with open(f, 'w', encoding='utf-8') as fh:
                fh.write(harness)
            out = subprocess.run([node, f], capture_output=True, text=True, timeout=30)
        self.assertEqual(out.returncode, 0, out.stderr[-1000:])
        calls = json.loads(out.stdout)
        self.assertIn(['ym', 12345678, 'init', {'clickmap': True, 'trackLinks': True, 'accurateTrackBounce': True, 'webvisor': True}], calls)
        self.assertIn(['gtag', 'event', 'loc_wa', {'branch': '01'}], calls)
        self.assertIn(['gtag', 'event', 'cta_locations', {}], calls, 'в GA — все события')
        self.assertEqual([c for c in calls if c[:3] == ['ym', 12345678, 'reachGoal']],
                         [['ym', 12345678, 'reachGoal', 'whatsapp', {'branch': '01'}]], 'в Метрику — только цели')

    def test_ugolok_without_track_links(self):
        # /ugolok: при включённой Метрике trackLinks:false — адреса PDF-талонов с именами ИП не уходят в Метрику
        saved = seo.YM_ID
        try:
            seo.YM_ID = 12345678
            out = seo.outputs(read('index.html'))
        finally:
            seo.YM_ID = saved
        for path, text in out.items():
            rel = os.path.relpath(path, ROOT)
            if rel.endswith('.html'):
                want = 'false' if rel == 'ugolok/index.html' else 'true'
                self.assertIn("trackLinks:%s" % want, text.split('</head>')[0], rel)

    def test_one_goal_per_action(self):
        node = find_node()
        if not node:
            self.skipTest('нет node — клики главной не прогнать')
        import html as H
        main = self.pages['index.html']
        page = main.replace(re.search(r'<!-- аналитика: Google Analytics[^\n]*-->\n.*?<!-- /аналитика -->\n', main, re.S).group(0),
                            seo.analytics_head(12345678), 1)
        handlers = [H.unescape(x) for x in re.findall(r'\son(?:click|toggle)="([^"]*)"', page)]
        pick = lambda sub: next(x for x in handlers if sub in x)
        actions = {   # действие посетителя → ровно одна цель
            'hero_menu': ([pick("track('cta_menu');openMenu()")], ['menu_open']),
            'nav_menu': ([pick("track('cta_menu',{src:'nav'})")], ['menu_open']),
            'hbar_menu': ([pick("track('cta_menu',{src:'hbar_m'})")], ['menu_open']),
            'card_menu': ([pick("track('loc_menu'")], ['menu_open']),
            'contact_wa_then_branch': ([pick("track('cta_wa_contact')"), 'MODAL:modal_wa'], ['whatsapp']),
            'route_then_branch': ([pick("track('cta_route')"), 'MODAL:modal_route'], ['route']),
            'picker_then_menu': ([pick("track('cta_route')"), 'MODAL:modal_menu'], ['menu_open']),
            'picker_then_call': ([pick("track('cta_route')"), 'MODAL:modal_call'], ['call']),
            'book': ([pick("track('cta_book')")], ['book_open']),
            'card_wa': ([pick("track('loc_wa'")], ['whatsapp']),
            'card_call': ([pick("track('loc_call'")], ['call']),
            'card_route': ([pick("track('loc_route'")], ['route']),
            'order': ([pick("track('cta_order')")], ['order_app']),
            'instagram': ([pick("track('cta_instagram')")], ['instagram']),
            'lang_kk': ([pick("track('lang_switch',{lang:'kk'})")], ['lang_switch']),
            'faq': ([pick("if(this.open)track('faq_open'")], ['faq_open']),
            'ugolok': ([pick("track('cta_ugolok')")], ['ugolok']),
        }
        hash_actions = {'deep_link_kk': ('#menu-kk', ['menu_open']), 'deep_link_togo_en': ('#menu-togo-en', ['menu_open'])}
        with tempfile.TemporaryDirectory() as d:
            h, data = os.path.join(d, 'h.js'), os.path.join(d, 'data.json')
            with open(h, 'w', encoding='utf-8') as f:
                f.write(GOALS_HARNESS)
            with open(data, 'w', encoding='utf-8') as f:
                json.dump({'html': page, 'actions': {k: v[0] for k, v in actions.items()},
                           'hashActions': {k: v[0] for k, v in hash_actions.items()}}, f)
            out = subprocess.run([node, h, data], capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr[-1500:])
        got = json.loads(out.stdout)
        for name, (_, want) in list(actions.items()) + list(hash_actions.items()):
            self.assertEqual(got[name], want, '%s: одно действие — одна цель' % name)

    def test_ugolok_events_without_names(self):
        html = self.pages['ugolok/index.html']
        branches = re.findall(r"track\('ugolok_talon',\{branch:'([^']*)'\}\)", html)
        self.assertEqual(branches, ['01', '02', '03', '04', '05'], 'параметр branch — номер точки, не имя ИП')
        for v in re.findall(r"branch:'([^']*)'", html):
            self.assertRegex(v, r'^\d\d$', 'в событиях /ugolok — только номер точки, без подписей и имён')

    def test_same_buttons_on_language_and_menu_pages(self):
        n = len(re.findall(r"\{n:'\d+ · ", re.search(r'const BRANCHES = \[(.*?)\n\];', read('index.html'), re.S).group(1)))
        faq_n = len(json.loads(read('tools/faq.json')))
        for p in ('kk/index.html', 'en/index.html'):
            page = self.pages[p]
            for ev in ('loc_call', 'loc_route', 'loc_wa'):
                self.assertEqual(page.count("track('%s'" % ev), n, '%s: %s на каждой точке' % (p, ev))
            for ev in ('cta_book', 'cta_order', 'cta_menu', 'cta_wa_contact', 'cta_instagram', 'cta_ugolok', 'loc_menu'):
                self.assertIn("track('%s'" % ev, page, p)
            self.assertEqual(page.count("track('lang_switch'"), 2, '%s: два других языка; у текущего события нет' % p)
            self.assertEqual(page.count("track('faq_open'"), faq_n, '%s: раскрытие каждого вопроса' % p)
        for p in ('menyu/index.html', 'kk/menyu/index.html', 'en/menu/index.html'):
            for ev in ('cta_menu', 'cta_order', 'cta_instagram'):
                self.assertIn("track('%s'" % ev, self.pages[p], p)
        main = self.pages['index.html']
        self.assertEqual(main.count("track('lang_switch'"), 2, 'переключатель в шапке главной: ҚАЗ и ENG')
        for page in (main, self.pages['kk/index.html'], self.pages['en/index.html']):
            self.assertNotRegex(page, r'aria-current="page"[^>]*onclick', 'клик по текущему языку — не цель')
        self.assertIn('class="dist ym-hide-content"', main, 'вебвизор не пишет расстояния до точек (по ним видно, где посетитель)')
        self.assertEqual(main.count("track('faq_open'"), faq_n)

    def test_branch_name_escaped_in_onclick(self):
        self.assertEqual(seo.js_str("01 · O'Neil \\ x"), "01 · O\\'Neil \\\\ x")
        self.assertEqual(seo.js_attr('a"b'), 'a&quot;b')


if __name__ == '__main__':
    unittest.main()
