"""/otzyv — «Для жалоб и предложений» (задача владельца 11.11.2026): карточки филиалов 01–05 из BRANCHES главной и новая точка
Sputnik Mall (только номер — в BRANCHES её нет), у каждой две кнопки: WhatsApp (wa.me, готовый текст на языке страницы)
и «Позвонить» (tel:). Кнопка «Для жалоб и предложений» — в подвале /, /kk/, /en/ над рядом ссылок с «Уголком потребителя».
Сторож: телефоны на странице = телефоны BRANCHES + новая точка; новой точки нет нигде, кроме /otzyv/; события без номеров;
кнопки (плоские с 11.11) — дословная копия общего слоя главной (сменится слой на главной — пересборка перенесёт, тест покажет расхождение).
Проверка без браузера: разбор разметки (html.parser), правила CSS, скрипт переключателя языка — в node на заглушках DOM.
Запуск из корня репозитория: python3 -m unittest discover -s tests -v"""
import glob, json, os, re, shutil, subprocess, sys, tempfile, unittest
from html.parser import HTMLParser
from urllib.parse import unquote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import seo_jsonld as seo  # noqa: E402
import feedback_page as fb  # noqa: E402

PAGE = os.path.relpath(fb.FILE, ROOT)                # otzyv/index.html
NEW_PHONE = '+77478839057'                           # мобильный номер новой точки Sputnik Mall (владелец 11.11.2026)
FOOTER = {'index.html': ('', 'Для жалоб и предложений'), 'kk/index.html': ('#kk', 'Шағымдар мен ұсыныстар'),
          'en/index.html': ('#en', 'Complaints &amp; suggestions')}
EVENT_ID = r'^(?:\d\d|sputnik)$'


def read(*p):
    with open(os.path.join(ROOT, *p), encoding='utf-8') as f:
        return f.read()


def digits(s):
    return re.sub(r'\D', '', s)


def css_of(html):
    css = html[html.index('<style>') + 7:html.index('</style>')]
    return re.sub(r'\s*\n\s*', '', re.sub(r'/\*.*?\*/', '', css, flags=re.S))


def rules(css):
    out = []
    for r in seo.css_rules(css):
        pre, body = r.split('{', 1)
        if pre.startswith(('@media', '@supports')):
            out += [(pre + ' ' + p, b) for p, b in rules(body[:-1])]
        elif not pre.startswith('@'):
            out.append((pre.strip(), body[:-1]))
    return out


def root_vars(html):
    return dict(re.findall(r'(--[\w-]+):\s*([^;]+?)\s*;', re.search(r':root\{(.*?)\}', css_of(html)).group(1)))


def layers(css):
    """{'' | ':active' | ':hover': (селекторы, тело)} — правила :where(…) общего слоя кнопок (плоские с 11.11, reduced-motion не нужен)"""
    out = {}
    for pre, body in rules(css):
        m = re.match(r'(@media\([^)]*\) )?:where\((.*)\)(:\w+)?$', pre)
        if m:
            out['reduce' if m.group(1) and 'reduced-motion' in m.group(1) else (m.group(3) or '')] = (m.group(2).split(','), body)
    return out


def tone_bodies(css, sel):
    """тела правил (вне :where), где sel в списке селекторов и задаются --tone-*, по порядку"""
    return [b for p, b in rules(css) if not p.startswith(('@', ':where')) and sel in [s.strip() for s in p.split(',')] and '--tone-' in b]


class Node:
    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.parent, self.children, self.text = tag, dict(attrs), parent, [], ''

    def cls(self):
        return (self.attrs.get('class') or '').split()

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()

    def all_text(self):
        return self.text + ''.join(c.all_text() for c in self.children)


class Dom(HTMLParser):
    VOID = {'meta', 'link', 'img', 'br', 'input', 'source', 'path', 'hr', 'use', 'circle', 'rect'}

    def __init__(self, html):
        super().__init__()
        self.root = self.cur = Node('#root', [], None)
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs, self.cur)
        self.cur.children.append(n)
        if tag not in self.VOID:
            self.cur = n

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(Node(tag, attrs, self.cur))

    def handle_endtag(self, tag):
        n = self.cur
        while n is not self.root and n.tag != tag:
            n = n.parent
        if n is not self.root:
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.text += data

    def find(self, pred):
        return [n for n in self.root.walk() if pred(n)]


