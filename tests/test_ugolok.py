"""/ugolok — «Уголок потребителя» (31.10.2026, решение владельца): ссылка «← На главную» вверху, в липкой шапке слева,
рядом с переключателем ҚАЗ/РУС/ENG; подпись — та же строка back из словаря I18N страницы, что у кнопки внизу (она остаётся).
Проверка без браузера: разбор разметки (заглушка DOM на html.parser), правила CSS и запас ширины шапки на 360–1024 px
с завышенной шириной букв Montserrat (по метрикам шрифта: подпись ≈0.6 em на букву, ҚАЗ/РУС/ENG ≈0.76 em, берём 0.66 и 0.85).
Запуск из корня репозитория: python3 -m unittest discover -s tests -v"""
import os, re, unittest
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, 'ugolok', 'index.html')
BACK = {'kk': 'Басты бетке', 'ru': 'На главную', 'en': 'Back to home'}


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
    VOID = {'meta', 'link', 'img', 'br', 'input', 'source', 'path', 'hr'}

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


def read():
    with open(PAGE, encoding='utf-8') as f:
        return f.read()


class TestUgolokTopBack(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = read()
        cls.dom = Dom(cls.html)
        cls.css = cls.html[cls.html.index('<style>'):cls.html.index('</style>')]
        bars = cls.dom.find(lambda n: n.tag == 'div' and 'topbar' in n.cls())
        assert len(bars) == 1, 'на странице одна шапка .topbar'
        cls.bar = bars[0]

    def test_link_first_in_topbar(self):
        kids = [n for n in self.bar.children]
        self.assertEqual(kids[0].tag, 'a', 'первым в шапке — ссылка на главную')
        self.assertEqual(kids[0].cls(), ['tb-back'])
        self.assertEqual(kids[0].attrs.get('href'), '/')
        self.assertEqual([k.cls()[0] for k in kids], ['tb-back', 'tb-brand', 'lang-switch'], 'ссылка · название · языки')

    def test_label_from_i18n_back(self):
        a = self.bar.children[0]
        self.assertNotIn('data-i18n', a.attrs, 'data-i18n на <a> стёр бы стрелку при смене языка (textContent)')
        spans = [n for n in a.walk() if n.attrs.get('data-i18n')]
        self.assertEqual([s.attrs['data-i18n'] for s in spans], ['back'], 'подпись — строка back словаря')
        self.assertEqual(spans[0].all_text().strip(), BACK['kk'], 'страница открывается на казахском')
        svg = [n for n in a.walk() if n.tag == 'svg']
        self.assertEqual(len(svg), 1, 'стрелка «←» — та же svg, что у кнопки внизу')
        self.assertEqual(svg[0].attrs.get('aria-hidden'), 'true')
        # словарь: back на трёх языках
        for lang, text in BACK.items():
            block = re.search(r'\b%s:\s*\{(.*?)\n  \}' % lang, self.html, re.S)
            self.assertIsNotNone(block, 'нет словаря %s' % lang)
            self.assertIn('back:"%s"' % text, block.group(1), lang)

    def test_set_lang_switches_both_links(self):
        # заглушка setLang: те же правила, что в скрипте страницы — каждый [data-i18n] получает dict[k]
        self.assertIn("document.querySelectorAll('[data-i18n]')", self.html)
        backs = self.dom.find(lambda n: n.attrs.get('data-i18n') == 'back')
        self.assertEqual(len(backs), 2, 'back — вверху и внизу')
        for lang, text in BACK.items():
            for n in backs:
                n.text = text            # как el.textContent = dict[k]
            self.assertEqual({n.all_text() for n in backs}, {text}, lang)

    def test_bottom_back_kept(self):
        foot = self.dom.find(lambda n: n.tag == 'footer')
        self.assertEqual(len(foot), 1)
        self.assertTrue([n for n in foot[0].walk() if n.tag == 'a' and 'back' in n.cls() and n.attrs.get('href') == '/'],
                        'кнопка «На главную» внизу остаётся')

    def test_css_no_wrap_no_overflow(self):
        css = self.css
        rule = re.search(r'\n\.tb-back\{([^}]*)\}', css).group(1)
        for prop in ('white-space:nowrap', 'min-width:0', 'display:inline-flex'):
            self.assertIn(prop, rule)
        self.assertRegex(css, r'\.tb-back span\{[^}]*text-overflow:ellipsis', 'запас: многоточие вместо прокрутки вбок')
        self.assertIn('.lang-switch{flex:none}', css)
        self.assertIn('overflow-x:hidden', re.search(r'\nbody\{([^}]*)\}', css).group(1))
        self.assertRegex(css, r'@media\(max-width:560px\)\{\s*\.tb-brand\{display:none\}', 'на узком экране название убрано')
        self.assertRegex(css, r'@media\(max-width:374px\)\{[^}]*\.topbar\{gap:8px;padding:7px 10px\}')
        self.assertNotRegex(css, r'\.topbar\{[^}]*justify-content:flex-end', 'ссылка слева, языки справа — space-between')

    def test_width_budget(self):
        # ширина шапки с завышенными буквами: ссылка (самая длинная подпись) + языки + название (если видно) + зазоры
        caps = lambda size: 3 * (0.85 * size + 0.03 * size)              # ҚАЗ / РУС / ENG, letter-spacing .03em
        longest = max(len(t) for t in BACK.values())
        # от 360 px (задание владельца); уже 360 — запас по настоящим метрикам ещё есть (+19 px на 320), дальше — многоточие
        for vw in (360, 375, 390, 414, 561, 721, 1024):
            compact, mid = vw <= 374, vw <= 720
            pad, gap = (10, 8) if compact else ((14, 12) if mid else (16, 12))
            btn_pad = 9 if compact else 12
            switch = 12 + 3 * (2 * btn_pad + caps(12))
            fs, pl, pr, ig = (12, 8, 10, 5) if compact else (13, 10, 13, 6)
            back = pl + 16 + ig + longest * 0.66 * fs + pr
            brand = 0 if vw <= 560 else 14 * ((0.8 + 0.16) * 13 if mid else (0.8 + 0.22) * 15)
            used = 2 * pad + back + gap + switch + (gap + brand if brand else 0)
            self.assertLessEqual(used, vw, '%d px: шапке нужно %.0f px — перенос или прокрутка вбок' % (vw, used))


if __name__ == '__main__':
    unittest.main()
