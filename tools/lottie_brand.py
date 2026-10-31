#!/usr/bin/env python3
"""Анимация «кофе наливается в чашку» для карточки подписки на главных (редизайн 31.10.2026).

Источник: Lottie «Brewing coffee», автор CAROLINA SALAZAR, LottieFiles, Lottie Simple License (бесплатно, коммерция
разрешена) — https://lottiefiles.com/free-animation/brewing-coffee-0nUzAZmeIR. Исходники лежат вне репозитория:
~/kofe-design-export/media/lottie/lottiefiles-brewing-coffee-carolina-salazar.json и …-poster.png.
Перекраска под бренд: линии чашки (PNG внутри анимации) — forest #426349, пар — forest 55 %, кофе — тёплый коричневый,
как в оригинале (#664430). Постер — тот же кадр: белый фон → прозрачный (карточка cream), обрезан как анимация в CSS.

Запуск из корня репозитория:  python3 tools/lottie_brand.py [папка-вывода, по умолчанию assets]
Пишет assets/brewing-coffee.<хэш>.json и assets/brewing-coffee-poster.<хэш>.webp; новые имена вписать в COFFEE_ANIM
(tools/seo_jsonld.py), пересобрать (seo_jsonld.py, sw_version.py). Лицензии — docs/LICENSES-media.md. Нужен Pillow.
"""
import base64, hashlib, io, json, sys, os
from PIL import Image
SRC = os.path.expanduser('~/kofe-design-export/media/lottie/')
FOREST = (0x42, 0x63, 0x49)
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets')
d = json.load(open(SRC + 'lottiefiles-brewing-coffee-carolina-salazar.json'))

def tint(png, rgb, alpha=1.0):
    im = Image.open(io.BytesIO(png)).convert('RGBA')
    a = im.getchannel('A').point(lambda v: int(v * alpha))
    res = Image.new('RGBA', im.size, rgb + (0,)); res.putalpha(a)
    buf = io.BytesIO(); res.save(buf, 'PNG', optimize=True); return buf.getvalue()

for a in d['assets']:
    if a.get('p', '').startswith('data:image/png;base64,'):
        png = base64.b64decode(a['p'].split(',', 1)[1])
        new = tint(png, FOREST, 1.0 if a['id'] == 'image_3' else 0.55)
        a['p'] = 'data:image/png;base64,' + base64.b64encode(new).decode()
d['nm'] = 'Brewing coffee — CAROLINA SALAZAR (LottieFiles, Lottie Simple License), перекрашено под del Cappuccino'
s = json.dumps(d, ensure_ascii=False, separators=(',', ':'))
h = hashlib.sha256(s.encode()).hexdigest()[:8]
open(os.path.join(out, 'brewing-coffee.%s.json' % h), 'w', encoding='utf-8').write(s)
print('json', h, len(s))

# постер: смесь трёх цветов — белый фон W, линии L, кофе C; раскладываем пиксель на пару цветов и перекрашиваем
im = Image.open(SRC + 'lottiefiles-brewing-coffee-poster.png').convert('RGB')
W = (255, 255, 255)
from collections import Counter
cnt = Counter(im.getdata())
C = (102, 68, 48)                                   # кофе — цвет заливки liquid в самой анимации (#664430)
L = next(c for c, _ in cnt.most_common(40) if sum(c) < sum(C) - 30)     # линии чашки — самый частый цвет темнее кофе
print('line', L, 'coffee', C)
def blend(p, a, b):
    v = [b[i] - a[i] for i in range(3)]; w = [p[i] - a[i] for i in range(3)]
    vv = sum(x * x for x in v) or 1
    t = max(0.0, min(1.0, sum(v[i] * w[i] for i in range(3)) / vv))
    err = sum((a[i] + t * v[i] - p[i]) ** 2 for i in range(3))
    return t, err
px = []
for p in im.getdata():
    best = min(((blend(p, W, L), 'WL'), (blend(p, W, C), 'WC'), (blend(p, L, C), 'LC')), key=lambda x: x[0][1])
    (t, _), k = best
    if k == 'WL':
        px.append(FOREST + (round(255 * t),))
    elif k == 'WC':
        px.append(C + (round(255 * t),))
    else:
        px.append(tuple(round(FOREST[i] * (1 - t) + C[i] * t) for i in range(3)) + (255,))
po = Image.new('RGBA', im.size); po.putdata(px)
po = po.crop((96, 38, 544, 486)).resize((256, 256), Image.LANCZOS)   # та же обрезка, что у анимации в CSS: x 15–85 %, y 6–76 %
buf = io.BytesIO(); po.save(buf, 'WEBP', quality=82, method=6); data = buf.getvalue()
h = hashlib.sha256(data).hexdigest()[:8]
open(os.path.join(out, 'brewing-coffee-poster.%s.webp' % h), 'wb').write(data)
print('poster', h, len(data))
