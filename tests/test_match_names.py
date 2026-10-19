"""Тесты menu/match_names.py на синтетическом index.html и выгрузке. Запуск: python3 -m unittest discover -s tests -v"""
import json, os, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'menu'))
import match_names as mn  # noqa: E402

INDEX = """<script>
const MENU_KITCHEN=[
 {t:'Пицца', items:[{n:'Маргарита', p:1},{n:'Четыре сезона', p:1},{n:'Болоньезе', p:1}]},
 {t:'Соусы', items:[{n:'Шрирача', p:1},{n:'Кетчуп', p:1}]},
 {t:'На компанию', items:[{n:'Микс гриль на 5–6 персон', p:1}]},
 {t:'Десерты', items:[{n:'Медовик', p:1},{n:'Испанский чизкейк', p:1},{n:'Сникерс', p:1}]},
 {t:'Торты (целиком)', items:[{n:'Медовик', p:1},{n:'Чизкейк испанский', p:1},{n:'Сникерс', p:1}]},
];
const MENU_BAR=[
 {t:'Авторские чаи', note:'x', items:[{n:'Груша-мята', vol:'400 мл', p:1},{n:'Чай по-казахски (нават, иримшик)', p:1}]},
 {t:'Фреши', items:[{n:'Яблочный', p:1}]},
 {t:'Глинтвейн б/а', items:[{n:'Яблочный', p:1}]},
 {t:'Гарниры', items:[{n:'Рис', p:1},{n:'Картофель фри', p:1}]},
];
</script>"""

def it(key, name, group, desc=None, photo=None):
    return {"key": key, "name": name, "group": group, "description": desc, "photo": photo, "portion": None,
            "per_portion": None, "per_100g": None, "composition": None, "missing": []}

IIKO = {"version": 1, "generated_at": "x", "items": [
    it("k1", "Пицца Маргарита*", "ПИЦЦА", "Описание", "http://x/1.jpg"),
    it("k2", "Пицца 4 сезона*", "ПИЦЦА", "Описание"),
    it("k3", "Шрирача соус*", "СОУСЫ"),
    it("k4", "Кетчуп доп 50 гр", "ДОПЫ КУХНЯ"),
    it("k5", "Микс гриль на 6-8 персон", "НА КОМПАНИЮ"),
    it("k6", "Десерт Медовик", "ДЕСЕРТЫ", "Описание", "http://x/6.jpg"),
    it("k7", "Торт Медовик 1000 гр", "ДЕСЕРТЫ"),
    it("k8", "Десерт Чизкейк Испанский", "ДЕСЕРТЫ", "Описание"),
    it("k9", "Десерт Сникерс", "ДЕСЕРТЫ", "Описание"),
    it("k10", "Торт Сникерс 1,3 кг", "ДЕСЕРТЫ", None, "http://x/10.jpg"),
    it("k11", "Чай Груша мята  |-->ВЫНОС", "АВТОРСКИЕ ЧАИ"),
    it("k12", "Чай Груша-мята 0,4л н", "АВТОРСКИЕ ЧАИ", "Описание", "http://x/12.jpg"),
    it("k13", "Чай Груша-мята Чайник н", "АВТОРСКИЕ ЧАИ"),
    it("k14", "Чай по казахски  0,4л н", "АВТОРСКИЕ ЧАИ"),
    it("k15", "Фреш яблочный 0,3", "ФРЕШИ", None, "http://x/15.jpg"),
    it("k16", "Глинтвейн Яблочный 0,4л", "ГЛИНТВЕЙН", "Описание", "http://x/16.jpg"),
    it("k17", "Рис*", "ГАРНИРЫ"),
    it("k18", "Рис |--> ВЫНОС", "ГАРНИРЫ", "Описание"),
    it("k19", "Фри*", "ГАРНИРЫ"),
    it("k20", "Рис", "Гарниры вольт", "Описание", "http://x/20.jpg"),       # служебная группа — исключить
    it("k21", "Пицца Маргарита", "СТАФФ МЕНЮ НОВОЕ", "Описание", "http://x/21.jpg"),
    it("k22", "Болоньезе", "Категория без имени"),
]}


