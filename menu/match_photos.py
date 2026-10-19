#!/usr/bin/env python3
"""Сопоставление фото из папки menu/menu_photos/ (скачанная папка Диска «все фото кухни») с названиями сайта.

Обходит папку рекурсивно (кухня, бар/…, десерты, десерты целые, пф и мясо), нормализует имя файла
так же, как match_names.py нормализует iiko (регистр, ё, «*», дефисы, объёмы/граммовки), плюс
«фото», «готовые», «1шт/5 шт», цифры-хвосты, скобки; «с/со» сводится к «с». Пары ищутся по точной
форме, по префиксу раздела («Соус Цезарь» ↔ «Цезарь» в Соусах), по началу названия (файл «крок мадам»
↔ сайт «Крок Мадам с копчёной индейкой», если такое начало у одной позиции) и «похоже» (difflib,
цифры должны совпадать). Среди дублей лучше: png/jpg над jfif, большее разрешение (PIL), литеральное
совпадение. Не берём: «ChatGPT Image», «1кг/1 кг», «бокс», «мякоть», «фарш».

Ручные пары — menu/name_map_overrides.json {сайт: путь|null}, накладываются поверх автоматики.
Результат — поле "drive_file" в menu/name_map.json (путь относительно menu/menu_photos/) рядом с
ключом iiko: {название_сайта: {"iiko": key|null, "drive_file": "кухня/Рибай на кости.png"|null}}.
Отчёт (спорные, ненайденные, лишние файлы) — menu/photo_map_report.md.
--listing <json> — сухой прогон по листингу Диска (title/fileSize) без файлов. Только stdlib; PIL — для разрешения.
"""
import argparse, difflib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import match_names as mn  # noqa: E402

IMG_EXT = {'.png', '.jpg', '.jpeg', '.jfif', '.webp'}
SKIP_RE = re.compile(r'chatgpt image|\b1\s*кг\b|\bбокс\b|\bмякоть\b|\bфарш\b', re.I)
NOISE_WORDS = ('фото', 'готовые', 'готовый', 'готовая', 'новое', 'новый', 'итог', 'копия', 'кусок', 'кусочек')
WHOLE_RE = re.compile(r'целы[ей]|цельн|целая|\b1\s*кг\b|\bторт\b', re.I)   # целый торт: только для раздела «Торты (целиком)»
WHOLE_SECTION = 'торты (целиком)'
EXT_RANK = {'.png': 0, '.jpg': 0, '.jpeg': 0, '.webp': 1, '.jfif': 2}
STRICT_SECTIONS = {'полуфабрикаты', 'мясо'}   # сырьё: только точное совпадение (котлеты-полуфабрикат ≠ котлеты с пюре)


def norm_file(title):
    """имя файла → форма для сравнения"""
    stem = os.path.splitext(os.path.basename(title))[0]
    s = re.sub(r'\([^)]*\)', ' ', stem)                       # скобки с пояснениями
    s = re.sub(r'\b\d+(?:[.,]\d+)?\s*(?:гр|г|шт|мл|л|кг)\b\.?', ' ', s, flags=re.I)   # 350 гр, 5 шт, 1шт, 0,2л
    s = re.sub(r'(?<=[а-яёa-z])\d+\b', ' ', s, flags=re.I)    # «цукини2»
    s = mn.norm(s)
    words = [w for w in s.split() if w not in NOISE_WORDS]
    while words and words[-1].isdigit():          # «0,33» → «0» на конце; «4 сезона» остаётся
        words.pop()
    return ' '.join('с' if w == 'со' else w for w in words)


def norm_site(name):
    s = re.sub(r'\([^)]*\)', ' ', name)
    s = mn.norm(s)
    return ' '.join('с' if w == 'со' else w for w in s.split())


