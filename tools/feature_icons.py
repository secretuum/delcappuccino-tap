#!/usr/bin/env python3
"""Значки карточек «Место для ваших планов» (правка владельца 1.11.2026): свой набор из 6 линейных значков в одном стиле —
сетка 48×48, обводка 2, скруглённые концы и стыки, currentColor (на сайте — forest). Без эмодзи и чужих наборов.

Геометрия задана здесь один раз; из неё же собираются <symbol> для SVG-спрайта страниц (tools/seo_jsonld.py → ICONS)
и PNG-превью для проверки глазами (системного SVG-рендера нет — рисуем те же линии Pillow):
    python3 tools/feature_icons.py --preview <папка>      # f-*.png по 384 px и общий лист sheet.png

Фигуры: ('P', [команды]) — путь из ('M', x, y) ('L', x, y) ('Q', cx, cy, x, y) ('C', c1x, c1y, c2x, c2y, x, y) ('Z',)
и ('ARC', cx, cy, r, a0, a1) — дуга окружности от угла a0 к a1 (градусы, 0 — вправо, по часовой — вниз, как в SVG);
('O', cx, cy, r) — окружность; ('OF', cx, cy, r) — закрашенный кружок (желток, глаз); ('E', cx, cy, rx, ry) — эллипс.
"""
import math, os, sys

SIZE, STROKE = 48, 2


def digits(text, x0, y0, h=10.0, w=5.0, gap=1.6):
    """цифры 2, 4, 7 и «/» штрихами (высота h): для значка «24/7»"""
    out, x = [], x0
    for ch in text:
        if ch == '2':
            out.append(('P', [('M', x, y0 + 2.4), ('Q', x, y0, x + w / 2, y0), ('Q', x + w, y0, x + w, y0 + 2.6),
                              ('Q', x + w, y0 + 4.6, x, y0 + h), ('L', x + w, y0 + h)]))
        elif ch == '4':
            out.append(('P', [('M', x + w * .72, y0 + h), ('L', x + w * .72, y0), ('L', x, y0 + h * .66), ('L', x + w, y0 + h * .66)]))
        elif ch == '7':
            out.append(('P', [('M', x, y0), ('L', x + w, y0), ('L', x + w * .35, y0 + h)]))
        elif ch == '/':
            w_ = w * .7
            out.append(('P', [('M', x + w_, y0 - .5), ('L', x, y0 + h + .5)]))
            x += w_ + gap
            continue
        x += w + gap
    return out


def text_width(text, w=5.0, gap=1.6):
    return sum((w * .7 if c == '/' else w) for c in text) + gap * (len(text) - 1)


def icon_247():
    """«24/7»: стрелка по кругу (циферблат) и знак 24/7 внутри"""
    tw = text_width('24/7')
    a0, a1 = -55, 245                                                            # дуга по часовой, щель сверху
    tip = arc_pt(24, 24, 19, a1)
    t = math.radians(a1)
    d = (-math.sin(t), math.cos(t))                                              # направление движения по дуге в конце
    wing = lambda s_: (tip[0] - 5 * (d[0] * math.cos(s_) - d[1] * math.sin(s_)), tip[1] - 5 * (d[0] * math.sin(s_) + d[1] * math.cos(s_)))
    w1, w2 = wing(math.radians(40)), wing(math.radians(-40))
    shapes = [('P', [('ARC', 24, 24, 19, a0, a1)]), ('P', [('M', w1[0], w1[1]), ('L', tip[0], tip[1]), ('L', w2[0], w2[1])])]
    return shapes + digits('24/7', 24 - tw / 2, 19)