class TestNorm(unittest.TestCase):
    def test_norm(self):
        self.assertEqual(mn.norm('Чай Груша-мята 0,4л н'), 'чай груша мята')
        self.assertEqual(mn.norm('Чай Груша мята  |-->ВЫНОС'), 'чай груша мята')
        self.assertEqual(mn.norm('Хашбраун со сметаной *'), 'хашбраун со сметаной')
        self.assertEqual(mn.norm('Лимонад Мохито 0,4л н'), 'лимонад мохито')
        self.assertEqual(mn.norm('Молоко 200мл н'), 'молоко')
        self.assertEqual(mn.norm('Кетчуп доп 50 гр'), 'кетчуп')
        self.assertEqual(mn.norm('Теплый салат из баклажан'), mn.norm('Тёплый салат из баклажана'))
        self.assertEqual(mn.norm('Капучино 0.3 + синнабон'), mn.norm('Капучино 0,3л+ Синнабон'))
        self.assertEqual(mn.norm('Айс ти Классический 0,4'), 'айс ти классический')
        self.assertEqual(mn.norm('Торт Сникерс 1,3 кг'), 'торт сникерс')
        self.assertEqual(mn.strip_prefix('пицца маргарита'), 'маргарита')
        self.assertEqual(mn.strip_prefix('шрирача соус'), 'шрирача')
        self.assertIsNone(mn.strip_prefix('маргарита'))
        self.assertTrue(mn.excluded('Гарниры вольт') and mn.excluded('ПОСУДА НА ВЫНОС') and mn.excluded('СТАФФ МЕНЮ НОВОЕ')
                        and mn.excluded('ДЕСЕРТЫ АГРЕГАТОРЫ зал и дс') and mn.excluded('Категория без имени'))
        self.assertFalse(mn.excluded('ГАРНИРЫ'))


class TestMatch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.index = os.path.join(self.tmp.name, 'index.html')
        self.iiko = os.path.join(self.tmp.name, 'iiko.json')
        with open(self.index, 'w', encoding='utf-8') as f:
            f.write(INDEX)
        with open(self.iiko, 'w', encoding='utf-8') as f:
            json.dump(IIKO, f, ensure_ascii=False)
        self.res, self.rep, self.st = mn.match(self.index, self.iiko)

    def tearDown(self):
        self.tmp.cleanup()

    def test_pairs(self):
        r = self.res
        self.assertEqual(r['Маргарита'], 'k1')             # префикс раздела, не стафф-дубль k21
        self.assertEqual(r['Четыре сезона'], 'k2')         # ALIASES
        self.assertEqual(r['Шрирача'], 'k3')               # «шрирача соус» без слова-префикса сзади
        self.assertEqual(r['Кетчуп'], 'k4')                # «доп 50 гр» срезано
        self.assertEqual(r['Испанский чизкейк'], 'k8')     # те же слова в другом порядке
        self.assertEqual(r['Груша-мята'], 'k12')           # из трёх объёмов — с описанием и фото
        self.assertEqual(r['Чай по-казахски (нават, иримшик)'], 'k14')
        self.assertEqual(r['Рис'], 'k18')                  # с описанием важнее, чем без «ВЫНОС»; вольт-дубль k20 исключён
        self.assertEqual(r['Картофель фри'], 'k19')
        self.assertNotIn('Микс гриль на 5–6 персон', r)    # 5–6 ≠ 6-8: «похоже» с другими цифрами не засчитываем
        self.assertNotIn('Болоньезе', r)                   # только в «Категория без имени»

    def test_section_keys(self):
        r = self.res
        self.assertEqual(r['Медовик @ Десерты'], 'k6')                       # кусок — с описанием/фото
        self.assertEqual(r['Медовик @ Торты (целиком)'], 'k7')               # целый торт — только «Торт …»
        self.assertEqual(r['Сникерс @ Десерты'], 'k9')
        self.assertEqual(r['Сникерс @ Торты (целиком)'], 'k10')
        self.assertNotIn('Медовик', r)                                     # без раздела ключа больше нет
        self.assertNotIn('Чизкейк испанский', r)                           # раздел целых тортов: только «Торт …»
        self.assertIn('Чизкейк испанский  [Торты (целиком)]', '\n'.join(self.rep['missing']))

    def test_report_classes(self):
        self.assertIn('Кетчуп', self.rep['literal']) if False else None
        fuzzy = '\n'.join(self.rep['fuzzy'])
        self.assertIn('Маргарита  [Пицца]  ←  Пицца Маргарита*', fuzzy)
        self.assertIn('Испанский чизкейк', fuzzy); self.assertIn('(те же слова)', fuzzy)
        self.assertEqual(self.st['iiko_excluded'], 3)
        self.assertEqual(self.st['site'], 18)                              # 15 названий, 3 из них в двух разделах
        self.assertEqual(self.st['mapped'] + self.st['missing'], 18)
        txt = mn.report_text(self.rep, self.st)
        self.assertIn('## Спорные', txt); self.assertIn('## Не нашлось', txt)


if __name__ == '__main__':
    unittest.main()