def scan_folder(folder):
    """[{path (относительно folder), ext, size, w, h}] — все картинки рекурсивно"""
    out = []
    try:
        from PIL import Image
    except ImportError:
        Image = None
    for dp, _, files in os.walk(folder):
        for fn in files:
            ext = os.path.splitext(fn)[1].lower()
            if ext not in IMG_EXT:
                continue
            full = os.path.join(dp, fn)
            rec = {'path': os.path.relpath(full, folder).replace(os.sep, '/'), 'ext': ext, 'size': os.path.getsize(full), 'w': 0, 'h': 0}
            if Image:
                try:
                    with Image.open(full) as im:
                        rec['w'], rec['h'] = im.size
                except Exception:
                    pass
            out.append(rec)
    return out


def scan_listing(path):
    """листинг Диска {folder, files:[{title,fileSize,mimeType}]} → те же записи без разрешения"""
    with open(path, encoding='utf-8') as f:
        d = json.load(f)
    folder = d.get('folder') or ''
    out = []
    for it in d.get('files', []):
        t = it.get('title') or it.get('name') or ''
        ext = os.path.splitext(t)[1].lower()
        if ext in IMG_EXT:
            out.append({'path': f'{folder}/{t}' if folder else t, 'ext': ext, 'size': int(it.get('fileSize') or 0), 'w': 0, 'h': 0})
    return out


def rank(rec, how):
    return (EXT_RANK.get(rec['ext'], 3), 0 if how == 'form' else 1, 1 if '~' in rec['path'] else 0, -(rec['w'] * rec['h']), -rec['size'])


def match(site, files, cutoff=0.88):
    """site: [(раздел, имя)]; files: записи scan_*; → ({ключ: path}, report, stats); ключ — mn.site_keys (с разделом у дублей)"""
    for f in files:
        f['form'] = norm_file(f['path'])
        f['whole'] = bool(WHOLE_RE.search(f['path']))
    files = [f for f in files if f['form'] and not SKIP_RE.search(os.path.basename(f['path'])) and not SKIP_RE.search(f['form'])]

    secs_of = {}
    for sec, name in site:
        secs_of.setdefault(name, []).append(sec)
    by_key = {}                                   # ключ → (раздел, название)
    for sec, name in site:
        key = (name + mn.SEP + sec) if len(set(secs_of[name])) > 1 else name
        by_key.setdefault(key, (sec, name))
    site_forms = {name: norm_site(name) for name in secs_of}

    def index(whole):
        """индексы по файлам: целые торты отдельно от остальных"""
        forms, squash, bag = {}, {}, {}
        for f in files:
            if f['whole'] != whole:
                continue
            forms.setdefault(f['form'], []).append(f)
            squash.setdefault(f['form'].replace(' ', ''), []).append(f)
            bag.setdefault(frozenset(f['form'].split()), []).append(f)
        return forms, squash, bag, list(forms)
    IDX = {True: index(True), False: index(False)}

    def candidates(name, secs):
        plain = site_forms[name]
        cands = []
        for sec in secs:
            pref = mn.SECTION_PREFIX.get(sec.lower())
            if pref and not plain.startswith(pref + ' '):
                cands.append(norm_site(pref + ' ' + name))
        cands.append(plain)
        if name in mn.ALIASES:
            cands.append(norm_site(mn.ALIASES[name]))
        sp = mn.strip_prefix(plain)
        if sp:
            cands.append(sp)
        return list(dict.fromkeys(cands))

    def find(name, secs):
        cands = candidates(name, secs)
        whole = all(sec.lower() == WHOLE_SECTION for sec in secs)
        forms, squash, bag, form_list = IDX[whole]
        for c in cands:
            if c in forms:
                return forms[c], 'form', c
            if c.replace(' ', '') in squash:                 # «ти бон» = «тибон»
                return squash[c.replace(' ', '')], 'form', c
        if all(sec.lower() in STRICT_SECTIONS for sec in secs):
            return None, None, None
        for c in cands:
            if frozenset(c.split()) in bag:                  # те же слова в другом порядке
                return bag[frozenset(c.split())], 'bag', c
        # «похоже» (опечатки, «и с» / «и»), цифры должны совпадать
        for c in cands:
            close = difflib.get_close_matches(c, form_list, n=1, cutoff=cutoff)
            if close and mn.digits(close[0]) == mn.digits(c):
                return forms[close[0]], 'similar', close[0]
        # файл — начало названия сайта («крок мадам» ⊂ «крок мадам с копчёной индейкой», «борщ» ⊂ «борщ с говядиной…»),
        # если такое начало есть ровно у одной позиции сайта
        for c in cands:
            hits = [f for f in form_list if c.startswith(f + ' ')]
            for f in sorted(hits, key=len, reverse=True):
                owners = {n for n, sf in site_forms.items() if sf.startswith(f + ' ') or sf == f}
                if len(owners) == 1:
                    return forms[f], 'head', f
        # название сайта — начало имени файла («бургер классический» ⊂ «бургер классический с картофелем фри» наоборот),
        # если такой файл один и в названии хотя бы два слова (иначе «эспрессо» ловит «эспрессо тоник»)
        for c in cands:
            if len(c.split()) < 2:
                continue
            hits = [f for f in form_list if f.startswith(c + ' ')]
            if len(hits) == 1:
                return forms[hits[0]], 'head', hits[0]
        return None, None, None

    result, report = {}, {'literal': [], 'fuzzy': [], 'missing': [], 'ambiguous': []}
    used = set()
    for key, (sec, name) in by_key.items():
        recs, how, form = find(name, [sec])
        if not recs:
            report['missing'].append(f'{key}  [{sec}]')
            continue
        best = sorted(recs, key=lambda r: rank(r, how))[0]
        result[key] = best['path']
        used.add(best['path'])
        alts = len(recs) - 1
        tag = {'form': '', 'bag': '  (те же слова)', 'head': '  (по началу названия)', 'similar': '  (похоже)'}[how]
        if how == 'form' and norm_file(best['path']) == norm_site(name) and mn.literal(os.path.splitext(os.path.basename(best['path']))[0]) == mn.literal(name):
            report['literal'].append(key)
        else:
            report['fuzzy'].append(f'{key}  ←  {best["path"]}{tag}' + (f'  (+{alts} дубл.)' if alts else ''))
    unused = sorted(f['path'] for f in files if f['path'] not in used and f['form'] not in {norm_file(p) for p in used})
    stats = {'site': len(by_key), 'mapped': len(result), 'literal': len(report['literal']), 'fuzzy': len(report['fuzzy']),
             'missing': len(report['missing']), 'ambiguous': len(report['ambiguous']), 'files': len(files), 'unused': len(unused)}
    report['unused'] = unused
    return result, report, stats