def i18n_of(html):
    return json.loads(re.search(r'const I18N = (\{.*?\});\n', html).group(1).replace('<\\/', '</'))


def expected_points(html):
    """[(id, телефон, {язык: название}, {язык: адрес}, {язык: «название (адрес)»})] — BRANCHES по порядку, затем новая точка"""
    out = []
    for b in seo.branches(html):
        names, addrs, places = {'ru': seo.short(b)}, {'ru': b['addr']}, {'ru': seo.place(b)}
        for l in ('kk', 'en'):
            c = seo.lang_ctx(html, l)
            names[l], addrs[l], places[l] = seo.T(c, seo.short(b)), seo.T(c, b['addr']), seo.place_l(c, b)
        out.append((seo.bnum(b), b['phone'], names, addrs, places))
    out.append(('sputnik', NEW_PHONE, {l: 'Sputnik Mall' for l in fb.LANGS}, fb.EXTRA_POINTS[0]['addr'],
                {l: 'Sputnik Mall (%s)' % fb.EXTRA_POINTS[0]['addr'][l] for l in fb.LANGS}))
    return out


def find_node():
    ver = lambda p: [int(x) for x in re.findall(r'\d+', p.split('/node/')[-1].split('/')[0])]
    return shutil.which('node') or (sorted(glob.glob(os.path.expanduser('~/.nvm/versions/node/*/bin/node')), key=ver) or [None])[-1]


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = read('index.html')
        cls.html = read(PAGE)
        cls.dom = Dom(cls.html)
        cls.cards = cls.dom.find(lambda n: n.tag == 'article' and 'fb-card' in n.cls())
        cls.points = expected_points(cls.main)
        cls.texts = {l: seo.i18n()[l]['otzyv'] for l in fb.LANGS}


