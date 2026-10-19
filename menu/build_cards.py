#!/usr/bin/env python3
"""Сборка menu/cards.json (карточки блюд на сайте) из выгрузок iiko и ТТК.

Входы (один формат, см. README в шапке функции load_export):
  menu/iiko-export.json  — от опер-бота: name, group, description, portion, per_portion, per_100g, photo
  menu/ttk-export.json   — от ТТК: composition [{name, qty, unit, via}] и выход блюда (portion); via — имя
                           полуфабриката, из которого раскрыт ингредиент (null — ингредиент верхнего уровня)
  menu/pf_names.json     — человеческие имена полуфабрикатов {форма via после clean_pf: {ru, kk, en}} для
                           списка состава в карточке («соус цезарь» вместо «*ПФ Соус Цезарь 1»)
  menu/nutrition_ref.json — справочник КБЖУ на 100 г + переводы kk/en + синонимы (aliases) + piece_g
  menu/name_map.json     — {название сайта: key iiko} от menu/match_names.py; с картой берём только
                           сопоставленные записи iiko и переименовываем их в названия сайта
  menu/descriptions.json — описания для гостя {название: {ru, kk, en}}; приоритетнее описаний iiko,
                           отдельный файл, чтобы состав из ТТК не затирал тексты
  menu/recipes_est.json  — оценочные составы с нетто-граммовками и порцией (пока нет ТТК): запасной
                           источник состава и КБЖУ после ТТК; такие КБЖУ помечаются "est": true;
                           бутылочные напитки — label_per_100 (этикетка), без состава

Правила:
  • ключ карточки — русское название блюда ровно как в index.html (n:'…'); между файлами
    записи сшиваются по cloud_key/key, иначе по названию;
  • КБЖУ: если в iiko per_portion заполнено целиком — берём его; иначе считаем по составу ТТК:
    все раскрытые ингредиенты (и из полуфабрикатов) × справочник / 100, делим на число порций
    (portions, по умолчанию 1); упаковка (стаканы, крышки, вилки…) и нулевые строки не считаются;
    ингредиент без записи в справочнике → в missing и в отчёт, КБЖУ блюда тогда не публикуем
    (неполная сумма — ложная цифра); иначе per_100g × выход / 100; иначе recipes_est (est: true);
  • выход порции: portion из iiko (номенклатурный выход) → portion ТТК в г/мл → сумма граммов состава ТТК
    (мл ≈ г, шт через piece_g) → portion_g из recipes_est;
  • описание — только ru (кладём d.ru; T()/cardLang на сайте падают на ru сами);
  • состав ru — из ТТК верхнего уровня: ингредиент без via — сам по себе, полуфабрикат — одним пунктом
    по человеческому имени (pf_names.json; с одним ингредиентом — этот ингредиент; с именем самого блюда
    или без имени — раскрывается); служебное (вода, лёд, сиропы в ассортименте, красители) в список не идёт;
    kk/en — по справочнику и pf_names; если переведены не все пункты, язык опускаем;
  • фото: drive_file из name_map.json (папка menu/menu_photos/, приоритет) или photo из iiko (url)
    → img/menu/<slug>.webp через PIL, ≤100 КБ, ≤960 px; img/menu/sources.json помнит источник
    каждого webp — перекодируем, когда источник сменился или по --refresh-photos; без PIL — без фото;
  • записи старого cards.json с "_stub": true сохраняются, пока выгрузка не даст такое же название;
    у собранных записей _stub нет.

Только стандартная библиотека; PIL — опционально, для фото.
"""
import argparse, io, json, os, re, sys, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LANGS = ('ru', 'kk', 'en')
UNIT_G = {'г': 1, 'гр': 1, 'g': 1, 'грамм': 1, 'кг': 1000, 'kg': 1000, 'мл': 1, 'ml': 1, 'л': 1000, 'l': 1000}
UNIT_PIECE = {'шт', 'шт.', 'pcs', 'pc', 'зубчик', 'ломтик', 'штука'}
# упаковка и расходники в составе ТТК: не еда — ни в список, ни в КБЖУ, ни в выход
PACKAGING_RE = re.compile(r'стакан|крышк|трубочк|вилк|ложк|нож(?:и|ик)?\b|контейнер|капхолдер|бутылк|пакет|салфетк|палочк|'
                          r'коробк|упаковк|плёнк|пленк|пергамент|фольг|стикер|этикетк|зубочист|однораз|\bоднор\b|\bодч\b|'
                          r'подложк|соусник|тарелк|держател|шпажк|бумаг|наклейк|крафт|бамбук', re.I)
# служебные ингредиенты: в КБЖУ и выходе считаем, в читаемый состав не выводим
HIDDEN_RE = re.compile(r'^(?:вода|лед|лёд)\b|сиропы в ассортименте|краситель|добавка пищевая|\bвспомогательн', re.I)
PF_HEAD_RE = re.compile(r'^(?:\W*(?:пф|п/ф|п\\ф|к|гп|г/п|тв|хт|бр)\b\.?\s*)+', re.I)                 # «*ПФ », «К », «ГП »
PF_TAIL_RE = re.compile(r'\s*(?:\d+(?:[.,]\d+)?\s*(?:г|гр|кг|л|мл|шт)?\.?|кг|шт|цех|вес|с фасовкой|действующая|нужно поменять|'
                        r'новый|новая|сырое|сырой|порци[яи]|зал|дс)\s*$', re.I)
UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-', re.I)
TRANSLIT = {
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z','и':'i','й':'j','к':'k','л':'l','м':'m',
    'н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h','ц':'c','ч':'ch','ш':'sh','щ':'sch','ъ':'',
    'ы':'y','ь':'','э':'e','ю':'yu','я':'ya','ә':'a','ғ':'g','қ':'q','ң':'n','ө':'o','ұ':'u','ү':'u','һ':'h','і':'i',
}


def slug(name):
    s = ''.join(TRANSLIT.get(ch, ch) for ch in name.lower())
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s or 'item'


def norm(s):
    return re.sub(r'\s+', ' ', str(s or '').strip().lower().replace('ё', 'е'))


def num(v):
    if v is None or v == '':
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(',', '.').strip())
    except ValueError:
        return None


class Report:
    def __init__(self):
        self.lines = []
        self.errors = 0

    def add(self, line, error=False):
        self.lines.append(line)
        if error:
            self.errors += 1

    def text(self):
        return '\n'.join(self.lines) + '\n'