def report_text(report, stats, source):
    L = [f'источник: {source}', f'фото: файлов {stats["files"]} (без мусора), позиций сайта {stats["site"]}, с фото {stats["mapped"]} '
         f'(буквально {stats["literal"]}, спорных {stats["fuzzy"]}), без фото {stats["missing"]}, файлов без пары {stats["unused"]}', '']
    L.append(f'## Ручные пары ({stats.get("manual", 0)}) — из name_map_overrides.json')
    L += ['  ' + x for x in report.get('manual', [])] or ['  —']
    L.append('')
    L.append(f'## Спорные ({stats["fuzzy"]}) — совпало не буквально: сайт ← файл')
    L += ['  ' + x for x in report['fuzzy']] or ['  —']
    L.append('')
    L.append(f'## Неоднозначные ({stats.get("ambiguous", 0)}) — одно название в разных разделах ведёт к разным файлам')
    L += ['  ' + x for x in report.get('ambiguous', [])] or ['  —']
    L.append('')
    L.append(f'## Без фото ({stats["missing"]})')
    L += ['  ' + x for x in report['missing']] or ['  —']
    L.append('')
    L.append(f'## Файлы без пары ({stats["unused"]}) — не похожи ни на одну позицию сайта')
    L += ['  ' + x for x in report['unused']] or ['  —']
    return '\n'.join(L) + '\n'


