"""Сторожа шлифовки главной (polish-main, 09.11.2026: «допиливай все детали мелкие»): то, что исправили, не должно вернуться.
Контраст кнопки WhatsApp, разметка без дублей id, у картинок alt и размеры, у кнопок type, окна — диалоги с возвратом фокуса,
видимый фокус, касание, reduced-motion, неразрывный пробел перед ₸, соцсети-превью на всех страницах.
Запуск из корня репозитория: python3 -m unittest discover -s tests -v"""
import os, re, unittest
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = ['index.html', 'kk/index.html', 'en/index.html', 'menyu/index.html', 'kk/menyu/index.html', 'en/menu/index.html']


def read(p):
    with open(os.path.join(ROOT, p), encoding='utf-8') as f:
        return f.read()


def css_of(html):
    css = html[html.index('<style>') + 7:html.index('</style>')]
    return re.sub(r'\s*\n\s*', '', re.sub(r'/\*.*?\*/', '', css, flags=re.S))


def root_vars(html):
    return dict(re.findall(r'(--[\w-]+):\s*([^;]+?)\s*;', re.search(r':root\{(.*?)\}', css_of(html)).group(1)))


# ── контраст по WCAG 2.x ──
def _lin(c):
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def lum(rgb):
    r, g, b = (_lin(x) for x in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def over(fg, a, bg):
    return tuple(f * a + b * (1 - a) for f, b in zip(fg, bg))


def rgba(s):
    m = re.match(r'rgba\((\d+),(\d+),(\d+),([\d.]+)\)', s)
    return tuple(int(x) for x in m.groups()[:3]), float(m.group(4))


def hexrgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


class TestWhatsAppContrast(unittest.TestCase):
    """09.11 (решение владельца через главного): тон WhatsApp #25D366 давал белому логотипу ~1,9:1 — теперь #128C7E.
    Значок — значимая графика: не ниже 3:1 по всей высоте значка (кнопка 48, значок 22 — от 27 % до 73 % высоты),
    с бликом стекла сверху и затемнением снизу, на белой карточке и на светло-сером"""

    def test_white_logo_readable(self):
        v = root_vars(read('index.html'))
        self.assertEqual(v['--c-whatsapp'], '#128C7E')
        base = tuple(int(x) for x in v['--glass-wa-rgb'].split())
        self.assertEqual(base, hexrgb(v['--c-whatsapp']))
        white = (255, 255, 255)
        self.assertGreaterEqual(contrast(white, base), 4.0, 'белый на самом тоне')
        alpha = float(v['--glass-base-plain'])
        (hl1, a1), (hl2, a2) = rgba(v['--glass-wa-hl-top']), rgba(v['--glass-wa-hl-mid'])
        bot = rgba(re.search(r'rgba\([^)]*\)', v['--glass-bottom']).group(0))
        for bg in ((255, 255, 255), hexrgb(v['--c-surface'])):
            for y in (27, 35, 45, 50, 60, 73):
                c = over(base, alpha, bg)
                if y > 50:                                           # низ: transparent 50% → затемнение 100%
                    c = over(bot[0], bot[1] * (y - 50) / 50, c)
                if y < 55:                                           # блик: hl-top 0% → hl-mid 45% → прозрачный 55%
                    if y <= 45:
                        t = y / 45
                        a = a1 * (1 - t) + a2 * t
                        col = tuple((p * a1 * (1 - t) + q * a2 * t) / a for p, q in zip(hl1, hl2))
                    else:
                        a, col = a2 * (55 - y) / 10, hl2
                    c = over(col, a, c)
                self.assertGreaterEqual(contrast(white, c), 3.0, 'фон %s, высота %d%%' % (bg, y))


if __name__ == '__main__':
    unittest.main()
