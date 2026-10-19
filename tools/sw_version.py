#!/usr/bin/env python3
"""Ставит в sw.js версию кэша = хэш содержимого index.html.

Запуск из корня репозитория после любой правки index.html:  python3 tools/sw_version.py
С ключом --check только сравнивает и выходит с кодом 1, если версия устарела (для тестов/CI).

Зачем: браузер переустанавливает service worker только когда меняются байты sw.js; смена VERSION
заставляет новый SW заново скачать оболочку (PRECACHE) и выбросить старый кэш оболочки.
Только stdlib.
"""
import hashlib, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, 'index.html')
SW = os.path.join(ROOT, 'sw.js')


def index_hash():
    with open(INDEX, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()[:10]


def current():
    with open(SW, encoding='utf-8') as f:
        src = f.read()
    m = re.search(r"var VERSION = '([^']*)';", src)
    if not m:
        sys.exit('в sw.js нет строки var VERSION = \'…\';')
    return src, m.group(1)


def main():
    src, old = current()
    new = index_hash()
    if '--check' in sys.argv:
        print('sw.js VERSION', old, '| index.html', new, '| ' + ('ok' if old == new else 'УСТАРЕЛА'))
        sys.exit(0 if old == new else 1)
    if old == new:
        print('sw.js уже актуален:', new)
        return
    with open(SW, 'w', encoding='utf-8') as f:
        f.write(src.replace("var VERSION = '%s';" % old, "var VERSION = '%s';" % new, 1))
    print('sw.js VERSION:', old, '→', new)


if __name__ == '__main__':
    main()
