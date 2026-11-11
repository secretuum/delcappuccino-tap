#!/usr/bin/env python3
"""Страница «Для жалоб и предложений» (задача владельца 11.11.2026): контакты каждого филиала, у каждого две кнопки —
«WhatsApp» и «Позвонить». Один файл с переключателем РУС / ҚАЗ / ENG, как /ugolok; без JS — русский текст и рабочие ссылки.

Собирает tools/seo_jsonld.py (вместе с остальными страницами; там же --check для tests/test_seo.py):
    python3 tools/seo_jsonld.py && python3 tools/sw_version.py
- филиалы 01–05 — из BRANCHES главной: название, адрес, телефон (руками не дублируются); названия и адреса на kk/en —
  из словаря MENU_TR главной, как на /kk/ и /en/;
- новая точка — список EXTRA_POINTS ниже: её нет в BRANCHES, поэтому нет и в JSON-LD, #locations, окне выбора филиала,
  sitemap и llms.txt — только на этой странице;
- тексты — tools/pages_i18n.json, раздел otzyv у ru / kk / en (казахские уходят на вычитку в menu/kk_review.md);
- вид — токены v5 и плоский слой кнопок главной (:root и правила её <style>; плоские с 11.11), шрифты — её @font-face;
  WhatsApp — тон кнопки WhatsApp главной (#25D366, решение владельца 09.11), «Позвонить» — светлый тон, как звонок в карточке точки;
- аналитика — блок analytics_head, события feedback_wa / feedback_call {branch:'01'…'05'|'sputnik'}, без номеров телефонов;
  открытие страницы с подвала /, /kk/, /en/ — feedback_open (кнопка рядом с «Уголком потребителя»).
Адрес страницы — SLUG (выбор главного; владелец может сменить): поменять здесь, переименовать папку, поправить ссылку
в подвале index.html (tests/test_otzyv.py сверяет) и <loc> в sitemap.xml. Язык при заходе — из #kk / #en в адресе
(подвалы /kk/ и /en/ ведут сразу на свой язык), иначе русский.
Только stdlib."""
import html as H, json, os, re, sys
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLUG = 'otzyv'                                   # адрес страницы: /otzyv/, canonical — без слэша, как /ugolok
PATH = '/%s/' % SLUG                             # ссылки на страницу (подвал главной, /kk/, /en/)
FILE = os.path.join(ROOT, SLUG, 'index.html')
LANGS = ('ru', 'kk', 'en')
LANG_BTN = {'kk': 'ҚАЗ', 'ru': 'РУС', 'en': 'ENG'}
HOME = {'ru': '/', 'kk': '/kk/', 'en': '/en/'}  # «← на главную» — на главную своего языка

# новая точка, данных о филиале пока нет (владелец 11.11.2026): «как филиал пока ничего неизвестно, но номер уже нужно
# добавить». Поэтому в BRANCHES её нет, номера 06 нет, часов и гео нет; только эта страница. Телефон — мобильный номер точки.
# Когда точка станет филиалом (появится в BRANCHES) — убрать её отсюда: генератор остановится, если номер или название
# окажутся в обоих местах.
EXTRA_POINTS = (
    {'id': 'sputnik', 'phone': '+77478839057',
     'name': {'ru': 'Sputnik Mall', 'kk': 'Sputnik Mall', 'en': 'Sputnik Mall'},
     'addr': {'ru': 'мкр. Мамыр-1, 8а, 1 этаж', 'kk': 'Мамыр-1 шағын ауданы, 8а, 1-қабат',
              'en': '8a Mamyr-1 microdistrict, ground floor'}},
)

ARROW = ('<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
         'stroke-linejoin="round" aria-hidden="true"><path d="M19 12H5"/><path d="M12 19l-7-7 7-7"/></svg>')


def phone_text(p):
    """+77025672332 → «+7 702 567 23 32» (как на /ugolok); другой формат — ошибка, а не догадка"""
    m = re.fullmatch(r'\+7(\d{3})(\d{3})(\d{2})(\d{2})', p or '')
    if not m:
        sys.exit('feedback_page: телефон %r не в формате +7XXXXXXXXXX — допишите разбор' % p)
    return '+7 %s %s %s %s' % m.groups()


def wa_url(phone, text):
    """как waLink() главной: wa.me/<цифры>?text=<encodeURIComponent(text)>"""
    return 'https://wa.me/%s?text=%s' % (re.sub(r'\D', '', phone), quote(text, safe="-_.!~*'()"))