# ── справочник ──────────────────────────────────────────────────────────────
class Ref:
    def __init__(self, data):
        self.items = {}
        self.index = {}
        for name, v in data.items():
            if name.startswith('_'):
                continue
            self.items[name] = v
            self.index[norm(name)] = name
            for a in v.get('aliases', []):
                self.index.setdefault(norm(a), name)

    def find(self, ing_name):
        key = norm(ing_name)
        if key in self.index:
            return self.index[key]
        # «лук репчатый свежий» → без хвоста; «соус дзадзики» → без головы
        words = key.split(' ')
        for n in range(len(words) - 1, 0, -1):
            for cand in (' '.join(words[:n]), ' '.join(words[-n:])):
                if cand in self.index:
                    return self.index[cand]
        return None

    def grams(self, name, qty, unit):
        """нетто в граммах или None, если единица непонятна / нет piece_g; factor (фритюрный жир: в блюдо
        уходит ~15 % списанного) уменьшает граммы"""
        u = norm(unit) or 'г'
        k = float(self.items.get(name, {}).get('factor') or 1)
        if u in UNIT_G:
            return qty * UNIT_G[u] * k
        if u in UNIT_PIECE:
            pg = self.items.get(name, {}).get('piece_g')
            return qty * pg * k if pg else None
        return None


def clean_pf(via):
    """«*ПФ Соус Цезарь 1» → «соус цезарь»; «ПФ Сырники классические КГ ЦЕХ» → «сырники классические»;
    «Бургер с томлёной говядиной  |--> ВЫНОС*» → «бургер с томленой говядиной»"""
    v = str(via or '').split('|')[0].replace('*', ' ').replace('ё', 'е').replace('Ё', 'Е')
    v = re.sub(r'\s+', ' ', v).strip()
    v = PF_HEAD_RE.sub('', v)
    prev = None
    while prev != v:
        prev, v = v, PF_TAIL_RE.sub('', v)
    return norm(v)


def pf_words(s):
    return {w for w in norm(s).replace('-', ' ').split() if w not in ('десерт', 'торт', 'пирожное', 'с', 'и', 'в', 'на')}


def ttk_rows(item):
    """строки состава ТТК, которые еда: без упаковки и нулевых граммовок; via: None — верхний уровень,
    без имени (uuid) — раскрываем, имя самого блюда — раскрываем, иначе — полуфабрикат"""
    comp = item.get('composition')
    if not isinstance(comp, list):
        return []
    own = pf_words(item.get('name_src') or item.get('name') or '') | pf_words(display_name(item.get('name') or ''))
    out = []
    for row in comp:
        name = str((row or {}).get('name') or '').strip()
        if not name or PACKAGING_RE.search(name):
            continue
        qty = num(row.get('qty'))
        if qty is not None and qty <= 0:
            continue
        via = row.get('via')
        pf = clean_pf(via) if via and not UUID_RE.match(str(via)) else None
        if pf and (pf_words(pf) <= own or (own and own <= pf_words(pf))):       # «ПФ Сырники классические» в «Сырники классические»
            pf = None
        out.append({'name': name, 'qty': qty, 'unit': row.get('unit'), 'pf': pf, 'hidden': bool(HIDDEN_RE.search(name))})
    total = sum(r['qty'] or 0 for r in out if norm(r['unit']) not in UNIT_PIECE)
    for pf in {r['pf'] for r in out if r['pf']}:         # полуфабрикат на ≥ 80 % веса — это само блюдо («ГП Шу малиновый»)
        if total and sum(r['qty'] or 0 for r in out if r['pf'] == pf and norm(r['unit']) not in UNIT_PIECE) >= 0.8 * total:
            for r in out:
                if r['pf'] == pf:
                    r['pf'] = None
    return out


def usable_composition(item):
    """состав ТТК годится, если в нём есть хоть один видимый продукт (не упаковка, не вода)"""
    return any(not r['hidden'] for r in ttk_rows(item))


def load_pf_names(path, rep):
    """menu/pf_names.json {форма clean_pf: {ru, kk, en}}"""
    if not path or not os.path.isfile(path):
        rep.add(f'нет {path} — полуфабрикаты без имён раскрываются по ингредиентам')
        return {}
    with open(path, encoding='utf-8') as f:
        d = {norm(k): v for k, v in json.load(f).items() if not k.startswith('_') and isinstance(v, dict)}
    rep.add(f'{os.path.relpath(path, ROOT)}: {len(d)} имён полуфабрикатов')
    return d


# ── выгрузки ────────────────────────────────────────────────────────────────
def load_export(path, rep):
    """{"version":1,"generated_at":…,"items":[{key,name,group,description,composition,portion,per_portion,per_100g,photo,missing}]}"""
    if not path or not os.path.isfile(path):
        rep.add(f'нет файла {path} — пропускаю')
        return []
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    items = data.get('items', []) if isinstance(data, dict) else data
    head = data if isinstance(data, dict) else {}
    rep.add(f'{os.path.relpath(path, ROOT)}: {len(items)} позиций, generated_at={head.get("generated_at", "?")}' +
            (f', menu_revision={json.dumps(head["menu_revision"], ensure_ascii=False)}' if head.get('menu_revision') else '') +
            (f', org other: {sum(1 for it in items if isinstance(it, dict) and it.get("org") == "other")}' if any(isinstance(it, dict) and it.get('org') for it in items) else ''))
    return [it for it in items if isinstance(it, dict) and it.get('name')]


def load_recipes(path, rep):
    """menu/recipes_est.json {блюдо: {portion_g, src, items:[{name, qty_g}] | label_per_100, no_ing}}"""
    if not path or not os.path.isfile(path):
        rep.add(f'нет {path} — без оценочных составов')
        return {}
    with open(path, encoding='utf-8') as f:
        r = {k: v for k, v in json.load(f).items() if not k.startswith('_')}
    rep.add(f'{os.path.relpath(path, ROOT)}: {len(r)} оценочных составов')
    return r


def load_descriptions(path, rep):
    """menu/descriptions.json {название: {ru, kk, en}}"""
    if not path or not os.path.isfile(path):
        rep.add(f'нет {path} — описания только из iiko')
        return {}
    with open(path, encoding='utf-8') as f:
        d = {k: v for k, v in json.load(f).items() if not k.startswith('_') and isinstance(v, dict)}
    rep.add(f'{os.path.relpath(path, ROOT)}: {len(d)} описаний')
    return d


def load_name_map(path, rep):
    """menu/name_map.json: {сайт: key_iiko} (старый формат) или {сайт: {"iiko": key|null, "drive_file": путь|null}}
    → ({key: сайт}, {сайт: drive_file})"""
    if not path or not os.path.isfile(path):
        rep.add(f'нет {path} — имена iiko берём как есть')
        return {}, {}
    with open(path, encoding='utf-8') as f:
        m = json.load(f)
    rev, photos, also = {}, {}, 0
    for site, v in m.items():
        key = v.get('iiko') if isinstance(v, dict) else v
        if key:
            rev.setdefault(str(key), (site, True))
        if isinstance(v, dict):
            for k in v.get('iiko_also') or []:          # двойники: дополняют пустые поля основной записи
                rev.setdefault(str(k), (site, False))
                also += 1
            if v.get('drive_file'):
                photos[site] = v['drive_file']
    rep.add(f'{os.path.relpath(path, ROOT)}: {len(m)} названий сайта → {len(rev)} позиций iiko (двойников {also}), фото из папки: {len(photos)}')
    return rev, photos


