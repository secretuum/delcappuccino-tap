"""Фото карточек блюд после menu/cutout_photos.py: все img/menu/*.webp из cards.json — webp в разумных пределах
(q85 без потолка с 1.11.2026: ≤250 КБ, -480 ≤100 КБ — защита от случайного PNG-веса),
квадратные, ar в cards.json совпадает с размером файла, у каждого фото в sources.json отметка обработки («+cut1» —
вырезано, «+fb1» — фолбэк без вырезки, «+kp1» — фото Kaspi QR как есть: квадрат + webp, menu/build_cards.py, 19.11.2026;
«+cr1» последней — фон перекрашен в кремовый как у Kaspi, menu/cream_bg.py, 19.11.2026). Вырезанные без «+cr» — с альфа-каналом
и прозрачным фоном (углы холста); фолбэк непрозрачен по определению (фон снимка доведён до белого), libwebp сохраняет его
без альфы; «+cr» — непрозрачные, углы — цвета cream_bg.CREAM.
Запуск из корня репозитория: python3 -m unittest discover -s tests -v"""
import json, os, re, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, 'img', 'menu')
MARK = re.compile(r'\+(cut|fb|kp|cr)\d+ \[(\d+), (\d+)\]$')

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
            sig = self.sources.get(self.slug(c), '')
            cut = '+cut' in sig and '+cr' not in sig
            for rel, limit in ((c['img'], 250 * 1024), (c['img'][:-5] + '-480.webp', 100 * 1024)):
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
                bad.append(f'{key}: в sources.json нет отметки +cut/+fb/+kp/+cr: {sig[-40:]!r}')
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
                if '+cut' in sig and '+cr' not in sig and 'A' in im.getbands():   # без альфы — ловит test_webp_in_limits_cutouts_with_alpha
                    a = im.getchannel('A')
                    w, h = im.size
                    corners = [a.getpixel(p) for p in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))]
                    if max(corners) > 8:
                        bad.append(f'{key}: у вырезки непрозрачные углы {corners}')
        self.assertEqual(bad, [])


class TestFrame(unittest.TestCase):
    """рамка вокруг блюда (cutout_photos.frame): обрезанная в исходнике сторона — к краю холста, без поля"""
    @classmethod
    def setUpClass(cls):
        import sys
        sys.path.insert(0, os.path.join(ROOT, 'menu'))
        import cutout_photos
        cls.frame = staticmethod(cutout_photos.frame)

    def test_centered_with_margins(self):
        x, y, side = self.frame((100, 300, 50, 250), 400, 300, set(), margin=0.1)
        self.assertEqual(side, 250)                              # 200 / (1 − 2·0,1)
        self.assertEqual((x, y), (75, 25))                       # по центру

    def test_cut_bottom_pressed_to_canvas_edge(self):
        # пицца 603×450, низ срезан краем кадра: низ холста = низ кадра, поля только сверху и по бокам
        x, y, side = self.frame((110, 490, 60, 450), 603, 450, {'B'}, margin=0.08)
        self.assertEqual(y + side, 450)
        self.assertEqual(x, round((110 + 490) / 2 - side / 2))
        self.assertEqual(side, round(max(380 / 0.84, 390 / 0.92)))

    def test_cut_both_sides_not_wider_than_source(self):
        x, y, side = self.frame((0, 1024, 200, 1400), 1024, 1536, {'L', 'R'}, margin=0.08)
        self.assertLessEqual(side, 1024)
        self.assertEqual(x, 0)


