#!/usr/bin/env python3
"""Сопоставление названий блюд на сайте (index.html, n:'…') с выгрузкой iiko → menu/name_map.json.

Имена в iiko с хвостами («Чай Груша-мята 0,4л н», «Рис |--> ВЫНОС», «Пицца Маргарита*»), поэтому
сравниваем нормализованные формы, а у позиций сайта ещё пробуем префикс раздела
(«Маргарита» в разделе «Пицца» = «Пицца Маргарита»). Служебные группы iiko исключаем.
У напитков с несколькими объёмами берём первую запись с описанием и фото.

Ключ карточки: название сайта; если название стоит в нескольких разделах — «Название @ Раздел» (site_keys).
Вывод: name_map.json {ключ: {"iiko": key, "iiko_also": [ключи двойников], "drive_file": …}}
(drive_file из существующей карты сохраняется; его ставит match_photos.py) и отчёт (stdout / --report):
буквальные, спорные (совпало не буквально — показать владельцу), неоднозначные и не найденные.
Только стандартная библиотека.
"""
import argparse, difflib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EXCLUDE_GROUPS = ('вольт', 'вынос', 'стафф', 'агрегатор', 'категория без имени')
# раздел сайта → слово-префикс, которое iiko ставит перед названием
SECTION_PREFIX = {
    'пицца': 'пицца', 'паста фреш': 'паста', 'десерты': 'десерт', 'торты (целиком)': 'торт',
    'авторские чаи': 'чай', 'листовые чаи': 'чай', 'салаты': 'салат', 'супы': 'суп', 'боулы': 'боул',
    'смузи': 'смузи', 'лимонады': 'лимонад', 'милкшейки': 'милкшейк', 'глинтвейн б/а': 'глинтвейн',
    'раф': 'раф', 'фреши': 'фреш', 'ice tea': 'айс ти', 'завтраки': 'завтрак', 'сладкие завтраки': 'завтрак',
    'соусы': 'соус', 'хлеба': 'хлеб',
}
VOL_RE = re.compile(r'\b\d+[.,]?\d*\s*(?:мл|л|ml|l|гр|г|кг)\b|\b0[.,]\d+\b', re.I)
PREFIX_WORDS = ('пицца', 'паста', 'десерт', 'торт', 'чай', 'соус', 'лимонад', 'смузи', 'милкшейк', 'глинтвейн',
                'раф', 'фреш', 'айс ти', 'суп', 'салат', 'боул', 'сок', 'морс')
STOP_WORDS = ('доп', 'чашка', 'чайник', 'н')
# разделы, где пара засчитывается только с позицией iiko, начинающейся с этого слова (целый торт ≠ кусочек десерта)
SECTION_REQUIRE = {'торты (целиком)': 'торт'}
# явные пары сайт → форма iiko (после norm), где нормализация не дотягивается; показываются как спорные
ALIASES = {
    'Картофель фри': 'фри', 'Эспрессо / Доппио': 'эспрессо', 'Четыре сезона': 'пицца 4 сезона',
    'Наполеон': 'десерт наполеон классический', 'Картошка': 'пирожное картошка',
    'Кесадилья с курицей': 'кесадилья', 'Клаб сэндвич с курицей и картофелем фри': 'клаб сэндвич с курицей',
    'Фраппучино: карамель, шоколад': 'фраппучино', 'Ice Американо': 'ice americano',
    'Бамбл кофе на соке / на фреше': 'бамбл кофе', 'Чай по-казахски (нават, иримшик)': 'чай по казахски',
    'Персиковый': 'айс ти персик', 'Borjomi glass': 'borjomi', 'Вода Del Cappuccino без газа': 'вода del cappuccino still water',
    'Декаф': 'decaf', 'Дзадзики': 'дзадзыки соус',
}


def norm(s):
    s = str(s or '').lower().replace('ё', 'е')
    s = s.split('|')[0]                      # «|-->ВЫНОС» и всё после «|»
    s = s.replace('*', ' ')
    s = VOL_RE.sub(' ', s)                   # 0,3л / 0.2л / 400мл / 0,4
    s = re.sub(r'[-–—/+]', ' ', s)           # Груша-мята = Груша мята
    s = re.sub(r'[^\w\s]', ' ', s)
    s = ' '.join(w for w in s.split() if w not in STOP_WORDS)   # «доп», «чашка», «чайник», одиночное «н»
    s = re.sub(r'^к ', '', s)                 # «К Десерт Медовик» — кондитерский цех (org other)
    s = re.sub(r'\bбаклажана\b', 'баклажан', s)
    s = re.sub(r'\bпо\s+казахски\b', 'по казахски', s)
    return re.sub(r'\s+', ' ', s).strip()


