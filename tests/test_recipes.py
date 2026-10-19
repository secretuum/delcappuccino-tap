"""Оценочные составы и КБЖУ (menu/recipes_est.json) для всех позиций сайта.
Запуск из корня репозитория: python3 -m unittest discover -s tests -v"""
import json, os, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'menu'))
import build_cards as bc  # noqa: E402
import match_names as mn  # noqa: E402

# ккал на порцию по разделам сайта (напитки — по умолчанию 0–600)
RANGES = {
    'Завтраки': (250, 1000), 'Сладкие завтраки': (250, 1000), 'Салаты': (150, 600), 'Боулы': (250, 700),
    'Супы': (100, 450), 'Паназия': (100, 1200), 'Сэндвичи / Закуски': (300, 1500), 'Сэндвичи': (300, 1200),
    'Пицца': (300, 1200), 'Паста фреш': (300, 1200), 'Горячие блюда': (300, 1200), 'Домашние блюда': (300, 1200),
    'Блюда на гриле': (300, 1200), 'Хлеба': (100, 700), 'Гарниры': (100, 600), 'Соусы': (10, 350),
    'На компанию': (1500, 9000), 'Дополнения': (0, 200), 'Десерты': (150, 700), 'Торты (целиком)': (150, 5000),
    'Полуфабрикаты': (200, 1500), 'Мясо': (500, 1600),
}
DRINK = (0, 600)
EXCEPTIONS = {'Мясной сет': (300, 1800)}     # сет на компанию в разделе домашних блюд


class TestRecipes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.site = {}
        for sec, name in mn.site_names(os.path.join(ROOT, 'index.html')):
            cls.site.setdefault(name, []).append(sec)
        with open(os.path.join(ROOT, 'menu', 'recipes_est.json'), encoding='utf-8') as f:
            cls.rec = {k: v for k, v in json.load(f).items() if not k.startswith('_')}
        with open(os.path.join(ROOT, 'menu', 'nutrition_ref.json'), encoding='utf-8') as f:
            cls.ref = bc.Ref(json.load(f))
        # сборка без выгрузок и фото — только рецепты и справочник
        cls.tmp = tempfile.TemporaryDirectory()
        out = os.path.join(cls.tmp.name, 'cards.json')
        cls.cards, rep = bc.build(None, None, os.path.join(ROOT, 'menu', 'nutrition_ref.json'), out, os.path.join(cls.tmp.name, 'img'),
                                  os.path.join(ROOT, 'index.html'), no_photos=True, recipes=os.path.join(ROOT, 'menu', 'recipes_est.json'))
        cls.report = rep.text()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_site_dish_has_recipe(self):
        self.assertEqual(sorted(set(self.site) - set(self.rec)), [])
        self.assertEqual(sorted(set(self.rec) - set(self.site)), [], 'рецепты для снятых с сайта позиций')

    def test_ingredients_resolve_and_fields(self):
        for name, r in self.rec.items():
            self.assertIn(r.get('src'), ('iiko', 'est', 'label'), name)
            self.assertGreater(float(r.get('portion_g') or 0), 0, name)
            if r.get('label_per_100'):
                self.assertTrue(r.get('no_ing'), name)
                self.assertEqual(set(r['label_per_100']), {'kcal', 'p', 'f', 'c'}, name)
                continue
            self.assertTrue(r.get('items'), name)
            for it in r['items']:
                self.assertIsNotNone(self.ref.find(it['name']), f'{name}: «{it["name"]}» нет в справочнике')
                self.assertGreater(float(it['qty_g']), 0, name)

    def test_cards_have_ing_and_kbju(self):
        for name in self.site:
            c = self.cards.get(name)
            self.assertIsNotNone(c, name)
            self.assertIn('kbju', c, name)
            self.assertIn('w', c, name)
            r = self.rec[name]
            if r.get('no_ing'):
                self.assertNotIn('ing', c, name)
                self.assertNotIn('est', c, name)           # этикетка — не оценка
            else:
                self.assertEqual(set(c['ing']), {'ru', 'kk', 'en'}, name)
                self.assertTrue(c['ing']['ru'] and c['ing']['kk'] and c['ing']['en'], name)
                self.assertTrue(c.get('est'), name)       # без iiko/ТТК КБЖУ только оценочное
            self.assertNotIn('_stub', c, name)

    def test_kbju_ranges_and_atwater(self):
        bad = []
        for name, secs in self.site.items():
            k = self.cards[name]['kbju']
            lo, hi = EXCEPTIONS.get(name) or RANGES.get(secs[0], DRINK)
            if not lo <= k['kcal'] <= hi:
                bad.append(f'{name} [{secs[0]}]: {k["kcal"]} ккал вне {lo}–{hi}')
            est = 4 * k['p'] + 9 * k['f'] + 4 * k['c']
            if abs(k['kcal'] - est) > max(0.2 * est, 12):
                bad.append(f'{name}: {k["kcal"]} ккал ≠ 4·{k["p"]}+9·{k["f"]}+4·{k["c"]}={est:.0f}')
        self.assertEqual(bad, [])

    def test_report_mentions_sources(self):
        self.assertIn('расчёт по оценочному составу', self.report)
        self.assertIn('этикетка', self.report)


if __name__ == '__main__':
    unittest.main()
