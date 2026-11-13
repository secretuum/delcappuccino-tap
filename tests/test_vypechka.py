"""Раздел «Выпечка» во вкладке десертов (владелец 13.11.2026): 23 позиции по его списку с розничными ценами — одинаково
в кофейнях (MENU_DESSERT) и на точке 05 (TOGO_DESSERT), сразу после «Десертов», без only; три мини-киша — NEW.
Переводы kk/en есть у раздела и у каждой позиции; у карточек — описание на трёх языках, фото — у всех, кроме позиций из NO_PHOTO
(товара нет ни в каталоге DC Bakery, ни в папке Диска).
Запуск из корня репозитория: python3 -m unittest discover -s tests -v"""
import json, os, re, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# список владельца, ₸ — розница (оптовые цены DC Bakery сюда не попадают)
OWNER = {'Сытный пирог куриный мини': 1900, 'Сытный пирог семга мини': 2700, 'Сытный пирог три сыра': 1700, 'Слойка вишня': 800,
         'Слойка с индейкой': 900, 'Слойка с малиной': 1000, 'Слойка с курицей и грибами': 1200, 'Слойка с творогом': 800,
         'Слойка со сгущенкой': 800, 'Слойка черничная': 800, 'Мини круассан с клубникой': 500, 'Мини круассан с соленой карамелью': 400,
         'Киш куриный': 5500, 'Киш с индейкой': 4500, 'Киш с семгой': 7500, 'Мини киш куриный': 1800, 'Мини киш с индейкой': 1600,
         'Мини киш с семгой': 2400, 'Орешки классические': 300, 'Мини вишневый пирог': 1600, 'Мини пирог яблоко-слива с шоколадом': 1300,
         'Мини пирог фисташка-яблоко': 2200, 'Творожный пирог мини': 2800}
NEW = {'Мини киш куриный', 'Мини киш с индейкой', 'Мини киш с семгой'}
NO_PHOTO = {'Мини пирог яблоко-слива с шоколадом'}


class TestVypechka(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, 'index.html'), encoding='utf-8') as f:
            cls.html = f.read()
        with open(os.path.join(ROOT, 'menu', 'cards.json'), encoding='utf-8') as f:
            cls.cards = json.load(f)

    def section(self, arr):
        a = self.html.index('const %s = [' % arr)
        blk = self.html[a:self.html.index('\n];', a)]
        secs = re.findall(r"\{t:'([^']*)'", blk)
        v = blk[blk.index("{t:'Выпечка'"):]
        return secs, re.findall(r"\{n:'([^']*)', p:(\d+)([^}]*)\}", v[:v.index(' ]},')])

    def test_same_list_in_cafes_and_togo(self):
        for arr in ('MENU_DESSERT', 'TOGO_DESSERT'):
            secs, items = self.section(arr)
            self.assertEqual(secs[:2], ['Десерты', 'Выпечка'], arr)
            self.assertEqual({n: int(p) for n, p, _ in items}, OWNER, arr)
            self.assertEqual({n for n, _, rest in items if "m:['new']" in rest}, NEW, arr)
            self.assertFalse([n for n, _, rest in items if 'only' in rest], '%s: выпечка есть во всех филиалах' % arr)
        self.assertEqual(self.section('MENU_DESSERT')[1], self.section('TOGO_DESSERT')[1])

    def test_translated(self):
        tr = self.html.index('const MENU_TR')
        for lang in ('kk', 'en'):
            a = self.html.index('\n %s:{' % lang, tr)
            blk = self.html[a:self.html.index('\n },', a)]
            for n in ['Выпечка'] + list(OWNER):
                m = re.search(r"'%s':'([^']+)'" % re.escape(n), blk)
                self.assertTrue(m, '%s: нет перевода «%s»' % (lang, n))
                self.assertNotEqual(m.group(1), n, '%s: «%s» не переведено' % (lang, n))
                if lang == 'en':
                    self.assertFalse(re.search('[а-яё]', m.group(1), re.I), n)

    def test_cards(self):
        for n in OWNER:
            c = self.cards[n]
            self.assertEqual(set(c['d']), {'ru', 'kk', 'en'}, n)
            self.assertTrue(c.get('est'), '%s: КБЖУ без ТТК — только с пометкой «ориентировочно»' % n)
            if n in NO_PHOTO:
                self.assertNotIn('img', c, n)
            else:
                for k in ('img', 'img480'):
                    self.assertTrue(os.path.isfile(os.path.join(ROOT, c[k])), '%s: %s' % (n, k))


if __name__ == '__main__':
    unittest.main()