def texts():
    import seo_jsonld as S
    d = S.i18n()
    out = {l: d[l].get('otzyv') for l in LANGS}
    keys = set(out['ru'] or ())
    for l, t in out.items():
        if not t or set(t) != keys:
            sys.exit('feedback_page: в tools/pages_i18n.json у %s.otzyv нужны те же ключи, что у ru.otzyv (%s)' % (l, ', '.join(sorted(keys))))
        if '{place}' not in t['wa_text']:
            sys.exit('feedback_page: %s.otzyv.wa_text без {place} — в сообщении не будет филиала' % l)
    return out


def points(html):
    """[{id, phone, name{l}, addr{l}, place{l}}] — филиалы из BRANCHES по порядку, затем EXTRA_POINTS"""
    import seo_jsonld as S
    bs, out = S.branches(html), []
    for x in EXTRA_POINTS:                             # до переводов: иначе ошибка была бы про словарь, а не про дубль
        if x['phone'] in [b['phone'] for b in bs] or any(x['name']['ru'] in b['n'] for b in bs):
            sys.exit('feedback_page: точка %s уже есть в BRANCHES — уберите её из EXTRA_POINTS' % x['name']['ru'])
    ctx = {l: S.lang_ctx(html, l) for l in LANGS if l != 'ru'}
    for b in bs:
        p = {'id': S.bnum(b), 'phone': b['phone'], 'name': {'ru': S.short(b)}, 'addr': {'ru': b['addr']}, 'place': {'ru': S.place(b)}}
        for l, c in ctx.items():
            p['place'][l] = S.place_l(c, b)            # нет перевода в MENU_TR — place_l остановит сборку (need)
            p['name'][l], p['addr'][l] = S.T(c, S.short(b)), S.T(c, b['addr'])
        out.append(p)
    for x in EXTRA_POINTS:
        out.append(dict(x, place={l: '%s (%s)' % (x['name'][l], x['addr'][l]) for l in LANGS}))
    ids = [p['id'] for p in out]
    if len(set(ids)) != len(ids) or not all(re.fullmatch(r'\d\d|[a-z]+', i) for i in ids):
        sys.exit('feedback_page: id точек должны быть разными: номер из BRANCHES (01…) или латиница (%s)' % ', '.join(ids))
    for p in out:
        phone_text(p['phone'])
    return out


def main_css(html):
    """<style> главной без комментариев, в одну строку на правило — источник токенов и слоя кнопок"""
    return re.sub(r'\s*\n\s*', '', re.sub(r'/\*.*?\*/', '', html[html.index('<style>') + 7:html.index('</style>')], flags=re.S))


def tone(html, sel):
    """тон кнопки главной: тела всех её правил (вне :where и @media), где sel в списке селекторов и задаются --tone-*,
    по порядку каскада — «.ib.wa» = цвет WhatsApp и белый логотип, «.mm-lang-btn.on» = зелёный и белый текст"""
    import seo_jsonld as S
    bodies = []
    for r in S.css_rules(main_css(html)):
        pre, body = r.split('{', 1)
        if pre.startswith(('@', ':where')):
            continue
        if sel in [s.strip() for s in pre.split(',')] and '--tone-' in body:
            bodies.append(body[:-1].rstrip(';'))
    if not bodies:
        sys.exit('feedback_page: на главной нет тона кнопки %s — поправьте tone()' % sel)
    return ';'.join(bodies)


def sprite():
    """значки трубки (Lucide, ISC) и WhatsApp (Simple Icons, CC0) — из спрайта главной"""
    import seo_jsonld as S
    syms = re.findall(r'<symbol id="i-(?:phone|wa)".*?</symbol>', S.ICONS)
    if len(syms) != 2:
        sys.exit('feedback_page: в спрайте ICONS нет i-phone / i-wa')
    return '<svg class="icons" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false">%s</svg>' % ''.join(syms)


def dict_js(T, ps):
    """словарь переключателя языка: тексты страницы + названия, адреса и ссылки WhatsApp точек на каждом языке"""
    out = {}
    for l in LANGS:
        t = T[l]
        d = {'pageTitle': t['title'], 'eyebrow': t['eyebrow'], 'h1': t['h1'], 'lead': t['lead'], 'call': t['call'],
             'back': t['back'], 'home': HOME[l]}
        for p in ps:
            d['n_' + p['id']], d['a_' + p['id']] = p['name'][l], p['addr'][l]
            d['wa_' + p['id']] = wa_url(p['phone'], t['wa_text'].format(place=p['place'][l]))
        out[l] = d
    return out