class TestPhones(Base):
    def test_up_to_date(self):
        self.assertEqual(self.html, fb.page(self.main), 'страница разошлась с генератором — python3 tools/seo_jsonld.py')

    def test_cards_from_branches_plus_new_point(self):
        self.assertEqual(len(self.cards), len(seo.branches(self.main)) + 1, 'карточки: 5 филиалов из BRANCHES + новая точка')
        for card, (pid, phone, names, addrs, _) in zip(self.cards, self.points):
            h2 = [n for n in card.walk() if n.tag == 'h2']
            self.assertEqual([n.all_text() for n in h2], [names['ru']], pid)
            addr = [n for n in card.walk() if 'fb-addr' in n.cls()]
            self.assertEqual([n.all_text() for n in addr], [addrs['ru']], pid)
            shown = [n.all_text() for n in card.walk() if 'fb-phone' in n.cls()]
            self.assertEqual([digits(s) for s in shown], [digits(phone)], '%s: номер на карточке — из BRANCHES' % pid)
            links = [n for n in card.walk() if n.tag == 'a']
            self.assertEqual(['tel:' + phone], [a.attrs['href'] for a in links if a.attrs['href'].startswith('tel:')], pid)
            wa = [a.attrs['href'] for a in links if 'wa.me' in a.attrs['href']]
            self.assertEqual([re.match(r'https://wa\.me/(\d+)\?text=', u).group(1) for u in wa], [digits(phone)], pid)

    def test_all_phones_on_page(self):
        """телефоны на странице (tel:, wa.me — и в словаре языков, номера текстом) = BRANCHES + новая точка, и только они"""
        want = {digits(b['phone']) for b in seo.branches(self.main)} | {digits(NEW_PHONE)}
        found = set(re.findall(r'tel:\+(\d+)', self.html)) | set(re.findall(r'wa\.me/(\d+)', self.html))
        found |= {digits(m) for m in re.findall(r'\+7 \d{3} \d{3} \d\d \d\d', self.html)}
        self.assertEqual(found, want)
        self.assertEqual(len(re.findall(r'wa\.me/', self.html)), len(want) * 4, 'по ссылке WhatsApp на точку в разметке и на трёх языках')

    def test_new_point_only_here(self):
        """Sputnik Mall — не филиал (владелец 11.11.2026): нет в BRANCHES, JSON-LD, #locations, окне выбора, sitemap, llms.txt"""
        x = fb.EXTRA_POINTS[0]
        self.assertEqual(x['phone'], NEW_PHONE)
        # 11.11 «ближайшая точка — сверху»: geo — только для сортировки карточек здесь (метка ТРЦ на Яндекс Картах, tests/test_near.py)
        self.assertEqual(set(x), {'id', 'phone', 'name', 'addr', 'geo'}, 'номера 06 и часов у новой точки нет')
        self.assertNotRegex(x['id'], r'\d', 'номер точки не даём')
        branches = re.search(r'const BRANCHES = \[(.*?)\n\];', self.main, re.S).group(1)
        self.assertNotIn(digits(NEW_PHONE), digits(branches))
        self.assertNotIn('Sputnik', branches)
        for p in ('index.html', 'kk/index.html', 'en/index.html', 'menyu/index.html', 'kk/menyu/index.html', 'en/menu/index.html',
                  'ugolok/index.html', '404.html', 'llms.txt', 'sitemap.xml', 'manifest.webmanifest'):
            text = read(p)
            self.assertNotIn(digits(NEW_PHONE), digits(text), '%s: номер новой точки' % p)
            self.assertNotRegex(text, r'(?i)sputnik', '%s: новая точка' % p)
        ld = json.loads(re.search(r'<script type="application/ld\+json">\n(.*?)\n</script>', self.main, re.S).group(1))
        shops = [n for n in ld['@graph'] if n['@type'] in ('CafeOrCoffeeShop', 'Bakery')]
        self.assertEqual(len(shops), len(seo.branches(self.main)))

    def test_new_point_in_branches_stops_build(self):
        # точку внесли в BRANCHES — генератор не должен показать её дважды: выход с ошибкой «уберите из EXTRA_POINTS»
        line = "  {n:'06 · Sputnik Mall', addr:'Мамыр-1, 8а', phone:'%s', geo:[43.2,76.8], hours:'24/7'},\n" % NEW_PHONE
        changed = re.sub(r'(const BRANCHES = \[.*?)(\n\];)', lambda m: m.group(1) + '\n' + line.rstrip('\n') + m.group(2), self.main, count=1, flags=re.S)
        self.assertNotEqual(changed, self.main)
        with self.assertRaises(SystemExit) as e:
            fb.points(changed)
        self.assertIn('EXTRA_POINTS', str(e.exception))


