#!/usr/bin/env python3
"""Сопоставление названий блюд на сайте (index.html, n:'…') с выгрузкой iiko → menu/name_map.json.

Имена в iiko с хвостами («Чай Груша-мята 0,4л н», «Рис |--> ВЫНОС», «Пицца Маргарита*»), поэтому
сравниваем нормализованные формы, а у позиций сайта ещё пробуем префикс раздела
(«Маргарита» в разделе «Пицца» = «Пицца Маргарита»). Служебные группы iiko исключаем.
Среди дублей одного названия (19 внешних меню) предпочитаем org=cafe, группу/меню, близкие к разделу сайта,
точную форму, запись с составом в ТТК (--ttk), потом с описанием и фото. Поле menus [{id, name}] у позиции
(появится в перевыгрузке) учитывается, если есть: позиция только в служебных меню исключается, название меню
участвует в близости к разделу; без поля работаем по group.

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
DEPRECATED = ('не исп',)      # «Десерты не использовать папку»: позиции не продаются, но техкарты живые — годятся как двойники
BULK_RE = re.compile(r'(?<![\d.,])[1-9]\d*(?:[.,]\d+)?\s*л\b', re.I)   # «Лимонад Мохито 1л», «морс 2,2 л» — объём на компанию, не порция
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
STOP_WORDS = ('доп', 'чашка', 'чайник', 'н', 'зал', 'дс', 'витрина', 'готовые', 'чоко', 'в2в', 'b2b', 'п', 'ф', 'пф', 'магазин')
PF_RE = re.compile(r'п/ф|\bпф\b|витрина|фасовк', re.I)      # позиция-полуфабрикат по имени
# разделы, где пара засчитывается только с подходящей позицией iiko: целый торт ≠ кусочек десерта,
# замороженный полуфабрикат ≠ готовое блюдо, сырое мясо ≠ стейк с гарниром
SECTION_REQUIRE = {
    'торты (целиком)': lambda it: 'целый' in it['name'].lower() or (bool(re.search(r'\bторт|\b1[0-9]{3}\s*гр|\b1[,.]\d+\s*кг', it['name'].lower()))
                                                                     and ((it.get('portion') or {}).get('value') or 0) >= 600),
    'полуфабрикаты': lambda it: 'полуфабрикат' in str(it.get('group') or '').lower() or bool(PF_RE.search(it['name'])) or
                               bool(re.search(r'\d\s*шт\b', it['name'].lower())),
    'мясо': lambda it: 'мясо' in str(it.get('group') or '').lower(),
}
RAW_SECTIONS = ('полуфабрикаты', 'мясо')
# приоритет меню при дублях (поле menus, перевыгрузка v3, 19.10.2026): чем раньше — тем лучше; меню-копии — в конец
MENU_PRIORITY = ('dc-bakery site', 'starter меню', 'меню для интеграции', 'freedom sr - del capppuccino')
MENU_PRIORITY_BAKERY = ('dc-bakery site', 'del capppuccino жандосова кондитерка kwaaka') + MENU_PRIORITY[1:]
BAKERY_SECTIONS = ('полуфабрикаты', 'торты (целиком)', 'мясо')
MENU_LAST = ('копия', 'не трогать', 'не рабочий', 'подтягивание счета')
# явные пары сайт → форма iiko (после norm), где нормализация не дотягивается; показываются как спорные
ALIASES = {
    'Картофель фри': 'фри', 'Эспрессо / Доппио': 'эспрессо', 'Четыре сезона': 'пицца 4 сезона',
    'Наполеон': 'десерт наполеон классический', 'Картошка': 'пирожное картошка',
    'Кесадилья с курицей': 'кесадилья', 'Клаб сэндвич с курицей и картофелем фри': 'клаб сэндвич с курицей',
    'Фраппучино: карамель, шоколад': 'фраппучино', 'Ice Американо': 'ice americano',
    'Бамбл кофе на соке / на фреше': 'бамбл кофе', 'Чай по-казахски (нават, иримшик)': 'чай по казахски',
    'Персиковый': 'айс ти персик', 'Borjomi glass': 'borjomi', 'Вода Del Cappuccino без газа': 'вода del cappuccino still water',
    'Декаф': 'decaf', 'Дзадзики': 'дзадзыки соус',
    # выгрузка 19.10.2026 (1345 позиций): ключи с разделом — для названий из нескольких разделов
    'Котлеты говяжьи': 'котлеты гов', 'Манты с говядиной': 'манты с рубленой говядиной',
    'Манты с рубленой говядиной и тыквой': 'манты с рубленой говядиной', 'Самса с говядиной @ Полуфабрикаты': 'самса с говядиной тыквой',
    'Мини-самса из пельменей': 'запеченная мини самса', 'Сырники классические @ Полуфабрикаты': 'сырники классика',
    'Мякоть': 'мякоть говядины постная', 'Фарш': 'фарш говяжий постный', 'Рибай': 'рибай стейк', 'Ти-бон': 'ти бон стейк',
    'Борщ с говядиной и бородинским хлебом': 'борщ', 'Чучвара (пельмени с говядиной)': 'чучвара на томатной основе',
    'Крок Мадам с копчёной индейкой': 'крок мадам с индейкой', 'Мини-панкейки': 'мини панкейки со сметаной',
    'Курица терияки с рисом': 'курица терияки', 'Курица карри с рисом и лепёшкой': 'курица карри c рисом и пито лепешкой',
    'Картофельные драники с лососем и соусом голландез': 'драники картофельные с лососеми соусом голландез',
    'Вафли из цукини с малосольным лососем': 'вафли из цукини со слабосоленным лососем',
    'Облепиха-мёд-апельсин': 'чай облепиховый', 'Микс гриль на 5–6 персон': 'микс гриль на 6 8 персон',
    'Бешбармак на 4–5 персон (только по предзаказу)': 'бешбармак на 4 5 персон',
    'Куырдак на 4–5 персон (только по предзаказу)': 'куырдак на 4 5 персон',
    'Меренговый рулет @ Торты (целиком)': 'меренговый рулет целый', 'Фисташковый рулет @ Торты (целиком)': 'фисташковый рулет целый',
    'Чизкейк по-казахски @ Торты (целиком)': 'десерт чизкейк по казахски целый', 'Чизкейк испанский': 'десерт чизкейк испанский целый',
    'Gracio: вишня, яблоко, апельсин': 'сок gracio premium', 'Salam Premium Cola can': 'salam cola',
    'AVA lemonade citrus': 'ava lemonade citron cun', 'Ice матча малина тоник': 'айс матча малина тоник',
    'Сырники с иримшиком': 'сырники с иримшик',
}


def norm(s):
    s = str(s or '').lower().replace('ё', 'е')
    s = s.split('|')[0]                      # «|-->ВЫНОС» и всё после «|»
    s = s.replace('*', ' ')
    s = VOL_RE.sub(' ', s)                   # 0,3л / 0.2л / 400мл / 0,4
    s = re.sub(r'\b\d+\s*шт\b', ' ', s)     # «Котлеты куриные 4 шт», «Багет 1шт»
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


def site_vols(index_html):
    """{ключ: vol} — объём/вес позиции как на сайте («375 мл», «500 гр», «200/300/400 мл»)"""
    with open(index_html, encoding='utf-8') as f:
        s = f.read()
    secs = {}
    for sec, n in site_names(index_html):
        secs.setdefault(n, []).append(sec)
    out = {}
    for m in re.finditer(r"\{t:'([^']*)'[^\[\]]*?items:\[", s):
        sec, i, depth, j = m.group(1), m.end(), 1, m.end()
        while depth:
            depth += (s[j] == '[') - (s[j] == ']')
            j += 1
        for im in re.finditer(r"\{n:'((?:[^'\\]|\\.)*)'([^{}]*)\}", s[i:j - 1]):
            n = im.group(1).replace("\\'", "'")
            v = re.search(r"vol:'([^']*)'", im.group(2))
            key = (n + SEP + sec) if len(set(secs.get(n, []))) > 1 else n
            if v and key not in out:
                out[key] = v.group(1)
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


def service(name):
    g = str(name or '').lower()
    return any(x in g for x in EXCLUDE_GROUPS)


def menu_names(it):
    """названия меню из поля menus [{id, name}] (перевыгрузка); без поля — []"""
    if not isinstance(it, dict):
        return []
    return [str(m.get('name') or '') for m in (it.get('menus') or []) if isinstance(m, dict)]


def excluded(group, it=None):
    """служебная группа; с полем menus — ещё и позиция, которая есть только в служебных меню"""
    if service(group):
        return True
    menus = menu_names(it)
    return bool(menus) and all(service(m) for m in menus)


GENERIC = ('для', 'без', 'или', 'блюда', 'блюдо', 'напитки', 'меню', 'позиции', 'новинки', 'зал')


def words(s):
    return {w for w in norm(s).split() if len(w) >= 3 and w not in GENERIC}


def same_word(a, b):
    """«дополнения» ~ «дополнительно», «десерты» ~ «десерт»: равны или общее начало в 5 букв"""
    return a == b or (len(a) >= 5 and len(b) >= 5 and a[:5] == b[:5])


def affinity(sec, it):
    """0 — группа iiko или одно из меню позиции пересекается словами с разделом сайта (или его префиксом), иначе 1"""
    sw = words(sec) | ({SECTION_PREFIX[sec.lower()]} if sec.lower() in SECTION_PREFIX else set())
    for g in [it.get('group')] + menu_names(it):
        if any(same_word(a, b) for a in sw for b in words(g)):
            return 0
    return 1


def menu_score(it, sec=''):
    """0..len(prio) — место лучшего меню позиции в списке приоритетов; без поля menus — нейтрально;
    только меню-копии / нерабочие — последними"""
    menus = [m.lower() for m in menu_names(it)]
    if not menus:
        return 5
    prio = MENU_PRIORITY_BAKERY if sec.lower() in BAKERY_SECTIONS else MENU_PRIORITY
    best = min((prio.index(m) for m in menus if m in prio), default=None)
    if best is not None:
        return best
    return 9 if all(any(x in m for x in MENU_LAST) for m in menus) else 5


PIECES_RE = re.compile(r'(\d+)\s*шт', re.I)


def pieces_mismatch(it, vol):
    """1 — в имени iiko «3 шт», а на сайте «1 шт» (Самса с курицей зал ≠ Самса с курицей 3 шт дс)"""
    n = PIECES_RE.findall(it['name'])
    v = PIECES_RE.findall(str(vol or ''))
    return 1 if n and v and not set(n) & set(v) else 0


def rank(it, level=0, sec='', comp=frozenset(), cand=0, vol=None):
    """лучшая запись среди дублей: не из папки «не использовать» → не «ЧОКО» → не полуфабрикат (вне разделов сырья) → штуки как на сайте → (в разделах сырья) есть техкарта → меню по приоритету (menu_score) → org cafe → группа/меню близки к разделу сайта → не литровый объём →
    форма с префиксом раздела раньше плоской → уровень совпадения (точная форма → без слова-префикса → те же слова) → без «|-->ВЫНОС» → есть состав в ТТК →
    с описанием и фото → с фото → с описанием → не чайник"""
    n = it['name'].lower()
    raw = sec.lower() in RAW_SECTIONS
    return (1 if any(x in str(it.get('group') or '').lower() for x in DEPRECATED) else 0,
            1 if n.lstrip(' *').startswith('чоко') else 0,            # «ЧОКО …» — карточки другого бренда, только если своей нет
            0 if raw else (1 if (PF_RE.search(n) or 'полуфабрикат' in str(it.get('group') or '').lower()) else 0),
            pieces_mismatch(it, vol), (1 if raw and it['key'] not in comp else 0), menu_score(it, sec), 0 if (it.get('org') or 'cafe') == 'cafe' else 1, affinity(sec, it), 1 if BULK_RE.search(n) else 0, cand, level,
            1 if '|' in n else 0,
            0 if it['key'] in comp else 1,
            0 if it.get('description') and it.get('photo') else 1 if it.get('photo') else 2 if it.get('description') else 3,
            1 if 'чайник' in n else 0)


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


def ttk_keys(ttk_path):
    """ключи позиций, у которых в выгрузке ТТК есть состав (при дублях — предпочитаем их)"""
    if not ttk_path or not os.path.isfile(ttk_path):
        return frozenset()
    with open(ttk_path, encoding='utf-8') as f:
        data = json.load(f)
    items = data.get('items', []) if isinstance(data, dict) else data
    return frozenset(str(it['key']) for it in items if isinstance(it, dict) and it.get('key') and it.get('composition'))


def match(index_html, export_path, cutoff=0.9, ttk_path=None):
    with open(export_path, encoding='utf-8') as f:
        data = json.load(f)
    items = [it for it in data['items'] if it.get('name') and it.get('key')]
    revision = data.get('menu_revision')
    comp = ttk_keys(ttk_path)
    usable = [it for it in items if not excluded(it.get('group'), it)]
    forms, loose, bag = {}, {}, {}        # точная форма / без слова-префикса / набор слов
    for it in usable:
        f = norm(it['name'])
        forms.setdefault(f, []).append(it)
        sp = strip_prefix(f)
        if sp:
            loose.setdefault(sp, []).append(it)
        bag.setdefault(frozenset(f.split()), []).append(it)
    LEVEL = {'form': 0, 'loose': 1, 'bag': 2}

    vols = site_vols(index_html)

    def find(sec, name, key=None):
        """→ (запись iiko | None, как нашли); в разделах из SECTION_REQUIRE кандидаты фильтруются"""
        req = SECTION_REQUIRE.get(sec.lower())
        vol = vols.get(key or name)
        plain = norm(name)
        pref = SECTION_PREFIX.get(sec.lower())
        cands = ([norm(pref + ' ' + name)] if pref and not plain.startswith(pref + ' ') else []) + [plain]
        alias = ALIASES.get(key) or ALIASES.get(name)
        if alias:
            cands.insert(0, alias)
        ok = (lambda it: req(it)) if req else (lambda it: True)
        pool = []                                        # все формы сразу: «ЧОКО Соус Кетчуп» (с префиксом) не важнее «Кетчуп»
        for ci, c in enumerate(cands):
            pool += [(it, 'form', ci) for it in forms.get(c, []) if ok(it)] + [(it, 'loose', ci) for it in loose.get(c, []) if ok(it)] + \
                    [(it, 'bag', ci) for it in bag.get(frozenset(c.split()), []) if ok(it)]
        if pool:
            it, how, _ = min(pool, key=lambda p: rank(p[0], LEVEL[p[1]], sec, comp, p[2], vol))
            return it, how
        for c in cands:
            close = difflib.get_close_matches(c, list(forms), n=1, cutoff=cutoff)
            if close and digits(close[0]) == digits(c):      # «5–6 персон» ≠ «6-8 персон»
                pool = [it for it in forms[close[0]] if ok(it)]
                if pool:
                    return min(pool, key=lambda it: rank(it, 0, sec, comp, 0, vol)), 'similar'
        return None, None

    def twins(it):
        """записи-двойники того же блюда с КБЖУ или составом ТТК (та же форма, другой ключ): у кондитерской
        «К Десерт Медовик» есть per_100g и техкарта, у кофейной «Десерт Медовик» — описание и фото;
        сборка дополняет пустые поля (и состав) из двойников"""
        f = norm(it['name'])
        pv = (it.get('portion') or {}).get('value')
        tw = [o for o in forms.get(f, []) if o['key'] != it['key'] and
              (o.get('per_100g') or o.get('per_portion') or (o['key'] in comp and it['key'] not in comp))]
        # сначала двойник с тем же выходом (Капучино 0,3л ← «Капучино 0,3 мл |-->ВЫНОС», не 400 мл), с составом
        return sorted(tw, key=lambda o: ((o.get('portion') or {}).get('value') != pv, o['key'] not in comp))

    # ключ карточки — с разделом для названий из нескольких разделов («Классический @ Раф»), поэтому
    # каждая пара ищется в своём разделе; неоднозначности по разделам больше нет
    result, report = {}, {'literal': [], 'fuzzy': [], 'missing': [], 'ambiguous': []}
    seen = set()
    for key, sec, name in site_keys(index_html):
        if key in seen:
            continue
        seen.add(key)
        hit, how = find(sec, name, key)
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
             'twins': sum(1 for v in result.values() if isinstance(v, dict)),
             'with_menus': sum(1 for it in items if it.get('menus')), 'ttk_comp': len(comp),
             'mapped_comp': sum(1 for v in result.values() if (v['iiko'] if isinstance(v, dict) else v) in comp or
                                (isinstance(v, dict) and any(k in comp for k in v.get('iiko_also', []))))}
    return result, report, stats


def report_text(report, stats):
    L = [f'сопоставление: позиций сайта {stats["site"]}, сопоставлено {stats["mapped"]} '
         f'(буквально {stats["literal"]}, спорных {stats["fuzzy"]}), не нашлось {stats["missing"]}; '
         f'iiko: всего {stats["iiko_total"]} (org other: {stats.get("iiko_other", 0)}), после исключения служебных групп {stats["iiko_usable"]}; '
         f'позиций с двойниками (iiko_also): {stats.get("twins", 0)}; с полем menus: {stats.get("with_menus", 0)}; '
         f'состав в ТТК: у {stats.get("ttk_comp", 0)} позиций выгрузки, у {stats.get("mapped_comp", 0)} сопоставленных; '
         f'menu_revision: {json.dumps(stats.get("revision"), ensure_ascii=False)}', '']
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
    ap.add_argument('--ttk', default=os.path.join(HERE, 'ttk-export.json'), help='выгрузка ТТК: при дублях предпочитаем позиции с составом')
    ap.add_argument('--out', default=os.path.join(HERE, 'name_map.json'))
    ap.add_argument('--report', default=os.path.join(HERE, 'name_map_report.md'))
    ap.add_argument('--cutoff', type=float, default=0.9, help='порог похожести difflib для «похоже»')
    a = ap.parse_args(argv)
    result, report, stats = match(a.menu, a.iiko, a.cutoff, a.ttk)
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