def apply_name_map(items, rev, src, rep):
    """переименовать по карте; без карты — как есть; с картой — несопоставленные записи выбрасываем"""
    if not rev:
        return items
    out, dropped = [], 0
    for it in items:
        hit = rev.get(str(it.get('cloud_key') or it.get('key') or ''))
        if hit:
            site, primary = hit
            out.append({**it, 'name': site, 'name_src': it.get('name'), 'primary': primary})
        elif src == 'ttk' and not it.get('key'):
            out.append(it)          # ТТК без ключей iiko (ручная выгрузка с названиями сайта) — сшиваем по имени
        else:
            dropped += 1
    if dropped:
        rep.add(f'{src}: {dropped} записей без пары в name_map.json пропущено')
    return sorted(out, key=lambda it: not it.get('primary', True))   # основные записи раньше двойников


PHONE_RE = re.compile(r'\+?\d[\d\s()\-]{7,}\d')
SERVICE_RE = re.compile(r'вынос|стафф|агрегатор|\|-->|iiko|whatsapp|instagram|https?://', re.I)


def clean_description(text, name, rep):
    """описание для сайта: схлопнуть пробелы, без звёздочек; с телефоном или служебными пометками — не публикуем"""
    t = re.sub(r'\s+', ' ', str(text or '')).replace('*', '').strip()
    if not t:
        return None
    if PHONE_RE.search(t):
        rep.add(f'  описание с телефоном не опубликовано: {name}', error=True)
        return None
    if SERVICE_RE.search(t):
        rep.add(f'  описание со служебной пометкой не опубликовано: {name}', error=True)
        return None
    return t[0].upper() + t[1:]


def merge_exports(iiko, ttk):
    """Сшивка по cloud_key/key, иначе по названию. iiko — базовая запись, ТТК дополняет."""
    merged, by_key, by_name = [], {}, {}

    def ident(it):
        return it.get('cloud_key') or it.get('key')

    for it in iiko:
        m = {'src': ['iiko'], **it}
        prev = by_name.get(norm(it['name']))
        if prev is not None:                            # одноимённые записи iiko (двойник): заполняем пустое
            if ident(it) and it.get('portion'):
                prev.setdefault('twin_portions', {})[str(ident(it))] = it['portion']
            for k, v in it.items():
                if k in ('key', 'name', 'name_src', 'primary', 'src'):
                    continue
                if k == 'missing':
                    prev['missing'] = sorted(set(prev.get('missing') or []) & set(v or []))
                elif prev.get(k) in (None, '', [], {}) and v not in (None, '', [], {}):
                    prev[k] = v
                    prev.setdefault('filled_from', []).append(f'{k} ← {str(it.get("name_src") or it.get("name")).strip()}')
            if ident(it):
                by_key[str(ident(it))] = prev
            continue
        merged.append(m)
        if ident(it):
            by_key[str(ident(it))] = m
        by_name[norm(it['name'])] = m
    for it in ttk:
        m = by_key.get(str(ident(it))) if ident(it) else None
        if m is None:
            m = by_name.get(norm(it['name']))
        if m is None:
            m = {'src': ['ttk'], **it}
            merged.append(m)
            by_name[norm(it['name'])] = m
            continue
        m['src'].append('ttk')
        for k, v in it.items():
            if k == 'composition':                         # состав — зона ТТК; пустой состав двойника не затирает полный
                if v and not m.get('composition'):
                    m[k] = v
                    if not it.get('primary', True):          # состав двойника — и выход двойника к нему (торт 1000 г ≠ 1664 г)
                        m.setdefault('filled_from', []).append(f'состав ← {str(it.get("name_src") or it.get("name")).strip()}')
                        tp = (m.get('twin_portions') or {}).get(str(ident(it)))
                        if tp:
                            m['comp_portion'] = tp
            elif k == 'portions':
                m[k] = v
            elif k == 'portion' and v:                     # выход ТТК отдельно: номенклатурный выход iiko точнее («1 шт», «18 г» зёрен)
                m['ttk_portion'] = v
            elif k == 'missing':
                m['missing'] = sorted(set(m.get('missing') or []) | set(v or []))
            elif m.get(k) in (None, '', [], {}):
                m[k] = v
    return merged


# ── расчёт ──────────────────────────────────────────────────────────────────
def full_pp(pp):
    if not isinstance(pp, dict):
        return None
    vals = {k: num(pp.get(k)) for k in ('kcal', 'protein', 'fat', 'carbs')}
    if any(v is None for v in vals.values()):
        return None
    return {'kcal': vals['kcal'], 'p': vals['protein'], 'f': vals['fat'], 'c': vals['carbs']}


def portion_g(item):
    p = item.get('portion')
    if not isinstance(p, dict):
        return None, None
    v = num(p.get('value'))
    unit = norm(p.get('unit')) or 'г'
    if v is None:
        return None, None
    if unit in UNIT_G:
        return v * UNIT_G[unit], ('мл' if unit in ('мл', 'ml', 'л', 'l') else 'г')
    return None, None


def calc_from_composition(item, ref, missing):
    rows = ttk_rows(item)
    if not rows:
        return None, []
    total = {'kcal': 0.0, 'p': 0.0, 'f': 0.0, 'c': 0.0}
    used, ok = [], True
    for row in rows:
        name = row['name']
        qty = row['qty']
        rname = ref.find(name)
        if rname is None:
            missing.append(f'ref:{name}')
            ok = False
            continue
        used.append(rname)
        if qty is None:
            missing.append(f'qty:{name}')
            ok = False
            continue
        g = ref.grams(rname, qty, row.get('unit'))
        if g is None:
            missing.append(f'unit:{name} ({row.get("unit")})')
            ok = False
            continue
        r = ref.items[rname]
        for k in total:
            total[k] += g * float(r[k]) / 100.0
    if not ok:
        return None, used
    n = num(item.get('portions')) or 1.0
    return {k: v / n for k, v in total.items()}, used


def composition_grams(item, ref):
    """сумма граммов еды в составе ТТК (мл ≈ г, шт через piece_g) → выход, когда его нет ни в iiko, ни в ТТК"""
    total, unit_ml = 0.0, 0
    for row in ttk_rows(item):
        if row['qty'] is None:
            continue
        g = ref.grams(ref.find(row['name']) or '', row['qty'], row['unit'])
        if g is None:
            continue
        total += g
        unit_ml += 1 if norm(row['unit']) in ('мл', 'ml', 'л', 'l') else -1
    return (round(total), 'мл' if unit_ml > 0 else 'г') if total > 0 else (None, None)