def icon_breakfast():
    """завтрак сверху: тарелка, яичница-глазунья (волнистый белок, желток) и полоска бекона"""
    egg = [('M', 10.5, 20), ('C', 10, 14.5, 15, 11, 19.5, 12.5), ('C', 22, 10.5, 27.5, 12, 27.5, 16.5),
           ('C', 30.5, 19.5, 29, 25, 25, 25.5), ('C', 23, 29, 16, 29.5, 13.5, 26.5), ('C', 10.5, 25.5, 9.5, 22.5, 10.5, 20), ('Z',)]
    bacon_a = [('M', 17.5, 35), ('Q', 21, 32.5, 24.5, 34.5), ('Q', 28, 36.5, 31.5, 33.5), ('Q', 34, 31.5, 36.5, 32)]
    bacon_b = [('M', 18.5, 39), ('Q', 22, 36.5, 25.5, 38.5), ('Q', 29, 40.5, 32.5, 37.5), ('Q', 35, 35.5, 37.5, 36)]
    ends = [('M', 17.5, 35), ('L', 18.5, 39), ('M', 36.5, 32), ('L', 37.5, 36)]           # концы полоски — лента бекона
    return [('O', 24, 24, 21), ('P', egg), ('OF', 19.5, 19.5, 3.6), ('P', bacon_a), ('P', bacon_b), ('P', ends)]


def icon_horse():
    """лошадка-качалка сбоку: изогнутые полозья, расставленные ноги, туловище с шеей и головой, ухо, глаз, грива, хвост"""
    rocker = [('M', 4, 37), ('Q', 24, 47, 44, 37)]
    body = [('M', 12, 22), ('Q', 20, 23.5, 27, 20), ('L', 31, 11), ('Q', 32, 8, 35, 8.5), ('L', 41.5, 12),
            ('Q', 43.5, 13.5, 42, 15.5), ('Q', 41, 16.8, 38.5, 16), ('L', 36, 15.5), ('Q', 35, 19, 35, 23),
            ('Q', 35, 27, 31, 27), ('L', 16, 27), ('Q', 12, 27, 12, 22), ('Z',)]
    ear = [('M', 32.5, 9), ('L', 32, 4.5), ('L', 35.5, 8.4)]
    mane = [('M', 30.5, 12.5), ('L', 27.5, 14), ('M', 29.3, 15.8), ('L', 26.3, 17.3)]
    tail = [('M', 12, 23), ('Q', 6, 22.5, 7, 30)]
    legs = [('M', 16, 27), ('L', 11.5, 39.5), ('M', 31, 27), ('L', 35.5, 39.5)]
    return [('P', rocker), ('P', body), ('P', ear), ('P', mane), ('P', tail), ('P', legs), ('OF', 37.5, 11.5, 1.2)]


def icon_glasses():
    """солнечные очки-вайфареры: широкие трапеции линз с толстой верхней кромкой, перемычка, дужки, блики"""
    def lens(m):
        f = (lambda x: x) if m > 0 else (lambda x: 48 - x)
        return [('M', f(4.5), 16.5), ('L', f(20.5), 16.5), ('Q', f(22), 16.5, f(21.6), 18.5), ('L', f(20), 27),
                ('Q', f(19.5), 29.5, f(17), 29.5), ('L', f(9.5), 29.5), ('Q', f(7), 29.5, f(6.4), 27), ('L', f(4), 18.5),
                ('Q', f(3.8), 16.5, f(4.5), 16.5), ('Z',)]
    glint = lambda m: [('M', 24 - m * 15.5, 20.5), ('L', 24 - m * 12.5, 25.5), ('M', 24 - m * 11.5, 20.5), ('L', 24 - m * 10, 23)]
    return [('P', lens(1)), ('P', lens(-1)), ('P', [('M', 21.8, 19), ('Q', 24, 16.8, 26.2, 19)]),
            ('P', [('M', 4.5, 16.5), ('L', 1.5, 15)]), ('P', [('M', 43.5, 16.5), ('L', 46.5, 15)]),
            ('P', glint(1)), ('P', glint(-1))]


def icon_banquet():
    """банкет сверху: тарелка с бортиком посередине, вилка слева, ложка справа"""
    fork = [('M', 5.5, 7), ('L', 5.5, 14), ('Q', 5.5, 18, 8.5, 18), ('Q', 11.5, 18, 11.5, 14), ('L', 11.5, 7),
            ('M', 8.5, 7), ('L', 8.5, 14), ('M', 8.5, 18), ('L', 8.5, 41)]
    spoon = [('M', 39.5, 18.5), ('L', 39.5, 41)]
    return [('O', 24, 24, 11.5), ('O', 24, 24, 7), ('P', fork), ('E', 39.5, 12, 3.5, 5.5), ('P', spoon)]


