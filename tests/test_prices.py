"""Цены со скидкой в меню и в подписи акции (index.html): у позиции с old — старая зачёркнута, новая с классом .sale
(красное подчёркивание). Скидка на гриле 22.10.2026: «Курица гриль», «Рибай на кости», «Ти-бон стейк» — 3990;
сырые «Рибай»/«Ти-бон» в «Мясо» и «Стейк лосося» владелец не менял.
Запуск из корня репозитория: python3 -m unittest discover -s tests -v"""
import os, re, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, 'index.html')

GRILL_SALE = {'Курица гриль': (3990, 6000), 'Рибай на кости': (3990, 7200),
              'Ти-бон стейк с молодым картофелем': (3990, 7200)}


def sections(s):
    """[(раздел, цена раздела|None, [{поле: значение}])] по всем массивам меню — как match_names.site_names"""
    out = []
    for m in re.finditer(r"\{t:'([^']*)'([^\[\]]*?)items:\[", s):
        p = re.search(r"\bp:(\d+)", m.group(2))
        i, depth, j = m.end(), 1, m.end()
        while depth:
            depth += (s[j] == '[') - (s[j] == ']')
            j += 1
        items = []
        for im in re.finditer(r"\{n:'((?:[^'\\]|\\.)*)'([^{}]*)\}", s[i:j - 1]):
            it = {'n': im.group(1).replace("\\'", "'")}
            for k in ('p', 'old'):
                v = re.search(r"\b%s:(\d+)" % k, im.group(2))
                it[k] = int(v.group(1)) if v else None
            items.append(it)
        out.append((m.group(1), int(p.group(1)) if p else None, items))
    return out


class TestSalePrices(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(INDEX, encoding='utf-8') as f:
            cls.html = f.read()
        cls.secs = sections(cls.html)

    def items(self, sec):
        return {it['n']: it for t, _, its in self.secs if t == sec for it in its}

    def test_grill_sale(self):
        grill = self.items('Блюда на гриле')
        for n, (p, old) in GRILL_SALE.items():
            self.assertIn(n, grill)
            self.assertEqual((grill[n]['p'], grill[n]['old']), (p, old), n)
        self.assertEqual((grill['Стейк лосося с молодым картофелем']['p'],
                          grill['Стейк лосося с молодым картофелем']['old']), (7200, None))

    def test_meat_untouched(self):
        meat = [(p, its) for t, p, its in self.secs if t == 'Мясо']
        self.assertEqual(len(meat), 2, 'раздел «Мясо» — в меню кофеен и в Bakery to go')
        for p, its in meat:
            self.assertEqual(p, 3596)
            for it in its:
                if it['n'] in ('Рибай', 'Ти-бон'):
                    self.assertEqual((it['p'], it['old']), (None, None), it['n'])

    def test_old_above_new(self):
        for t, _, its in self.secs:
            for it in its:
                if it['old'] is not None:
                    self.assertIsNotNone(it['p'], it['n'])
                    self.assertGreater(it['old'], it['p'], '%s · %s' % (t, it['n']))

    def test_sale_class_rendered_and_red(self):
        self.assertIn('<span class="old">${fmtP(it.old)}</span> <span class="sale">${fmtP(it.p)}</span>', self.html)
        rule = re.search(r'^\.sale\{([^}]*)\}', self.html, re.M)
        self.assertIsNotNone(rule, 'нет правила .sale')
        self.assertIn('underline', rule.group(1))
        self.assertIn('var(--sale)', rule.group(1))
        red = re.search(r'--sale:#([0-9A-Fa-f]{6})', self.html)
        self.assertIsNotNone(red)
        r, g, b = (int(red.group(1)[k:k + 2], 16) for k in (0, 2, 4))
        self.assertTrue(r > 150 and g < 80 and b < 80, 'подчёркивание должно быть красным')

    def test_grill_caption(self):
        cap = re.search(r'<p class="grill-cap">(.*?)</p>', self.html, re.S).group(1)
        self.assertIn('<s>6000</s> <span class="sale">3990 ₸</span>', cap)
        self.assertIn('aria-label="Курица гриль за 3990 ₸ вместо 6000 ₸', cap)


if __name__ == '__main__':
    unittest.main()