def apply_overrides(result, report, stats, overrides_path, photos_dir=None, listing_names=None):
    """menu/name_map_overrides.json {сайт: путь|null} поверх автоматики; путь проверяется по папке (или листингу)"""
    if not overrides_path or not os.path.isfile(overrides_path):
        return
    with open(overrides_path, encoding='utf-8') as f:
        over = {k: v for k, v in json.load(f).items() if not k.startswith('_')}
    manual = []
    for name, path in over.items():
        if path is None:
            if name in result:
                del result[name]
                manual.append(f'{name}  ⇒ фото снято')
            continue
        exists = (os.path.isfile(os.path.join(photos_dir, path)) if photos_dir else (path in (listing_names or set())))
        if not exists:
            manual.append(f'{name}  ←  {path}  — НЕТ ТАКОГО ФАЙЛА, пропущено')
            continue
        was = result.get(name)
        result[name] = path
        manual.append(f'{name}  ←  {path}' + (f'  (было: {was})' if was and was != path else ''))
    report['manual'] = manual
    stats['manual'] = sum(1 for m in manual if 'пропущено' not in m)
    stats['mapped'] = len(result)
    report['missing'] = [m for m in report['missing'] if m.split('  [')[0] not in result]
    report['unused'] = [u for u in report['unused'] if u not in set(result.values())]
    stats['missing'], stats['unused'] = len(report['missing']), len(report['unused'])


def load_map(path):
    if not os.path.isfile(path):
        return {}
    with open(path, encoding='utf-8') as f:
        m = json.load(f)
    # старый формат {site: key} → новый {site: {iiko, drive_file}}
    return {k: (v if isinstance(v, dict) else {'iiko': v, 'drive_file': None}) for k, v in m.items()}


def main(argv=None):
    ap = argparse.ArgumentParser(description='фото из menu/menu_photos/ ↔ названия сайта → name_map.json[drive_file]')
    ap.add_argument('--menu', default=os.path.join(ROOT, 'index.html'))
    ap.add_argument('--photos', default=os.path.join(HERE, 'menu_photos'), help='папка с исходниками (рекурсивно)')
    ap.add_argument('--listing', help='сухой прогон по листингу Диска (json с files[].title) вместо папки')
    ap.add_argument('--map', default=os.path.join(HERE, 'name_map.json'))
    ap.add_argument('--report', default=os.path.join(HERE, 'photo_map_report.md'))
    ap.add_argument('--overrides', default=os.path.join(HERE, 'name_map_overrides.json'), help='ручные пары поверх автоматики')
    ap.add_argument('--dry-run', action='store_true', help='только отчёт, name_map.json не писать')
    ap.add_argument('--cutoff', type=float, default=0.88)
    a = ap.parse_args(argv)
    if a.listing:
        files, source = scan_listing(a.listing), f'листинг {a.listing}'
    else:
        if not os.path.isdir(a.photos):
            sys.stderr.write(f'нет папки {a.photos}\n')
            return 2
        files, source = scan_folder(a.photos), f'папка {os.path.relpath(a.photos, ROOT)}'
    result, report, stats = match(mn.site_names(a.menu), files, a.cutoff)
    apply_overrides(result, report, stats, a.overrides, photos_dir=None if a.listing else a.photos,
                    listing_names={f['path'] for f in files})
    txt = report_text(report, stats, source)
    if not a.dry_run:
        m = load_map(a.map)
        for name in set(m) | set(result):
            m.setdefault(name, {'iiko': None, 'drive_file': None})['drive_file'] = result.get(name)
        m = {k: v for k, v in m.items() if v.get('iiko') or v.get('drive_file')}
        with open(a.map, 'w', encoding='utf-8') as f:
            json.dump(m, f, ensure_ascii=False, indent=1)
            f.write('\n')
        if a.report:
            with open(a.report, 'w', encoding='utf-8') as f:
                f.write('# Сопоставление фото с названиями сайта\n\nСобрано `menu/match_photos.py`; правится руками в `name_map.json` (поле drive_file).\n\n' + txt)
    sys.stdout.write(txt)
    return 0


if __name__ == '__main__':
    sys.exit(main())
