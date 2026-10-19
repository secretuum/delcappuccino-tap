"""Описания блюд (menu/descriptions.json): полнота, длина, стоп-слова, попадание в карточки.
Запуск из корня репозитория: python3 -m unittest discover -s tests -v"""
import json, os, re, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'menu'))
import build_cards as bc  # noqa: E402
import match_names as mn  # noqa: E402

STOP = re.compile(r'изысканн|нежнейш|непревзойд|шедевр', re.I)


class TestDescriptions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.site = {}
        for sec, name in mn.site_names(os.path.join(ROOT, 'index.html')):
            cls.site.setdefault(name, []).append(sec)
        with open(os.path.join(ROOT, 'menu', 'descriptions.json'), encoding='utf-8') as f:
            cls.desc = {k: v for k, v in json.load(f).items() if not k.startswith('_')}
        with open(os.path.join(ROOT, 'menu', 'recipes_est.json'), encoding='utf-8') as f:
            cls.rec = {k: v for k, v in json.load(f).items() if not k.startswith('_')}
        cls.tmp = tempfile.TemporaryDirectory()
        cls.cards, rep = bc.build(None, None, os.path.join(ROOT, 'menu', 'nutrition_ref.json'), os.path.join(cls.tmp.name, 'cards.json'),
                                  os.path.join(cls.tmp.name, 'img'), os.path.join(ROOT, 'index.html'), no_photos=True,
                                  recipes=os.path.join(ROOT, 'menu', 'recipes_est.json'),
                                  descriptions=os.path.join(ROOT, 'menu', 'descriptions.json'))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_dish_with_ing_has_three_languages(self):
        for name in self.site:
            c = self.cards[name]
            if 'ing' in c:
                self.assertIn('d', c, name)
                self.assertEqual(set(c['d']), {'ru', 'kk', 'en'}, name)
            else:
                self.assertTrue(self.rec[name].get('no_ing'), name)       # без состава только бутылочные
                self.assertNotIn(name, self.desc, f'{name}: бутылочному описание не нужно')
        self.assertEqual(sorted(set(self.desc) - set(self.site)), [], 'описания для снятых позиций')

    def test_length_and_stop_words(self):
        for name, d in self.desc.items():
            ru = d['ru']
            self.assertTrue(40 <= len(ru) <= 220, f'{name}: ru {len(ru)} символов')
            self.assertIsNone(STOP.search(ru), f'{name}: стоп-слово в ru')
            for l in ('kk', 'en'):
                self.assertTrue(20 <= len(d[l]) <= 300, f'{name}: {l} {len(d[l])} символов')
                self.assertNotEqual(d[l], ru, f'{name}: {l} не переведён')
            self.assertFalse(re.search(r'[а-яё]', d['en'], re.I), f'{name}: кириллица в en')
            self.assertTrue(re.search(r'[әғқңөұүһі]', d['kk']) or re.search(r'[а-я]', d['kk'], re.I), name)

    def test_own_description_beats_iiko(self):
        # запись iiko с описанием, но в descriptions.json своё — в карточке своё на трёх языках
        d = tempfile.TemporaryDirectory()
        try:
            iiko = os.path.join(d.name, 'iiko.json')
            with open(iiko, 'w', encoding='utf-8') as f:
                json.dump({'version': 1, 'items': [{'key': 'k1', 'name': 'Рис', 'group': 'ГАРНИРЫ', 'description': 'Из iiko.', 'portion': {'value': 150, 'unit': 'г'}}]}, f, ensure_ascii=False)
            cards, rep = bc.build(iiko, None, os.path.join(ROOT, 'menu', 'nutrition_ref.json'), os.path.join(d.name, 'cards.json'),
                                  os.path.join(d.name, 'img'), os.path.join(ROOT, 'index.html'), no_photos=True,
                                  descriptions=os.path.join(ROOT, 'menu', 'descriptions.json'))
            self.assertEqual(cards['Рис']['d'], self.desc['Рис'])
        finally:
            d.cleanup()


if __name__ == '__main__':
    unittest.main()
