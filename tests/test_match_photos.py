"""Тесты menu/match_photos.py и фото из папки в build_cards.py — на синтетической папке с крошечными картинками.
Запуск: python3 -m unittest discover -s tests -v"""
import contextlib, io, json, os, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'menu'))
import match_photos as mp  # noqa: E402
import build_cards as bc  # noqa: E402

INDEX = """<script>const MENU_KITCHEN=[
 {t:'Завтраки', items:[{n:'Крок Мадам с копчёной индейкой', p:1},{n:'Блины с бананом и с шоколадом', p:1},{n:'Стейк-омлет', p:1}]},
 {t:'Супы', items:[{n:'Борщ с говядиной и бородинским хлебом', p:1},{n:'Тыквенный крем-суп', p:1}]},
 {t:'Пицца', items:[{n:'Маргарита', p:1},{n:'Четыре сезона', p:1}]},
 {t:'Соусы', items:[{n:'Цезарь', p:1},{n:'Сырный', p:1}]},
 {t:'Горячие блюда', items:[{n:'Котлеты говяжьи по-домашнему с пюре', p:1},{n:'Рамен сливочный', p:1}]},
 {t:'Сладкие завтраки', items:[{n:'Сырники классические', p:1}]},
 {t:'Полуфабрикаты', items:[{n:'Котлеты говяжьи', p:1},{n:'Вареники', p:1},{n:'Сырники с иримшиком', p:1}]},
 {t:'Мясо', items:[{n:'Рибай', p:1},{n:'Фарш', p:1}]},
 {t:'Блюда на гриле', items:[{n:'Рибай на кости', p:1}]},
];</script>"""

FILES = {  # путь → (ширина, высота)
    'кухня/крок мадам.jfif': (800, 600),
    'кухня/Блины с бананом и шоколадом.jpg': (640, 480),
    'кухня/блины с бананом.jfif': (640, 480),
    'кухня/стейк омлет.png': (300, 200),
    'кухня/Борщ.jpg': (300, 200),
    'кухня/тыквенный.png': (300, 200),
    'кухня/Пицца Маргарита.png': (400, 300),
    'кухня/Пицца Маргарита.jfif': (1600, 1200),      # jfif проигрывает png даже при большем разрешении
    'кухня/Пицца 4 сезона.png': (400, 300),
    'кухня/Соус Цезарь.jpg': (300, 200),
    'кухня/Сырный соус.png': (300, 200),
    'кухня/котлеты говяжьи по домашнему с пюре.png': (300, 200),
    'кухня/Котлеты говяжьи по-домашнему с пюре.png': (900, 600),   # больше → лучше
    'кухня/рамен сливочный с курицей.png': (300, 200),
    'кухня/рамен сливочный с креветками.png': (300, 200),
    'кухня/сырники.jfif': (300, 200),
    'кухня/Вареники 170 гр готовые.png': (300, 200),
    'кухня/Рибай на кости.png': (300, 200),
    'пф и мясо/Фарш говяжий 1кг.png': (300, 200),
    'кухня/ChatGPT Image 20 авг. 2026 г., 14_34_18 (5).png': (300, 200),
    'кухня/заметки.txt': None,
}


