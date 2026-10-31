#!/usr/bin/env python3
"""Фото карточек блюд: вырезка фона, единая цветокоррекция и центровка (правка владельца 1.11.2026: «разная цветокоррекция —
выровняй; лаконичная карточка с прозрачным фоном; блюдо или напиток — по центру карточки»).

Разовый инструмент обработки фото, тестами не гоняется. Нужны onnxruntime, numpy, Pillow и модель вырезки rembg
isnet-general-use (ONNX, https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx) — всё в
отдельном venv вне репозитория; модель запускается напрямую через onnxruntime с той же подготовкой, что в rembg (сам пакет
rembg тянет ещё ~200 МБ зависимостей, для вырезки они не нужны). Например:
    python3 -m venv /tmp/…/venv-img && /tmp/…/venv-img/bin/pip install onnxruntime numpy pillow
Запуск из корня репозитория:
    /tmp/…/venv-img/bin/python menu/cutout_photos.py --photos /путь/к/menu/menu_photos --model /путь/isnet-general-use.onnx
        [--only slug,…] [--fallback slug,…] [--cut slug,…]
        [--sheets папка]       # листы «до / после» для проверки глазами (до | после на белом | после на тёмном)

Что делает для каждого фото из img/menu/sources.json (источник — файл из папки Диска или ссылка iiko, как в build_cards.py):
  1. Вырезка: модель rembg isnet-general-use (сегментация, а не порог по белому — белые тарелки и чашки остаются);
     края — мягкая маска модели, подтянутая по контрасту и размытая на 1 px, без белой каймы (цвет кромки — от предмета).
     Белые тарелки на белом фоне модель иногда «съедает» — это ловит recover_plates (фон — область от краёв кадра по
     плавным переходам цвета; кромка тарелки её обрывает) — и такое фото идёт в фолбэк, а не обрезается без тарелки.
     Признак грубый: окончательно решают листы «до / после» (--fallback — в фолбэк, --cut — вырезать вопреки признаку).
  2. Цвет по единому эталону: баланс белого — по нейтральным участкам (светлые малонасыщенные пиксели предмета: тарелка,
     чашка; нет таких — фон до вырезки), сдвиг не больше ±6 %; светлое — мягкие уровни (99-й перцентиль предмета на 35 %
     к 0,98, чёрная точка не трогается); тёмные снимки (медиана яркости ниже 0,56) — гамма на 30 % к ней, светлые не
     гасятся; насыщенность — на четверть к общей средней, в пределах 0,94–1,03. Цель — выровнять, а не перекрасить.
  3. Центровка: рамка по маске → квадратный холст, предмет по центру, поля 8 % по большей стороне (все предметы одного
     визуального масштаба, высокие стаканы — по высоте, без обрезки); под предметом — едва заметная тень-эллипс.
  4. Фолбэк: модель «съела» белую тарелку (PLATE_EATEN) или фото в списке --fallback (брак по листам «до / после») —
     исходник без вырезки, тот же цвет, предмет вместе с тарелкой — по центру квадрата, поля цветом фона; светлый студийный
     фон с оттенком доводится до белого (сдвиг ≤ 15 %), чтобы на белой карточке не было видно квадрата.
Результат пишется прямо в img/menu/<slug>.webp и <slug>-480.webp (webp с альфой, ≤ 90 и ≤ 35 КБ), в sources.json к подписи
источника добавляется «+cut1» или «+fb1» — build_cards.py оставляет такие файлы как есть, пока источник тот же (нужен
только PIL, rembg не нужен). ar в menu/cards.json — под новый квадратный холст.
"""
import argparse, io, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import build_cards as bc  # noqa: E402  fetch_bytes, encode_webp, SIZES

IMG_DIR = os.path.join(ROOT, 'img', 'menu')
SOURCES = os.path.join(IMG_DIR, 'sources.json')
CARDS = os.path.join(HERE, 'cards.json')
CUT_VER, FB_VER = 'cut1', 'fb1'
WORK_PX = 1600          # рабочий размер для вырезки и цвета
CANVAS = 960            # квадратный холст итогового фото (и 480 для телефона)
MARGIN = 0.08           # поля по большей стороне предмета
WB_LIMIT = 0.06
TARGET_MED = 0.56       # общая медиана яркости предмета (эталон «света»)
TARGET_SAT = 0.30       # общая средняя насыщенность предмета
PLATE_EATEN = 0.12      # «не фона» сверх маски модели больше 12 % — модель съела тарелку → фолбэк


