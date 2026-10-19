#!/usr/bin/env python3
"""tools/flame_frame.py — огонёк-рамка акции «Курица гриль» (как эмодзи 🔥): SVG с плавными кривыми + clip-path видео.

Запуск из корня:  python3 tools/flame_frame.py            — печатает блоки для index.html:
  1) <svg class="grill-fire">  — внешнее пламя (красный → оранжевый) и внутренний язык (оранжевый → жёлтый);
  2) CSS .grill-win            — окно: положение бокса в % рамки, clip-path: polygon(...) в % бокса (точки — выборка
                                  той же кривой, что у внутреннего языка, чуть меньше), z-index:1 — окно лежит НАД svg;
                                  внутри окна: видео (object-fit:cover), виньетка и бегущая строка — всё режется контуром.
  --preview файл.png            — отрисовать постер в рамке (Pillow) для проверки глазами.
В stderr: доля бокса видео, которую оставляет окно (tests/test_perf.py требует ≥ 50 %).

Геометрия в единицах viewBox W×H. Бокс видео — габарит окна (object-fit:cover
показывает центр ролика); под окном остаётся полоса тела огня для бегущей строки (TICKER_Y0..H).
"""
import sys

W, H = 910, 700
# Внешнее пламя: M + кубические кривые (x,y) — тело-капля с языком вверх и боковыми язычками.
OUTER = [
    ('M', (455, 700)),
    ('C', (650, 700), (840, 600), (840, 430)),       # правое брюшко
    ('C', (840, 320), (760, 260), (735, 150)),       # правый бок вверх, правый язычок
    ('C', (720, 215), (690, 250), (660, 240)),       # впадина после правого язычка
    ('C', (640, 170), (580, 70), (500, 0)),          # главный язык (остриё)
    ('C', (495, 90), (440, 150), (395, 165)),        # спуск слева от острия
    ('C', (360, 130), (330, 80), (300, 55)),         # левый язычок
    ('C', (290, 150), (190, 240), (130, 330)),       # левый бок вниз
    ('C', (85, 380), (70, 400), (70, 430)),          # плавный переход в брюшко
    ('C', (70, 600), (260, 700), (455, 700)),        # левое брюшко (зеркало правого)
    ('Z',),
]
PIVOT = (455, 700)                                   # масштабируем вокруг низа пламени
INNER = (0.78, 0.72, 650)                            # внутренний язык: kx, ky, y низа — уменьшенная копия внешнего
WINDOW = (0.70, 0.60, 638)                           # окно видео: ещё меньше и шире, низ выше — ниже полоса тикера
TICKER_Y0 = 646


def scaled(path, spec):
    kx, ky, bottom = spec
    px, py = PIVOT
    out = []
    for seg in path:
        out.append((seg[0],) + tuple((px + (x - px) * kx, bottom + (y - py) * ky) for x, y in seg[1:]))
    return out


def bbox(pts):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


def d_attr(path):
    parts = []
    for seg in path:
        if seg[0] == 'Z':
            parts.append('Z')
        else:
            parts.append(seg[0] + ' '.join(f'{x:.0f} {y:.0f}' for x, y in seg[1:]))
    return ' '.join(parts)


def flatten(path, n=12):
    """Точки вдоль пути (выборка кубических кривых), для clip-path polygon и площади."""
    pts, cur = [], None
    for seg in path:
        if seg[0] == 'M':
            cur = seg[1]; pts.append(cur)
        elif seg[0] == 'C':
            p0, p1, p2, p3 = cur, seg[1], seg[2], seg[3]
            for i in range(1, n + 1):
                t = i / n
                x = (1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t ** 2 * p2[0] + t ** 3 * p3[0]
                y = (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t ** 2 * p2[1] + t ** 3 * p3[1]
                pts.append((x, y))
            cur = p3
    return pts


def area(p):
    return abs(sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1] for i in range(len(p)))) / 2


def build():
    inner = scaled(OUTER, INNER)
    window = scaled(OUTER, WINDOW)
    bx, by, bw, bh = [round(v) for v in bbox(flatten(window))]   # бокс видео = габарит окна; object-fit:cover
    poly = [(min(max((x - bx) / bw, 0), 1) * 100, min(max((y - by) / bh, 0), 1) * 100) for x, y in flatten(window)]
    visible = area(poly) / (100 * 100)
    svg = (f'<svg class="grill-fire" viewBox="0 0 {W} {H}" preserveAspectRatio="none" aria-hidden="true" focusable="false">'
           '<defs>'
           '<radialGradient id="grill-g1" cx="50%" cy="92%" r="80%"><stop offset="0" stop-color="#FF7A00"/><stop offset=".55" stop-color="#F23A10"/><stop offset="1" stop-color="#C2140F"/></radialGradient>'
           '<radialGradient id="grill-g2" cx="50%" cy="95%" r="75%"><stop offset="0" stop-color="#FFE500"/><stop offset=".6" stop-color="#FFB300"/><stop offset="1" stop-color="#FF6A00"/></radialGradient>'
           '</defs>'
           f'<path class="grill-fire-outer" fill="url(#grill-g1)" d="{d_attr(OUTER)}"/>'
           f'<path class="grill-fire-inner" fill="url(#grill-g2)" d="{d_attr(inner)}"/>'
           '</svg>')
    css = (f'.grill-win{{position:absolute;left:{bx / W * 100:.2f}%;top:{by / H * 100:.2f}%;width:{bw / W * 100:.2f}%;height:{bh / H * 100:.2f}%;'
           'overflow:hidden;z-index:1;clip-path:polygon(' +
           ','.join(f'{x:.1f}% {y:.1f}%' for x, y in poly) + ')}')
    return svg, css, poly, visible, inner, window


def preview(out, poster):
    from PIL import Image, ImageDraw
    svg, css, poly, visible, inner, window = build()
    S = 1
    im = Image.new('RGB', (W, H), (254, 241, 232))
    dr = ImageDraw.Draw(im)
    dr.polygon(flatten(OUTER), fill=(226, 48, 20))
    dr.polygon(flatten(inner), fill=(255, 190, 0))
    bx, by, bw, bh = [round(v) for v in bbox(flatten(window))]
    v = Image.open(poster).convert('RGB')
    k = max(bw / v.width, bh / v.height)
    v = v.resize((round(v.width * k), round(v.height * k)))
    v = v.crop(((v.width - bw) // 2, (v.height - bh) // 2, (v.width - bw) // 2 + bw, (v.height - bh) // 2 + bh))
    mask = Image.new('L', (bw, bh), 0)
    ImageDraw.Draw(mask).polygon([(x / 100 * bw, y / 100 * bh) for x, y in poly], fill=255)
    im.paste(v, (bx, by), mask)
    dr.rectangle((140, TICKER_Y0 + 8, 770, H - 8), outline=(255, 229, 0))
    im.save(out)


if __name__ == '__main__':
    svg, css, poly, visible, *_ = build()
    print(f'окно оставляет {visible:.1%} бокса видео', file=sys.stderr)
    if '--preview' in sys.argv:
        preview(sys.argv[sys.argv.index('--preview') + 1], sys.argv[sys.argv.index('--preview') + 2])
    else:
        print(svg)
        print(css)
