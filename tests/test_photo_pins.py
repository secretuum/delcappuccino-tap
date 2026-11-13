"""Закреплённые фото (владелец 13.11.2026: «чтобы не заменилось»): полный прогон menu/match_photos.py сам подбирал
«Крок Мадам с копчёной индейкой» другой файл, а «Salam Premium Cola can» — фото стеклянной бутылки. Обе записи закреплены
в menu/name_map_overrides.json и должны совпадать с menu/name_map.json; у банки колы файла с Диска нет (null) — фото из iiko.
Запуск из корня репозитория: python3 -m unittest discover -s tests -v"""
import json, os, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PINS = {'Крок Мадам с копчёной индейкой': 'кухня/крок мадам.jfif', 'Salam Premium Cola can': None}


def load(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as f:
        return json.load(f)


class TestPhotoPins(unittest.TestCase):
    def test_pinned_in_overrides_and_map(self):
        over, name_map = load('menu', 'name_map_overrides.json'), load('menu', 'name_map.json')
        for name, path in PINS.items():
            self.assertIn(name, over, '%s: закрепление снято из name_map_overrides.json' % name)
            self.assertEqual(over[name], path, name)
            self.assertEqual(name_map[name]['drive_file'], path, '%s: name_map.json разошёлся с закреплением' % name)

    def test_cards_and_sources(self):
        cards, sources = load('menu', 'cards.json'), load('img', 'menu', 'sources.json')

        def source(name):
            return sources[os.path.basename(cards[name]['img'])[:-5]]
        # банка колы: файла с Диска нет (null) — в карточке остаётся своё фото из iiko, а не бутылка «SALAM Cola 0,45»
        self.assertTrue(source('Salam Premium Cola can').startswith('iiko:'), source('Salam Premium Cola can')[:40])
        krok = source('Крок Мадам с копчёной индейкой')
        self.assertTrue(krok.startswith('drive:' + PINS['Крок Мадам с копчёной индейкой'] + ':'), krok)


if __name__ == '__main__':
    unittest.main()
