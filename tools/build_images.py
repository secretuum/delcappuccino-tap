#!/usr/bin/env python3
"""Сборка картинок главной страницы: webp нужных размеров из исходников в assets/.

Запуск из корня репозитория:  python3 tools/build_images.py [--src ПАПКА]

Таблица SPEC ниже — единственный источник правды о том, какие размеры нужны разметке index.html
(srcset/sizes там должны ей соответствовать). Размеры подобраны под реальное отображение:
телефон ≤680px (@2x/@3x) и десктоп (сетка 1160px). Исходники фото без внешних ссылок в репозитории
не хранятся (см. git-историю до 19.10.2026: `git show 0ac6c63:assets/photo_06.jpg > assets/photo_06.jpg`);
чтобы пересобрать, положи исходники в assets/ (или укажи --src) и запусти скрипт.

Также: photo_01.jpg пережимается ≤150 КБ (на него ссылаются og:image/twitter:image — мессенджеры webp не
принимают), из logo-mono.png делаются иконки PWA icon-192.png / icon-512.png / apple-touch-icon.png.
Только stdlib + Pillow.
"""
import argparse, os, sys
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, 'assets')
QUALITY = 80

# (исходник, имя результата, ширины, обрезка w:h или None)
SPEC = [
    ('logo-lockup.png', 'logo-lockup', [128, 256], None),        # шапка: высота 42px → ширина ~85px (@1x/@2x/@3x)
    ('logo-mono.png',   'logo-mono',   [192], None),             # шапка-моб 34px, контакты 64px, подвал 24px (до @3x)
    ('4.png',           'halal',       [104, 156], None),        # значок Halal 52×52 (@2x/@3x), альфа сохраняется
    ('photo_01.jpg',    'photo_01',    [480, 800, 1200, 1600], None),  # герой: 100vw на ≤900px, ~520px на десктопе
    ('photo_10.jpg',    'photo_10',    [480, 900, 1600], None),        # «о нас»: 100vw на ≤900px, ~440px на десктопе
    ('photo_06.jpg',    'photo_06',    [320, 640], (3, 4)),            # витрина 4 фото 3:4: 265px десктоп, 58vw телефон
    ('photo_07.jpg',    'photo_07',    [320, 640], (3, 4)),
    ('photo_08.jpg',    'photo_08',    [320, 640], (3, 4)),
    ('photo_09.jpg',    'photo_09',    [320, 640], (3, 4)),
]
OG_SOURCE, OG_MAX_KB, OG_WIDTH = 'photo_01.jpg', 150, 1200
ICON_SOURCE = 'logo-mono.png'
ICONS = [('icon-192.png', 192), ('icon-512.png', 512), ('apple-touch-icon.png', 180)]


def crop_ratio(im, ratio):
    """Центральная обрезка под w:h — то же, что object-fit:cover с object-position по центру."""
    rw, rh = ratio
    w, h = im.size
    if w * rh > h * rw:            # слишком широкая → режем бока
        nw = h * rw // rh
        x = (w - nw) // 2
        return im.crop((x, 0, x + nw, h))
    nh = w * rh // rw              # слишком высокая → режем верх/низ
    y = (h - nh) // 2
    return im.crop((0, y, w, y + nh))


def build(src_dir):
    made = []
    for src, name, widths, ratio in SPEC:
        path = os.path.join(src_dir, src)
        if not os.path.isfile(path):
            print('нет исходника, пропуск:', src, file=sys.stderr)
            continue
        im = Image.open(path)
        if ratio:
            im = crop_ratio(im, ratio)
        has_alpha = im.mode in ('RGBA', 'LA') or 'transparency' in im.info
        im = im.convert('RGBA' if has_alpha else 'RGB')
        for w in widths:
            if w > im.width:
                print(f'{src}: ширина {w} больше исходника {im.width}, пропуск', file=sys.stderr)
                continue
            h = round(im.height * w / im.width)
            out = os.path.join(ASSETS, f'{name}-{w}.webp')
            im.resize((w, h), Image.LANCZOS).save(out, 'WEBP', quality=QUALITY, method=6)
            made.append((out, w, h))

    # og:image — jpg ≤ OG_MAX_KB
    og = os.path.join(src_dir, OG_SOURCE)
    if os.path.isfile(og):
        im = Image.open(og).convert('RGB')
        if im.width > OG_WIDTH:
            im = im.resize((OG_WIDTH, round(im.height * OG_WIDTH / im.width)), Image.LANCZOS)
        out = os.path.join(ASSETS, OG_SOURCE)
        for q in range(82, 50, -4):
            im.save(out, 'JPEG', quality=q, optimize=True, progressive=True)
            if os.path.getsize(out) <= OG_MAX_KB * 1024:
                break
        made.append((out, im.width, im.height))

    # иконки PWA
    ic = os.path.join(src_dir, ICON_SOURCE)
    if os.path.isfile(ic):
        im = Image.open(ic).convert('RGB')
        side = max(im.size)
        sq = Image.new('RGB', (side, side), im.getpixel((0, 0)))
        sq.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
        for fname, s in ICONS:
            out = os.path.join(ASSETS, fname)
            sq.resize((s, s), Image.LANCZOS).save(out, 'PNG', optimize=True)
            made.append((out, s, s))

    for out, w, h in made:
        print(f'{os.path.relpath(out, ROOT):40} {w}×{h}  {os.path.getsize(out) / 1024:6.1f} КБ')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--src', default=ASSETS, help='папка с исходниками (по умолчанию assets/)')
    build(ap.parse_args().src)
