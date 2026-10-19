#!/usr/bin/env python3
"""Сборка menu/cards.json (карточки блюд на сайте) из выгрузок iiko и ТТК.

Входы (один формат, см. README в шапке функции load_export):
  menu/iiko-export.json  — от опер-бота: name, group, description, portion, per_portion, per_100g, photo
  menu/ttk-export.json   — от ТТК: composition [{name, qty, unit}] и выход блюда (portion)
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
  • КБЖУ: если в iiko per_portion заполнено целиком — берём его; иначе считаем по составу:
    сумма нетто-граммовок × справочник / 100, делим на число порций (portions, по умолчанию 1);
    ингредиент без записи в справочнике → в missing и в отчёт, КБЖУ блюда тогда не публикуем
    (неполная сумма — ложная цифра); иначе per_100g × выход / 100;
  • описание — только ru (кладём d.ru; T()/cardLang на сайте падают на ru сами);
  • состав ru — из ТТК, kk/en — по справочнику; если переведены не все ингредиенты, язык опускаем;
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
        """нетто в граммах или None, если единица непонятна / нет piece_g"""
        u = norm(unit) or 'г'
        if u in UNIT_G:
            return qty * UNIT_G[u]
        if u in UNIT_PIECE:
            pg = self.items.get(name, {}).get('piece_g')
            return qty * pg if pg else None
        return None


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
        elif src == 'ttk':
            out.append(it)          # ТТК может прийти уже с названиями сайта — сшиваем по имени
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
            if k in ('composition', 'portions'):          # состав и выход — зона ТТК
                m[k] = v
            elif k == 'portion' and v:
                m[k] = v
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
    comp = item.get('composition')
    if not isinstance(comp, list) or not comp:
        return None, []
    total = {'kcal': 0.0, 'p': 0.0, 'f': 0.0, 'c': 0.0}
    used, ok = [], True
    for row in comp:
        name = (row or {}).get('name')
        if not name:
            continue
        qty = num(row.get('qty'))
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


def build_kbju(item, ref, missing, recipe=None):
    """→ (kbju | None, источник, оценочно?)"""
    pp = full_pp(item.get('per_portion'))
    if pp:
        return pp, 'iiko per_portion', False
    p100 = full_pp(item.get('per_100g'))
    g, _ = portion_g(item)
    if p100 and g:
        return {k: v * g / 100.0 for k, v in p100.items()}, 'per_100g × выход', False
    if item.get('composition'):
        calc, _ = calc_from_composition(item, ref, missing)
        if calc:
            return calc, 'расчёт по составу ТТК', False
    if recipe:
        if recipe.get('label_per_100'):
            l = recipe['label_per_100']
            g = g or num(recipe.get('portion_g')) or 0
            return {'kcal': l['kcal'] * g / 100, 'p': l['p'] * g / 100, 'f': l['f'] * g / 100, 'c': l['c'] * g / 100}, 'этикетка', False
        if recipe.get('items'):
            fake = {'composition': [{'name': it['name'], 'qty': it['qty_g'], 'unit': 'г'} for it in recipe['items']], 'portions': 1}
            calc, _ = calc_from_composition(fake, ref, missing)
            if calc:
                return calc, 'расчёт по оценочному составу', True
    return None, 'нет данных', False


def ingredients_text(item, ref):
    comp = item.get('composition')
    if not isinstance(comp, list) or not comp:
        return None
    out, seen = {'ru': [], 'kk': [], 'en': []}, set()
    kk_ok = en_ok = True
    for row in comp:
        name = (row or {}).get('name')
        if not name:
            continue
        rname = ref.find(name)
        ru = (rname or name).lower()
        if ru in seen:
            continue
        seen.add(ru)
        out['ru'].append(ru)
        r = ref.items.get(rname) if rname else None
        if r and r.get('kk'):
            out['kk'].append(r['kk'])
        else:
            kk_ok = False
        if r and r.get('en'):
            out['en'].append(r['en'])
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


def save_webp(data, dst, max_px=960, max_bytes=100 * 1024):
    from PIL import Image  # опционально
    im = Image.open(io.BytesIO(data))
    im = im.convert('RGB')
    im.thumbnail((max_px, max_px))
    for q in (82, 74, 66, 58, 50, 42, 34, 26):
        buf = io.BytesIO()
        im.save(buf, 'WEBP', quality=q, method=6)
        if buf.tell() <= max_bytes:
            break
    else:
        im.thumbnail((max_px * 2 // 3, max_px * 2 // 3))
        buf = io.BytesIO()
        im.save(buf, 'WEBP', quality=40, method=6)
    os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
    with open(dst, 'wb') as f:
        f.write(buf.getvalue())
    return buf.tell()


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
    """→ путь webp для карточки или None. sources — манифест {slug: подпись источника}:
    перекодируем, когда источник сменился (напр. пришло фото с Диска вместо iiko) или webp нет."""
    src, sign = photo_source(item, photos_dir or '', drive_file)
    if drive_file and not (sign or '').startswith('drive:'):
        rep.add(f'  нет файла {drive_file} в папке фото: {item["name"]}', error=True)
    if not src:
        return None
    sl = slug(item['name'])
    rel = f'{os.path.relpath(img_dir, ROOT)}/{sl}.webp'.replace(os.sep, '/')
    dst = os.path.join(img_dir, f'{sl}.webp')
    sources = sources if sources is not None else {}
    if os.path.isfile(dst) and not refresh and sources.get(sl) == sign:   # нет записи в манифесте — источник неизвестен, перекодируем
        return rel
    if no_photos:
        rep.add(f'  фото пропущено (--no-photos): {item["name"]}')
        return rel if os.path.isfile(dst) else None
    try:
        import PIL  # noqa: F401
    except ImportError:
        rep.add(f'  нет PIL — фото не обработано: {item["name"]}', error=True)
        return rel if os.path.isfile(dst) else None
    try:
        size = save_webp(fetch_bytes(src), dst)
        sources[sl] = sign
        rep.add(f'  фото: {rel} ({size // 1024} КБ) ← {sign.split(":", 1)[0]}')
        return rel
    except Exception as e:  # сеть/формат — не валим сборку
        rep.add(f'  фото не удалось ({type(e).__name__}: {e}): {item["name"]}', error=True)
        return rel if os.path.isfile(dst) else None


# ── меню на сайте ───────────────────────────────────────────────────────────
def menu_names(index_html):
    """названия блюд из index.html в порядке появления (n:'…' в массивах меню)"""
    if not index_html or not os.path.isfile(index_html):
        return []
    with open(index_html, encoding='utf-8') as f:
        s = f.read()
    names, seen = [], set()
    for m in re.finditer(r"\{n:'((?:[^'\\]|\\.)*)'", s):
        n = m.group(1).replace("\\'", "'")
        if n not in seen:
            seen.add(n)
            names.append(n)
    return names


# ── сборка ──────────────────────────────────────────────────────────────────
def build(iiko_path, ttk_path, ref_path, out_path, img_dir, index_html=None, no_photos=False, refresh=False, rep=None,
          name_map=None, photos_dir=None, recipes=None, recipes_report=None, descriptions=None, descriptions_report=None):
    rep = rep or Report()
    with open(ref_path, encoding='utf-8') as f:
        ref = Ref(json.load(f))
    rep.add(f'справочник: {len(ref.items)} ингредиентов')
    rev, drive = load_name_map(name_map, rep) if name_map else ({}, {})
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
        img = handle_photo(it, img_dir, rep, no_photos, refresh, photos_dir, drive.get(name), sources)
        if img:
            card['img'] = img
        g, unit = portion_g(it)
        if not g and recipe and num(recipe.get('portion_g')):
            g, unit = num(recipe['portion_g']), ('мл' if recipe.get('label_per_100') or recipe.get('unit') == 'мл' else 'г')
            it = {**it, 'portion': {'value': g, 'unit': unit}}
        if g:
            card['w'] = f'{int(g) if float(g).is_integer() else g} {unit}'
        else:
            missing.append('portion')
        kbju, src, est = build_kbju(it, ref, missing, recipe)
        stats[src] = stats.get(src, 0) + 1
        if kbju:
            card['kbju'] = {k: int(round(v)) for k, v in kbju.items()}
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
        ing = ingredients_text(it, ref)
        if not ing and recipe and recipe.get('items') and not recipe.get('no_ing'):
            ing = ingredients_text({'composition': [{'name': x['name']} for x in recipe['items']]}, ref)
        if ing:
            card['ing'] = ing
        if recipe:
            rrows.append((name, recipe, card, src))
        line = f'• {name} [{"+".join(it["src"])}' + (f' org={it["org"]}' if it.get('org') and it['org'] != 'cafe' else '') + ']' + \
            (f' ← {it["name_src"].strip()}' if it.get('name_src') and it['name_src'].strip() != name else '') + f' — КБЖУ: {src}' + \
            (f' — дополнено: {"; ".join(it["filled_from"])}' if it.get('filled_from') else '')
        if names and name not in name_set:
            line += ' — НЕТ В МЕНЮ index.html'
            rep.errors += 1
        if missing:
            line += ' — missing: ' + ', '.join(dict.fromkeys(missing))
            if any(m.startswith(('ref:', 'qty:', 'unit:')) for m in missing):
                rep.errors += 1
        if not ing and 'ing' not in card and not kbju and 'd' not in card and 'img' not in card:
            line += ' — ПУСТО, карточка не создана'
            rep.add(line)
            continue
        rep.add(line)
        cards[name] = card

    if not no_photos:
        os.makedirs(img_dir, exist_ok=True)
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
        write_recipes_report(recipes_report, sorted(rrows, key=lambda r: (order.get(r[0], len(order)), r[0])), ref)
    if descriptions_report:
        write_descriptions_report(descriptions_report, sorted(drows, key=lambda r: (order.get(r[0], len(order)), r[0])))
    stats['описаний своих'] = len(drows)
    rep.add('')
    rep.add('итого: ' + ', '.join(f'{k}: {v}' for k, v in stats.items() if v) + f'; заглушек сохранено: {kept}' +
            (f'; удалено старых: {", ".join(dropped)}' if dropped else ''))
    rep.add(f'карточек в {os.path.relpath(out_path, ROOT)}: {len(ordered)}; замечаний: {rep.errors}')
    return ordered, rep


def write_recipes_report(path, rows, ref):
    """menu/recipes_report.md — блюдо → состав с граммовками → порция → КБЖУ → источник; для вычитки владельцем"""
    SRC = {'iiko': 'по перечню iiko', 'est': 'состав оценочный', 'label': 'этикетка'}
    L = ['# Составы и КБЖУ для вычитки', '',
         'Собрано `menu/build_cards.py` из `menu/recipes_est.json` (оценочные нетто-граммовки на порцию) и справочника',
         '`menu/nutrition_ref.json`. Правки — в recipes_est.json (ключ — название на сайте); придёт ТТК — его состав важнее.', '']
    cnt = {}
    for name, r, card, src in rows:
        cnt[r.get('src', '?')] = cnt.get(r.get('src', '?'), 0) + 1
    L.append('Итого: ' + ', '.join(f'{SRC.get(k, k)} — {v}' for k, v in cnt.items()) + '.')
    L.append('')
    for name, r, card, src in rows:
        k = card.get('kbju') or {}
        kb = f"{k.get('kcal', '—')} ккал · б {k.get('p', '—')} · ж {k.get('f', '—')} · у {k.get('c', '—')}" if k else 'КБЖУ нет'
        if r.get('label_per_100'):
            comp = 'состав не указываем (бутылочный напиток), КБЖУ по этикетке на 100 мл: ' + json.dumps(r['label_per_100'], ensure_ascii=False)
        else:
            comp = ', '.join(f"{x['name']} {x['qty_g']} г" for x in r.get('items', []))
        L.append(f"- **{name}** — {card.get('w', '')} — {comp} → {kb} [{SRC.get(r.get('src'), r.get('src'))}; КБЖУ: {src}]")
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
                       descriptions=a.descriptions, descriptions_report=None if a.dry_run else a.descriptions_report)
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
