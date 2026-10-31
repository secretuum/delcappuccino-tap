"""Фото карточек блюд после menu/cutout_photos.py: все img/menu/*.webp из cards.json — webp в лимитах (≤90 КБ, -480 ≤35 КБ),
квадратные, ar в cards.json совпадает с размером файла, у каждого фото в sources.json отметка обработки («+cut1» —
вырезано, «+fb1» — фолбэк без вырезки). Вырезанные — с альфа-каналом и прозрачным фоном (углы холста); фолбэк непрозрачен
по определению (фон снимка доведён до белого), libwebp сохраняет его без альфы.
Запуск из корня репозитория: python3 -m unittest discover -s tests -v"""
import json, os, re, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, 'img', 'menu')
MARK = re.compile(r'\+(cut|fb)\d+ \[(\d+), (\d+)\]$')

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None


@unittest.skipIf(Image is None, 'нужен Pillow')
class TestMenuPhotos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, 'menu', 'cards.json'), encoding='utf-8') as f:
            cls.cards = {k: v for k, v in json.load(f).items() if v.get('img')}
        with open(os.path.join(IMG, 'sources.json'), encoding='utf-8') as f:
            cls.sources = json.load(f)

    @staticmethod
    def slug(card):
        return os.path.basename(card['img'])[:-5]

    def test_cards_have_photos(self):
        self.assertGreater(len(self.cards), 200)

    def test_webp_in_limits_cutouts_with_alpha(self):
        bad = []
        for key, c in self.cards.items():
            cut = '+cut' in self.sources.get(self.slug(c), '')
            for rel, limit in ((c['img'], 90 * 1024), (c['img'][:-5] + '-480.webp', 35 * 1024)):
                p = os.path.join(ROOT, rel)
                if not os.path.isfile(p):
                    bad.append(f'{key}: нет {rel}')
                    continue
                with Image.open(p) as im:
                    if im.format != 'WEBP' or (cut and 'A' not in im.getbands()):
                        bad.append(f'{key}: {rel} {im.format} {im.mode} — нужен webp' + (' с альфой' if cut else ''))
                if os.path.getsize(p) > limit:
                    bad.append(f'{key}: {rel} {os.path.getsize(p)} байт > {limit}')
        self.assertEqual(bad, [])

    def test_ar_matches_file(self):
        bad = []
        for key, c in self.cards.items():
            with Image.open(os.path.join(ROOT, c['img'])) as im:
                if list(c.get('ar') or []) != list(im.size):
                    bad.append(f'{key}: ar {c.get("ar")} ≠ файл {list(im.size)}')
        self.assertEqual(bad, [])

    def test_processing_mark_in_sources(self):
        bad = []
        for key, c in self.cards.items():
            sig = self.sources.get(self.slug(c), '')
            m = MARK.search(sig)
            if not m:
                bad.append(f'{key}: в sources.json нет отметки +cut/+fb: {sig[-40:]!r}')
            elif [int(m.group(2)), int(m.group(3))] != list(c['ar']):
                bad.append(f'{key}: размер в sources.json {m.group(2)}×{m.group(3)} ≠ ar {c["ar"]}')
        self.assertEqual(bad, [])

    def test_cutouts_transparent_square(self):
        bad = []
        for key, c in self.cards.items():
            sig = self.sources.get(self.slug(c), '')
            with Image.open(os.path.join(ROOT, c['img'])) as im:
                if im.width != im.height:
                    bad.append(f'{key}: холст не квадратный {im.size}')
                if '+cut' in sig and 'A' in im.getbands():     # без альфы — ловит test_webp_in_limits_cutouts_with_alpha
                    a = im.getchannel('A')
                    w, h = im.size
                    corners = [a.getpixel(p) for p in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))]
                    if max(corners) > 8:
                        bad.append(f'{key}: у вырезки непрозрачные углы {corners}')
        self.assertEqual(bad, [])


if __name__ == '__main__':
    unittest.main()
