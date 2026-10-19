"""Тесты menu/build_cards.py на синтетических выгрузках (настоящих данных iiko/ТТК ещё нет).
Запуск из корня репозитория:  python3 -m unittest discover -s tests -v
"""
import json, os, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'menu'))
import build_cards as bc  # noqa: E402

# синтетический справочник: круглые числа, чтобы считать руками
REF = {
    "_meta": {"units": "тест"},
    "тест-курица": {"kcal": 200, "p": 20, "f": 10, "c": 0, "kk": "тест-тауық", "en": "test chicken", "aliases": ["тестовая курица"]},
    "тест-рис": {"kcal": 300, "p": 10, "f": 0, "c": 60, "kk": "тест-күріш", "en": "test rice"},
    "тест-масло": {"kcal": 900, "p": 0, "f": 100, "c": 0, "kk": "тест-май", "en": "test oil"},
    "тест-яйцо": {"kcal": 150, "p": 12, "f": 10, "c": 1, "kk": "тест-жұмыртқа", "en": "test egg", "piece_g": 50},
    "тест-соль": {"kcal": 0, "p": 0, "f": 0, "c": 0, "kk": "тұз"},  # без en — язык en должен выпасть
}

def export(items, version=1):
    return {"version": version, "generated_at": "2026-10-20T10:00:00Z", "items": items}