class TestButtons(Base):
    def test_two_buttons_per_card(self):
        for card, (pid, phone, *_rest) in zip(self.cards, self.points):
            box = [n for n in card.walk() if 'fb-links' in n.cls()]
            self.assertEqual(len(box), 1, pid)
            links = [n for n in box[0].children if n.tag == 'a']
            self.assertEqual([a.cls() for a in links], [['fb-btn', 'wa'], ['fb-btn', 'call']], '%s: WhatsApp, затем «Позвонить»' % pid)
            wa, call = links
            self.assertEqual((wa.attrs.get('target'), wa.attrs.get('rel'), wa.attrs.get('data-wa')), ('_blank', 'noopener', pid))
            self.assertEqual(wa.all_text().strip(), 'WhatsApp')
            self.assertEqual(call.attrs['href'], 'tel:' + phone)
            self.assertEqual(call.all_text().strip(), 'Позвонить')
            for a, icon in ((wa, '#i-wa'), (call, '#i-phone')):
                self.assertEqual([u.attrs.get('href') for u in a.walk() if u.tag == 'use'], [icon], pid)
        for sym in ('i-wa', 'i-phone'):
            self.assertEqual(self.html.count('<symbol id="%s"' % sym), 1, 'значок %s — из спрайта главной' % sym)

    def test_wa_text_on_each_language(self):
        """готовый текст: «Здравствуйте! У меня отзыв / предложение по филиалу <название (адрес)>: » — на ru/kk/en свой язык"""
        d = i18n_of(self.html)
        self.assertEqual(sorted(d), sorted(fb.LANGS))
        self.assertEqual(self.texts['ru']['wa_text'], 'Здравствуйте! У меня отзыв / предложение по филиалу {place}: ')
        static = {c.attrs['data-wa']: c.attrs['href'] for c in self.dom.find(lambda n: 'data-wa' in n.attrs)}
        for pid, phone, _, addrs, places in self.points:
            for l in fb.LANGS:
                u = d[l]['wa_' + pid]
                m = re.fullmatch(r'https://wa\.me/(\d+)\?text=([A-Za-z0-9%\-_.!~*\'()]+)', u)
                self.assertIsNotNone(m, '%s %s: ссылка как waLink() главной (encodeURIComponent)' % (l, pid))
                self.assertEqual(m.group(1), digits(phone))
                text = unquote(m.group(2))
                self.assertEqual(text, self.texts[l]['wa_text'].format(place=places[l]), '%s %s' % (l, pid))
                self.assertIn(addrs[l], text, '%s %s: адрес на языке страницы' % (l, pid))
            self.assertEqual(static[pid].replace('&amp;', '&'), d['ru']['wa_' + pid], '%s: без JS — русский текст' % pid)
        self.assertIn('Сәлеметсіз бе!', d['kk']['wa_01'] and unquote(d['kk']['wa_01']))
        self.assertIn('Hello!', unquote(d['en']['wa_01']))

    def test_buttons_are_copy_of_main_layer(self):
        """кнопки — плоский общий слой главной через --tone-*: слои :where(…) дословно, тона — тела правил главной
        («Позвонить», языки, «на главную» — светлый, как .btn.ghost; WhatsApp — как .ib.wa; выбранный язык — как .mm-lang-btn.on)"""
        main, page = css_of(self.main), css_of(self.html)
        lm, lp = layers(main), layers(page)
        self.assertEqual(sorted(lp), ['', ':active', ':hover'])
        for key in lp:
            self.assertEqual(lp[key][0], ['.fb-btn', '.lang-btn', '.tb-back'], key)
            self.assertEqual(lp[key][1], lm[key][1], 'слой %s — дословно как на главной' % (key or 'основа'))
        light = re.search(r'(?:^|\})\.btn\.ghost,[^{]*\{([^}]*)\}', main).group(1)
        self.assertEqual(tone_bodies(page, '.fb-btn.call'), [light])
        self.assertEqual(tone_bodies(page, '.lang-btn'), [light])
        self.assertEqual(tone_bodies(page, '.tb-back'), [light])
        self.assertEqual(tone_bodies(page, '.fb-btn.wa'), [';'.join(tone_bodies(main, '.ib.wa'))])
        self.assertEqual(tone_bodies(page, '.lang-btn.on'), [';'.join(tone_bodies(main, '.mm-lang-btn.on'))])
        self.assertEqual(root_vars(self.html), root_vars(self.main), 'токены v5 и кнопок — :root главной')
        # своих заливок, теней и размытия поверх слоя у кнопок нет (плоские — tests/test_glass.py)
        for pre, body in rules(page):
            if re.search(r'\.(?:fb-btn|lang-btn|tb-back)\b', pre) and not pre.startswith(':where') and ':where(' not in pre:
                self.assertNotRegex(body, r'(?:^|;)(?:background|box-shadow|backdrop-filter)\s*:', pre)

    def test_footer_button_on_three_pages(self):
        for p, (hash_, label) in FOOTER.items():
            html = read(p)
            foot = re.search(r'<footer\b.*?</footer>', html, re.S).group(0)
            want = ('<div class="f-otzyv"><a class="btn ghost" href="%s%s" onclick="track(\'feedback_open\')">%s</a></div>\n  <div class="f-row">'
                    % (fb.PATH, hash_, label))
            self.assertIn(want, foot, '%s: кнопка над рядом ссылок с «Уголком потребителя»' % p)
            self.assertEqual(html.count('href="%s' % fb.PATH), 1, '%s: ссылка на %s — одна' % (p, fb.PATH))
            self.assertEqual(html.count("track('feedback_open')"), 1, p)
            css = css_of(html)
            place = [b for pre, b in rules(css) if pre == '.f-otzyv']
            self.assertEqual(place, ['text-align:center;margin-bottom:var(--s-16)'], '%s: правило места кнопки (по центру, над рядом)' % p)
            self.assertEqual([pre for pre, _ in rules(css) if 'f-otzyv' in pre], ['.f-otzyv'], '%s: стиль кнопки — общий слой (.btn.ghost)' % p)
            self.assertTrue(tone_bodies(css, '.btn.ghost'), '%s: светлый тон .btn.ghost есть на странице' % p)
            self.assertIn('.btn', layers(css)[''][0], '%s: .btn — в общем слое' % p)


