#!/usr/bin/env python3
"""Сообщает поисковикам (Bing, Яндекс и др. через api.indexnow.org) об обновлении страниц сайта — протокол IndexNow.

Запуск из корня репозитория ПОСЛЕ деплоя (файл ключа должен уже отдаваться сайтом):
    python3 tools/indexnow.py              # отправить все URL из sitemap.xml
    python3 tools/indexnow.py --dry-run    # только показать запрос, без сети
Ключ — файл <32 hex>.txt в корне репозитория, внутри тот же ключ; сайт отдаёт его по https://tap.delcappuccino.kz/<ключ>.txt.
Ключ не секретный (так задумано протоколом), менять не нужно. Ответ 200/202 — принято; 403 — сайт не отдаёт файл
ключа; 422 — URL не с этого хоста; 429 — слишком часто. Только stdlib.
"""
import json, os, re, sys, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = 'tap.delcappuccino.kz'
ENDPOINT = 'https://api.indexnow.org/indexnow'


def key():
    keys = [f[:-4] for f in os.listdir(ROOT) if re.fullmatch(r'[0-9a-f]{32}\.txt', f)]
    if len(keys) != 1:
        sys.exit('indexnow: в корне должен быть ровно один файл <32 hex>.txt, найдено %d' % len(keys))
    with open(os.path.join(ROOT, keys[0] + '.txt'), encoding='utf-8') as f:
        if f.read().strip() != keys[0]:
            sys.exit('indexnow: содержимое %s.txt не совпадает с именем файла' % keys[0])
    return keys[0]


def urls():
    with open(os.path.join(ROOT, 'sitemap.xml'), encoding='utf-8') as f:
        return re.findall(r'<loc>([^<]+)</loc>', f.read())


def payload():
    k = key()
    return {'host': HOST, 'key': k, 'keyLocation': 'https://%s/%s.txt' % (HOST, k), 'urlList': urls()}


def main():
    body = payload()
    print(json.dumps(body, ensure_ascii=False, indent=1))
    if '--dry-run' in sys.argv:
        return
    req = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode('utf-8'), method='POST',
                                 headers={'Content-Type': 'application/json; charset=utf-8'})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            print('IndexNow:', r.status, '— принято')
    except urllib.error.HTTPError as e:
        sys.exit('IndexNow: %s %s' % (e.code, e.reason))
    except urllib.error.URLError as e:
        sys.exit('IndexNow: нет связи с %s — %s' % (ENDPOINT, e.reason))


if __name__ == '__main__':
    main()