def base_sign(val):
    """«drive:кухня/X.jpg:446775:v3+cut1 [1920, 1280]» → «drive:кухня/X.jpg:446775:v3»"""
    sign = val.split(' [', 1)[0]
    return re.sub(r'\+(?:cut|fb)\d+$', '', sign)


def source_of(sign, photos):
    kind, rest = sign.split(':', 1)
    rest = rest.rsplit(':', 1)[0]                       # без «:v3»
    if kind == 'drive':
        return os.path.join(photos, rest.rsplit(':', 1)[0])
    return rest                                        # iiko: ссылка


def load(src):
    from PIL import Image, ImageOps
    im = Image.open(io.BytesIO(bc.fetch_bytes(src)))
    im = ImageOps.exif_transpose(im)
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA')
        bg = Image.new('RGBA', im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        im = bg
    im = im.convert('RGB')
    im.thumbnail((WORK_PX, WORK_PX))
    return im


def correct(rgb, mask):
    """rgb float32 [h,w,3] 0..1, mask float32 [h,w] 0..1 → скорректированный rgb"""
    import numpy as np
    mx, mn = rgb.max(2), rgb.min(2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    subj = mask > 0.5
    # баланс белого: нейтральные светлые участки предмета (тарелка, чашка), иначе фон
    neutral = subj & (sat < 0.10) & (mx > 0.65)
    if neutral.sum() < 0.01 * max(subj.sum(), 1):
        neutral = (~subj) & (sat < 0.08) & (mx > 0.70)
    if neutral.sum() > 500:
        mean = rgb[neutral].mean(0)
        gains = np.clip(mean.mean() / np.maximum(mean, 1e-6), 1 - WB_LIMIT, 1 + WB_LIMIT)
        rgb = np.clip(rgb * gains, 0, 1)
    lum = rgb @ np.array([.2126, .7152, .0722], dtype=np.float32)
    vals = lum[subj] if subj.sum() > 1000 else lum.ravel()
    lo, hi = np.percentile(vals, 1), np.percentile(vals, 99)
    # мягкие уровни: только светлое — на 35 % к 0.98 (вытянуть сероватые снимки); чёрную точку не трогаем, иначе
    # светлые блюда темнеют и пестрят (капучино в белой чашке)
    lo_t, hi_t = lo, hi + (0.98 - hi) * 0.35
    if hi - lo > 0.05:
        rgb = np.clip((rgb - lo) / (hi - lo) * (hi_t - lo_t) + lo_t, 0, 1)
    lum = rgb @ np.array([.2126, .7152, .0722], dtype=np.float32)
    med = float(np.median(lum[subj] if subj.sum() > 1000 else lum))
    if 0.05 < med < TARGET_MED:                     # только высветлить тёмное: белые чашки и тарелки не «гасим»
        g = np.log(TARGET_MED) / np.log(med)
        g = 1 + (g - 1) * 0.3                           # к общей медиане — на 30 %, без «пересвета» тёмного кофе
        rgb = np.clip(rgb, 1e-6, 1) ** np.clip(g, 0.85, 1.18)
    mx, mn = rgb.max(2), rgb.min(2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    s_mean = float(sat[subj].mean()) if subj.sum() > 1000 else float(sat.mean())
    k = np.clip(1 + (TARGET_SAT / max(s_mean, 1e-3) - 1) * 0.25, 0.94, 1.03)
    gray = (rgb @ np.array([.2126, .7152, .0722], dtype=np.float32))[..., None]
    return np.clip(gray + (rgb - gray) * k, 0, 1)


def new_session(model):
    import onnxruntime as ort
    return ort.InferenceSession(model, providers=['CPUExecutionProvider'])


def get_mask(im, session):
    """маска предмета моделью isnet-general-use — подготовка как в rembg (DisCustomSession): 1024×1024, /max, −0.5"""
    import numpy as np
    from PIL import Image, ImageFilter
    x = np.asarray(im.convert('RGB').resize((1024, 1024), Image.LANCZOS), dtype=np.float32)
    x = x / max(float(x.max()), 1e-6) - 0.5
    pred = session.run(None, {session.get_inputs()[0].name: x.transpose(2, 0, 1)[None]})[0][0, 0]
    pred = (pred - pred.min()) / max(float(pred.max() - pred.min()), 1e-6)
    m = Image.fromarray((pred * 255).astype('uint8'), 'L').resize(im.size, Image.LANCZOS)
    a = np.asarray(m, dtype=np.float32) / 255
    a = np.clip((a - 0.15) / 0.7, 0, 1)                       # мягкий край: шум фона — в 0, ядро предмета — в 1
    return Image.fromarray((a * 255).astype('uint8'), 'L').filter(ImageFilter.GaussianBlur(1))


def recover_plates(im, alpha):
    """белая тарелка на белом фоне: модель её часто «съедает» (маска 0), а дорисовать её краем по порогу аккуратно не
    выходит (рваная кайма). Поэтому здесь только признак: «не фон» — всё, до чего нельзя дойти от краёв кадра по плавным
    переходам цвета (соседи отличаются ≤ 5 из 255) от пикселей цвета фона; берём то, что рядом с маской модели (~15 %
    кадра). → (доля «не фона» сверх маски модели, маска предмета вместе с тарелкой, цвет фона). Доля больше
    PLATE_EATEN — модель съела тарелку: такое фото идёт в фолбэк (без вырезки, по центру по маске с тарелкой)."""
    import numpy as np
    from collections import deque
    from PIL import Image, ImageFilter
    small = im.copy()
    small.thumbnail((384, 384))
    a = np.asarray(small.filter(ImageFilter.GaussianBlur(1)), dtype=np.int16)
    h, w = a.shape[:2]
    border = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    ref = np.median(border, 0)
    ok_h = (np.abs(a[:, 1:] - a[:, :-1]).max(2) <= 5).tolist()     # можно шагнуть (y, x) ↔ (y, x+1)
    ok_v = (np.abs(a[1:] - a[:-1]).max(2) <= 5).tolist()           # (y, x) ↔ (y+1, x)
    like_bg = (np.abs(a - ref).max(2) <= 24).tolist()
    seen = [[False] * w for _ in range(h)]
    q = deque()
    for y in range(h):
        for x in (0, w - 1):
            if like_bg[y][x] and not seen[y][x]:
                seen[y][x] = True; q.append((y, x))
    for x in range(w):
        for y in (0, h - 1):
            if like_bg[y][x] and not seen[y][x]:
                seen[y][x] = True; q.append((y, x))
    while q:
        y, x = q.popleft()
        if x + 1 < w and not seen[y][x + 1] and ok_h[y][x]:
            seen[y][x + 1] = True; q.append((y, x + 1))
        if x > 0 and not seen[y][x - 1] and ok_h[y][x - 1]:
            seen[y][x - 1] = True; q.append((y, x - 1))
        if y + 1 < h and not seen[y + 1][x] and ok_v[y][x]:
            seen[y + 1][x] = True; q.append((y + 1, x))
        if y > 0 and not seen[y - 1][x] and ok_v[y - 1][x]:
            seen[y - 1][x] = True; q.append((y - 1, x))
    seen = np.array(seen)
    fg = ~seen
    model = np.asarray(Image.fromarray((alpha * 255).astype('uint8')).resize((w, h)), dtype=np.float32) / 255 > 0.5
    near = Image.fromarray((model * 255).astype('uint8'))
    for _ in range(4):
        near = near.filter(ImageFilter.MaxFilter(15))
    near = np.asarray(near) > 0
    extra = fg & near & ~model
    union = Image.fromarray(((fg & near) | model).astype('uint8') * 255).resize(im.size, Image.NEAREST)
    return float(extra.sum()) / max(float(model.sum()), 1), np.asarray(union) > 0, ref


def defringe(rgb, alpha):
    """цвет полупрозрачной кромки — от соседнего непрозрачного предмета (убирает белую/серую кайму фона)"""
    import numpy as np
    from PIL import Image, ImageFilter
    solid = (alpha > 0.9).astype(np.float32)
    img = Image.fromarray((rgb * 255).astype('uint8'))
    acc = np.zeros_like(rgb)
    w = np.zeros(alpha.shape, dtype=np.float32)
    for r in (2, 4, 8):
        blur_c = np.asarray(Image.fromarray((rgb * solid[..., None] * 255).astype('uint8')).filter(ImageFilter.BoxBlur(r)), dtype=np.float32) / 255
        blur_w = np.asarray(Image.fromarray((solid * 255).astype('uint8')).filter(ImageFilter.BoxBlur(r)), dtype=np.float32) / 255
        take = (w == 0) & (blur_w > 0.02)
        acc[take] = blur_c[take] / blur_w[take, None]
        w[take] = 1
    edge = (alpha > 0.01) & (alpha < 0.9) & (w > 0)
    out = rgb.copy()
    out[edge] = acc[edge]
    return out


def compose(rgb, alpha, shadow=True):
    """предмет по центру квадратного холста с полями MARGIN; под ним — едва заметная тень-эллипс → RGBA CANVAS×CANVAS"""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter
    ys, xs = np.where(alpha > 0.5)
    if len(xs) == 0:
        raise ValueError('пустая маска')
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    bw, bh = x1 - x0, y1 - y0
    side = int(max(bw, bh) / (1 - 2 * MARGIN))
    rgba = np.dstack([rgb, alpha]).astype(np.float32)
    canvas = np.zeros((side, side, 4), dtype=np.float32)
    ox, oy = (side - bw) // 2, (side - bh) // 2
    canvas[oy:oy + bh, ox:ox + bw] = rgba[y0:y1, x0:x1]
    out = Image.fromarray((canvas * 255).astype('uint8'), 'RGBA').resize((CANVAS, CANVAS), Image.LANCZOS)
    if shadow:
        k = CANVAS / side
        sh = Image.new('L', (CANVAS, CANVAS), 0)
        cx, cy, rx, ry = float((ox + bw / 2) * k), float((oy + bh) * k), float(bw * k * 0.36), float(max(6, bh * k * 0.035))
        ImageDraw.Draw(sh).ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=46)
        sh = sh.filter(ImageFilter.GaussianBlur(ry * 1.2))
        base = Image.new('RGBA', (CANVAS, CANVAS), (36, 28, 21, 0))
        base.putalpha(sh)
        base.alpha_composite(out)
        out = base
    return out


def fallback(im, obj=None, bg=None):
    """без вырезки: тот же цвет; предмет (маска с тарелкой, если есть) — по центру квадрата с полями MARGIN, поля — цветом
    фона снимка (у студийных — белым); без маски — центр кадра"""
    import numpy as np
    from PIL import Image
    rgb = np.asarray(im, dtype=np.float32) / 255
    rgb = correct(rgb, obj.astype(np.float32) if obj is not None else np.ones(rgb.shape[:2], dtype=np.float32))
    h, w = rgb.shape[:2]
    if obj is None or not obj.any():
        s = min(h, w)
        crop = rgb[(h - s) // 2:(h - s) // 2 + s, (w - s) // 2:(w - s) // 2 + s]
        return Image.fromarray((crop * 255).astype('uint8')).convert('RGBA').resize((CANVAS, CANVAS), Image.LANCZOS)
    ys, xs = np.where(obj)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    side = int(max(x1 - x0, y1 - y0) / (1 - 2 * MARGIN))
    fill = np.array(bg if bg is not None else (255, 255, 255), dtype=np.float32) / 255
    fill = correct(fill.reshape(1, 1, 3) * np.ones((4, 4, 3), dtype=np.float32), np.zeros((4, 4), dtype=np.float32))[0, 0]
    if fill.min() > 0.85:            # светлый студийный фон с оттенком (розоватый, голубоватый) — доводим до белого, как лист карточки
        gains = np.clip(1 / np.maximum(fill, 1e-6), 1, 1.15)
        rgb = np.clip(rgb * gains, 0, 1)
        fill = np.clip(fill * gains, 0, 1)
    canvas = np.ones((side, side, 3), dtype=np.float32) * fill
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    sx0, sy0 = cx - side // 2, cy - side // 2
    ix0, iy0, ix1, iy1 = max(sx0, 0), max(sy0, 0), min(sx0 + side, w), min(sy0 + side, h)
    canvas[iy0 - sy0:iy1 - sy0, ix0 - sx0:ix1 - sx0] = rgb[iy0:iy1, ix0:ix1]
    return Image.fromarray((canvas * 255).astype('uint8')).convert('RGBA').resize((CANVAS, CANVAS), Image.LANCZOS)


def save(img, sl):
    out = {}
    for px, limit, suf in bc.SIZES:
        dst = os.path.join(IMG_DIR, f'{sl}{suf}.webp')
        im = img.copy()
        if px < CANVAS:
            im = im.resize((px, px), __import__('PIL.Image', fromlist=['Image']).LANCZOS)
        data, q = bc.encode_webp(im, px, limit)
        with open(dst, 'wb') as f:
            f.write(data)
        out[suf or '960'] = (len(data), q)
        if not suf:                                  # encode_webp мог уменьшить сторону, чтобы влезть в лимит
            from PIL import Image
            out['size'] = list(Image.open(io.BytesIO(data)).size)
    return out


def sheet(rows, path):
    """лист «до / после»: на строку 4 фото × (исходник | после на белом | после на тёмном), подпись — slug"""
    from PIL import Image, ImageDraw
    cell, cols = 120, 4
    w, h = cols * (cell * 3 + 12) + 12, ((len(rows) + cols - 1) // cols) * (cell + 18) + 12
    sh = Image.new('RGB', (w, h), (230, 230, 230))
    dr = ImageDraw.Draw(sh)
    for i, (sl, before, after, mode) in enumerate(rows):
        x, y = 12 + (i % cols) * (cell * 3 + 12), 12 + (i // cols) * (cell + 18)
        b = before.copy(); b.thumbnail((cell, cell))
        sh.paste(b, (x + (cell - b.width) // 2, y + (cell - b.height) // 2))
        for j, bgc in enumerate(((255, 255, 255), (70, 70, 70))):
            bg = Image.new('RGBA', (cell, cell), bgc + (255,))
            a = after.resize((cell, cell))
            bg.alpha_composite(a)
            sh.paste(bg.convert('RGB'), (x + cell * (j + 1), y))
        dr.text((x, y + cell + 2), ('[FB] ' if mode == 'fb' else '') + sl[:44], fill=(150, 0, 0) if mode == 'fb' else (0, 0, 0))
    sh.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--photos', required=True, help='папка исходников с Диска (menu/menu_photos)')
    ap.add_argument('--only', default='', help='slug,… — только эти')
    ap.add_argument('--fallback', default='', help='slug,… — без вырезки (фолбэк)')
    ap.add_argument('--cut', default='', help='slug,… — вырезать, даже если признак «съеденной тарелки» сработал (проверено глазами)')
    ap.add_argument('--sheets', default='', help='папка для листов «до / после»')
    ap.add_argument('--model', required=True, help='путь к isnet-general-use.onnx (модель rembg)')
    ap.add_argument('--no-shadow', action='store_true')
    a = ap.parse_args()
    import numpy as np
    session = new_session(a.model)
    with open(SOURCES, encoding='utf-8') as f:
        sources = json.load(f)
    with open(CARDS, encoding='utf-8') as f:
        cards = json.load(f)
    only = [x for x in a.only.split(',') if x]
    fb = set(x for x in a.fallback.split(',') if x)
    force_cut = set(x for x in a.cut.split(',') if x)
    rows, report = [], {}
    for sl in sorted(sources):
        if only and sl not in only:
            continue
        sign = base_sign(sources[sl])
        im = load(source_of(sign, a.photos))
        alpha = np.asarray(get_mask(im, session), dtype=np.float32) / 255
        plate, union, bg = recover_plates(im, alpha)
        if sl in fb or (plate > PLATE_EATEN and sl not in force_cut):                 # ручной список или модель съела тарелку
            img, mode = fallback(im, union, bg), 'fb'
        else:
            rgb = np.asarray(im, dtype=np.float32) / 255
            rgb = correct(rgb, alpha)
            rgb = defringe(rgb, alpha)
            img, mode = compose(rgb, alpha, shadow=not a.no_shadow), 'cut'
        sizes = save(img, sl)
        dims = sizes.pop('size')
        sources[sl] = '%s+%s %s' % (sign, CUT_VER if mode == 'cut' else FB_VER, json.dumps(dims))
        report[sl] = {'mode': mode, 'size': dims, 'kb': {k: round(v[0] / 1024, 1) for k, v in sizes.items()}, 'plate': round(plate, 2), 'why': 'список' if sl in fb else ('тарелка' if mode == 'fb' else '')}
        b, t = im.copy(), img.copy()                   # для листа хватит миниатюр: 220 полных кадров не держим в памяти
        b.thumbnail((240, 240)); t.thumbnail((240, 240))
        rows.append((sl, b, t, mode))
        print('%-50s %s %s' % (sl, mode, report[sl]['kb']), flush=True)
    for key, c in cards.items():
        m = re.match(r'img/menu/(.+)\.webp$', c.get('img') or '')
        if m and m.group(1) in report:
            c['ar'] = report[m.group(1)]['size']
    with open(SOURCES, 'w', encoding='utf-8') as f:
        json.dump(dict(sorted(sources.items())), f, ensure_ascii=False, indent=1)   # как build_cards.py
        f.write('\n')
    with open(CARDS, 'w', encoding='utf-8') as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)                           # как build_cards.py
        f.write('\n')
    if a.sheets:
        os.makedirs(a.sheets, exist_ok=True)
        for n in range(0, len(rows), 24):
            sheet(rows[n:n + 24], os.path.join(a.sheets, 'sheet-%02d.png' % (n // 24 + 1)))
        with open(os.path.join(a.sheets, 'report.json'), 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