class TestAnalytics(Base):
    def test_events_without_phones(self):
        calls = re.findall(r"track\('(\w+)'(?:,(\{[^}]*\}))?\)", self.html.split('</head>')[1])
        self.assertEqual(sorted({n for n, _ in calls}), ['feedback_call', 'feedback_wa'])
        ids = [pid for pid, *_ in self.points]
        for ev in ('feedback_wa', 'feedback_call'):
            got = [re.fullmatch(r"\{branch:'([^']*)'\}", p).group(1) for n, p in calls if n == ev]
            self.assertEqual(got, ids, '%s: по одному на точку, параметр — номер точки или sputnik' % ev)
            for v in got:
                self.assertRegex(v, EVENT_ID, 'в событиях нет номеров телефонов и названий')
        for h in re.findall(r'onclick="([^"]*)"', self.html):
            self.assertNotRegex(h, r'\d{5,}', 'onclick без номеров телефонов')

    def test_analytics_block(self):
        head = self.html.split('</head>')[0]
        self.assertEqual(head.count(seo.AN_MARK), 1)
        self.assertIn(seo.analytics_head(seo.YM_ID), head, 'блок аналитики — как у генератора')
        self.assertEqual(len(re.findall(r'function track\(', self.html)), 1)
        self.assertIn('googletagmanager.com/gtag/js?id=%s' % seo.GA_ID, self.html)
        if not seo.YM_ID:
            self.assertNotRegex(self.html, r'\bym\(|mc\.yandex|YM_GOALS|reachGoal')


class TestSeoAndSw(Base):
    def test_head_and_sitemap(self):
        head = self.html.split('</head>')[0]
        self.assertTrue(self.html.startswith('<!DOCTYPE html>\n<html lang="ru">'))
        self.assertEqual(re.findall(r'<link rel="canonical" href="([^"]+)">', head), [seo.SITE + 'otzyv'])
        self.assertIn('<meta name="robots" content="index, follow">', head)
        self.assertIn('<meta property="og:url" content="%sotzyv">' % seo.SITE, head)
        self.assertIn('<meta name="viewport" content="width=device-width, initial-scale=1">', head)
        self.assertEqual(fb.PATH, '/otzyv/')
        self.assertEqual(seo.PAGES.get(seo.SITE + 'otzyv'), PAGE)
        self.assertIn('<loc>%sotzyv</loc>' % seo.SITE, read('sitemap.xml'))
        self.assertIn(fb.FILE, seo.outputs(self.main), 'страницу собирает tools/seo_jsonld.py (и проверяет --check)')
        self.assertEqual(len(re.findall(r'<h1[ >]', self.html)), 1)
        # страница отдаётся и как /otzyv (без слэша) — пути только от корня
        self.assertNotRegex(self.html, r'(?:src|href|srcset)="(?!/|https://|#|tel:)', 'пути только от корня')
        self.assertNotRegex(self.html, r'(?<![\w-])legal/', 'на legal/ ссылается только подвал главных')

    def test_sw_network_first(self):
        sw = read('sw.js')
        rules_ = sw.split('*/', 1)[0]
        self.assertRegex(rules_, r'любая навигация \([^)]*/otzyv[^)]*\)', 'страница — в комментарии правил sw.js')
        handler = sw.split("addEventListener('fetch'", 1)[1]
        for prefix in re.findall(r"url\.pathname\.indexOf\('([^']+)'\) === 0\) return", handler):
            self.assertFalse(fb.PATH.startswith(prefix), 'sw.js пропускает %s мимо себя' % prefix)
        self.assertIn("if (req.mode === 'navigate' || isShell(url)) {", handler)
        self.assertIn('e.respondWith(networkFirst(e, req, key));', handler)
        self.assertIn("p.slice(-1) === '/'", sw, '/otzyv/ — оболочка (network-first) и не как навигация')