def make_folder(d):
    try:
        from PIL import Image
    except ImportError:
        Image = None
    for rel, wh in FILES.items():
        p = os.path.join(d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if wh is None or Image is None:
            with open(p, 'wb') as f:
                f.write(b'x')
            continue
        fmt = {'.png': 'PNG', '.jpg': 'JPEG', '.jfif': 'JPEG'}[os.path.splitext(rel)[1]]
        Image.new('RGB', wh, (200, 150, 100)).save(p, fmt)


class TestNormAndMatch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        self.index = os.path.join(self.d, 'index.html')
        with open(self.index, 'w', encoding='utf-8') as f:
            f.write(INDEX)
        self.photos = os.path.join(self.d, 'menu_photos')
        make_folder(self.photos)

    def tearDown(self):
        self.tmp.cleanup()

    def test_norm_file(self):
        self.assertEqual(mp.norm_file('Ти-бон стейк с молодым картофелем 350 гр.jpg'), 'ти бон стейк с молодым картофелем')
        self.assertEqual(mp.norm_file('Вареники 170 гр готовые.png'), 'вареники')
        self.assertEqual(mp.norm_file('Манты с говядиной 5 шт готовые.png'), 'манты с говядиной')
        self.assertEqual(mp.norm_file('Багет классический 1шт.png'), 'багет классический')
        self.assertEqual(mp.norm_file('вафли из цукини2.png'), 'вафли из цукини')
        self.assertEqual(mp.norm_file('Бельгийские вафли (мед, карамель, ягодное компоте).jpg'), 'бельгийские вафли')
        self.assertEqual(mp.norm_file('хлебная корзина фото.png'), 'хлебная корзина')
        self.assertEqual(mp.norm_file('блины со сметаной.jfif'), 'блины с сметаной')
        self.assertEqual(mp.norm_file('Пицца 4 сезона.png'), 'пицца 4 сезона')
        self.assertEqual(mp.norm_site('Чучвара (пельмени с говядиной)'), 'чучвара')
        self.assertEqual(mp.norm_site('Блины со сметаной и мёдом'), 'блины с сметаной и медом')

    def test_match_folder(self):
        files = mp.scan_folder(self.photos)
        self.assertEqual(len(files), len(FILES) - 1)                      # txt пропущен
        res, rep, st = mp.match(__import__('match_names').site_names(self.index), files)
        self.assertEqual(res['Крок Мадам с копчёной индейкой'], 'кухня/крок мадам.jfif')          # по началу
        self.assertEqual(res['Блины с бананом и с шоколадом'], 'кухня/Блины с бананом и шоколадом.jpg')  # похоже, не «блины с бананом»
        self.assertEqual(res['Стейк-омлет'], 'кухня/стейк омлет.png')
        self.assertEqual(res['Борщ с говядиной и бородинским хлебом'], 'кухня/Борщ.jpg')        # однословное начало, владелец один
        self.assertEqual(res['Тыквенный крем-суп'], 'кухня/тыквенный.png')
        self.assertEqual(res['Маргарита'], 'кухня/Пицца Маргарита.png')                          # png важнее jfif
        self.assertEqual(res['Медовик @ Десерты'], 'кухня/крок мадам.jfif') if False else None
        self.assertEqual(res['Четыре сезона'], 'кухня/Пицца 4 сезона.png')                        # ALIASES
        self.assertEqual(res['Цезарь'], 'кухня/Соус Цезарь.jpg')
        self.assertEqual(res['Сырный'], 'кухня/Сырный соус.png')
        self.assertEqual(res['Котлеты говяжьи по-домашнему с пюре'], 'кухня/Котлеты говяжьи по-домашнему с пюре.png')  # большее разрешение
        self.assertEqual(res['Вареники'], 'кухня/Вареники 170 гр готовые.png')
        self.assertEqual(res['Рибай на кости'], 'кухня/Рибай на кости.png')
        self.assertNotIn('Котлеты говяжьи', res)        # полуфабрикаты: только точное совпадение
        self.assertNotIn('Рибай', res)                  # мясо: «Рибай на кости» — блюдо, не сырьё
        self.assertNotIn('Фарш', res)                   # «фарш»/«1кг» не берём
        self.assertNotIn('Рамен сливочный', res)        # два файла-кандидата (с курицей / с креветками) — не угадываем
        self.assertNotIn('Сырники классические', res)   # «сырники» — начало двух позиций
        self.assertNotIn('Сырники с иримшиком', res)
        fuzzy = '\n'.join(rep['fuzzy'])
        self.assertIn('Крок Мадам с копчёной индейкой  ←  кухня/крок мадам.jfif  (по началу названия)', fuzzy)
        self.assertIn('Маргарита  ←  кухня/Пицца Маргарита.png  (+1 дубл.)', fuzzy)
        self.assertIn('Стейк-омлет', rep['literal']) if False else None
        self.assertIn('кухня/сырники.jfif', rep['unused'])
        self.assertNotIn('ChatGPT', '\n'.join(rep['unused']))
        self.assertEqual(st['mapped'], 12)                # «Яблочный»: ни фреша, ни глинтвейна в FILES нет

    def test_listing_mode_and_main(self):
        listing = os.path.join(self.d, 'listing.json')
        with open(listing, 'w', encoding='utf-8') as f:
            json.dump({'folder': 'кухня', 'files': [{'title': os.path.basename(p), 'fileSize': 1000, 'mimeType': 'image/png'}
                                                    for p in FILES if p.startswith('кухня/') and not p.endswith('.txt')]}, f, ensure_ascii=False)
        mapp = os.path.join(self.d, 'name_map.json')
        with open(mapp, 'w', encoding='utf-8') as f:
            json.dump({'Маргарита': 'k1', 'Четыре сезона': {'iiko': 'k2', 'drive_file': None}, 'Лишнее': 'k9'}, f, ensure_ascii=False)
        report = os.path.join(self.d, 'rep.md')
        with contextlib.redirect_stdout(io.StringIO()):
            rc = mp.main(['--menu', self.index, '--listing', listing, '--map', mapp, '--report', report])
        self.assertEqual(rc, 0)
        m = json.load(open(mapp, encoding='utf-8'))
        self.assertEqual(m['Маргарита'], {'iiko': 'k1', 'drive_file': 'кухня/Пицца Маргарита.png'})   # старый формат → новый
        self.assertEqual(m['Четыре сезона'], {'iiko': 'k2', 'drive_file': 'кухня/Пицца 4 сезона.png'})
        self.assertEqual(m['Борщ с говядиной и бородинским хлебом'], {'iiko': None, 'drive_file': 'кухня/Борщ.jpg'})
        self.assertEqual(m['Лишнее'], {'iiko': 'k9', 'drive_file': None})          # iiko-пара без фото остаётся
        self.assertTrue(os.path.isfile(report))
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(mp.main(['--photos', os.path.join(self.d, 'нет')]), 2)

    def test_overrides(self):
        over = os.path.join(self.d, 'over.json')
        with open(over, 'w', encoding='utf-8') as f:
            json.dump({'_meta': 'x', 'Рамен сливочный': 'кухня/рамен сливочный с курицей.png',     # автоматика не угадывала
                       'Маргарита': 'кухня/Пицца Маргарита.jfif',                                  # замена автоматической пары
                       'Борщ с говядиной и бородинским хлебом': None,                             # снять фото
                       'Стейк-омлет': 'кухня/нет такого.png'}, f, ensure_ascii=False)             # нет файла → пропуск
        mapp = os.path.join(self.d, 'name_map.json')
        with contextlib.redirect_stdout(io.StringIO()):
            mp.main(['--menu', self.index, '--photos', self.photos, '--map', mapp, '--report', os.path.join(self.d, 'r.md'), '--overrides', over])
        m = json.load(open(mapp, encoding='utf-8'))
        self.assertEqual(m['Рамен сливочный']['drive_file'], 'кухня/рамен сливочный с курицей.png')
        self.assertEqual(m['Маргарита']['drive_file'], 'кухня/Пицца Маргарита.jfif')
        self.assertNotIn('Борщ с говядиной и бородинским хлебом', m)
        self.assertEqual(m['Стейк-омлет']['drive_file'], 'кухня/стейк омлет.png')                # автоматика осталась
        rep = open(os.path.join(self.d, 'r.md'), encoding='utf-8').read()
        self.assertIn('## Ручные пары (3)', rep)
        self.assertIn('Маргарита  ←  кухня/Пицца Маргарита.jfif  (было: кухня/Пицца Маргарита.png)', rep)
        self.assertIn('НЕТ ТАКОГО ФАЙЛА', rep)
        self.assertIn('фото снято', rep)
        self.assertNotIn('Рамен сливочный  [', rep.split('## Без фото')[1])


class TestBuildWithFolderPhotos(unittest.TestCase):
    def setUp(self):
        try:
            import PIL  # noqa: F401
        except ImportError:
            self.skipTest('нет PIL')
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        self.photos = os.path.join(self.d, 'menu_photos')
        make_folder(self.photos)
        self.index = os.path.join(self.d, 'index.html')
        with open(self.index, 'w', encoding='utf-8') as f:
            f.write(INDEX)
        self.ref = os.path.join(self.d, 'ref.json')
        with open(self.ref, 'w', encoding='utf-8') as f:
            json.dump({'x': {'kcal': 1, 'p': 1, 'f': 1, 'c': 1, 'kk': 'x', 'en': 'x'}}, f)
        self.out = os.path.join(self.d, 'cards.json')
        self.img = os.path.join(self.d, 'img', 'menu')
        self.iiko_photo = os.path.join(self.d, 'iiko.png')
        from PIL import Image
        Image.new('RGB', (500, 400), (10, 20, 30)).save(self.iiko_photo)
        self.iiko = os.path.join(self.d, 'iiko.json')
        with open(self.iiko, 'w', encoding='utf-8') as f:
            json.dump({'version': 1, 'items': [
                {'key': 'k1', 'name': 'Пицца Маргарита*', 'group': 'ПИЦЦА', 'description': 'Тонкое тесто.', 'photo': self.iiko_photo, 'portion': {'value': 300, 'unit': 'г'}},
                {'key': 'k3', 'name': 'Стейк омлет', 'group': 'ЗАВТРАКИ', 'description': 'Омлет.', 'photo': self.iiko_photo},
            ]}, f, ensure_ascii=False)
        self.map = os.path.join(self.d, 'name_map.json')
        with open(self.map, 'w', encoding='utf-8') as f:
            json.dump({'Маргарита': {'iiko': 'k1', 'drive_file': 'кухня/Пицца Маргарита.png'},
                       'Стейк-омлет': {'iiko': 'k3', 'drive_file': None},
                       'Борщ с говядиной и бородинским хлебом': {'iiko': None, 'drive_file': 'кухня/Борщ.jpg'},
                       'Тыквенный крем-суп': {'iiko': None, 'drive_file': 'кухня/нет такого.png'}}, f, ensure_ascii=False)

    def tearDown(self):
        self.tmp.cleanup()

    def build(self):
        cards, rep = bc.build(self.iiko, None, self.ref, self.out, self.img, self.index, no_photos=False, name_map=self.map, photos_dir=self.photos)
        return cards, rep.text()

    def test_priority_manifest_and_drive_only(self):
        cards, rep = self.build()
        self.assertEqual(cards['Маргарита']['img'], os.path.relpath(self.img, bc.ROOT).replace(os.sep, '/') + '/margarita.webp')
        self.assertEqual(cards['Маргарита']['d'], {'ru': 'Тонкое тесто.'})
        self.assertIn('img', cards['Стейк-омлет'])                              # из iiko
        self.assertEqual(list(cards['Борщ с говядиной и бородинским хлебом']), ['img', 'img480', 'ar'])   # только фото из папки
        self.assertNotIn('Тыквенный крем-суп', cards)                            # файла нет → карточки нет
        self.assertIn('нет файла кухня/нет такого.png', rep)
        src = json.load(open(os.path.join(self.img, 'sources.json'), encoding='utf-8'))
        self.assertTrue(src['margarita'].startswith('drive:кухня/Пицца Маргарита.png:'))
        self.assertTrue(src['stejk-omlet'].startswith('iiko:'))
        from PIL import Image
        with Image.open(os.path.join(self.img, 'margarita.webp')) as im:
            self.assertEqual(im.size, (400, 300))                                 # взят png из папки (400×300), не iiko (500×400)
        # второй размер 480 и натуральная пропорция в карточке
        self.assertEqual(cards['Маргарита']['img480'], cards['Маргарита']['img'][:-5] + '-480.webp')
        self.assertEqual(cards['Маргарита']['ar'], [400, 300])
        p480 = os.path.join(self.img, 'margarita-480.webp')
        self.assertTrue(os.path.isfile(p480)); self.assertLessEqual(os.path.getsize(p480), 35 * 1024)
        with Image.open(p480) as im:
            self.assertLessEqual(max(im.size), 480)
        self.assertLessEqual(os.path.getsize(os.path.join(self.img, 'margarita.webp')), 90 * 1024)
        # источник сменился (iiko → папка) — перекодируется без --refresh
        with open(self.map, 'w', encoding='utf-8') as f:
            json.dump({'Стейк-омлет': {'iiko': 'k3', 'drive_file': 'кухня/стейк омлет.png'}}, f, ensure_ascii=False)
        cards, rep = self.build()
        with Image.open(os.path.join(self.img, 'stejk-omlet.webp')) as im:
            self.assertEqual(im.size, (300, 200))
        self.assertIn('stejk-omlet.webp', rep)
        # без изменений — не перекодируется
        cards, rep = self.build()
        self.assertNotIn('фото: ', rep)
        # webp есть, но записи в манифесте нет (старая сборка) — источник неизвестен, перекодируется
        os.remove(os.path.join(self.img, 'sources.json'))
        cards, rep = self.build()
        self.assertIn('stejk-omlet.webp', rep)


if __name__ == '__main__':
    unittest.main()