def icon_crescent():
    """полумесяц со звездой: два дуговых края месяца и пятиконечная звезда в его раскрытии"""
    # внешний круг (21, 25) r 17, вырез — круг (28, 20) r 13; точки пересечения считаем
    (ax, ay, ar), (bx, by, br) = (21, 25, 17), (28, 20, 13)
    d = math.hypot(bx - ax, by - ay)
    a = (ar * ar - br * br + d * d) / (2 * d)
    h = math.sqrt(ar * ar - a * a)
    mx, my = ax + a * (bx - ax) / d, ay + a * (by - ay) / d
    p1 = (mx + h * (by - ay) / d, my - h * (bx - ax) / d)
    p2 = (mx - h * (by - ay) / d, my + h * (bx - ax) / d)
    ang = lambda c, p: math.degrees(math.atan2(p[1] - c[1], p[0] - c[0]))
    a1o, a2o = ang((ax, ay), p1), ang((ax, ay), p2)
    a1i, a2i = ang((bx, by), p1), ang((bx, by), p2)
    # внешняя дуга — длинная, через левый-нижний край; внутренняя — короткая, обратно
    outer = (a1o, a2o) if (a2o - a1o) % 360 > 180 else (a2o, a1o)
    span = (outer[1] - outer[0]) % 360
    start_pt = p1 if outer[0] == a1o else p2
    end_pt = p2 if start_pt is p1 else p1
    i0, i1 = ang((bx, by), end_pt), ang((bx, by), start_pt)
    ispan = (i0 - i1) % 360                                  # внутренняя идёт против часовой (короткая)
    crescent = [('ARC', ax, ay, ar, outer[0], outer[0] + span), ('ARC', bx, by, br, i0, i0 - ispan), ('Z',)]
    star, cx, cy, R, r = [], 35.5, 17, 5.2, 2.2
    for k in range(10):
        t = math.radians(-90 + k * 36)
        rr = R if k % 2 == 0 else r
        star.append(('M' if k == 0 else 'L', cx + rr * math.cos(t), cy + rr * math.sin(t)))
    star.append(('Z',))
    return [('P', crescent), ('P', star)]


ICONS = [('f-247', icon_247), ('f-breakfast', icon_breakfast), ('f-kids', icon_horse), ('f-vip', icon_glasses),
         ('f-banquet', icon_banquet), ('f-namaz', icon_crescent)]
FEATURE_IDS = [i for i, _ in ICONS]       # по порядку карточек «Формата»: 24/7, завтраки, детская, VIP, банкеты, намазхана


def n(v):
    s = ('%.2f' % v).rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def arc_pt(cx, cy, r, a):
    t = math.radians(a)
    return cx + r * math.cos(t), cy + r * math.sin(t)


def svg_path(cmds):
    out, started = [], False
    for c in cmds:
        k = c[0]
        if k == 'ARC':
            _, cx, cy, r, a0, a1 = c
            x0, y0 = arc_pt(cx, cy, r, a0)
            x1, y1 = arc_pt(cx, cy, r, a1)
            out.append(('L' if started else 'M') + '%s %s' % (n(x0), n(y0)))
            large = 1 if abs(a1 - a0) > 180 else 0
            sweep = 1 if a1 > a0 else 0
            out.append('A%s %s 0 %d %d %s %s' % (n(r), n(r), large, sweep, n(x1), n(y1)))
        elif k == 'Z':
            out.append('Z')
        else:
            out.append(k + ' '.join(n(v) for v in c[1:]))
        started = True
    return ''.join(out)


def svg_shape(sh):
    if sh[0] == 'OF':
        return '<circle cx="%s" cy="%s" r="%s" fill="currentColor"/>' % tuple(n(v) for v in sh[1:])
    if sh[0] == 'O':
        return '<circle cx="%s" cy="%s" r="%s"/>' % tuple(n(v) for v in sh[1:])
    if sh[0] == 'E':
        return '<ellipse cx="%s" cy="%s" rx="%s" ry="%s"/>' % tuple(n(v) for v in sh[1:])
    return '<path d="%s"/>' % svg_path(sh[1])