class TestMobile(Base):
    def test_touch_targets_and_wrap(self):
        css, v = css_of(self.html), root_vars(self.html)
        rule = lambda sel: next(b for p, b in rules(css) if p == sel)
        self.assertEqual(v['--h-btn'], '52px')
        self.assertIn('min-height:56px', rule('.fb-btn'), 'филиалы крупно (владелец 11.11): кнопки 56')
        self.assertIn('white-space:nowrap', rule('.fb-btn'), 'подпись кнопки не рвётся — кнопка переносится целиком')
        self.assertIn('flex-wrap:wrap', rule('.fb-links'))
        self.assertIn('min-height:40px', rule('.lang-btn'))
        self.assertIn('inset:-2px 0', rule('.lang-btn::after'), 'языки: 40 + 2×2 = 44 px касания')
        self.assertIn('min-height:44px', rule('.tb-back'))
        self.assertIn('min-height:44px', rule('.f-row a'))
        self.assertIn('overflow-x:hidden', rule('body'))
        self.assertIn('grid-template-columns:repeat(auto-fill,minmax(280px,1fr))', rule('.fb-grid'))

    def test_width_budget(self):
        """360–430 px: колонка карточек не шире экрана; самая длинная кнопка (с завышенной шириной букв Geologica 700 —
        0,66 em) помещается в карточку одна; две в ряд — если влезают, иначе перенос"""
        labels = ['WhatsApp'] + [self.texts[l]['call'] for l in fb.LANGS]
        for vw in (360, 375, 390, 414, 430):
            shell = 16
            self.assertLessEqual(280, vw - 2 * shell, '%d px: минимум колонки 280 px' % vw)
            inner = vw - 2 * shell - 2 * (20 if vw <= 374 else 24)     # 11.11: карточки крупнее — поля 20 / 24
            for t in labels:
                need = 2 * 16 + 22 + 8 + len(t) * 0.66 * 17          # поля кнопки, значок 22, зазор, подпись 17 px
                self.assertLessEqual(need, inner, '%d px: кнопка «%s» шире карточки' % (vw, t))
        # шапка: «← на главную» (самая длинная подпись) + языки — как на /ugolok, от 360 px
        back = max(len(self.texts[l]['back']) for l in fb.LANGS)
        for vw in (360, 375, 390, 414, 430):
            compact = vw <= 374
            pad, gap, btn_pad = (10, 8, 9) if compact else (14, 12, 12)
            switch = 12 + 3 * (2 * btn_pad + 3 * 0.88 * 12)
            fs, pl, pr, ig = (12, 8, 10, 5) if compact else (13, 10, 13, 6)
            used = 2 * pad + pl + 16 + ig + back * 0.66 * fs + pr + gap + switch
            self.assertLessEqual(used, vw, '%d px: шапке нужно %.0f px' % (vw, used))


