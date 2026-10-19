#!/usr/bin/env python3
"""tools/flame_frame.py — генератор огненной рамки: кольцо «внешний прямоугольник − внутренний многоугольник с языками пламени».
Запуск из корня: python3 tools/flame_frame.py > /dev/stdout — SVG вставить в index.html (<svg class="grill-fire">), покрытие печатается в stderr.
Только M/L/Z, чтобы тест считал площадь по формуле шнурков. Печатает SVG и долю покрытия."""
import math, sys

W, H = 910, 512

def tongues(length, base, amp, n, seed):
    """Точки вдоль стороны длиной length: расстояние от края = base + язык (0..amp), пилообразные языки разной высоты."""
    pts = []
    rnd = seed
    for k in range(n + 1):
        rnd = (rnd * 1103515245 + 12345) % 2**31
        hgt = amp * (0.35 + 0.65 * (rnd % 1000) / 1000)
        x0 = length * k / n
        pts.append((x0, base))                      # впадина
        if k < n:
            rnd = (rnd * 1103515245 + 12345) % 2**31
            step = length / n
            tip = x0 + step * (0.35 + 0.3 * (rnd % 1000) / 1000)
            # язык: плечи на 45% высоты, узкое остриё — похоже на пламя, а не на пилу
            pts.append((x0 + (tip - x0) * 0.45, base + hgt * 0.45))
            pts.append((tip, base + hgt))           # остриё языка (внутрь видео)
            pts.append((tip + (x0 + step - tip) * 0.55, base + hgt * 0.45))
    return pts

def inner_polygon(top, side, bottom, n_top, n_side, seed):
    """Обход по часовой: верх (слева направо), правая сторона (сверху вниз), низ (справа налево), левая (снизу вверх)."""
    poly = []
    for x, d in tongues(W, *top, n_top, seed):             poly.append((x, d))
    for y, d in tongues(H, *side, n_side, seed + 7):      poly.append((W - d, y))
    for x, d in tongues(W, *bottom, n_top, seed + 13):    poly.append((W - x, H - d))
    for y, d in tongues(H, *side, n_side, seed + 29):     poly.append((d, H - y))
    return poly

def area(p):
    return abs(sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1] for i in range(len(p)))) / 2

def path(poly):
    return 'M0 0 L910 0 L910 512 L0 512Z M' + ' L'.join(f'{x:.0f} {y:.0f}' for x, y in poly) + 'Z'

# (база, амплитуда языка) для верха, боков, низа; низ толще — на нём бегущая строка
red = inner_polygon((9, 30), (9, 34), (46, 22), 14, 8, 42)
ora = inner_polygon((5, 18), (5, 20), (40, 12), 14, 8, 42)
cov_red = (W * H - area(red)) / (W * H)
cov_ora = (W * H - area(ora)) / (W * H)
print(f'покрытие красного кольца {cov_red:.1%}, оранжевого {cov_ora:.1%}', file=sys.stderr)
svg = (f'<svg class="grill-fire" viewBox="0 0 {W} {H}" preserveAspectRatio="none" aria-hidden="true" focusable="false">'
       f'<path fill="#D7261E" fill-rule="evenodd" d="{path(red)}"/>'
       f'<path fill="#FF8A1F" fill-rule="evenodd" d="{path(ora)}"/>'
       f'</svg>')
print(svg)
print(len(svg), 'байт', file=sys.stderr)