def card(T, p):
    e = lambda s: H.escape(s, quote=False)
    a = lambda s: H.escape(s, quote=True)
    i = p['id']
    wa = wa_url(p['phone'], T['ru']['wa_text'].format(place=p['place']['ru']))
    return ('    <article class="fb-card">\n'
            '      <h2 data-i18n="n_%(i)s">%(name)s</h2>\n'
            '      <p class="fb-addr" data-i18n="a_%(i)s">%(addr)s</p>\n'
            '      <p class="fb-phone">%(phone)s</p>\n'
            '      <div class="fb-links">\n'
            '        <a class="fb-btn wa" href="%(wa)s" data-wa="%(i)s" target="_blank" rel="noopener" onclick="track(\'feedback_wa\',{branch:\'%(i)s\'})">'
            '<svg class="ic" aria-hidden="true" focusable="false"><use href="#i-wa"/></svg><span>WhatsApp</span></a>\n'
            '        <a class="fb-btn call" href="tel:%(tel)s" onclick="track(\'feedback_call\',{branch:\'%(i)s\'})">'
            '<svg class="ic" aria-hidden="true" focusable="false"><use href="#i-phone"/></svg><span data-i18n="call">%(call)s</span></a>\n'
            '      </div>\n'
            '    </article>' % {'i': i, 'name': e(p['name']['ru']), 'addr': e(p['addr']['ru']), 'phone': phone_text(p['phone']),
                                'wa': a(wa), 'tel': p['phone'], 'call': e(T['ru']['call'])})