class TestLanguages(Base):
    def test_dict_covers_page(self):
        d = i18n_of(self.html)
        keys = {n.attrs['data-i18n'] for n in self.dom.find(lambda n: 'data-i18n' in n.attrs)}
        was = {n.attrs['data-wa'] for n in self.dom.find(lambda n: 'data-wa' in n.attrs)}
        for l in fb.LANGS:
            self.assertEqual(keys - set(d[l]), set(), l)
            self.assertEqual({'wa_' + x for x in was} - set(d[l]), set(), l)
            self.assertEqual(d[l]['home'], {'ru': '/', 'kk': '/kk/', 'en': '/en/'}[l])
        # без JS страница — та же, что русский словарь
        for n in self.dom.find(lambda n: 'data-i18n' in n.attrs):
            self.assertEqual(n.all_text().strip(), d['ru'][n.attrs['data-i18n']], n.attrs['data-i18n'])
        self.assertEqual(re.search(r'<title>(.*?)</title>', self.html).group(1), d['ru']['pageTitle'])
        self.assertRegex(d['kk']['h1'] + d['kk']['lead'], r'[әғқңөұүһі]', 'казахский — на казахском')
        self.assertNotRegex(json.dumps({k: x for k, x in d['en'].items() if not k.startswith(('n_', 'a_', 'wa_'))}, ensure_ascii=False),
                            r'[А-Яа-яЁё]', 'английские тексты — без кириллицы')
        for pid, _, names, addrs, _ in self.points:
            for l in fb.LANGS:
                self.assertEqual((d[l]['n_' + pid], d[l]['a_' + pid]), (names[l], addrs[l]), '%s %s' % (l, pid))

    def test_kk_on_review(self):
        review = read('menu', 'kk_review.md')
        for k, x in self.texts['kk'].items():
            self.assertIn('| `otzyv.%s` |' % k, review)
        self.assertIn('| `page.footer_otzyv` | страница /kk/ | Шағымдар мен ұсыныстар |', review)
        self.assertIn(fb.EXTRA_POINTS[0]['addr']['kk'], review)

    def test_set_lang_in_node(self):
        node = find_node()
        if not node:
            self.skipTest('нет node — переключатель языка не прогнать')
        script = re.search(r'<script>\n(const I18N = .*?)</script>', self.html, re.S).group(1)
        els = []
        for n in self.dom.find(lambda n: any(k in n.attrs for k in ('data-i18n', 'data-wa', 'data-home')) or 'lang-btn' in n.cls()):
            els.append({'attrs': {k: (x if x is not None else '') for k, x in n.attrs.items()}, 'text': n.all_text().strip()})
        harness = r"""
const vm = require('vm');
const { lang_js, script, els, hash, click, store } = JSON.parse(process.argv[2]);
const nodes = els.map(e => ({ attrs: Object.assign({}, e.attrs), textContent: e.text, href: e.attrs.href,
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }, setAttribute(k, v) { this.attrs[k] = String(v); },
  classList: { _n: null, toggle(c, on) { const n = this._n; const s = new Set((n.attrs['class'] || '').split(' ').filter(Boolean));
    on ? s.add(c) : s.delete(c); n.attrs['class'] = [...s].join(' '); } } }));
nodes.forEach(n => n.classList._n = n);
const sel = { '[data-i18n]': 'data-i18n', '[data-wa]': 'data-wa', '[data-home]': 'data-home' };
const replaced = [];
const document = { title: '', documentElement: {}, querySelector: () => null, querySelectorAll(s) {
  if (s === '.lang-btn') return nodes.filter(n => (n.attrs['class'] || '').split(' ').includes('lang-btn'));
  return nodes.filter(n => sel[s] in n.attrs); } };
// 11.11: язык — общий выбор сайта: скрипт языка из <head> (seo.LANG_JS) идёт до скрипта страницы; store === 'throw' — нет хранилища
const st = store === 'throw' ? null : Object.assign({}, store || {});
const localStorage = st ? { getItem: k => (k in st ? st[k] : null), setItem: (k, v) => { st[k] = String(v); } }
  : { getItem() { throw new Error('SecurityError'); }, setItem() { throw new Error('SecurityError'); } };
const ctx = { document, localStorage, addEventListener() {}, location: { hash, pathname: '/otzyv/', search: '' },
  history: { replaceState(a, b, u) { replaced.push(u); } } };
vm.createContext(ctx);
vm.runInContext(lang_js, ctx);
vm.runInContext(script, ctx);
if (click) vm.runInContext("setLang('" + click + "')", ctx);
console.log(JSON.stringify({ lang: document.documentElement.lang || null, title: document.title, replaced, store: st,
  nodes: nodes.map(n => ({ attrs: n.attrs, text: n.textContent, href: n.href })) }));
"""
        d = i18n_of(self.html)
        with tempfile.TemporaryDirectory() as tmp:
            h = os.path.join(tmp, 'h.js')
            with open(h, 'w', encoding='utf-8') as f:
                f.write(harness)
            run = lambda hash_, click=None, store=None: json.loads(subprocess.run(
                [node, h, json.dumps({'lang_js': seo.LANG_JS, 'script': script, 'els': els, 'hash': hash_, 'click': click, 'store': store})],
                capture_output=True, text=True, timeout=30, check=True).stdout)
            plain = run('')
            self.assertIsNone(plain['lang'], 'без метки в адресе — русский из разметки, скрипт ничего не трогает')
            self.assertEqual((plain['replaced'], plain['store']), ([], {}), 'открытие /otzyv/ — не выбор языка')
            for junk in ('#constructor', '#__proto__', '#toString', '#de'):     # не язык — как без метки
                got = run(junk)
                self.assertIsNone(got['lang'], junk)
                self.assertTrue(all('undefined' not in str(n.get('href', '')) for n in got['nodes']), junk)
                self.assertEqual(got['title'], '', '%s: заголовок не трогали' % junk)
            for lang in ('kk', 'en'):
                got = run('#' + lang)
                self.assertEqual((got['lang'], got['title']), (lang, d[lang]['pageTitle']))
                self.assertEqual(got['replaced'], [], 'заход по метке — без записи в историю')
                for n in got['nodes']:
                    a = n['attrs']
                    if 'data-i18n' in a:
                        self.assertEqual(n['text'], d[lang][a['data-i18n']], a['data-i18n'])
                    if 'data-wa' in a:
                        self.assertEqual(n['href'], d[lang]['wa_' + a['data-wa']])
                    if 'data-home' in a:
                        self.assertEqual(n['href'], '/%s/' % lang)
                    if 'lang-btn' in a.get('class', ''):
                        on = a['data-lang'] == lang
                        self.assertEqual((('on' in a['class'].split()), a['aria-pressed']), (on, 'true' if on else 'false'))
            clicked = run('', 'en')
            self.assertEqual((clicked['lang'], clicked['replaced']), ('en', ['#en']), 'выбор языка — метка в адресе')
            self.assertEqual(clicked['store'], {'dc_lang': 'en'}, 'выбор здесь — на весь сайт')
            # 11.11 владелец: «если выбран в одном любом месте язык, то он автоматически везде меняется»
            for lang in ('kk', 'en'):
                got = run('', store={'dc_lang': lang})
                self.assertEqual((got['lang'], got['title'], got['replaced']), (lang, d[lang]['pageTitle'], []), 'выбор с другой страницы')
                self.assertEqual([n['href'] for n in got['nodes'] if 'data-home' in n['attrs']][:1], ['/%s/' % lang])
            self.assertIsNone(run('', store={'dc_lang': 'ru'})['lang'], 'выбран русский — как в разметке')
            got = run('#kk', store={'dc_lang': 'en'})
            self.assertEqual((got['lang'], got['store']), ('kk', {'dc_lang': 'kk'}), 'метка в адресе важнее хранилища и сама — выбор')
            for junk in ('de', '"><x', 'kk;'):
                self.assertIsNone(run('', store={'dc_lang': junk})['lang'], 'в хранилище не язык — как без выбора: %r' % junk)
            self.assertIsNone(run('', store='throw')['lang'], 'нет хранилища — по-старому, русский')
            got = run('#en', store='throw')
            self.assertEqual(got['lang'], 'en', 'нет хранилища — метка всё равно работает')
            got = run('', 'kk', store='throw')
            self.assertEqual((got['lang'], got['replaced']), ('kk', ['#kk']), 'нет хранилища — переключатель работает')


if __name__ == '__main__':
    unittest.main()
