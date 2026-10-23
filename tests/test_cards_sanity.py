"""Собранный menu/cards.json: вес и КБЖУ из одного источника — ккал на 100 г в разумных пределах,
у напитков объём не меньше 30 мл (кроме явного объёма на сайте, как у эспрессо 25 мл).
Запуск из корня репозитория: python3 -m unittest discover -s tests -v"""
import json, os, re, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'menu'))
import build_cards as bc  # noqa: E402
import match_names as mn  # noqa: E402

DEFAULT = (60, 450)
# супы и овощные гарниры легче 60 ккал/100 г по природе; соусы, масла, мёд, сыры, хлеб с маслом — плотнее
RANGES = {'Супы': (25, 450), 'Гарниры': (25, 450), 'Паназия': (50, 450), 'Соусы': (0, 750), 'Дополнения': (0, 750), 'Хлеба': (60, 750)}
DRINK = (0, 450)


class TestCardsSanity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, 'menu', 'cards.json'), encoding='utf-8') as f:
            cls.cards = json.load(f)
        with open(os.path.join(ROOT, 'menu', 'recipes_est.json'), encoding='utf-8') as f:
            # вес и КБЖУ не публикуем по решению владельца (список закреплён в test_recipes.OWNER_FIXED)
            cls.no_w_kbju = {k for k, v in json.load(f).items() if not k.startswith('_') and v.get('no_w') and v.get('no_kbju')}
        cls.secs, cls.vols = {}, mn.site_vols(os.path.join(ROOT, 'index.html'))
        for key, sec, name in mn.site_keys(os.path.join(ROOT, 'index.html')):
            cls.secs.setdefault(key, sec)

    @staticmethod
    def grams(w):
        m = re.match(r'(\d+(?:\.\d+)?)\s*(г|мл)$', w or '')
        return (float(m.group(1)), m.group(2)) if m else (None, None)

    def test_kcal_per_100g(self):
        bad = []
        for key, sec in self.secs.items():
            c = self.cards.get(key)
            self.assertIsNotNone(c, key)
            if key in self.no_w_kbju:
                self.assertFalse(c.get('w') or c.get('kbju') or c.get('est'), key)
                continue
            g, unit = self.grams(c.get('w'))
            self.assertTrue(g and c.get('kbju'), key)
            per = c['kbju']['kcal'] / g * 100
            lo, hi = (RANGES.get(sec, DEFAULT) if bc.is_food(sec, key) else DRINK)
            if not lo <= per <= hi:
                bad.append(f'{key} [{sec}]: {c["kbju"]["kcal"]} ккал / {c["w"]} = {per:.0f} ккал/100 г вне {lo}–{hi}')
        self.assertEqual(bad, [])

    def test_drinks_volume(self):
        bad = []
        for key, sec in self.secs.items():
            if bc.is_food(sec, key):
                continue
            g, unit = self.grams(self.cards[key].get('w'))
            site, _ = bc.site_vol_g(self.vols.get(key))
            if unit != 'мл' or (g < bc.DRINK_MIN_G and not (site and g == site)):
                bad.append(f'{key} [{sec}]: {self.cards[key].get("w")}')
        self.assertEqual(bad, [])
        self.assertEqual(self.cards['Эспрессо / Доппио']['w'], '25 мл')
        self.assertEqual(self.cards['Декаф']['w'], self.cards['Американо']['w'])

    def test_site_vol_parsing(self):
        self.assertEqual(bc.site_vol_g('200/300/400 мл'), (200, 'мл'))
        self.assertEqual(bc.site_vol_g('300 мл / 1 л'), (300, 'мл'))
        self.assertEqual(bc.site_vol_g('0,5 л'), (500, 'мл'))
        self.assertEqual(bc.site_vol_g('125 гр'), (125, 'г'))
        self.assertEqual(bc.site_vol_g('1 шт (~300 гр)'), (None, None))


if __name__ == '__main__':
    unittest.main()
