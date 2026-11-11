#!/usr/bin/env python3
"""Ставит в sw.js версию кэша = хэш содержимого index.html и имена файлов кода главной в PRECACHE.

Запуск из корня репозитория после любой правки index.html:  python3 tools/sw_version.py
С ключом --check только сравнивает и выходит с кодом 1, если версия или имена устарели (для тестов/CI).

Зачем: браузер переустанавливает service worker только когда меняются байты sw.js; смена VERSION
заставляет новый SW заново скачать оболочку (PRECACHE) и выбросить старый кэш оболочки.
Код главной (11.11.2026) — отдельные файлы assets/home.<хэш>.js и assets/site.<хэш>.js (собирает tools/seo_jsonld.py,
теги — в index.html): их имена в PRECACHE берутся из тегов index.html, чтобы меню офлайн работало, как с кодом в странице.
Только stdlib.
"""
import hashlib, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, 'index.html')
SW = os.path.join(ROOT, 'sw.js')
PRECACHED_JS = ('home', 'site')     # файлы кода главной в оболочке service worker


def index_hash():
    with open(INDEX, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()[:10]


def code_files():
    """{'home': 'assets/home.<хэш>.js', …} — по тегам <script src="/assets/…" defer> в index.html"""
    with open(INDEX, encoding='utf-8') as f:
        html = f.read()
    out = {}
    for name in PRECACHED_JS:
        found = re.findall(r'<script src="/(assets/%s\.[0-9a-f]{8}\.js)" defer></script>' % name, html)
        if len(found) != 1:
            sys.exit('в index.html нужен ровно один <script src="/assets/%s.<хэш>.js" defer> (tools/seo_jsonld.py)' % name)
        out[name] = found[0]
    return out


def current():
    with open(SW, encoding='utf-8') as f:
        src = f.read()
    m = re.search(r"var VERSION = '([^']*)';", src)
    if not m:
        sys.exit('в sw.js нет строки var VERSION = \'…\';')
    return src, m.group(1)


def with_files(src, files):
    """PRECACHE с текущими именами файлов кода (в sw.js — ровно по одной строке на файл)"""
    for name, path in files.items():
        rx = re.compile(r"'assets/%s\.[0-9a-f]{8}\.js'" % name)
        if len(rx.findall(src)) != 1:
            sys.exit("в PRECACHE sw.js нужна ровно одна строка 'assets/%s.<хэш>.js'" % name)
        src = rx.sub("'%s'" % path, src)
    return src


def main():
    src, old = current()
    new = index_hash()
    want = with_files(src, code_files())
    if '--check' in sys.argv:
        files_ok = want == src
        print('sw.js VERSION', old, '| index.html', new, '| ' + ('ok' if old == new else 'УСТАРЕЛА') +
              ('' if files_ok else ' | PRECACHE: имена файлов кода устарели'))
        sys.exit(0 if old == new and files_ok else 1)
    if old == new and want == src:
        print('sw.js уже актуален:', new)
        return
    with open(SW, 'w', encoding='utf-8') as f:
        f.write(want.replace("var VERSION = '%s';" % old, "var VERSION = '%s';" % new, 1))
    print('sw.js VERSION:', old, '→', new, '' if want == src else '(и имена файлов кода в PRECACHE)')


if __name__ == '__main__':
    main()