def build_kbju(item, ref, missing, recipe=None):
    """→ (kbju | None, источник, оценочно?). Порядок: этикетка (бутылочное) → состав ТТК → оценочный состав →
    iiko per_portion → per_100g × выход. Ручные поля iiko — последними: там встречаются «191 ккал, белка 0,36»
    и per_100g, которое на самом деле на порцию (728 ккал у бургера)"""
    g, _ = portion_g(item)
    if recipe and recipe.get('label_per_100'):
        l = recipe['label_per_100']
        g = g or num(recipe.get('portion_g')) or 0
        return {'kcal': l['kcal'] * g / 100, 'p': l['p'] * g / 100, 'f': l['f'] * g / 100, 'c': l['c'] * g / 100}, 'этикетка', False
    if item.get('composition'):
        calc, _ = calc_from_composition(item, ref, missing)
        if calc:
            return calc, 'расчёт по составу ТТК', False
    if recipe and recipe.get('items'):
        fake = {'composition': [{'name': it['name'], 'qty': it['qty_g'], 'unit': 'г'} for it in recipe['items']], 'portions': 1}
        calc, _ = calc_from_composition(fake, ref, missing)
        if calc:
            return calc, 'расчёт по оценочному составу', True
    pp = full_pp(item.get('per_portion'))
    if pp:
        return pp, 'iiko per_portion', False
    p100 = full_pp(item.get('per_100g'))
    if p100 and g:
        return {k: v * g / 100.0 for k, v in p100.items()}, 'per_100g × выход', False
    return None, 'нет данных', False


def ingredients_text(item, ref, pf_names=None, pf_missing=None):
    """читаемый состав верхнего уровня: {ru, kk?, en?}; pf_missing — список полуфабрикатов без имени
    в pf_names.json (раскрыты по ингредиентам)"""
    rows = ttk_rows(item)
    if not rows:
        return None
    pf_names = pf_names or {}
    groups = {}
    for row in rows:
        if row['pf']:
            groups.setdefault(row['pf'], []).append(row)
    for pf, rs in list(groups.items()):                 # полуфабрикат из одного продукта — сам продукт («ПФ Лимон очищенные»)
        vis = [r for r in rs if not r['hidden']]
        if len(vis) == 1 or (not vis and len(rs) == 1):
            for r in rs:
                r['pf'] = None
            del groups[pf]
        elif pf not in pf_names and norm(pf) not in ref.index:   # имени нет — раскрываем, но просим имя
            if pf_missing is not None:
                pf_missing.append(pf)
            for r in rs:
                r['pf'] = None
            del groups[pf]
    out, seen, done_pf = {'ru': [], 'kk': [], 'en': []}, set(), set()
    kk_ok = en_ok = True
    for row in rows:
        if row['pf']:
            if row['pf'] in done_pf:
                continue
            done_pf.add(row['pf'])
            v = pf_names.get(row['pf'])
            if v:
                ru, kk, en = norm(v.get('ru') or row['pf']), v.get('kk'), v.get('en')
            else:
                rn = ref.index[norm(row['pf'])]
                r = ref.items[rn]
                ru, kk, en = rn, r.get('kk'), r.get('en')
        else:
            if row['hidden']:
                continue
            rname = ref.find(row['name'])
            r = ref.items.get(rname) if rname else None
            ru, kk, en = (rname or row['name']).lower(), (r or {}).get('kk'), (r or {}).get('en')
        if ru in seen:
            continue
        seen.add(ru)
        out['ru'].append(ru)
        if kk:
            out['kk'].append(kk)
        else:
            kk_ok = False
        if en:
            out['en'].append(en)
        else:
            en_ok = False
    res = {'ru': ', '.join(out['ru'])}
    if kk_ok and out['kk']:
        res['kk'] = ', '.join(out['kk'])
    if en_ok and out['en']:
        res['en'] = ', '.join(out['en'])
    return res if res['ru'] else None