def literal(s):
    """«буквально»: только звёздочка, хвост «|-->ВЫНОС», регистр и пробелы"""
    return re.sub(r'\s+', ' ', str(s or '').split('|')[0].replace('*', '').lower().replace('ё', 'е')).strip()


def site_names(index_html):
    """[(раздел, название)] в порядке появления по всем массивам меню"""
    with open(index_html, encoding='utf-8') as f:
        s = f.read()
    out, seen = [], set()
    for m in re.finditer(r"\{t:'([^']*)'[^\[\]]*?items:\[", s):
        sec, i, depth, j = m.group(1), m.end(), 1, m.end()
        while depth:
            depth += (s[j] == '[') - (s[j] == ']')
            j += 1
        for im in re.finditer(r"\{n:'((?:[^'\\]|\\.)*)'", s[i:j - 1]):
            n = im.group(1).replace("\\'", "'")
            if (sec, n) not in seen:
                seen.add((sec, n))
                out.append((sec, n))
    return out


SEP = ' @ '


def site_keys(index_html):
    """[(ключ, раздел, название)] в порядке меню: уникальное название — ключ = название;
    название в нескольких разделах — свой ключ на раздел: «Название @ Раздел» (ровно t секции)"""
    pairs = site_names(index_html)
    secs = {}
    for sec, n in pairs:
        secs.setdefault(n, []).append(sec)
    return [((n + SEP + sec) if len(set(secs[n])) > 1 else n, sec, n) for sec, n in pairs]


def key_name(key):
    """«Медовик @ Торты (целиком)» → «Медовик»"""
    return key.split(SEP, 1)[0]


def excluded(group):
    g = str(group or '').lower()
    return any(x in g for x in EXCLUDE_GROUPS)


def rank(it, level=0):
    """лучшая запись среди дублей: с описанием и фото → с фото → с описанием → остальные; потом org cafe,
    уровень совпадения (точная форма → без слова-префикса → те же слова), без «|-->ВЫНОС», не чайник"""
    n = it['name'].lower()
    return (0 if it.get('description') and it.get('photo') else 1 if it.get('photo') else 2 if it.get('description') else 3,
            0 if (it.get('org') or 'cafe') == 'cafe' else 1, level, 1 if '|' in n else 0, 1 if 'чайник' in n else 0)


def strip_prefix(form):
    """«пицца маргарита» → «маргарита», «шрирача соус» → «шрирача» (одно слово-префикс спереди или сзади)"""
    for w in PREFIX_WORDS:
        if form.startswith(w + ' '):
            return form[len(w) + 1:]
        if form.endswith(' ' + w):
            return form[:-len(w) - 1]
    return None


def digits(s):
    return re.findall(r'\d+', s)


def match(index_html, export_path, cutoff=0.9):
    with open(export_path, encoding='utf-8') as f:
        data = json.load(f)
    items = [it for it in data['items'] if it.get('name') and it.get('key')]
    revision = data.get('menu_revision')
    usable = [it for it in items if not excluded(it.get('group'))]
    forms, loose, bag = {}, {}, {}        # точная форма / без слова-префикса / набор слов
    for it in usable:
        f = norm(it['name'])
        forms.setdefault(f, []).append(it)
        sp = strip_prefix(f)
        if sp:
            loose.setdefault(sp, []).append(it)
        bag.setdefault(frozenset(f.split()), []).append(it)
    LEVEL = {'form': 0, 'loose': 1, 'bag': 2}

    def find(sec, name):
        """→ (запись iiko | None, как нашли)"""
        it, how = find_any(sec, name)
        req = SECTION_REQUIRE.get(sec.lower())
        if it and req and not norm(it['name']).startswith(req + ' '):
            return None, None
        return it, how

    def find_any(sec, name):
        plain = norm(name)
        pref = SECTION_PREFIX.get(sec.lower())
        cands = ([norm(pref + ' ' + name)] if pref and not plain.startswith(pref + ' ') else []) + [plain]
        if name in ALIASES:
            cands.insert(0, ALIASES[name])
        for c in cands:
            pool = [(it, 'form') for it in forms.get(c, [])] + [(it, 'loose') for it in loose.get(c, [])] + \
                   [(it, 'bag') for it in bag.get(frozenset(c.split()), [])]
            if pool:
                it, how = min(pool, key=lambda p: rank(p[0], LEVEL[p[1]]))
                return it, how
        for c in cands:
            close = difflib.get_close_matches(c, list(forms), n=1, cutoff=cutoff)
            if close and digits(close[0]) == digits(c):      # «5–6 персон» ≠ «6-8 персон»
                return min(forms[close[0]], key=rank), 'similar'
        return None, None

    def twins(it):
        """записи-двойники того же блюда с КБЖУ (та же форма, другой ключ): у кондитерской «К Десерт Медовик»
        есть per_100g, у кофейной «Десерт Медовик» — описание и фото; сборка дополняет пустые поля из двойников"""
        f = norm(it['name'])
        return [o for o in forms.get(f, []) if o['key'] != it['key'] and (o.get('per_100g') or o.get('per_portion'))]

    # ключ карточки — с разделом для названий из нескольких разделов («Классический @ Раф»), поэтому
    # каждая пара ищется в своём разделе; неоднозначности по разделам больше нет
    result, report = {}, {'literal': [], 'fuzzy': [], 'missing': [], 'ambiguous': []}
    seen = set()
    for key, sec, name in site_keys(index_html):
        if key in seen:
            continue
        seen.add(key)
        hit, how = find(sec, name)
        if not hit:
            report['missing'].append(f'{key}  [{sec}]')
            continue
        also = twins(hit)
        result[key] = {'iiko': hit['key'], 'iiko_also': [t['key'] for t in also]} if also else hit['key']
        if how == 'form' and literal(hit['name']) == literal(name):
            report['literal'].append(key)
        else:
            tag = {'form': '', 'loose': '', 'bag': '  (те же слова)', 'similar': '  (похоже)'}[how]
            org = f' org={hit["org"]}' if hit.get('org') and hit['org'] != 'cafe' else ''
            tag += f'  +двойник: {", ".join(t["name"].strip() for t in also)}' if also else ''
            report['fuzzy'].append(f'{key}  [{sec}]  ←  {hit["name"].strip()}  [{hit.get("group")}{org}]{tag}')
    stats = {'site': len(seen), 'mapped': len(result), 'literal': len(report['literal']),
             'fuzzy': len(report['fuzzy']), 'missing': len(report['missing']), 'ambiguous': 0,
             'iiko_total': len(items), 'iiko_usable': len(usable), 'iiko_excluded': len(items) - len(usable),
             'iiko_other': sum(1 for it in items if it.get('org') == 'other'), 'revision': revision,
             'twins': sum(1 for v in result.values() if isinstance(v, dict))}
    return result, report, stats