@unittest.skipIf(Image is None, 'нужен Pillow')
class TestKaspiSquare(unittest.TestCase):
    """фото Kaspi «как есть» (build_cards.kaspi_square): квадрат во всю высоту кадра по центру предмета; предмет шире
    квадрата — квадрат шире, недостающее по высоте — продолжением фона"""
    @classmethod
    def setUpClass(cls):
        import sys
        sys.path.insert(0, os.path.join(ROOT, 'menu'))
        import build_cards
        cls.sq = staticmethod(build_cards.kaspi_square)

    def frame(self, w, h, box):
        from PIL import ImageDraw
        im = Image.new('RGB', (w, h), (240, 225, 205))
        ImageDraw.Draw(im).rectangle(box, fill=(150, 40, 30))
        return im

    def test_square_full_height_centered_on_subject(self):
        out = self.sq(self.frame(1600, 900, (1000, 300, 1300, 600)))     # предмет правее центра
        self.assertEqual(out.size, (900, 900))
        self.assertEqual(out.getpixel((450, 450)), (150, 40, 30))        # предмет в середине квадрата

    def test_wide_subject_not_cut(self):
        out = self.sq(self.frame(1600, 900, (200, 350, 1400, 550)))      # предмет 1200 px шире высоты 900
        self.assertGreaterEqual(out.width, 1200)
        self.assertEqual(out.width, out.height)
        self.assertEqual(out.getpixel((5, 5)), (240, 225, 205))          # поле сверху — тот же фон
        self.assertEqual(out.getpixel((out.width // 2, out.height // 2)), (150, 40, 30))

    def test_wide_subject_high_in_frame_centered_vertically(self):
        out = self.sq(self.frame(1600, 900, (200, 50, 1400, 250)))       # широкий предмет у верхнего края кадра
        self.assertEqual(out.size, (1296, 1296))
        # всё поле (396 px) — сверху, предмет сдвинут к середине: 446…646 (без сдвига было бы 248…448)
        self.assertEqual(out.getpixel((648, 600)), (150, 40, 30))
        self.assertEqual(out.getpixel((648, 420)), (240, 225, 205))

    def test_portrait_frame(self):
        out = self.sq(self.frame(900, 1600, (300, 1100, 600, 1400)))     # вертикальный кадр, предмет внизу
        self.assertEqual(out.size, (900, 900))
        self.assertEqual(out.getpixel((450, 450)), (150, 40, 30))

    def test_plain_frame_without_subject(self):
        out = self.sq(Image.new('RGB', (1600, 900), (240, 225, 205)))    # рамки нет — центральный квадрат
        self.assertEqual(out.size, (900, 900))


@unittest.skipIf(Image is None, 'нужен Pillow')
class TestCreamBg(unittest.TestCase):
    """кремовый фон (menu/cream_bg.py, 19.11.2026): у перекрашенных («+cr») углы — CREAM, без альфы; на синтетике — фон
    становится CREAM, а предмет (насыщенное, тёмное) не меняется"""
    @classmethod
    def setUpClass(cls):
        import sys
        sys.path.insert(0, os.path.join(ROOT, 'menu'))
        import cream_bg
        cls.cb = cream_bg
        with open(os.path.join(ROOT, 'menu', 'cards.json'), encoding='utf-8') as f:
            cls.cards = {k: v for k, v in json.load(f).items() if v.get('img')}
        with open(os.path.join(IMG, 'sources.json'), encoding='utf-8') as f:
            cls.sources = json.load(f)

    def near(self, c, ref, tol):
        return max(abs(a - b) for a, b in zip(c, ref)) <= tol

    def test_recolored_files_cream_corners(self):
        bad, n = [], 0
        for key, c in self.cards.items():
            sl = os.path.basename(c['img'])[:-5]
            if '+cr' not in self.sources.get(sl, ''):
                continue
            n += 1
            for rel in (c['img'], c['img'][:-5] + '-480.webp'):
                with Image.open(os.path.join(ROOT, rel)) as im:
                    if 'A' in im.getbands():
                        bad.append(f'{rel}: осталась альфа')
                    im = im.convert('RGB')
                    w, h = im.size
                    if not self.near(self.cb.border_color(im), self.cb.CREAM, 3):   # медиана краёв; webp q85 — допуск
                        bad.append(f'{rel}: фон по краям {self.cb.border_color(im)} ≠ {self.cb.CREAM}')
                    # углы: хотя бы три из четырёх (в четвёртом бывает край блюдца или тень, как у latte)
                    off = [p for p in ((1, 1), (w - 2, 1), (1, h - 2), (w - 2, h - 2)) if not self.near(im.getpixel(p), self.cb.CREAM, 6)]
                    if len(off) > 1:
                        bad.append(f'{rel}: углы {off} не {self.cb.CREAM}')
        self.assertGreater(n, 40)
        self.assertEqual(bad, [])

    def test_no_white_or_transparent_left(self):
        """все фото карточек — на кремовом: белый фон или прозрачность — только у оставленных (cream_bg.KEEP)"""
        bad = []
        for key, c in self.cards.items():
            sl = os.path.basename(c['img'])[:-5]
            if sl in self.cb.KEEP:
                continue
            with Image.open(os.path.join(ROOT, c['img'])) as im:
                if 'A' in im.getbands() and im.getchannel('A').getextrema()[0] < 250:
                    bad.append(f'{sl}: прозрачный фон')
                    continue
                if min(self.cb.border_color(im.convert('RGB'))) >= self.cb.WHITE_MIN:
                    bad.append(f'{sl}: белый фон')
        self.assertEqual(bad, [])

    def test_cutout_on_cream_subject_untouched(self):
        from PIL import ImageDraw
        im = Image.new('RGBA', (400, 400), (0, 0, 0, 0))
        ImageDraw.Draw(im).rectangle((120, 80, 280, 320), fill=(150, 40, 30, 255))      # предмет 160×240, доля 0,6
        out = self.cb.on_cream(im, fill=0.6)
        self.assertEqual(out.mode, 'RGB')
        self.assertEqual(out.size, (400, 400))
        for p in ((0, 0), (399, 0), (0, 399), (399, 399)):
            self.assertEqual(out.getpixel(p), self.cb.CREAM)
        self.assertEqual(out.getpixel((200, 200)), (150, 40, 30))                     # предмет не тронут
        self.assertEqual(out.getpixel((200, 84)), (150, 40, 30))                      # и не сдвинут
        self.assertEqual(out.getpixel((200, 76)), self.cb.CREAM)

    def test_cutout_scaled_to_fill(self):
        from PIL import ImageDraw
        im = Image.new('RGBA', (400, 400), (0, 0, 0, 0))
        ImageDraw.Draw(im).rectangle((100, 100, 299, 299), fill=(20, 90, 40, 255))       # доля 0,5
        out = self.cb.on_cream(im, fill=0.8)
        box = self.cb.solid_box(Image.eval(out.convert('L'), lambda v: 255 if v < 150 else 0), thr=128)
        self.assertAlmostEqual((box[1] - box[0]) / 400, 0.8, delta=0.02)
        self.assertAlmostEqual((box[0] + box[1]) / 2, 200, delta=2)                    # по центру

    def test_white_bg_recolored_subject_untouched(self):
        from PIL import ImageDraw
        im = Image.new('RGB', (300, 300), (255, 255, 255))
        d = ImageDraw.Draw(im)
        d.ellipse((40, 40, 260, 260), fill=(250, 250, 250), outline=(225, 225, 225))   # белая тарелка
        d.rectangle((110, 110, 190, 190), fill=(150, 40, 30))                          # еда
        d.rectangle((120, 270, 180, 280), fill=(200, 200, 200))                        # мягкая тень
        out, share = self.cb.recolor_white(im)
        for p in ((0, 0), (299, 0), (0, 299), (299, 299)):
            self.assertEqual(out.getpixel(p), self.cb.CREAM)
        self.assertEqual(out.getpixel((150, 150)), (150, 40, 30))                     # еда не тронута
        plate = out.getpixel((70, 150))                                              # белая посуда теплеет, как у Kaspi,
        self.assertTrue(self.near(plate, [250 * c / 255 for c in self.cb.CREAM], 2), plate)   # но тон к фону — как был
        r, g, b = out.getpixel((150, 275))
        self.assertTrue(r > g > b and r < 237, (r, g, b))                             # тень — тёплая, темнее фона
        self.assertGreater(share, 0.3)

    def test_cream_bg_left_alone(self):
        im = Image.new('RGB', (200, 200), self.cb.CREAM)
        out, share = self.cb.recolor_white(im)
        self.assertIsNone(out)                                                       # уже кремовый — не трогаем


if __name__ == '__main__':
    unittest.main()