def symbols():
    """<symbol> всех значков для SVG-спрайта (fill none, обводка 2 currentColor, скруглённые концы)"""
    return ''.join('<symbol id="%s" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
                   'stroke-linejoin="round">%s</symbol>' % (i, ''.join(svg_shape(s) for s in f())) for i, f in ICONS)


# ── превью Pillow: те же фигуры, ломаной ──

def flatten(cmds, steps=24):
    polys, cur, pts, start = [], None, [], None
    for c in cmds:
        k = c[0]
        if k == 'M':
            if len(pts) > 1:
                polys.append(pts)
            pts, cur = [(c[1], c[2])], (c[1], c[2])
            start = cur
        elif k == 'L':
            cur = (c[1], c[2]); pts.append(cur)
        elif k == 'Q':
            p0, p1, p2 = cur, (c[1], c[2]), (c[3], c[4])
            for i in range(1, steps + 1):
                t = i / steps
                pts.append(tuple((1 - t) ** 2 * p0[j] + 2 * (1 - t) * t * p1[j] + t * t * p2[j] for j in (0, 1)))
            cur = p2
        elif k == 'C':
            p0, p1, p2, p3 = cur, (c[1], c[2]), (c[3], c[4]), (c[5], c[6])
            for i in range(1, steps + 1):
                t = i / steps
                pts.append(tuple((1 - t) ** 3 * p0[j] + 3 * (1 - t) ** 2 * t * p1[j] + 3 * (1 - t) * t * t * p2[j] + t ** 3 * p3[j]
                                 for j in (0, 1)))
            cur = p3
        elif k == 'ARC':
            _, cx, cy, r, a0, a1 = c
            m = max(8, int(abs(a1 - a0) / 4))
            seg = [arc_pt(cx, cy, r, a0 + (a1 - a0) * i / m) for i in range(m + 1)]
            if not pts:
                start = seg[0]
            pts.extend(seg)
            cur = seg[-1]
        elif k == 'Z':
            if start:
                pts.append(start); cur = start
    if len(pts) > 1:
        polys.append(pts)
    return polys


def shape_polys(sh):
    if sh[0] in ('O', 'E'):
        cx, cy = sh[1], sh[2]
        rx, ry = (sh[3], sh[3]) if sh[0] == 'O' else (sh[3], sh[4])
        return [[(cx + rx * math.cos(math.radians(a)), cy + ry * math.sin(math.radians(a))) for a in range(0, 361, 4)]]
    return flatten(sh[1])


def render(f, px=384, color=(0x42, 0x63, 0x49)):
    from PIL import Image, ImageDraw
    k = px / SIZE
    im = Image.new('RGB', (px, px), (255, 255, 255))
    dr = ImageDraw.Draw(im)
    w = STROKE * k
    for sh in f():
        if sh[0] == 'OF':
            cx, cy, r = (v * k for v in sh[1:])
            dr.ellipse((cx - r - w / 2, cy - r - w / 2, cx + r + w / 2, cy + r + w / 2), fill=color)
            continue
        for poly in shape_polys(sh):
            p = [(x * k, y * k) for x, y in poly]
            dr.line(p, fill=color, width=round(w))
            for x, y in p:
                dr.ellipse((x - w / 2, y - w / 2, x + w / 2, y + w / 2), fill=color)
    return im


def preview(out):
    from PIL import Image
    os.makedirs(out, exist_ok=True)
    sheet = Image.new('RGB', (6 * 200 + 7 * 10, 2 * 200 + 30), (255, 255, 255))
    for i, (name, f) in enumerate(ICONS):
        big = render(f)
        big.save(os.path.join(out, '%s.png' % name))
        sheet.paste(big.resize((200, 200)), (10 + i * 210, 10))
        sheet.paste(render(f, 48).resize((48, 48)), (10 + i * 210 + 76, 230))      # как на сайте, 48 px
    sheet.save(os.path.join(out, 'sheet.png'))
    print('превью:', out)


if __name__ == '__main__':
    if '--preview' in sys.argv:
        preview(sys.argv[sys.argv.index('--preview') + 1])
    else:
        print(symbols())