def page(html):
    """otzyv/index.html целиком — из главной (BRANCHES, MENU_TR, токены, слой кнопок, шрифты), EXTRA_POINTS и pages_i18n.json"""
    import seo_jsonld as S
    T, ps = texts(), points(html)
    t = T['ru']
    e = lambda s: H.escape(s, quote=False)
    url = S.SITE + SLUG
    preload = '\n'.join(S.root_paths(l) for l in re.findall(r'<link rel="preload" href="assets/fonts/[^>]*>', html))
    btn = '\n'.join([S.btn_css(html, '.fb-btn,.lang-btn,.tb-back', '.fb-btn.call,.lang-btn,.tb-back'),
                     '.fb-btn.wa{%s}' % tone(html, '.ib.wa'), '.lang-btn.on{%s}' % tone(html, '.mm-lang-btn.on')])
    langs = '\n'.join('    <button type="button" class="lang-btn%s" data-lang="%s" lang="%s" aria-pressed="%s" onclick="setLang(\'%s\')">%s</button>'
                      % (' on' if l == 'ru' else '', l, l, 'true' if l == 'ru' else 'false', l, LANG_BTN[l]) for l in ('kk', 'ru', 'en'))
    i18n_js = S.dumps(dict_js(T, ps)).replace('</', '<\\/')
    return '''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="format-detection" content="telephone=no">
<title>%(title)s</title>
<meta name="description" content="%(description)s">
<meta name="robots" content="index, follow">
<link rel="canonical" href="%(url)s">
%(analytics)s%(preload)s
<meta name="theme-color" content="#426349">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="icon" type="image/png" sizes="192x192" href="/assets/icon-192.png">
<link rel="apple-touch-icon" sizes="180x180" href="/assets/apple-touch-icon.png">
<meta property="og:type" content="website">
<meta property="og:url" content="%(url)s">
<meta property="og:title" content="%(title)s">
<meta property="og:description" content="%(description)s">
<meta property="og:locale" content="ru_RU">
%(og_image)s
<!-- Страница собрана tools/feedback_page.py (запуск — python3 tools/seo_jsonld.py): филиалы — BRANCHES главной и новая точка
     из EXTRA_POINTS, тексты — tools/pages_i18n.json (otzyv), токены, кнопки и шрифты — главной. Руками не править -->
<style>
%(fonts)s
%(tokens)s
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
body{background:var(--c-bg);color:var(--c-text);font-family:var(--font-body);-webkit-font-smoothing:antialiased;line-height:1.5;overflow-x:hidden}
a{color:inherit}
h1,h2{font-family:var(--font-display);font-weight:700;text-transform:lowercase;letter-spacing:-.01em}
.shell{max-width:960px;margin:0 auto;padding:0 24px}
:focus-visible{outline:2px solid var(--c-olive-text);outline-offset:2px}
.icons{position:absolute;width:0;height:0;overflow:hidden}
/* шапка — как на /ugolok: «← на главную» · логотип · языки; кнопки — плоские, слой и тона главной (ниже) */
.topbar{position:sticky;top:0;z-index:100;background:color-mix(in srgb,var(--c-bg) 92%%,transparent);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);display:flex;align-items:center;justify-content:space-between;gap:12px;padding:8px 16px;min-height:64px}
.tb-brand{display:inline-flex;align-items:center;flex:none;min-height:44px}
.tb-brand img{height:40px;width:auto;display:block;border-radius:10px}
.lang-switch{display:flex;gap:4px;flex:none}
.lang-btn{position:relative;color:var(--c-text);font-family:var(--font-body);font-weight:500;font-size:12px;letter-spacing:.03em;padding:6px 12px;min-height:40px;border-radius:var(--r-pill);cursor:pointer}
.lang-btn::after{content:'';position:absolute;inset:-2px 0}
.tb-back{display:inline-flex;align-items:center;gap:6px;flex:0 1 auto;min-width:0;white-space:nowrap;min-height:44px;padding:6px 13px 6px 10px;border-radius:var(--r-pill);color:var(--c-text);font-family:var(--font-body);font-weight:600;font-size:13px;line-height:1.2;text-decoration:none}
.tb-back svg{flex:none}
.tb-back span{min-width:0;overflow:hidden;text-overflow:ellipsis}
/* заголовок и строка под ним */
.fb-hero{padding:32px 0 8px}
.eyebrow{font-size:var(--fs-caption);text-transform:lowercase;color:var(--c-olive-text);font-weight:700;margin-bottom:6px}
.fb-hero h1{font-size:34px;line-height:1.08}
.fb-lead{margin-top:12px;max-width:560px;font-size:var(--fs-body);color:var(--c-muted);line-height:1.5}
/* карточки точек — как карточки точек главной: белые, мягкая тень; кнопки — плоские, высотой 52, переносятся целиком */
main{padding:24px 0 32px}
.fb-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px}
.fb-card{display:flex;flex-direction:column;padding:20px;border-radius:var(--r-lg);background:var(--c-bg);box-shadow:var(--shadow-floating)}
.fb-card h2{font-size:19px;line-height:1.2;color:var(--c-text)}
.fb-addr{margin-top:4px;font-size:var(--fs-body);font-weight:500;color:var(--c-muted);line-height:1.4}
.fb-phone{margin-top:2px;font-size:var(--fs-small);color:var(--c-muted);font-variant-numeric:tabular-nums;white-space:nowrap}
.fb-links{display:flex;flex-wrap:wrap;gap:8px;margin-top:auto;padding-top:16px}
.fb-btn{flex:1 1 auto;display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:var(--h-btn);padding:8px 16px;border-radius:var(--r-pill);font-family:var(--btn-font);font-size:15px;font-weight:700;line-height:1.2;text-transform:lowercase;text-decoration:none;white-space:nowrap;color:var(--c-text)}
.fb-btn .ic{width:18px;height:18px;flex:none}
%(btn)s
/* подвал — как на /ugolok */
footer{border-top:1px solid var(--c-border);padding:24px 0 40px;margin-top:8px}
.f-row{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;font-size:var(--fs-caption);color:var(--c-muted)}
.f-row a{display:inline-flex;align-items:center;justify-content:center;min-width:44px;min-height:44px}
.f-row img{height:28px;width:auto;border-radius:6px;display:block}
.f-row a.back{gap:7px;color:var(--c-accent);font-weight:600;text-decoration:none}
.f-row a.back:hover{text-decoration:underline}
@media(max-width:720px){
  .shell{padding:0 16px}
  .topbar{padding:7px 14px}
  .fb-hero{padding:24px 0 4px}
  .fb-hero h1{font-size:28px}
  main{padding:20px 0 24px}
  .fb-grid{gap:12px}
  .f-row{justify-content:center;text-align:center}
}
@media(max-width:560px){.tb-brand{display:none}}
@media(max-width:374px){
  .topbar{gap:8px;padding:7px 10px}
  .tb-back{font-size:12px;padding:6px 10px 6px 8px;gap:5px}
  .lang-btn{padding:6px 9px}
  .fb-card{padding:16px}
}
</style>
</head>
<body>
%(sprite)s

<div class="topbar">
  <a class="tb-back" href="/" data-home>
    %(arrow)s
    <span data-i18n="back">%(back)s</span>
  </a>
  <a class="tb-brand" href="/" data-home aria-label="Del Cappuccino"><img src="/assets/logo-lockup-256.webp" srcset="/assets/logo-lockup-128.webp 128w, /assets/logo-lockup-256.webp 256w" sizes="81px" width="256" height="127" alt="Del Cappuccino"></a>
  <div class="lang-switch" role="group" aria-label="Тіл / Язык / Language">
%(langs)s
  </div>
</div>

<header class="fb-hero shell">
  <p class="eyebrow" data-i18n="eyebrow">%(eyebrow)s</p>
  <h1 data-i18n="h1">%(h1)s</h1>
  <p class="fb-lead" data-i18n="lead">%(lead)s</p>
</header>

<main class="shell">
  <div class="fb-grid">
%(cards)s
  </div>
</main>

<footer class="shell">
  <div class="f-row">
    <a href="/" data-home aria-label="Del Cappuccino"><img src="/assets/logo-mono-192.webp" width="192" height="192" loading="lazy" decoding="async" alt="dC"></a>
    <a class="back" href="/" data-home>
      %(arrow)s
      <span data-i18n="back">%(back)s</span>
    </a>
    <span>© 2026 Del Cappuccino · coffee &amp; food · Алматы</span>
  </div>
</footer>

<script>
const I18N = %(i18n)s;
/* язык: тексты [data-i18n], ссылки WhatsApp [data-wa] (сообщение на этом языке), «на главную» [data-home] — на главную языка */
function setLang(lang, quiet){
  const d = Object.prototype.hasOwnProperty.call(I18N, lang) ? I18N[lang] : I18N.ru;
  document.documentElement.lang = lang;
  document.querySelectorAll('[data-i18n]').forEach(function(el){
    const k = el.getAttribute('data-i18n');
    if(d[k] !== undefined) el.textContent = d[k];
  });
  document.querySelectorAll('[data-wa]').forEach(function(a){
    const u = d['wa_' + a.getAttribute('data-wa')];
    if(u) a.href = u;
  });
  document.querySelectorAll('[data-home]').forEach(function(a){ a.href = d.home; });
  document.querySelectorAll('.lang-btn').forEach(function(b){
    const on = b.getAttribute('data-lang') === lang;
    b.classList.toggle('on', on);
    b.setAttribute('aria-pressed', on ? 'true' : 'false');
  });
  document.title = d.pageTitle;
  if(!quiet){ try{ history.replaceState(null, '', '#' + lang); }catch(e){} }
}
/* с подвала /kk/ и /en/ приходят с #kk / #en — сразу свой язык; без метки — русский, как в разметке */
(function(){ var h = (location.hash || '').slice(1); if(h !== 'ru' && Object.prototype.hasOwnProperty.call(I18N, h)) setLang(h, true); })();
</script>
<script>
/* Аналитика — после load, в простое; service worker общий с главной (правила — в /sw.js) */
(function(){
  function loadGtag(){var s=document.createElement('script');s.src='https://www.googletagmanager.com/gtag/js?id=%(ga)s';s.async=true;document.head.appendChild(s)}
  function idle(){('requestIdleCallback'in window)?requestIdleCallback(loadGtag,{timeout:4000}):setTimeout(loadGtag,1500)}
  if(document.readyState==='complete')idle();else addEventListener('load',idle);
  if('serviceWorker'in navigator)addEventListener('load',function(){navigator.serviceWorker.register('/sw.js').catch(function(){})});
})();
</script>
</body>
</html>
''' % {'title': H.escape(t['title']), 'description': H.escape(t['description']), 'url': url, 'analytics': S.analytics_head(S.YM_ID),
       'preload': preload, 'og_image': S.OG_IMAGE, 'fonts': S.font_faces(html), 'tokens': S.tokens_css(html), 'btn': btn,
       'sprite': sprite(), 'arrow': ARROW, 'back': e(t['back']), 'langs': langs, 'eyebrow': e(t['eyebrow']), 'h1': e(t['h1']),
       'lead': e(t['lead']), 'cards': '\n'.join(card(T, p) for p in ps), 'i18n': i18n_js, 'ga': S.GA_ID}


def kk_review_rows():
    """строки для menu/kk_review.md: казахский адрес новой точки (тексты страницы попадают туда из pages_i18n.json сами)"""
    return ['| `feedback_page.EXTRA_POINTS.%s.addr` | адрес новой точки на %s (ҚАЗ) | %s |' % (x['id'], PATH, x['addr']['kk'])
            for x in EXTRA_POINTS]
