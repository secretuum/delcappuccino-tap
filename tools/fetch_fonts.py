#!/usr/bin/env python3
"""Самохостинг шрифтов: скачивает woff2-подмножества (latin, cyrillic, cyrillic-ext) только нужных
начертаний с Google Fonts в assets/fonts/ и печатает готовый блок @font-face для <style> в index.html.

Запуск из корня репозитория:  python3 tools/fetch_fonts.py
Результат: assets/fonts/<семейство>-<вес>[i]-<подмножество>.<хэш8>.woff2 и assets/fonts/fonts.css (тот же
блок @font-face, для справки — страница грузит его из inline <style>, а не этим файлом).

Имя файла содержит хэш содержимого — поэтому sw.js кэширует их навечно (cache-first); при смене шрифта
меняется имя → index.html и sw.js надо обновить (скрипт печатает новый CSS).

Какие начертания нужны (по grep font-family/font-weight в index.html, 19.10.2026):
  Comfortaa            700                       — заголовки, цифры (h1, h2, <b>)
  Golos Text           400 500 600 700 800       — текст, кнопки, оверлей меню (.mm-only — 800)
  Cormorant Garamond   500 600, italic 500       — оверлей меню (.mm-*)
cyrillic-ext нужен Golos и Cormorant ради казахских букв (ҚӘҒҢӨҰҮҺІ) в меню; Comfortaa в меню не используется.
Только stdlib.
"""
import hashlib, os, re, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'assets', 'fonts')
# (семейство, slug, [(style, weight), ...], [подмножества])
FAMILIES = [
    ('Comfortaa', 'comfortaa', [('normal', 700)], ['latin', 'cyrillic']),
    ('Golos Text', 'golos', [('normal', 400), ('normal', 500), ('normal', 600), ('normal', 700), ('normal', 800)],
     ['latin', 'cyrillic', 'cyrillic-ext']),
    ('Cormorant Garamond', 'cormorant', [('normal', 500), ('normal', 600), ('italic', 500)],
     ['latin', 'cyrillic', 'cyrillic-ext']),
    ('Montserrat', 'montserrat', [('normal', 400), ('normal', 600), ('normal', 700)],
     ['latin', 'cyrillic', 'cyrillic-ext']),                       # только /ugolok (казахский → cyrillic-ext)
]
# Google отдаёт woff2 только «современному» браузеру
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36'


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def css_url(family, faces):
    ital = any(s == 'italic' for s, _ in faces)
    if ital:
        axes = ';'.join(f"{1 if s == 'italic' else 0},{w}" for s, w in sorted(faces, key=lambda f: (f[0] == 'italic', f[1])))
        spec = f"{family.replace(' ', '+')}:ital,wght@{axes}"
    else:
        spec = f"{family.replace(' ', '+')}:wght@{';'.join(str(w) for _, w in faces)}"
    return f'https://fonts.googleapis.com/css2?family={spec}&display=swap'


def main():
    os.makedirs(OUT, exist_ok=True)
    # Собираем все нужные грани; переменные шрифты (Golos Text, Cormorant Garamond) Google отдаёт одним файлом
    # на все веса — группируем по содержимому и пишем один @font-face с диапазоном font-weight.
    groups = {}   # (slug, style, subset, hash) → [family, weights, urange, data]
    for family, slug, faces, subsets in FAMILIES:
        css = get(css_url(family, faces)).decode('utf-8')
        cache = {}
        for subset, body in re.findall(r'/\*\s*([\w-]+)\s*\*/\s*@font-face\s*\{([^}]*)\}', css):   # /* subset */ @font-face {…}
            if subset not in subsets:
                continue
            style = re.search(r'font-style:\s*(\w+)', body).group(1)
            weight = int(re.search(r'font-weight:\s*(\d+)', body).group(1))
            if (style, weight) not in faces:
                continue
            src = re.search(r'url\((\S+?)\)\s*format\(\'woff2\'\)', body).group(1)
            urange = re.search(r'unicode-range:\s*([^;]+)', body).group(1).strip()
            data = cache.get(src) or cache.setdefault(src, get(src))
            key = (slug, style, subset, hashlib.sha256(data).hexdigest()[:8])
            g = groups.setdefault(key, [family, set(), urange, data])
            g[1].add(weight)

    wanted, lines, total = set(), [], 0
    for (slug, style, subset, h), (family, weights, urange, data) in groups.items():
        lo, hi = min(weights), max(weights)
        wtag = f'{lo}-{hi}' if lo != hi else str(lo)
        fname = f"{slug}-{wtag}{'i' if style == 'italic' else ''}-{subset}.{h}.woff2"
        with open(os.path.join(OUT, fname), 'wb') as f:
            f.write(data)
        wanted.add(fname)
        total += len(data)
        print(f'{fname:48} {len(data) / 1024:6.1f} КБ', file=sys.stderr)
        fw = f'{lo} {hi}' if lo != hi else str(lo)
        lines.append(f"@font-face{{font-family:'{family}';font-style:{style};font-weight:{fw};font-display:swap;"
                     f"src:url(assets/fonts/{fname}) format('woff2');unicode-range:{urange}}}")

    css_out = f'/* сгенерировано tools/fetch_fonts.py — {len(wanted)} файлов */\n' + '\n'.join(lines) + '\n'
    with open(os.path.join(OUT, 'fonts.css'), 'w', encoding='utf-8') as f:
        f.write(css_out)
    print(css_out)

    stale = [f for f in os.listdir(OUT) if f.endswith('.woff2') and f not in wanted]
    if stale:
        print('устаревшие файлы (удали вручную и обнови index.html/sw.js):', *stale, sep='\n  ', file=sys.stderr)
    print(f'итого {len(wanted)} файлов, {total / 1024:.0f} КБ', file=sys.stderr)


if __name__ == '__main__':
    main()
