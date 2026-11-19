#!/usr/bin/env python3
"""Кремовый фон у фото карточек, которые не с Kaspi (владелец 19.11.2026: «фон у белых изображений сделать как у новых»).

После PR #73 большинство карточек — фото Kaspi QR на ровном кремовом студийном фоне (+kp1), остальные — вырезки на
прозрачном (+cut, menu/cutout_photos.py) и фолбэки на белом (+fb), а часть самих Kaspi-снимков (бутылки, лимонады, чаи)
снята на белом. Рядом это смесь; этот шаг доводит фон всех до одного кремового CREAM. Нужен только Pillow (моделей нет).

  • вырезка с прозрачностью (+cut): на кремовый холст (alpha composite), квадрат, предмет по центру; длинная сторона
    предмета — доля кадра как у фото Kaspi того же раздела сайта (SECTION_FILL); сторона, срезанная краем ещё в исходнике,
    остаётся прижатой к краю (cutout_photos.frame). Новой тени не добавляем (владелец 1.11: «не стало лучше»): мягкая
    тень-эллипс из вырезки остаётся как была. Масштаб снимка не меняем.
  • непрозрачное на белом (+fb, и +kp на белом): умножение на CREAM / цвет фона с весом по светлоте пикселя
    (light_weight: самый тёмный канал от LIGHT_FROM до фона, плавно) — фон становится ровно CREAM, мягкая тень — тёплой
    тенью, еда, напиток, этикетки (насыщенное и тёмное) не меняются. Белая посуда и плёнка теплеют вместе с фоном,
    как на снимках Kaspi (там чашки и тарелки того же кремового тона). Заливку фона от краёв (маска) пробовали на
    пробном листе 19.11: на белой посуде на белом фоне она затекает в блюдце и чашку пятнами — отказались.
    Кремовые Kaspi не трогаем. Масштаб и кадр — как были.
  • KEEP — оставить как есть (риск съесть белое; решение по пробному листу), с причиной.
В img/menu/sources.json к подписи добавляется «+cr1» — build_cards.py и cutout_photos.py такие фото не перезаписывают,
пока источник тот же; повторный запуск этого скрипта их пропускает (на неизменных данных — пустой git status).
Исходник шага — сам файл img/menu/<slug>.webp (вырезка с альфой / фолбэк / Kaspi): после перекраски вырезка с
прозрачностью остаётся только в истории git (коммит до «+cr1»). Перекрасить заново: вернуть файлы и подпись без «+cr1»
(git checkout <коммит> -- img/menu/<slug>.webp img/menu/<slug>-480.webp) или прогнать cutout_photos.py --only <slug>,
потом этот скрипт с --only <slug> --force.

Запуск из корня репозитория (системный python3 с Pillow):
    python3 menu/cream_bg.py [--only slug,…] [--out папка]   # --out — проба: файлы туда, sources/cards не трогаем
"""
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import build_cards as bc  # noqa: E402

IMG_DIR = os.path.join(ROOT, 'img', 'menu')
SOURCES = os.path.join(IMG_DIR, 'sources.json')
CARDS = os.path.join(HERE, 'cards.json')
MARK = 'cr1'

# Цвет фона фото Kaspi: медиана краёв кадра по 197 фото «+kp1» (19.11.2026). У 168 кремовых — R 233…238, G 224…229,
# B 205…213 (лёгкая виньетка: угол слева сверху темнее на 5–10), самые частые (236, 228, 212) и (237, 228, 212);
# разброс мал — один общий цвет, медиана по всем кремовым. 29 Kaspi-снимков на белом (бутылки, лимонады, чаи) сюда не входят.
CREAM = (237, 228, 212)

# Доля кадра, которую занимает предмет (длинная сторона рамки build_cards.subject_box / сторона квадрата) — медиана фото
# Kaspi того же раздела сайта (19.11.2026, раздел — из index.html); разделы, где Kaspi-фото меньше трёх, — общая медиана.
# Вырезки cutout_photos.py были с полями 8 % (доля 0,84) у всех: торты целиком у Kaspi мельче, выпечка — крупнее.
SECTION_FILL = {
    'Выпечка': 0.91, 'Десерты': 0.89, 'Торты (целиком)': 0.65, 'Напитки': 0.90, 'Авторские чаи': 0.84,
    'Блюда на гриле': 0.69, 'Завтраки': 0.85, 'Классический кофе': 0.85, 'Лимонады': 0.70, 'Спешл напитки': 0.66,
    'Холодные кофейные напитки': 0.65, 'Домашние блюда': 0.93, 'Полуфабрикаты': 0.74,
}
FILL_DEFAULT = 0.79          # медиана по всем 197 фото Kaspi (p10 0,60 · p90 0,92)
# чашка с блюдцем в «Спешл напитках» (у Kaspi там высокие стаканы, 0,66) — как чаи и кофе Kaspi в чашках
SLUG_FILL = {'matcha-latte': 0.84, 'goryachij-shokolad': 0.84}