# ── фото ────────────────────────────────────────────────────────────────────
def fetch_bytes(src, timeout=20):
    if os.path.isfile(src):
        with open(src, 'rb') as f:
            return f.read()
    req = urllib.request.Request(src, headers={'User-Agent': 'dc-cards-builder/1'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


SIZES = ((960, 90 * 1024, ''), (480, 35 * 1024, '-480'))   # (сторона, лимит байт, суффикс): 960 для десктопа, 480 для телефона
PHOTO_FMT = 'v3'                                           # менять при смене набора размеров/лимитов — всё перекодируется
MIN_PX = 400                                               # исходник меньше — в карточке будет мыло, лучше без фото


class TooSmall(ValueError):
    pass


def encode_webp(im, max_px, max_bytes):
    im = im.copy()
    im.thumbnail((max_px, max_px))
    for q in ((78, 72, 66, 60, 54, 48, 42, 36, 30) if max_px >= 900 else (82, 76, 70, 64, 58, 52, 46, 40, 34)):
        buf = io.BytesIO()
        im.save(buf, 'WEBP', quality=q, method=6)
        if buf.tell() <= max_bytes:
            return buf.getvalue(), q
    im.thumbnail((max_px * 2 // 3, max_px * 2 // 3))
    buf = io.BytesIO()
    im.save(buf, 'WEBP', quality=40, method=6)
    return buf.getvalue(), 40


def save_webp(data, dst, max_px=960, max_bytes=90 * 1024):
    """→ (байт 960-версии, (w, h) исходника). Пишет dst (960) и dst-480.webp; для карточки нужны оба."""
    from PIL import Image  # опционально
    im = Image.open(io.BytesIO(data)).convert('RGB')
    ar = im.size
    if max(ar) < MIN_PX:
        raise TooSmall(f'{ar[0]}×{ar[1]} px')
    os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
    first = None
    for px, limit, suf in SIZES:
        out = dst[:-5] + suf + '.webp' if suf else dst
        buf, _ = encode_webp(im, px, limit)
        with open(out, 'wb') as f:
            f.write(buf)
        first = first if first is not None else len(buf)
    return first, ar


def photo_source(item, photos_dir, drive_file):
    """(источник, подпись) — файл из папки Диска приоритетнее ссылки iiko (новее, актуальное меню)"""
    if drive_file:
        p = os.path.join(photos_dir, drive_file)
        if os.path.isfile(p):
            return p, f'drive:{drive_file}:{os.path.getsize(p)}'
    url = item.get('photo')
    if url:
        return url, f'iiko:{url}'
    return None, None


def handle_photo(item, img_dir, rep, no_photos, refresh, photos_dir=None, drive_file=None, sources=None):
    """→ (путь 960-webp, путь 480-webp, [w, h] исходника) или (None, None, None). sources — манифест
    {slug: подпись источника + ' ' + [w,h]}: перекодируем, когда источник или формат сменился или webp нет."""
    src, sign = photo_source(item, photos_dir or '', drive_file)
    sign = f'{sign}:{PHOTO_FMT}' if sign else sign
    if drive_file and not (sign or '').startswith('drive:'):
        rep.add(f'  нет файла {drive_file} в папке фото: {item["name"]}', error=True)
    if not src:
        return None, None, None
    sl = slug(item['name'])
    rel = f'{os.path.relpath(img_dir, ROOT)}/{sl}.webp'.replace(os.sep, '/')
    rel480 = rel[:-5] + '-480.webp'
    dst, dst480 = os.path.join(img_dir, f'{sl}.webp'), os.path.join(img_dir, f'{sl}-480.webp')
    sources = sources if sources is not None else {}
    have = os.path.isfile(dst) and os.path.isfile(dst480)
    cur = sources.get(sl) or ''
    if have and not refresh and cur.startswith(sign + ' '):   # манифест: «<источник>:<формат> [w, h]»
        return rel, rel480, json.loads(cur[len(sign) + 1:])
    if no_photos:
        rep.add(f'  фото пропущено (--no-photos): {item["name"]}')
        return (rel, rel480, json.loads(cur.split(' ', 1)[1]) if have and ' ' in cur else None) if have else (None, None, None)
    try:
        import PIL  # noqa: F401
    except ImportError:
        rep.add(f'  нет PIL — фото не обработано: {item["name"]}', error=True)
        return (rel, rel480, None) if have else (None, None, None)
    try:
        size, ar = save_webp(fetch_bytes(src), dst)
        sources[sl] = f'{sign} {json.dumps(list(ar))}'
        rep.add(f'  фото: {rel} ({size // 1024} КБ, {os.path.getsize(dst480) // 1024} КБ@480) ← {sign.split(":", 1)[0]}')
        return rel, rel480, list(ar)
    except TooSmall as e:
        for fn in (dst, dst480):
            if os.path.isfile(fn):
                os.remove(fn)
        sources.pop(sl, None)
        rep.add(f'  фото пропущено, исходник мал ({e}): {item["name"]}')
        return None, None, None
    except Exception as e:  # сеть/формат — не валим сборку
        rep.add(f'  фото не удалось ({type(e).__name__}: {e}): {item["name"]}', error=True)
        return (rel, rel480, None) if have else (None, None, None)


# ── меню на сайте ───────────────────────────────────────────────────────────
def menu_names(index_html):
    """ключи карточек из index.html в порядке меню: название, а для названий из нескольких разделов —
    «Название @ Раздел» (match_names.site_keys)"""
    if not index_html or not os.path.isfile(index_html):
        return []
    sys.path.insert(0, HERE)
    import match_names as mn
    keys, seen = [], set()
    for key, sec, name in mn.site_keys(index_html):
        if key not in seen:
            seen.add(key)
            keys.append(key)
    return keys


def menu_info(index_html):
    """{ключ: (раздел, vol)} из index.html"""
    if not index_html or not os.path.isfile(index_html):
        return {}
    sys.path.insert(0, HERE)
    import match_names as mn
    vols = mn.site_vols(index_html)
    out = {}
    for key, sec, name in mn.site_keys(index_html):
        out.setdefault(key, (sec, vols.get(key)))
    return out


TTK_MIN_SHARE = 0.3          # ТТК даёт < 30 % ккал от оценки (у Ice Капучино одни зёрна) → техкарта неполная, берём оценочный состав
TTK_MAX_RATIO = 2.5          # сумма граммов состава больше выхода в 2,5+ раза → техкарта сломана, берём оценочный состав
SITE_VOL_RE = re.compile(r'^\s*(\d+(?:[.,]\d+)?)(?:\s*/\s*\d+(?:[.,]\d+)?)*\s*(мл|л|г|гр|кг)\b', re.I)   # «200/300/400 мл» → 200 мл
VOL_LIKE = {'Декаф': 'Американо'}                           # объёма на сайте нет — как у соседа
DRINK_ITEMS = {'Декаф'}                                     # напиток в «кухонном» разделе сайта (Дополнения)
DRINK_FIT = (0.6, 1.6)                                      # напиток: состав описывает другой объём (капучино 300 ↔ 200 мл) — КБЖУ масштабируем
FOOD_EXTRA = ('На компанию', 'Торты (целиком)', 'Полуфабрикаты', 'Мясо')
DRINK_MIN_G = 30                                            # у напитка вес меньше 30 мл не показываем (18 г зёрен — не порция)
WEIGHT_FIT = (0.6, 1.1)                                     # вес принимается, если он в этих долях от суммы состава (усушка/ужарка)
# вес iiko — заявленная порция меню, её по порогу не трогаем; точечно — там, где она явно не про это блюдо:
# Стейк-омлет: iiko 300 г при 497 г состава (3 яйца, полстейка, сыр) — 0,604, формально проходит, но 381 ккал/100 г
# невозможны для омлета, главный терминал 19.10.2026: вес = сумма × усушка
FORCE_SUM_WEIGHT = {'Стейк-омлет'}
EST_FIT = 1.6                                               # для оценочного состава: вес = сумма, если расходится сильнее
SHRINK_SOUP = 0.8                                           # супы и тушёное — ×0,8, остальная еда и выпечка — ×0,85
SHRINK_FOOD = 0.85
# правдоподобный выход по разделу: iiko иногда отдаёт 1050 г у тоника и 138 г у целого торта
SECTION_MIN_G = {'Торты (целиком)': 600, 'На компанию': 1000, 'Полуфабрикаты': 150, 'Мясо': 250}
SECTION_MAX_G = {'На компанию': 15000, 'Торты (целиком)': 5000, 'Полуфабрикаты': 2000, 'Мясо': 2000}
KITCHEN_SECTIONS = ('Завтраки', 'Сладкие завтраки', 'Салаты', 'Боулы', 'Супы', 'Паназия', 'Сэндвичи / Закуски', 'Сэндвичи', 'Пицца',
                    'Паста фреш', 'Горячие блюда', 'Домашние блюда', 'Блюда на гриле', 'Хлеба', 'Гарниры', 'Соусы', 'Дополнения', 'Десерты')


def site_vol_g(vol):
    """«375 мл» → (375, 'мл'); «500 гр» → (500, 'г'); «200/300/400 мл» → (200, 'мл') — первое значение; «8 шт» → (None, None)"""
    m = SITE_VOL_RE.match(str(vol or ''))
    if not m:
        return None, None
    v, u = num(m.group(1)), m.group(2).lower()
    return v * UNIT_G[u], ('мл' if u in ('мл', 'л') else 'г')


DRINK_SECTIONS = ('Классический кофе', 'Холодные кофейные напитки', 'Листовые чаи', 'Авторские чаи', 'Ice tea', 'Лимонады',
                  'Милкшейки', 'Фреши', 'Раф', 'Спешл напитки', 'Глинтвейн б/а', 'Смузи', 'Напитки')


def is_food(sec, name=''):
    """еда — всё, что не раздел напитков сайта и не DRINK_ITEMS (неизвестный раздел считаем едой)"""
    return display_name(name) not in DRINK_ITEMS and sec not in DRINK_SECTIONS


def shrink(sec, name):
    return SHRINK_SOUP if sec == 'Супы' or 'томлен' in norm(name) else SHRINK_FOOD


def resolve_portion(it, recipe, sec, vol, ref, missing, name=''):
    """→ (г, единица, источник, it, kscale): выход порции, согласованный с составом; kscale — множитель КБЖУ
    (напиток, чей состав описывает другой объём).
    Еда: сайт → выход двойника → iiko → ТТК → оценка, но только если он в WEIGHT_FIT от суммы состава ТТК
    (иначе вес = сумма × усушка); для оценочного состава — сумма, если расхождение больше EST_FIT.
    Напитки: объём сайта (первое значение) → iiko → ТТК → сумма → оценка, не меньше DRINK_MIN_G, в мл.
    По дороге отбрасывается техкарта, которая не сходится с выходом или даёт < 30 % ккал от оценки."""
    food = is_food(sec, name)
    kscale = 1.0
    chain = [('сайт', site_vol_g(vol)), ('двойник', portion_g({'portion': it.get('comp_portion')}) if it.get('comp_portion') else (None, None)),
             ('iiko', portion_g(it)), ('ТТК', portion_g({'portion': it['ttk_portion']}) if it.get('ttk_portion') else (None, None)),
             ('сумма ТТК', composition_grams(it, ref) if it.get('composition') and not food else (None, None)),   # еда: сумма × усушка ниже
             ('оценка', (num(recipe.get('portion_g')), 'мл' if recipe.get('label_per_100') or recipe.get('unit') == 'мл' else 'г') if recipe and num(recipe.get('portion_g')) else (None, None))]
    g, unit, wsrc, rejected = None, None, None, []
    for src_w, (gv, uv) in chain:
        if not gv:
            continue
        if src_w != 'сайт' and sec and not plausible(sec, gv):
            rejected.append(f'{src_w} {gv:.0f} г')
            continue
        if not food and src_w != 'сайт' and gv < DRINK_MIN_G:
            rejected.append(f'{src_w} {gv:.0f} г — меньше {DRINK_MIN_G} мл')
            continue
        g, unit, wsrc = gv, uv, src_w
        break
    if rejected:
        missing.append('выход отвергнут: ' + ', '.join(rejected))
    if g and wsrc != 'сумма ТТК' and it.get('composition'):
        sg, _ = composition_grams(it, ref)
        if sg and sg > TTK_MAX_RATIO * g:              # «Самса 63 г» из 162 г муки — техкарта не сходится с выходом
            missing.append(f'ТТК не сходится с выходом: сумма {sg} г при выходе {g:.0f} г — взят оценочный состав')
            it = {**it, 'composition': None}
    if it.get('composition') and recipe and recipe.get('items'):   # в техкарте только зёрна/украшение — остального нет
        tk_calc, _ = calc_from_composition(it, ref, [])
        est_calc, _ = calc_from_composition({'composition': [{'name': x['name'], 'qty': x['qty_g'], 'unit': 'г'} for x in recipe['items']]}, ref, [])
        if tk_calc and est_calc and est_calc['kcal'] >= 50 and tk_calc['kcal'] < TTK_MIN_SHARE * est_calc['kcal']:
            missing.append(f'ТТК неполная: {tk_calc["kcal"]:.0f} ккал против {est_calc["kcal"]:.0f} по оценке — взят оценочный состав')
            it = {**it, 'composition': None}
    if food:                                           # вес и КБЖУ — от одного состава
        if it.get('composition'):
            sg, _ = composition_grams(it, ref)
            if sg and (not g or not WEIGHT_FIT[0] * sg <= g <= WEIGHT_FIT[1] * sg or display_name(name) in FORCE_SUM_WEIGHT):
                k = shrink(sec, name)
                if g:
                    missing.append(f'вес {wsrc} {g:.0f} г не сходится с суммой состава {sg} г — вес = сумма × {k}')
                g, unit, wsrc = round(sg * k), 'г', f'сумма ТТК × {k}'
        elif recipe and recipe.get('items'):
            es = round(sum(float(x['qty_g']) for x in recipe['items']))
            if es and (not g or g > EST_FIT * es or es > EST_FIT * g):
                if g:
                    missing.append(f'вес {wsrc} {g:.0f} г расходится с оценочным составом {es} г — вес = сумма состава')
                g, unit, wsrc = es, 'г', 'сумма оценки'
    elif g:
        unit = 'мл'
        total = composition_grams(it, ref)[0] if it.get('composition') else \
            (round(sum(float(x['qty_g']) for x in recipe['items'])) if recipe and recipe.get('items') else None)
        if total and total != g and DRINK_FIT[0] <= g / total <= DRINK_FIT[1]:
            kscale = g / total
            missing.append(f'состав на {total} г, объём {g:.0f} мл — КБЖУ × {kscale:.2f}')
    return g, unit, wsrc, it, kscale


def plausible(sec, g):
    """кухня — до 1200 г, напитки — до 700 мл, наборы/торты/сырьё — по своим границам"""
    return SECTION_MIN_G.get(sec, 0) <= g <= SECTION_MAX_G.get(sec, 1200 if sec in KITCHEN_SECTIONS else 700)


def display_name(key):
    return key.split(' @ ', 1)[0]


# ── сборка ──────────────────────────────────────────────────────────────────
def build(iiko_path, ttk_path, ref_path, out_path, img_dir, index_html=None, no_photos=False, refresh=False, rep=None,
          name_map=None, photos_dir=None, recipes=None, recipes_report=None, descriptions=None, descriptions_report=None,
          pf_names=None):
    rep = rep or Report()
    with open(ref_path, encoding='utf-8') as f:
        ref = Ref(json.load(f))
    rep.add(f'справочник: {len(ref.items)} ингредиентов')
    rev, drive = load_name_map(name_map, rep) if name_map else ({}, {})
    pf_names = load_pf_names(pf_names, rep) if pf_names else {}
    recipes = load_recipes(recipes, rep) if recipes else {}
    descriptions = load_descriptions(descriptions, rep) if descriptions else {}
    photos_dir = photos_dir or os.path.join(HERE, 'menu_photos')
    items = merge_exports(apply_name_map(load_export(iiko_path, rep), rev, 'iiko', rep),
                          apply_name_map(load_export(ttk_path, rep), rev, 'ttk', rep))
    have = {str(it['name']).strip() for it in items}
    for site in drive:                              # позиция только с фото из папки — карточка с одним фото
        if site not in have:
            items.append({'src': ['drive'], 'name': site})
            have.add(site)
    for site in recipes:                            # позиция только с оценочным составом — карточка с составом и КБЖУ
        if site not in have:
            items.append({'src': ['est'], 'name': site})
            have.add(site)
    for site in descriptions:
        if site not in have:
            items.append({'src': ['desc'], 'name': site})
    sources_path = os.path.join(img_dir, 'sources.json')
    sources = {}
    if os.path.isfile(sources_path):
        with open(sources_path, encoding='utf-8') as f:
            sources = json.load(f)
    names = menu_names(index_html)
    name_set = set(names)
    info = menu_info(index_html)
    by_name = {str(it['name']).strip(): it for it in items}
    mn_sep = ' @ '
    old = {}
    if os.path.isfile(out_path):
        with open(out_path, encoding='utf-8') as f:
            old = json.load(f)

    cards, stats, rrows, drows = {}, {}, [], []
    for it in items:
        name = str(it['name']).strip()
        missing = list(it.get('missing') or [])
        card = {}
        recipe = recipes.get(name)
        img, img480, ar = handle_photo(it, img_dir, rep, no_photos, refresh, photos_dir, drive.get(name), sources)
        if img:
            card['img'] = img
            if img480:
                card['img480'] = img480
            if ar:
                card['ar'] = ar
        if it.get('composition') and not usable_composition(it):
            missing.append('composition:только вода/упаковка')
            it = {**it, 'composition': None}
        sec, vol = info.get(name, (None, None))
        if not vol and VOL_LIKE.get(name):
            vol = info.get(VOL_LIKE[name], (None, None))[1]
        base = display_name(name)
        whole = by_name.get(base + ' @ Торты (целиком)') if sec == 'Десерты' and mn_sep in name else None
        if whole and whole.get('composition') and usable_composition(whole):
            # кусок торта: КБЖУ целого торта на 100 г × вес куска; состав куска — состав торта в той же пропорции
            wsec, wvol = info.get(base + ' @ Торты (целиком)', (None, None))
            wg, _, _, whole_it, _ = resolve_portion(whole, recipes.get(base + ' @ Торты (целиком)'), wsec, wvol, ref, [], base)
            sl_g, _, sl_src, _, _ = resolve_portion({**it, 'composition': None}, None, sec, vol, ref, [], name)
            if wg and sl_g and whole_it.get('composition'):
                k = sl_g / wg
                it = {**it, 'composition': [{**row, 'qty': (num(row.get('qty')) or 0) * k} for row in whole_it['composition']],
                      'portion': {'value': sl_g, 'unit': 'г'}, 'comp_portion': None, 'ttk_portion': None}
                missing.append(f'кусок: состав и КБЖУ от целого торта ({wg:.0f} г) в доле {k:.3f}, вес куска {sl_src}')
        g, unit, wsrc, it, kscale = resolve_portion(it, recipe, sec, vol, ref, missing, name)
        if g:
            it = {**it, 'portion': {'value': g, 'unit': unit}}
            card['w'] = f'{int(g) if float(g).is_integer() else g} {unit}'
        else:
            missing.append('portion')
        kbju, src, est = build_kbju(it, ref, missing, recipe)
        stats[src] = stats.get(src, 0) + 1
        if kbju:
            card['kbju'] = {k: int(round(v * kscale)) for k, v in kbju.items()}
            if est:
                card['est'] = True
        own = descriptions.get(name)
        if own and own.get('ru'):
            card['d'] = {l: own[l].strip() for l in LANGS if own.get(l) and own[l].strip()}
            drows.append((name, card['d']))
        else:
            desc = clean_description(it.get('description'), name, rep)
            if desc:
                card['d'] = {'ru': desc}
        pf_missing = []
        ing = None if recipe and recipe.get('no_ing') else ingredients_text(it, ref, pf_names, pf_missing)
        if not ing and recipe and recipe.get('items') and not recipe.get('no_ing'):
            ing = ingredients_text({'composition': [{'name': x['name']} for x in recipe['items']]}, ref)
        if ing:
            card['ing'] = ing
        for pf in dict.fromkeys(pf_missing):
            missing.append(f'pf:{pf}')
        if recipe or it.get('composition'):
            rrows.append((name, recipe, card, src, it, wsrc))
        line = f'• {name} [{"+".join(it["src"])}' + (f' org={it["org"]}' if it.get('org') and it['org'] != 'cafe' else '') + ']' + \
            (f' ← {it["name_src"].strip()}' if it.get('name_src') and it['name_src'].strip() != name else '') + f' — КБЖУ: {src}' + \
            (f' — дополнено: {"; ".join(it["filled_from"])}' if it.get('filled_from') else '')
        if names and name not in name_set:
            line += ' — НЕТ В МЕНЮ index.html'
            rep.errors += 1
        if missing:
            line += ' — missing: ' + ', '.join(dict.fromkeys(missing))
            if any(m.startswith(('ref:', 'qty:', 'unit:', 'pf:')) for m in missing):
                rep.errors += 1
        if not ing and 'ing' not in card and not kbju and 'd' not in card and 'img' not in card:
            line += ' — ПУСТО, карточка не создана'
            rep.add(line)
            continue
        rep.add(line)
        cards[name] = card

    if not no_photos:
        os.makedirs(img_dir, exist_ok=True)
        live = {slug(k) for k in cards} | {slug(k) for k, v in old.items() if isinstance(v, dict) and v.get('_stub') and k not in cards}
        for sl in sorted(set(sources) - live):          # webp, сделанный сборкой, но больше никому не нужный
            for fn in (f'{sl}.webp', f'{sl}-480.webp', f'{sl}-960.webp'):      # только свои файлы: «medovik-» ≠ «medovik-deserty»
                if os.path.isfile(os.path.join(img_dir, fn)):
                    os.remove(os.path.join(img_dir, fn))
            sources.pop(sl, None)
            rep.add(f'  сирота удалён: {sl}.webp')
        with open(sources_path, 'w', encoding='utf-8') as f:
            json.dump(dict(sorted(sources.items())), f, ensure_ascii=False, indent=1)
            f.write('\n')
    kept = 0
    for name, v in old.items():
        if isinstance(v, dict) and v.get('_stub') and name not in cards:
            cards[name] = v
            kept += 1
    dropped = [n for n in old if n not in cards]
    order = {n: i for i, n in enumerate(names)}
    ordered = dict(sorted(cards.items(), key=lambda kv: (order.get(kv[0], len(order)), kv[0])))

    order = {n: i for i, n in enumerate(names)}
    if recipes_report:
        write_recipes_report(recipes_report, sorted(rrows, key=lambda r: (order.get(r[0], len(order)), r[0])), ref, pf_names)
    if descriptions_report:
        write_descriptions_report(descriptions_report, sorted(drows, key=lambda r: (order.get(r[0], len(order)), r[0])))
    stats['описаний своих'] = len(drows)
    rep.add('')
    rep.add('итого: ' + ', '.join(f'{k}: {v}' for k, v in stats.items() if v) + f'; заглушек сохранено: {kept}' +
            (f'; удалено старых: {", ".join(dropped)}' if dropped else ''))
    rep.add(f'карточек в {os.path.relpath(out_path, ROOT)}: {len(ordered)}; замечаний: {rep.errors}')
    return ordered, rep


def comp_summary(item, ref, pf_names):
    """состав верхнего уровня с граммами: «сырники 190 г (творог, сахар, манка…), сметана 40 г, …»"""
    rows = ttk_rows(item)
    groups, order = {}, []
    for r in rows:
        k = r['pf'] or ('#' + r['name'])
        if k not in groups:
            groups[k] = []
            order.append(k)
        groups[k].append(r)
    parts = []
    for k in order:
        rs = groups[k]
        g = sum((ref.grams(ref.find(r['name']) or '', r['qty'], r['unit']) or 0) for r in rs if r['qty'] is not None)
        gs = f' {g:.0f} г' if g else ''
        if k.startswith('#'):
            r = rs[0]
            label = (ref.find(r['name']) or r['name']).lower() + (' (служебное)' if r['hidden'] else '')
            parts.append(label + gs)
        else:
            v = (pf_names or {}).get(k)
            label = norm(v['ru']) if v else ref.index.get(norm(k), k)
            inner = ', '.join(dict.fromkeys((ref.find(r['name']) or r['name']).lower() for r in rs if not r['hidden']))
            parts.append(f'{label}{gs} ({inner})')
    return ', '.join(parts)


def write_recipes_report(path, rows, ref, pf_names=None):
    """menu/recipes_report.md — блюдо → состав с граммовками → порция → КБЖУ → источник; для вычитки владельцем.
    rows: (name, recipe | None, card, src_kbju, item, src_portion)"""
    SRC = {'iiko': 'по перечню iiko', 'est': 'состав оценочный', 'label': 'этикетка'}
    L = ['# Составы и КБЖУ для вычитки', '',
         'Собрано `menu/build_cards.py`. Состав и КБЖУ — из техкарт iiko (`menu/ttk-export.json`, не в репозитории) через',
         'справочник `menu/nutrition_ref.json`; у позиций без техкарты — оценочный состав из `menu/recipes_est.json`.',
         'В скобках у полуфабриката — из чего он раскрыт (в карточке показывается одним пунктом, имя — `menu/pf_names.json`).',
         'Выход: номенклатурный из iiko; «сумма ТТК» — когда выхода нет и он посчитан как сумма граммов состава.', '']
    ttk = [r for r in rows if r[4].get('composition')]
    est = [r for r in rows if not r[4].get('composition') and r[1] and not r[1].get('label_per_100')]
    lab = [r for r in rows if not r[4].get('composition') and r[1] and r[1].get('label_per_100')]
    L.append(f'Итого: по техкартам — {len(ttk)}, оценочных (техкарты нет) — {len(est)}, этикетка — {len(lab)}.')
    L.append('')

    def kb(card):
        k = card.get('kbju') or {}
        return f"{k.get('kcal', '—')} ккал · б {k.get('p', '—')} · ж {k.get('f', '—')} · у {k.get('c', '—')}" if k else 'КБЖУ нет'

    L.append(f'## По техкартам ({len(ttk)})')
    L.append('')
    for name, r, card, src, it, wsrc in ttk:
        g, _ = composition_grams(it, ref)
        w = card.get('w', '—') + (f' [{wsrc}]' if wsrc != 'iiko' else '') + (f', сумма ТТК {g} г' if g and wsrc == 'iiko' else '')
        L.append(f"- **{name}** — {w} — {comp_summary(it, ref, pf_names)} → {kb(card)} [КБЖУ: {src}]")
    L.append('')
    L.append(f'## Оценочные — техкарты не нашлось ({len(est)})')
    L.append('')
    for name, r, card, src, it, wsrc in est:
        comp = ', '.join(f"{x['name']} {x['qty_g']} г" for x in r.get('items', []))
        L.append(f"- **{name}** — {card.get('w', '')} — {comp} → {kb(card)} [{SRC.get(r.get('src'), r.get('src'))}; КБЖУ: {src}]")
    L.append('')
    L.append(f'## По этикетке ({len(lab)})')
    L.append('')
    for name, r, card, src, it, wsrc in lab:
        L.append(f"- **{name}** — {card.get('w', '')} — состав не указываем (бутылочный напиток), КБЖУ по этикетке на 100 мл: "
                 f"{json.dumps(r['label_per_100'], ensure_ascii=False)} → {kb(card)}")
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')


def write_descriptions_report(path, rows):
    """menu/descriptions_report.md — блюдо → ru / kk / en; для вычитки владельцем и носителем"""
    L = ['# Описания блюд для вычитки', '',
         'Собрано `menu/build_cards.py` из `menu/descriptions.json` (ключ — название на сайте). Правки — в descriptions.json.', '',
         f'Всего: {len(rows)}.', '']
    for name, d in rows:
        L.append(f"- **{name}**")
        for l in LANGS:
            if d.get(l):
                L.append(f"  - {l}: {d[l]}")
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')


def main(argv=None):
    ap = argparse.ArgumentParser(description='Собрать menu/cards.json из выгрузок iiko и ТТК')
    ap.add_argument('--iiko', default=os.path.join(HERE, 'iiko-export.json'))
    ap.add_argument('--ttk', default=os.path.join(HERE, 'ttk-export.json'))
    ap.add_argument('--ref', default=os.path.join(HERE, 'nutrition_ref.json'))
    ap.add_argument('--out', default=os.path.join(HERE, 'cards.json'))
    ap.add_argument('--img-dir', default=os.path.join(ROOT, 'img', 'menu'))
    ap.add_argument('--menu', default=os.path.join(ROOT, 'index.html'), help='index.html для порядка и проверки названий')
    ap.add_argument('--name-map', default=os.path.join(HERE, 'name_map.json'), help='сайт → key iiko / drive_file (match_names.py, match_photos.py)')
    ap.add_argument('--photos-dir', default=os.path.join(HERE, 'menu_photos'), help='папка исходников фото (drive_file относительно неё)')
    ap.add_argument('--recipes', default=os.path.join(HERE, 'recipes_est.json'), help='оценочные составы (fallback после ТТК)')
    ap.add_argument('--pf-names', default=os.path.join(HERE, 'pf_names.json'), help='человеческие имена полуфабрикатов для состава')
    ap.add_argument('--recipes-report', default=os.path.join(HERE, 'recipes_report.md'), help='отчёт по составам для вычитки')
    ap.add_argument('--descriptions', default=os.path.join(HERE, 'descriptions.json'), help='описания ru/kk/en (приоритетнее iiko)')
    ap.add_argument('--descriptions-report', default=os.path.join(HERE, 'descriptions_report.md'), help='отчёт по описаниям для вычитки')
    ap.add_argument('--no-photos', action='store_true', help='не качать и не конвертировать фото')
    ap.add_argument('--refresh-photos', action='store_true', help='перекачать фото, даже если webp уже есть')
    ap.add_argument('--report', help='куда дописать отчёт (текст)')
    ap.add_argument('--dry-run', action='store_true', help='только отчёт, cards.json не писать')
    a = ap.parse_args(argv)
    cards, rep = build(a.iiko, a.ttk, a.ref, a.out, a.img_dir, a.menu, a.no_photos, a.refresh_photos, name_map=a.name_map,
                       photos_dir=a.photos_dir, recipes=a.recipes, recipes_report=None if a.dry_run else a.recipes_report,
                       descriptions=a.descriptions, descriptions_report=None if a.dry_run else a.descriptions_report,
                       pf_names=a.pf_names)
    if not a.dry_run:
        with open(a.out, 'w', encoding='utf-8') as f:
            json.dump(cards, f, ensure_ascii=False, indent=2)
            f.write('\n')
    head = f'build_cards {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}{" (dry-run)" if a.dry_run else ""}\n'
    sys.stdout.write(head + rep.text())
    if a.report:
        with open(a.report, 'a', encoding='utf-8') as f:
            f.write(head + rep.text() + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
