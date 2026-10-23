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
PLAN = {'order_app': ['cta_order'], 'book_open': ['cta_book'], 'whatsapp': ['loc_wa', 'modal_wa', 'cta_wa_contact'],
        'call': ['loc_call', 'modal_call'], 'route': ['cta_route', 'loc_route', 'modal_route'],
        'menu_open': ['cta_menu', 'menu_open', 'loc_menu', 'modal_menu'], 'dish_card': ['menu_card'],
        'grill_promo': ['cta_grill'], 'instagram': ['cta_instagram'], 'lang_switch': ['lang_switch', 'menu_lang'],
        'faq_open': ['faq_open'], 'ugolok': ['cta_ugolok', 'ugolok_talon']}


def read(p):
    with open(os.path.join(ROOT, p), encoding='utf-8') as f:
        return f.read()


def find_node():
    ver = lambda p: [int(x) for x in re.findall(r'\d+', p.split('/node/')[-1].split('/')[0])]
    return shutil.which('node') or (sorted(glob.glob(os.path.expanduser('~/.nvm/versions/node/*/bin/node')), key=ver) or [None])[-1]


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

    def test_ugolok_events_without_names(self):
        html = self.pages['ugolok/index.html']
        branches = re.findall(r"track\('ugolok_talon',\{branch:'([^']*)'\}\)", html)
        self.assertEqual(branches, ['01', '02', '03', '04', '05'], 'параметр branch — номер точки, не имя ИП')
        self.assertNotRegex(html, r"branch:'[^'0-9]", 'в событиях /ugolok нет подписей с именами')

    def test_same_buttons_on_language_and_menu_pages(self):
        n = len(re.findall(r"\{n:'\d+ · ", read('index.html')))
        faq_n = len(json.loads(read('tools/faq.json')))
        for p in ('kk/index.html', 'en/index.html'):
            page = self.pages[p]
            for ev in ('loc_call', 'loc_route', 'loc_wa'):
                self.assertEqual(page.count("track('%s'" % ev), n, '%s: %s на каждой точке' % (p, ev))
            for ev in ('cta_book', 'cta_order', 'cta_menu', 'cta_wa_contact', 'cta_instagram', 'cta_ugolok', 'loc_menu'):
                self.assertIn("track('%s'" % ev, page, p)
            self.assertEqual(page.count("track('lang_switch'"), 3, '%s: РУС / ҚАЗ / ЕNG' % p)
            self.assertEqual(page.count("track('faq_open'"), faq_n, '%s: раскрытие каждого вопроса' % p)
        for p in ('menyu/index.html', 'kk/menyu/index.html', 'en/menu/index.html'):
            for ev in ('cta_menu', 'cta_order', 'cta_instagram'):
                self.assertIn("track('%s'" % ev, self.pages[p], p)
        main = self.pages['index.html']
        self.assertEqual(main.count("track('lang_switch'"), 3, 'переключатель в шапке главной')
        self.assertEqual(main.count("track('faq_open'"), faq_n)


if __name__ == '__main__':
    unittest.main()