def report_text(report, stats):
    L = [f'сопоставление: позиций сайта {stats["site"]}, сопоставлено {stats["mapped"]} '
         f'(буквально {stats["literal"]}, спорных {stats["fuzzy"]}), не нашлось {stats["missing"]}; '
         f'iiko: всего {stats["iiko_total"]} (org other: {stats.get("iiko_other", 0)}), после исключения служебных групп {stats["iiko_usable"]}; '
         f'позиций с двойниками (iiko_also): {stats.get("twins", 0)}; menu_revision: {json.dumps(stats.get("revision"), ensure_ascii=False)}', '']
    L.append(f'## Спорные ({stats["fuzzy"]}) — совпало не буквально, показать владельцу: сайт ← iiko')
    L += ['  ' + x for x in report['fuzzy']] or ['  —']
    L.append('')
    L.append(f'## Не нашлось ({stats["missing"]})')
    L += ['  ' + x for x in report['missing']] or ['  —']
    return '\n'.join(L) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser(description='сайт ↔ iiko: name_map.json')
    ap.add_argument('--menu', default=os.path.join(ROOT, 'index.html'))
    ap.add_argument('--iiko', default=os.path.join(HERE, 'iiko-export.json'))
    ap.add_argument('--out', default=os.path.join(HERE, 'name_map.json'))
    ap.add_argument('--report', default=os.path.join(HERE, 'name_map_report.md'))
    ap.add_argument('--cutoff', type=float, default=0.9, help='порог похожести difflib для «похоже»')
    a = ap.parse_args(argv)
    result, report, stats = match(a.menu, a.iiko, a.cutoff)
    old = {}
    if os.path.isfile(a.out):
        with open(a.out, encoding='utf-8') as f:
            old = json.load(f)
    out = {}
    live = {k for k, _, _ in site_keys(a.menu)}          # ключи снятых/переименованных позиций из старой карты не тащим
    for name in sorted((set(old) & live) | set(result), key=lambda n: (n not in result, n)):
        v = result.get(name)
        rec = dict(v) if isinstance(v, dict) else {'iiko': v}
        prev = old.get(name)
        drive = prev.get('drive_file') if isinstance(prev, dict) else None
        if rec.get('iiko') or drive:
            out[name] = {'iiko': rec.get('iiko'), **({'iiko_also': rec['iiko_also']} if rec.get('iiko_also') else {}), 'drive_file': drive}
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write('\n')
    txt = report_text(report, stats)
    if a.report:
        with open(a.report, 'w', encoding='utf-8') as f:
            f.write('# Сопоставление названий сайта и iiko\n\nСобрано `menu/match_names.py`; правится руками в `name_map.json`, если владелец поправит.\n\n' + txt)
    sys.stdout.write(txt)
    return 0


if __name__ == '__main__':
    sys.exit(main())