WHITE_MIN = 240              # фон кадра светлее (по каждому каналу) — «белый», перекрашиваем; ниже — уже не белый
LIGHT_FROM = 160             # перекраска непрозрачных: самый тёмный канал ниже 160 — пиксель не трогаем, выше — плавно до фона

# оставить как есть (решения по пробному листу 19.11.2026): slug → почему
KEEP = {
    'tartaletka-banofi-paj': 'белое безе на белой тарелке на белом фоне: перекраска гасит безе до тона фона, '
                             'маска от краёв затекает в тарелку — оставлено на белом',
}


def border_color(im):
    """медиана цвета краёв кадра (как в build_cards.subject_box)"""
    k = 8
    sm = im.convert('RGB').resize((max(1, im.width // k), max(1, im.height // k)))
    w, h = sm.size
    border = [sm.getpixel((x, y)) for x in range(w) for y in (0, h - 1)] + [sm.getpixel((x, y)) for y in range(h) for x in (0, w - 1)]
    return tuple(sorted(c[i] for c in border)[len(border) // 2] for i in range(3))


def solid_box(alpha, thr=128):
    """рамка (x0, x1, y0, y1) непрозрачного предмета: альфа > thr (тень-эллипс вырезки — альфа ≤ 46 — не входит)"""
    b = alpha.point(lambda v: 255 if v > thr else 0).getbbox()
    return None if b is None else (b[0], b[2], b[1], b[3])


def touches(alpha, thr=128, share=0.02):
    """стороны холста, к которым предмет прижат (срезан ещё в исходнике): больше 2 % кромки непрозрачно"""
    w, h = alpha.size
    m = alpha.point(lambda v: 1 if v > thr else 0)
    out = set()
    for side, box in (('T', (0, 0, w, 1)), ('B', (0, h - 1, w, h)), ('L', (0, 0, 1, h)), ('R', (w - 1, 0, w, h))):
        e = m.crop(box)
        if sum(e.getdata()) > share * max(e.size):
            out.add(side)
    return out


def on_cream(rgba, fill=FILL_DEFAULT, cream=CREAM):
    """вырезка RGBA → квадрат RGB того же размера на кремовом фоне; длинная сторона предмета — доля fill стороны"""
    from PIL import Image
    import cutout_photos as cp
    rgba = rgba.convert('RGBA')
    W, H = rgba.size
    a = rgba.getchannel('A')
    box = solid_box(a)
    if box is None:
        raise ValueError('пустая вырезка')
    cut = touches(a)
    sx, sy, side = cp.frame(box, W, H, cut, margin=(1 - fill) / 2)
    part = rgba.crop((sx, sy, sx + side, sy + side))            # за краем холста — прозрачно
    if side != W:
        part = part.resize((W, W), Image.LANCZOS)
    out = Image.new('RGBA', (W, W), cream + (255,))
    out.alpha_composite(part)
    return out.convert('RGB')


def light_weight(rgb, bg):
    """вес перекраски пикселя (L, 0…255): по самому тёмному каналу — белое и светлое нейтральное (фон, тень, белая
    посуда, плёнка) → 255, насыщенное и тёмное (еда, этикетки, напиток) → 0; плавно между LIGHT_FROM и цветом фона"""
    from PIL import ImageChops
    r, g, b = rgb.split()
    lo, hi = LIGHT_FROM, min(bg) - 2
    def ramp(v):
        x = min(max((v - lo) / (hi - lo), 0.0), 1.0)
        return round(255 * x * x * (3 - 2 * x))                 # smoothstep: без ступеньки на тенях
    return ImageChops.darker(ImageChops.darker(r, g), b).point(ramp)


def recolor_white(rgb, cream=CREAM):
    """непрозрачное фото на белом → (RGB с кремовым фоном, доля кадра, ставшая кремом целиком); фон не белый — (None, 0)"""
    from PIL import Image
    rgb = rgb.convert('RGB')
    bg = border_color(rgb)
    if min(bg) < WHITE_MIN:
        return None, 0.0
    t = light_weight(rgb, bg)
    share = sum(t.histogram()[230:]) / (t.width * t.height)
    gains = [c / max(b, 1) for c, b in zip(cream, bg)]
    tinted = Image.merge('RGB', [ch.point(lambda v, g=g: min(255, round(v * g))) for ch, g in zip(rgb.split(), gains)])
    return Image.composite(tinted, rgb, t), share


def sections(index_html):
    """card key → раздел сайта (для SECTION_FILL)"""
    import match_names as mn
    return {key: sec for key, sec, _ in mn.site_keys(index_html)}


def main(argv=None):
    from PIL import Image
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--only', default='', help='slug,… — только эти')
    ap.add_argument('--force', action='store_true', help='и уже с «+cr» (только вместе с --only)')
    ap.add_argument('--out', default='', help='проба: webp в эту папку, sources.json и cards.json не трогать')
    ap.add_argument('--menu', default=os.path.join(ROOT, 'index.html'))
    a = ap.parse_args(argv)
    only = {x for x in a.only.split(',') if x}
    with open(SOURCES, encoding='utf-8') as f:
        sources = json.load(f)
    with open(CARDS, encoding='utf-8') as f:
        cards = json.load(f)
    secs = sections(a.menu)
    used = {}
    for key, c in cards.items():
        m = re.match(r'img/menu/(.+)\.webp$', c.get('img') or '')
        if m:
            used.setdefault(m.group(1), key)
    out_dir = a.out or IMG_DIR
    os.makedirs(out_dir, exist_ok=True)
    done, kept, sizes = {}, {}, {}
    for sl in sorted(sources):
        sig = sources[sl]
        if sl not in used or (only and sl not in only):
            continue
        if '+' + MARK in sig and not (a.force and only):
            continue
        if sl in KEEP:
            kept[sl] = KEEP[sl]
            continue
        src = os.path.join(IMG_DIR, f'{sl}.webp')
        with Image.open(src) as im:
            im.load()
        if '+cut' in sig and 'A' in im.getbands():
            fill = SLUG_FILL.get(sl) or SECTION_FILL.get(secs.get(used[sl]), FILL_DEFAULT)
            img, how = on_cream(im, fill), f'вырезка → крем, доля {fill:.2f}'
        else:
            img, share = recolor_white(im)
            if img is None:
                continue                                         # фон не белый (Kaspi на креме) — как есть
            how = f'белый фон → крем ({share:.0%} кадра)'
        before = os.path.getsize(src) + os.path.getsize(src[:-5] + '-480.webp')
        size, ar = bc.write_square_webp(img, os.path.join(out_dir, f'{sl}.webp'))
        after = size + os.path.getsize(os.path.join(out_dir, f'{sl}-480.webp'))
        sizes[sl] = (before, after)
        done[sl] = ar
        print(f'{sl:48} {how}; {before // 1024} → {after // 1024} КБ (960+480)', flush=True)
        if not a.out:
            sources[sl] = re.sub(r'(?:\+cr\d+)* \[.*\]$', '', sig) + f'+{MARK} {json.dumps(ar)}'   # --force: без «+cr1+cr1»
    for sl, why in sorted(kept.items()):
        print(f'{sl:48} оставлено как есть: {why}')
    if not a.out and done:
        for key, c in cards.items():
            m = re.match(r'img/menu/(.+)\.webp$', c.get('img') or '')
            if m and m.group(1) in done:
                c['ar'] = done[m.group(1)]
        with open(SOURCES, 'w', encoding='utf-8') as f:
            json.dump(dict(sorted(sources.items())), f, ensure_ascii=False, indent=1)   # как build_cards.py
            f.write('\n')
        with open(CARDS, 'w', encoding='utf-8') as f:
            json.dump(cards, f, ensure_ascii=False, indent=2)                           # как build_cards.py
            f.write('\n')
    b, n = sum(v[0] for v in sizes.values()), sum(v[1] for v in sizes.values())
    print(f'перекрашено {len(done)}, оставлено {len(kept)}; вес 960+480: {b / 1048576:.2f} → {n / 1048576:.2f} МБ')
    return 0


if __name__ == '__main__':
    sys.exit(main())