INDEX_HTML = """<script>const MENU_KITCHEN=[{t:'Тест',items:[
 {n:'Тест: курица с рисом', p:1000},
 {n:'Тест: омлет', p:900},
 {n:'Тест: без состава', p:800},
 {n:'Капучино', p:1500},
]}];</script>"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        self.ref = self.w('nutrition_ref.json', REF)
        self.index = os.path.join(self.d, 'index.html')
        with open(self.index, 'w', encoding='utf-8') as f:
            f.write(INDEX_HTML)
        self.out = os.path.join(self.d, 'cards.json')
        self.img = os.path.join(self.d, 'img', 'menu')

    def tearDown(self):
        self.tmp.cleanup()

    def w(self, name, obj):
        p = os.path.join(self.d, name)
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False)
        return p

    def build(self, iiko=None, ttk=None, **kw):
        cards, rep = bc.build(iiko, ttk, self.ref, self.out, self.img, self.index, no_photos=kw.pop('no_photos', True), **kw)
        return cards, rep.text()


class TestCalc(Base):
    def test_kbju_from_composition_and_translations(self):
        ttk = self.w('ttk.json', export([{
            "key": "t1", "name": "Тест: курица с рисом", "group": "Горячее", "description": None,
            "composition": [{"name": "Тестовая курица", "qty": 150, "unit": "г"},
                            {"name": "тест-рис", "qty": "0,1", "unit": "кг"},
                            {"name": "тест-масло", "qty": 10, "unit": "мл"}],
            "portion": {"value": 230, "unit": "г"}, "per_portion": None, "per_100g": None, "photo": None, "missing": []}]))
        cards, rep = self.build(ttk=ttk)
        c = cards['Тест: курица с рисом']
        # 150 г курицы: 300/30/15/0; 100 г риса: 300/10/0/60; 10 г масла: 90/0/10/0
        self.assertEqual(c['kbju'], {'kcal': 690, 'p': 40, 'f': 25, 'c': 60})
        self.assertEqual(c['w'], '230 г')
        self.assertEqual(c['ing'], {'ru': 'тест-курица, тест-рис, тест-масло',
                                    'kk': 'тест-тауық, тест-күріш, тест-май',
                                    'en': 'test chicken, test rice, test oil'})
        self.assertNotIn('_stub', c)
        self.assertNotIn('d', c)
        self.assertIn('расчёт по составу', rep)

    def test_iiko_per_portion_has_priority(self):
        iiko = self.w('iiko.json', export([{
            "key": "t1", "name": "Тест: курица с рисом", "group": "Горячее", "description": "Описание из iiko.",
            "composition": None, "portion": {"value": 250, "unit": "г"},
            "per_portion": {"kcal": 500, "protein": 30, "fat": 20, "carbs": 40}, "per_100g": None, "photo": None, "missing": []}]))
        ttk = self.w('ttk.json', export([{
            "key": "t1", "name": "Тест: курица с рисом", "composition": [{"name": "тест-рис", "qty": 100, "unit": "г"}],
            "portion": {"value": 230, "unit": "г"}}]))
        cards, rep = self.build(iiko=iiko, ttk=ttk)
        c = cards['Тест: курица с рисом']
        self.assertEqual(c['kbju'], {'kcal': 500, 'p': 30, 'f': 20, 'c': 40})   # не 300/10/0/60 из состава
        self.assertEqual(c['w'], '230 г')                                       # выход — из ТТК
        self.assertEqual(c['d'], {'ru': 'Описание из iiko.'})
        self.assertEqual(c['ing']['ru'], 'тест-рис')
        self.assertIn('[iiko+ttk]', rep)

    def test_pieces_and_partial_translation(self):
        ttk = self.w('ttk.json', export([{
            "key": "t2", "name": "Тест: омлет",
            "composition": [{"name": "тест-яйцо", "qty": 2, "unit": "шт"}, {"name": "тест-соль", "qty": 1, "unit": "г"}],
            "portion": {"value": 100, "unit": "г"}}]))
        cards, rep = self.build(ttk=ttk)
        c = cards['Тест: омлет']
        self.assertEqual(c['kbju'], {'kcal': 150, 'p': 12, 'f': 10, 'c': 1})    # 2 × 50 г
        self.assertEqual(c['ing'], {'ru': 'тест-яйцо, тест-соль', 'kk': 'тест-жұмыртқа, тұз'})  # en выпал: у соли нет en

    def test_missing_ingredient_no_kbju_but_reported(self):
        ttk = self.w('ttk.json', export([{
            "key": "t3", "name": "Тест: курица с рисом",
            "composition": [{"name": "тест-рис", "qty": 100, "unit": "г"}, {"name": "неизвестный трюфель", "qty": 5, "unit": "г"}],
            "portion": {"value": 100, "unit": "г"}, "missing": ["photo"]}]))
        cards, rep = self.build(ttk=ttk)
        c = cards['Тест: курица с рисом']
        self.assertNotIn('kbju', c)
        self.assertEqual(c['ing'], {'ru': 'тест-рис, неизвестный трюфель'})
        self.assertIn('missing: photo, ref:неизвестный трюфель', rep)
        self.assertIn('нет данных', rep)

    def test_per_100g_fallback_and_portions(self):
        iiko = self.w('iiko.json', export([{
            "key": "t4", "name": "Тест: без состава", "portion": {"value": 200, "unit": "г"},
            "per_portion": {"kcal": 500, "protein": None, "fat": 20, "carbs": 40},   # неполное → не берём
            "per_100g": {"kcal": 100, "protein": 5, "fat": 2, "carbs": 10}}]))
        cards, rep = self.build(iiko=iiko)
        self.assertEqual(cards['Тест: без состава']['kbju'], {'kcal': 200, 'p': 10, 'f': 4, 'c': 20})
        ttk = self.w('ttk.json', export([{
            "key": "t5", "name": "Тест: омлет", "portions": 2,
            "composition": [{"name": "тест-рис", "qty": 200, "unit": "г"}], "portion": {"value": 90, "unit": "г"}}]))
        cards, rep = self.build(ttk=ttk)
        self.assertEqual(cards['Тест: омлет']['kbju'], {'kcal': 300, 'p': 10, 'f': 0, 'c': 60})   # на 2 порции

    def test_stubs_kept_and_order_and_unknown_name(self):
        with open(self.out, 'w', encoding='utf-8') as f:
            json.dump({"Капучино": {"_stub": True, "d": {"ru": "x"}},
                       "Тест: омлет": {"_stub": True, "d": {"ru": "старая заглушка"}},
                       "Старое блюдо": {"d": {"ru": "не заглушка, из прошлой сборки"}}}, f, ensure_ascii=False)
        ttk = self.w('ttk.json', export([
            {"key": "a", "name": "Тест: омлет", "composition": [{"name": "тест-яйцо", "qty": 100, "unit": "г"}], "portion": {"value": 100, "unit": "г"}},
            {"key": "b", "name": "Тест: курица с рисом", "composition": [{"name": "тест-рис", "qty": 100, "unit": "г"}], "portion": {"value": 100, "unit": "г"}},
            {"key": "c", "name": "Нет такого в меню", "composition": [{"name": "тест-рис", "qty": 100, "unit": "г"}], "portion": {"value": 100, "unit": "г"}},
        ]))
        cards, rep = self.build(ttk=ttk)
        self.assertEqual(list(cards), ['Тест: курица с рисом', 'Тест: омлет', 'Капучино', 'Нет такого в меню'])
        self.assertEqual(cards['Капучино'], {"_stub": True, "d": {"ru": "x"}})          # заглушка сохранена
        self.assertNotIn('_stub', cards['Тест: омлет'])                                   # заглушка заменена сборкой
        self.assertNotIn('Старое блюдо', cards)                                           # не-заглушка без выгрузки — удалена
        self.assertIn('Нет такого в меню [ttk] — КБЖУ: расчёт по составу — НЕТ В МЕНЮ index.html', rep)
        self.assertIn('удалено старых: Старое блюдо', rep)

    def test_no_exports_keeps_site_as_is(self):
        with open(self.out, 'w', encoding='utf-8') as f:
            json.dump({"Капучино": {"_stub": True}}, f)
        cards, rep = self.build(iiko=os.path.join(self.d, 'нет.json'), ttk=None)
        self.assertEqual(cards, {"Капучино": {"_stub": True}})

    def test_slug(self):
        self.assertEqual(bc.slug('Курица гриль'), 'kurica-gril')
        self.assertEqual(bc.slug('Рибай на кости'), 'ribaj-na-kosti')
        self.assertEqual(bc.slug('Капучино'), 'kapuchino')
        self.assertEqual(bc.slug('Чебуреки с фаршем (2 шт)'), 'chebureki-s-farshem-2-sht')

    def test_photo_local_file_to_webp(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('нет PIL')
        src = os.path.join(self.d, 'big.png')
        Image.new('RGB', (2000, 1500), (120, 90, 60)).save(src)
        iiko = self.w('iiko.json', export([{"key": "p", "name": "Тест: омлет", "photo": src, "portion": {"value": 100, "unit": "г"},
                                             "per_portion": {"kcal": 1, "protein": 1, "fat": 1, "carbs": 1}}]))
        cards, rep = self.build(iiko=iiko, no_photos=False)
        rel = cards['Тест: омлет']['img']
        self.assertTrue(rel.endswith('/test-omlet.webp'), rel)
        dst = os.path.join(self.img, 'test-omlet.webp')
        self.assertTrue(os.path.isfile(dst))
        self.assertLessEqual(os.path.getsize(dst), 100 * 1024)
        with Image.open(dst) as im:
            self.assertEqual(im.format, 'WEBP')
            self.assertLessEqual(max(im.size), 960)
        # повторная сборка без --refresh не перекачивает (ссылка битая, а img остаётся)
        iiko2 = self.w('iiko2.json', export([{"key": "p", "name": "Тест: омлет", "photo": "/нет/такого.png", "portion": {"value": 100, "unit": "г"}}]))
        cards, rep = self.build(iiko=iiko2, no_photos=False)
        self.assertEqual(cards['Тест: омлет']['img'], rel)


class TestRealRef(unittest.TestCase):
    """настоящий справочник: структура и грубая физика (ккал ≈ 4·б + 9·ж + 4·у, у сухих специй расходится из-за клетчатки)"""
    def test_ref_shape(self):
        with open(os.path.join(ROOT, 'menu', 'nutrition_ref.json'), encoding='utf-8') as f:
            data = json.load(f)
        ref = bc.Ref(data)
        self.assertGreaterEqual(len(ref.items), 80)
        off = []
        for n, v in ref.items.items():
            for k in ('kcal', 'p', 'f', 'c'):
                self.assertIsInstance(v[k], (int, float), (n, k))
                self.assertGreaterEqual(v[k], 0, (n, k))
            self.assertTrue(v.get('kk') and v.get('en'), n)
            est = 4 * v['p'] + 9 * v['f'] + 4 * v['c']
            if abs(v['kcal'] - est) > max(40, 0.3 * v['kcal']):
                off.append(n)
        self.assertLessEqual(len(off), 8, off)
        self.assertEqual(ref.find('Филе куриное'), 'куриное филе')
        self.assertEqual(ref.find('лук репчатый свежий'), 'лук репчатый')
        self.assertIsNone(ref.find('неизвестный трюфель'))
        self.assertEqual(ref.grams('яйцо куриное', 2, 'шт'), 110)
        self.assertEqual(ref.grams('чеснок', 3, 'зубчик'), 15)
        self.assertIsNone(ref.grams('рис', 1, 'стакан'))


if __name__ == '__main__':
    unittest.main()
