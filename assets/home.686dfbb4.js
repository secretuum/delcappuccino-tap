/* Код главной. Собран tools/seo_jsonld.py из tools/home.js, руками не править */
/* Код главной (tap.delcappuccino.kz/): окно выбора филиала, меню-оверлей (вкладки, разделы, поиск, языки), карточка блюда,
   «Курица гриль», глубокие ссылки /#menu…, видео плитки «Курицы гриль».
   Данные — BRANCHES, MENU_*, TOGO_*, MK, LEGEND, MENU_UI, MENU_TR — остаются в index.html, во встроенном <script> прямо перед
   тегом этого файла: их правят там (точки, меню из Excel), их же читают tools/seo_jsonld.py и menu/*.py.
   Исходник общего файла assets/home.<хэш>.js (вынесен 11.11.2026: запас веса главной без подъёма пределов
   tests/test_redesign.py → test_weight). Собирает tools/seo_jsonld.py: копия байт в байт с заголовком, имя — по хэшу
   содержимого; в index.html — <script src="/assets/home.<хэш>.js" defer>. sw.js держит файл в кэше навсегда и кладёт его в
   оболочку при установке (tools/sw_version.py вписывает имя в PRECACHE) — меню офлайн работает, как раньше.
   Собранный файл руками не править: правка здесь → python3 tools/seo_jsonld.py → python3 tools/sw_version.py.
   defer: файл выполняется после разбора страницы, до DOMContentLoaded — вся разметка уже есть. До этого кнопки с onclick
   (goHome, openModal, openMenu, openGrill) — заглушки из index.html (перед <header>): вызов ждёт в window.dcQ, в конце
   файла повторяется последний (если меню или окно уже не открыты, например по #menu в адресе). */
const RM=matchMedia('(prefers-reduced-motion: reduce)');
function goHome(){try{closeMenu()}catch(e){}try{closeModal()}catch(e){}window.scrollTo({top:0,behavior:RM.matches?'auto':'smooth'})}

function waLink(phone,text){return `https://wa.me/${phone.replace(/\D/g,'')}?text=${encodeURIComponent(text)}`}
function branchWa(b){return waLink(b.phone,(b.wa||'Здравствуйте! Хочу забронировать столик в Del Cappuccino, ')+b.addr)}

/* уход: .closing до animationend или таймера; stay() — отмена */
function gone(el,done){if(!el)return;if(RM.matches){el.classList.remove('closing');done&&done();return}el._done=done;if(el._c)return;
  el._c=1;el.classList.add('closing');const fin=()=>{if(!el._c)return;el._c=0;clearTimeout(el._t);el.removeEventListener('animationend',el._ae);el.classList.remove('closing');const d=el._done;el._done=null;d&&d()};
  el._ae=e=>{if(/^(out|sink|down)$/.test(e.animationName))fin()};el.addEventListener('animationend',el._ae);el._t=setTimeout(fin,260)}
function enter(el){el.classList.add('pre','anim');const go=()=>{el.classList.remove('pre');el.classList.add('in');setTimeout(()=>el.classList.remove('anim'),320)};
  RM.matches?go():requestAnimationFrame(()=>requestAnimationFrame(go))}
function bg(off){const o=id=>document.getElementById(id).classList.contains('open');if(!off&&(o('menu-modal')||o('modal')))return;document.body.classList.toggle('ovl',off);document.querySelectorAll('.grill-video,.sub-video').forEach(v=>{if(off){if(!v.paused){v._w=1;v.pause()}}else if(v._w){v._w=0;v.play().catch(()=>{})}})}
function stay(el){if(!el||!el._c)return;el._c=0;clearTimeout(el._t);el.removeEventListener('animationend',el._ae);el.classList.remove('closing');el._done=null}
function openModal(intent){
  intent=intent||'route';
  const m=document.getElementById('modal');
  if(!m.classList.contains('open')) modalOpener=document.activeElement;
  stay(m); m.classList.add('open'); enter(m); bg(1); m.querySelector('.x').focus();
  const list = document.getElementById('branch-list');
  const status = document.getElementById('modal-status');
  const hint = {book:'Забронируйте столик в WhatsApp или по телефону', wa:'Напишите нам в WhatsApp', route:'Откройте маршрут в 2GIS'}[intent]||'';
  list.innerHTML='';
  const N=window.dcNear;   /* dist и геолокация — в общем файле assets/near.*.js (tools/near.js), с карточками #locations */
  if(N&&navigator.geolocation){
    status.textContent='Определяем ваше местоположение…';
    N.locate(here=>{
      if(!here){ status.textContent='Не удалось определить геолокацию — выберите филиал вручную. '+hint; return draw(BRANCHES,false); }
      const ordered = [...BRANCHES].map(b=>({...b,d:N.dist(here,b.geo)})).sort((a,b)=>a.d-b.d);
      status.textContent = 'Ближайший к вам филиал — сверху. '+hint;
      draw(ordered,true);
    },4000);
  } else { status.textContent='Выберите филиал вручную. '+hint; draw(BRANCHES,false); }
  function draw(arr,showDist){
    /* как карточки точек (владелец 31.10): название без номера, часы — кроме 24/7, круглые значки из спрайта #i-… */
    const ic=id=>`<svg class="ic" aria-hidden="true" focusable="false"><use href="#i-${id}"/></svg>`;
    list.innerHTML = arr.map(b=>`
      <div class="branch-row">
        <div class="br-top">
          <div class="bn"><small>${b.n.replace(/^\d+\s*·\s*/,'')}</small><b>${b.addr}</b>${b.hours!=='24/7'?`<span class="hrs">${b.hours}${b.note?` · ${b.note}`:''}</span>`:''}</div>
          ${showDist&&b.d!==undefined?`<span class="dist ym-hide-content">${N.km(b.d)}</span>`:''}
        </div>
        <div class="br-acts">
          <a class="ib route" href="${b.route}" target="_blank" rel="noopener" onclick="track('modal_route',{branch:'${b.n}'})" aria-label="Маршрут" title="Маршрут">${ic('pin')}</a>
          <a class="ib" href="tel:${b.phone}" onclick="track('modal_call',{branch:'${b.n}'})" aria-label="Позвонить" title="Позвонить">${ic('phone')}</a>
          <a class="ib wa" href="${branchWa(b)}" target="_blank" rel="noopener" onclick="track('modal_wa',{branch:'${b.n}',intent:'${intent}'})" aria-label="WhatsApp" title="WhatsApp">${ic('wa')}</a>
          ${b.menu?`<button class="pill" type="button" onclick="track('modal_menu',{branch:'${b.n}'});closeModal();openMenu('${b.menu}')">Меню</button>`:''}
        </div>
      </div>`).join('');
  }
}
let modalOpener=null;
function closeModal(){const m=document.getElementById('modal');if(!m.classList.contains('open'))return;m.classList.remove('open','in');gone(m,()=>bg(0));if(modalOpener&&modalOpener.focus)modalOpener.focus();modalOpener=null}
/* Tab — по кругу внутри окна */
function trapTab(e,box){if(e.key!=='Tab')return;const f=[...box.querySelectorAll('a[href],button,input,[tabindex="0"]')].filter(x=>x.offsetParent&&x.tabIndex>=0),n=f.length-1,i=f.indexOf(document.activeElement);if(n>=0&&(e.shiftKey?i<=0:i<0||i===n)){e.preventDefault();f[e.shiftKey?n:0].focus()}}
document.getElementById('modal').addEventListener('keydown',e=>trapTab(e,document.querySelector('#modal .sheet')));
document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeMenu();closeModal()}});

const MENU_LANGS = ['kk','ru','en'];
let menuLang = dcLang||'ru';

/* единицы в объёмах/весах без словаря: «350 гр», «300 мл / 1 л» */
function trUnits(s){
  if(menuLang==='en') return s.replace(/мл/g,'ml').replace(/(\d) гр/g,'$1 g').replace(/(\d) л(?![а-яё])/g,'$1 L').replace(/\b1 шт/g,'1 pc').replace(/(\d) шт/g,'$1 pcs');
  if(menuLang==='kk') return s.replace(/(\d) гр/g,'$1 г').replace(/(\d) шт/g,'$1 дана');
  return s;
}
function T(s){
  if(menuLang==='ru' || !s) return s;
  const d=MENU_TR[menuLang];
  return d[s]!==undefined ? d[s] : trUnits(String(s));
}

function applyMenuLang(){
  const ui=MENU_UI[menuLang];
  document.querySelectorAll('#menu-modal [data-mm]').forEach(el=>{ el.innerHTML=ui[el.dataset.mm]; });
  document.getElementById('menu-modal').setAttribute('aria-label', ui.dialog);
  document.getElementById('menu-modal').lang = menuLang;
  document.getElementById('mm-x').setAttribute('aria-label', ui.close);
  document.querySelectorAll('.mm-lang-btn').forEach(b=>{ b.classList.toggle('on', b.dataset.lang===menuLang); b.setAttribute('aria-current', b.dataset.lang===menuLang); });
}
function switchMenuLang(lang){
  if(!MENU_LANGS.includes(lang)) return;
  menuLang=lang;
  dcSave(lang);
  const tab=menuTab, cat=menuCat;
  applyMenuLang(); renderFeed(); renderTabs(); renderCats(); setTopH(); refreshCard();
  if(document.getElementById('menu-modal').scrollTop>0) scrollToMenuEl(document.getElementById(`mm-sec-${tab}-${cat}`), false);
  track('menu_lang',{lang});
}
let menuMode='cafe';
let menuTab='kitchen';
function curTabs(){return MENU_MODES[menuMode].tabs}
let menuCat=0;   /* активная категория текущей вкладки (подсветка, scroll-spy) */

/* карточки блюд: menu/cards.json, ключ — русское название как в n:; у названий из нескольких разделов —
   «Название @ Раздел» (t секции), поэтому ищем сначала с разделом, потом без; null — ещё не грузили */
let CARDS=null;
function escA(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;')}
function cardKey(name, sec){
  if(!CARDS) return null;
  if(sec && CARDS[name+' @ '+sec]) return name+' @ '+sec;
  return CARDS[name] ? name : null;
}
function nameHTML(it, sec){
  if(cardKey(it.n, sec)) return `<span class="nm-t has-card" role="button" tabindex="0" aria-haspopup="dialog" aria-label="${escA(T(it.n))} — ${MENU_UI[menuLang].card_aria}" data-n="${escA(it.n)}" data-sec="${escA(sec||'')}">${T(it.n)}</span>`;
  return `<span class="nm-t">${T(it.n)}</span>`;
}

function fmtP(p){return String(p).split('/').map(x=>(+String(x).trim()).toLocaleString('ru-RU')).join(' / ')}

function secHTML(s, tab, i){
  /* заголовок секции не печатаем, если он тот же, что заголовок вкладки (h3 выше): «Полуфабрикаты» → «Полуфабрикаты»;
     сравниваем русские ключи, чтобы скрывать одинаково на всех языках */
  const dupT = s.t === MENU_UI.ru['tab_'+tab] && s.badge==null && s.p==null;
  return `
    <section class="mm-sec${dupT?' mm-sec-notitle':''}" id="mm-sec-${tab}-${i}" data-i="${i}">
      ${dupT?'':`<h4>${T(s.t)}${s.badge?` <span class="mm-badge">${T(s.badge)}</span>`:''}${s.p!=null?`<span class="mm-secp">${fmtP(s.p)}</span>`:''}</h4>`}
      ${s.note?`<p class="mm-note">${T(s.note)}</p>`:''}
      ${s.items.map(it=>itemHTML(it, s.t)).join('')}
    </section>`;
}
/* позиция — текстовая строка «название … цена», как в прежнем меню, в новой стати (правка владельца 1.11): пометки,
   название, значок фото (у блюда есть карточка — тап по строке открывает её), «!», объём мелко; справа цена; без превью */
function itemHTML(it, sec, secLabel){
  const key=cardKey(it.n, sec);
  return `
        <div class="mm-it${key?' has-card':''}"${key?` data-n="${escA(it.n)}" data-sec="${escA(sec||'')}"`:''}>
          <span class="nm">${(it.m||[]).map(k=>MK[k]).join('')} ${nameHTML(it, sec)}${key?'<svg class="mm-ph" aria-hidden="true" focusable="false"><use href="#i-photo"/></svg>':''}${onlyBtn(it)}${it.vol?` <span class="vol">${T(it.vol)}</span>`:''}${it.note?`<span class="itnote">${T(it.note)}</span>`:''}${secLabel?`<span class="mm-it-sec">${secLabel}</span>`:''}</span>
          <span class="sp"></span>
          ${it.p!=null?`<span class="pr">${it.old?`<span class="old">${fmtP(it.old)}</span> <span class="sale">${fmtP(it.p)}</span>`:fmtP(it.p)}</span>`:''}
        </div>`;
}

/* Всё меню режима одной лентой: ME/NU с адресами → легенда → части по вкладкам (внутри — колонки) */
function legendLine(){
  const L=MENU_MODES[menuMode].legend, seen=new Set(), out=[];
  Object.keys(curTabs()).forEach(t=>(L[t]||[]).forEach(l=>{ if(!seen.has(l)){ seen.add(l); out.push(l); } }));
  return out.length ? `<div class="mm-legend-row">${out.map(l=>`<span>${T(l)}</span>`).join('')}</div>` : '';
}
function renderFeed(){
  hidePop();
  const ui=MENU_UI[menuLang], tabs=curTabs();
  if(menuQ!==null){ document.getElementById('mm-cols').innerHTML = searchHTML(); return; }
  document.getElementById('mm-cols').innerHTML =
    `<div class="mm-intro">${noticeHTML()}</div>` + legendLine() +
    Object.keys(tabs).map(t=>`
    <section class="mm-part" id="mm-part-${t}" data-tab="${t}">
      <h3 class="mm-part-h">${ui['tab_'+t]}</h3>
      <div class="mm-cols">${tabs[t].map((s,i)=>secHTML(s,t,i)).join('')}</div>
    </section>`).join('');
  if(window.revealMenu) revealMenu();   /* подложки разделов мягко появляются при прокрутке меню (скрипт «движение») */
}

function renderCats(){
  const cats=document.getElementById('mm-cats');
  cats.innerHTML = curTabs()[menuTab].map((s,i)=>
    `<button class="mm-cat${menuCat===i?' on':''}" type="button" onclick="goMenuCat(${i})">${T(s.t)}</button>`).join('');
  centerCat(false);
}
function centerCat(smooth){
  const cats=document.getElementById('mm-cats'), on=cats.querySelector('.mm-cat.on');
  if(on) cats.scrollTo({left:Math.max(0, on.offsetLeft-(cats.clientWidth-on.offsetWidth)/2), behavior:smooth&&!RM.matches?'smooth':'auto'});
}

function renderTabs(){
  const ui=MENU_UI[menuLang], tabs=document.getElementById('mm-tabs');
  if(menuQ!==null){
    tabs.innerHTML = `<div class="mm-search"><svg class="ic" aria-hidden="true" focusable="false"><use href="#i-search"/></svg>` +
      `<input id="mm-q" type="search" enterkeyhint="search" autocomplete="off" placeholder="${ui.search}" aria-label="${ui.search}" value="${escA(menuQ)}" oninput="menuSearch(this.value)">` +
      `<button type="button" class="mm-search-x" aria-label="${ui.close}" onclick="closeSearch()">×</button></div>`;
    return;
  }
  tabs.innerHTML = Object.keys(curTabs()).map(t=>
    `<button class="mm-tab${t===menuTab?' on':''}" type="button" onclick="switchMenuTab('${t}')">${ui['tab_'+t]}</button>`).join('') +
    `<button type="button" class="mm-search-btn" aria-label="${ui.search}" title="${ui.search}" onclick="openSearch()"><svg class="ic" aria-hidden="true" focusable="false"><use href="#i-search"/></svg></button>`;
}

/* ── Поиск по меню (правка владельца 1.11): кнопка-лупа после вкладок → поле вместо вкладок. Ищет по всем вкладкам текущего
   режима (кофейни или bakery to go) — по названию на текущем языке и по-русски, без учёта регистра и ё/е. Результаты —
   строки того же вида с подписью раздела; Esc или крестик — назад к вкладкам. В аналитику — только длина запроса. ── */
let menuQ=null, searchTimer=0;
const normQ=s=>String(s).toLowerCase().replace(/ё/g,'е').replace(/\s+/g,' ').trim();
function openSearch(){
  menuQ=''; hidePop();
  renderTabs(); document.getElementById('mm-cats').hidden=true; renderFeed();
  const q=document.getElementById('mm-q'); if(q&&q.focus) q.focus();
}
function closeSearch(){
  if(menuQ===null) return false;
  menuQ=null; clearTimeout(searchTimer);
  const f=document.querySelector('#mm-tabs .mm-search'), q=document.getElementById('mm-q'); if(q&&q.blur) q.blur();
  const back=()=>{ if(menuQ!==null) return;
    document.getElementById('mm-cats').hidden=false;
    const c=document.getElementById('mm-cols'); c.classList.remove('in'); renderTabs(); renderFeed(); renderCats(); lockSpy(); document.getElementById('menu-modal').scrollTop=0; enter(c); };
  f ? gone(f, back) : back();
  return true;
}
function searchHits(q){
  const n=normQ(q), out=[];
  if(!n) return out;
  const tabs=curTabs();
  Object.keys(tabs).forEach(t=>tabs[t].forEach(s=>s.items.forEach(it=>{
    if(normQ(it.n).includes(n) || normQ(T(it.n)).includes(n)) out.push({it, s});
  })));
  return out;
}
function searchHTML(){
  const ui=MENU_UI[menuLang];
  if(!normQ(menuQ)) return '';
  const hits=searchHits(menuQ);
  if(!hits.length) return `<p class="mm-search-none">${ui.search_none}</p>`;
  return `<section class="mm-sec mm-results">${hits.map(h=>itemHTML(h.it, h.s.t, T(h.s.t))).join('')}</section>`;
}
function menuSearch(q){
  menuQ=q;
  renderFeed();
  document.getElementById('menu-modal').scrollTop=0;
  clearTimeout(searchTimer);
  if(normQ(q)) searchTimer=setTimeout(()=>track('menu_search',{len:normQ(q).length, found:searchHits(q).length}), 800);
}

/* подсветка вкладки и категории; при смене вкладки полоса категорий показывает её разделы */
function setActive(tab, cat){
  if(tab!==menuTab){ menuTab=tab; menuCat=cat; renderTabs(); renderCats(); return; }
  if(cat===menuCat) return;
  menuCat=cat;
  document.querySelectorAll('#mm-cats .mm-cat').forEach((b,i)=>b.classList.toggle('on', i===cat));
  centerCat(true);
}

/* прокрутка к месту с поправкой на липкую шапку (на мобильном при движении вниз верх шапки уезжает) */
let spyLock=false, spyTimer=0;
function lockSpy(){ spyLock=true; clearTimeout(spyTimer); spyTimer=setTimeout(()=>{ spyLock=false; }, 900); }
function scrollToMenuEl(el, smooth){
  if(!el) return;
  const modal=document.getElementById('menu-modal'), head=modal.querySelector('.mm-head');
  const y=el.getBoundingClientRect().top - modal.getBoundingClientRect().top + modal.scrollTop;
  const down = y > modal.scrollTop;
  const off = (mmMobile.matches && down ? head.offsetHeight - modal.querySelector('.mm-top').offsetHeight : head.offsetHeight) + 10;
  lockSpy();
  modal.scrollTo({top:Math.max(0, y-off), behavior:smooth===false||RM.matches?'auto':'smooth'});
}
function menuSpy(){
  if(spyLock) return;
  const modal=document.getElementById('menu-modal'), feed=document.getElementById('mm-cols');
  const probe=modal.querySelector('.mm-head').getBoundingClientRect().bottom + 16;
  const parts=[...feed.querySelectorAll('.mm-part')]; if(!parts.length) return;
  let part=parts[0];
  const atEnd = modal.scrollTop + modal.clientHeight >= modal.scrollHeight - 4;
  if(atEnd) part=parts[parts.length-1];
  else parts.forEach(p=>{ if(p.getBoundingClientRect().top<=probe) part=p; });
  let cat=0, best=-Infinity;
  part.querySelectorAll('.mm-sec').forEach(sec=>{ const t=sec.getBoundingClientRect().top; if(t<=probe && t>=best){ best=t; cat=+sec.dataset.i; } });
  setActive(part.dataset.tab, cat);
}

function menuJump(id){
  const c=document.getElementById('mm-cols');
  c.classList.remove('in');
  gone(c, ()=>{ c.classList.add('pre'); scrollToMenuEl(document.getElementById(id), false); enter(c); });
}
function switchMenuTab(tab){
  setActive(tab, 0);
  menuJump('mm-part-'+tab);
  track('menu_tab',{mode:menuMode, tab});
}
function goMenuCat(i, now){
  setActive(menuTab, i);
  if(now) scrollToMenuEl(document.getElementById(`mm-sec-${menuTab}-${i}`), false);
  else menuJump(`mm-sec-${menuTab}-${i}`);
  track('menu_cat',{mode:menuMode, tab:menuTab, cat:curTabs()[menuTab][i].t});
}

/* новая лента режима — с начала */
function renderMenuStart(){
  menuTab=Object.keys(curTabs())[0]; menuCat=0;
  renderFeed(); renderTabs(); renderCats();
  lockSpy(); document.getElementById('menu-modal').scrollTop=0;
}

function setMenuMode(mode){
  const next = mode==='togo' ? 'togo' : 'cafe';
  menuMode = next;
  document.querySelectorAll('.mm-mode-btn').forEach(b=>{ b.classList.toggle('on', b.dataset.mode===menuMode); b.setAttribute('aria-pressed', b.dataset.mode===menuMode); });
}
function switchMenuMode(mode){ setMenuMode(mode); renderMenuStart(); track('menu_mode',{mode:menuMode}); }

/* openMenu() — меню кофеен; openMenu('togo') — меню точки 05 Bakery to go */
let menuOpener=null;
function openMenu(mode){
  const m=document.getElementById('menu-modal');
  if(!m.classList.contains('open')) menuOpener=document.activeElement;
  stay(m);
  applyMenuLang();
  setMenuMode(mode);
  m.classList.add('open'); bg(1);
  renderMenuStart(); enter(m);
  loadCards(); scheduleIdlePrefetch();
  document.body.style.overflow='hidden';
  document.querySelector('#menu-modal .mm-head').classList.remove('compact');
  setTopH(); syncLangAria();
  document.getElementById('mm-x').focus({preventScroll:true});
  track('menu_open',{mode:menuMode});
}
/* меню не на РУС закрыли — на главную его языка */
function closeMenu(){
  const m=document.getElementById('menu-modal'), was=m.classList.contains('open');
  if(was&&menuLang!='ru'){ location.replace('/'+menuLang+'/'); return; }
  closeCard(); hidePop(); closeLangMenu();
  if(menuQ!==null){ menuQ=null; clearTimeout(searchTimer); document.getElementById('mm-cats').hidden=false; }
  m.classList.remove('open','in'); if(was) gone(m,()=>bg(0));   /* видео — когда меню ушло */
  document.body.style.overflow='';
  if(MENU_HASH.test(location.hash))history.replaceState(null,'',location.pathname+location.search);
  if(was&&menuOpener&&menuOpener.focus) menuOpener.focus();
  menuOpener=null;
}
/* Глубокие ссылки (hasMenu в JSON-LD): /#menu — меню кофеен, /#menu-togo — меню точки 05 Bakery to go */
/* …-kk / -en в конце (/#menu-kk, /#menu-togo-en) — меню сразу на этом языке, как кнопка языка в самом меню (ссылки с /kk/ и /en/);
   /#menu-grill(-kk|-en) — меню кофеен сразу на «Блюда на гриле» (плитка «Курицы гриль» на /kk/ и /en/) */
const MENU_HASH=/^#menu(-togo|-grill)?(?:-(kk|ru|en))?$/;
function menuFromHash(){
  const m=MENU_HASH.exec(location.hash);
  if(!m)return;
  if(m[2]) dcSave(menuLang=m[2]);
  if(m[1]==='-grill'){ showGrill(); return; }
  openMenu(m[1]?'togo':undefined);
}

/* над меню — одна строка: аллергия всегда, сервисный сбор — только в режимах с fee:true. Кнопки «Меню Жандосова / Меню
   кофеен» и адресов больше нет (владелец, 31.10): режим переключает «Кофейни / Bakery to go» в шапке, адреса — на главной */
function noticeHTML(){
  const ui=MENU_UI[menuLang];
  return `<p class="mm-notice">${ui.allergy.replace(/\s*<br>\s*/g,' ')}${MENU_MODES[menuMode].fee?` · ${ui.fee}`:''}</p>`;
}

/* ── «Есть не во всех кофейнях»: значок «!» у позиции с only:['03','01'] (номера точек из BRANCHES) ── */
const mmMobile = window.matchMedia('(max-width:680px)');
const mmHover = window.matchMedia('(hover:hover)');
function branchLabel(id){
  const b = BRANCHES.find(b=>b.n.startsWith(id+' '));
  if(!b) return id;
  return `${T(b.n.slice(b.n.indexOf(' · ')+3))} (${T(b.addr)})`;
}
function onlyBtn(it){
  return it.only ? `<button type="button" class="mm-only" data-only="${it.only.join(',')}" aria-label="${MENU_UI[menuLang].only_aria}" aria-expanded="false" aria-controls="mm-pop">!</button>` : '';
}
let popBtn=null, popPinned=false;
function showPop(btn, pin){
  const pop=document.getElementById('mm-pop');
  if(popBtn && popBtn!==btn){ popBtn.setAttribute('aria-expanded','false'); popBtn.removeAttribute('aria-describedby'); }
  popBtn=btn; popPinned=pin;
  pop.innerHTML = `<b>${MENU_UI[menuLang].only}</b>` + btn.dataset.only.split(',').map(id=>`<div>${branchLabel(id)}</div>`).join('');
  stay(pop); pop.hidden=false;
  btn.setAttribute('aria-expanded','true'); btn.setAttribute('aria-describedby','mm-pop');
  const r=btn.getBoundingClientRect(), w=pop.offsetWidth, h=pop.offsetHeight;
  const vw=document.documentElement.clientWidth, vh=window.innerHeight;
  let top=r.bottom+8; if(top+h>vh-8) top=Math.max(8, r.top-h-8);
  pop.style.left = Math.max(8, Math.min(r.left+r.width/2-w/2, vw-w-8))+'px';
  pop.style.top = top+'px';
}
function hidePop(){
  const pop=document.getElementById('mm-pop');
  if(!pop || pop.hidden) return false;
  pop.hidden=true; gone(pop);
  if(popBtn){ popBtn.setAttribute('aria-expanded','false'); popBtn.removeAttribute('aria-describedby'); }
  popBtn=null; popPinned=false;
  return true;
}

/* ── Карточка блюда: фото / описание / состав / КБЖУ из menu/cards.json.
   Файл грузится один раз при первом открытии меню (иначе не узнать, какие названия кликабельны),
   кэш — в CARDS; без записи название остаётся обычным текстом, пустой карточки не бывает. ── */
const CARDS_URL='menu/cards.json';
let cardsReq=null, cardName=null, cardOpener=null;
function loadCards(){
  if(cardsReq) return cardsReq;
  cardsReq = fetch(CARDS_URL).then(r=>r.ok?r.json():{}).catch(()=>({})).then(j=>{
    CARDS = (j && typeof j==='object' && !Array.isArray(j)) ? j : {};
    const m=document.getElementById('menu-modal');
    if(Object.keys(CARDS).length && m.classList.contains('open')) setTimeout(()=>{ if(m.classList.contains('open')){ renderFeed(); scheduleIdlePrefetch(); } }, 320);
    return CARDS;
  });
  return cardsReq;
}
function cardLang(o){ return o ? (o[menuLang] || o.ru || '') : ''; }
/* пропорция контейнера фото: натуральная w/h, но не уже 4/5 (совсем высокие — с полями по бокам) */
function picRatio(ar){
  const r = ar && ar[1] ? ar[0]/ar[1] : 4/3;
  return Math.max(r, 0.8).toFixed(3);
}
/* ── Префетч фото карточек: в простое — видимые и следующие ~10, при касании названия — сразу ── */
const prefetched = new Set();
function cardImgSrc(c){ return (mmMobile.matches && c.img480) ? c.img480 : c.img; }
function prefetchCard(key){
  const c = CARDS && CARDS[key]; if(!c || !c.img) return;
  const src = cardImgSrc(c); if(prefetched.has(src)) return;
  prefetched.add(src);
  const im = new Image(); im.decoding = 'async'; im.src = src;
}
let idleHandle = 0;
function scheduleIdlePrefetch(){
  if(!CARDS || idleHandle) return;
  const run = () => { idleHandle = 0; prefetchVisible(); };
  idleHandle = window.requestIdleCallback ? requestIdleCallback(run, {timeout: 1500}) : setTimeout(run, 300);
}
function prefetchVisible(){
  const modal = document.getElementById('menu-modal');
  if(!modal.classList.contains('open')) return;
  const els = [...document.querySelectorAll('#mm-cols .nm-t.has-card')];
  const vh = window.innerHeight; let after = 0;
  for(const el of els){
    const r = el.getBoundingClientRect();
    const visible = r.bottom > 0 && r.top < vh;
    if(visible || (r.top >= vh && after < 10)){ prefetchCard(cardKey(el.dataset.n, el.dataset.sec)); if(!visible) after++; }
    if(after >= 10) break;
  }
}
function cardW(w){
  if(menuLang==='en') return w.replace(/(\d)\s*гр?(?![а-яё])/g,'$1 g').replace(/мл/g,'ml');
  if(menuLang==='kk') return w.replace(/(\d)\s*гр(?![а-яё])/g,'$1 г');
  return w;
}
/* позиция меню для карточки: «Название @ Раздел» — в этом разделе; ищем в текущем режиме, потом в остальных */
function findItem(key){
  const [name, sec]=key.split(' @ ');
  const modes=[menuMode].concat(Object.keys(MENU_MODES).filter(m=>m!==menuMode));
  for(const m of modes) for(const arr of Object.values(MENU_MODES[m].tabs)) for(const s of arr){
    if(sec && s.t!==sec) continue;
    const it=s.items.find(x=>x.n===name); if(it) return {it, s};
  }
  return null;
}
/* цена карточки — пилюлей forest: цена позиции (или раздела), старая — зачёркнута */
function cardPrice(key){
  const f=findItem(key); if(!f) return '';
  const p=f.it.p!=null?f.it.p:f.s.p; if(p==null) return '';
  return `<div class="mm-card-p">${f.it.old?`<span class="old">${fmtP(f.it.old)}</span> `:''}${fmtP(p)}&nbsp;₸</div>`;
}
function cardHTML(key){
  const c=CARDS[key], name=key.split(' @ ')[0], ui=MENU_UI[menuLang], k=c.kbju, d=cardLang(c.d), ing=cardLang(c.ing);
  return `<button type="button" class="mm-card-x" aria-label="${ui.close}">×</button>` +
    (c.img ? `<div class="mm-card-pic" style="aspect-ratio:${picRatio(c.ar)}"><img class="mm-card-img" src="${escA(c.img)}"${c.img480?` srcset="${escA(c.img480)} 480w, ${escA(c.img)} 960w" sizes="(max-width:680px) calc(100vw - 44px), 476px"`:''}${c.ar?` width="${c.ar[0]}" height="${c.ar[1]}"`:''} alt="" fetchpriority="high" decoding="async"></div>` : '') +
    `<h3 class="mm-card-t" id="mm-card-t">${T(name)}</h3>` + cardPrice(key) +
    (c.w ? `<div class="mm-card-w">${ui.card_w}: ${escA(cardW(String(c.w)))}</div>` : '') +
    (d ? `<p class="mm-card-d">${escA(d)}</p>` : '') +
    (ing ? `<div class="mm-card-h">${ui.card_ing}</div><p class="mm-card-ing">${escA(ing)}</p>` : '') +
    (k ? `<div class="mm-card-h">${ui.card_kbju}</div><div class="mm-card-k">` +
         [[k.kcal,ui.kcal],[k.p,ui.prot],[k.f,ui.fat],[k.c,ui.carb]].map(([v,l])=>`<div><b>${v==null?'—':escA(v)}</b><span>${l}</span></div>`).join('') + `</div>` : '');
}
function openCard(name, opener, sec){
  const key=cardKey(name, sec);
  if(!key) return false;
  hidePop(); closeLangMenu();
  const wrap=document.getElementById('mm-card'), box=document.getElementById('mm-card-box');
  cardName=key; cardOpener=opener||document.activeElement;
  box.innerHTML=cardHTML(key);
  stay(wrap); wrap.hidden=false; enter(wrap);
  document.getElementById('menu-modal').style.overflow='hidden';
  box.scrollTop=0; box.focus();
  track('menu_card',{name:key});
  return true;
}
function closeCard(){
  const wrap=document.getElementById('mm-card');
  if(!wrap || wrap.hidden) return false;
  wrap.hidden=true; wrap.classList.remove('in'); gone(wrap); cardName=null;
  document.getElementById('menu-modal').style.overflow='';
  if(cardOpener && cardOpener.focus) cardOpener.focus();
  cardOpener=null;
  return true;
}
/* смена языка при открытой карточке — перерисовать её */
function refreshCard(){
  if(!cardName) return;
  if(CARDS && CARDS[cardName]) document.getElementById('mm-card-box').innerHTML=cardHTML(cardName);
  else closeCard();
}

/* язык на мобильном: видна только текущая кнопка, тап раскрывает список */
function syncLangAria(){
  document.querySelectorAll('.mm-lang-btn').forEach(b=>{
    if(mmMobile.matches && b.classList.contains('on')) b.setAttribute('aria-expanded', document.querySelector('.mm-lang').classList.contains('open'));
    else b.removeAttribute('aria-expanded');
  });
}
function closeLangMenu(){
  const l=document.querySelector('.mm-lang');
  if(!l.classList.contains('open')) return false;
  l.classList.remove('open'); gone(l); syncLangAria(); return true;
}
function menuLangClick(lang){
  const l=document.querySelector('.mm-lang');
  if(mmMobile.matches && lang===menuLang && !l.classList.contains('open')){ stay(l); l.classList.add('open'); syncLangAria(); return; }
  if(l.classList.contains('open')){ l.classList.remove('open'); gone(l); }
  if(lang!==menuLang) switchMenuLang(lang);
  syncLangAria();
}

/* высота верхней строки шапки — на мобильном она уезжает при прокрутке вниз, категории остаются */
function setTopH(){
  const m=document.getElementById('menu-modal');
  m.style.setProperty('--mm-top-h', m.querySelector('.mm-top').offsetHeight+'px');
}

(function(){
  const modal=document.getElementById('menu-modal'), head=modal.querySelector('.mm-head'), cols=document.getElementById('mm-cols');
  cols.addEventListener('click', e=>{
    const b=e.target.closest('.mm-only');
    if(b){ if(popBtn===b && popPinned) hidePop(); else showPop(b, true); return; }
    const row=e.target.closest('.mm-it.has-card');
    if(row) openCard(row.dataset.n, row.querySelector('.nm-t.has-card')||row, row.dataset.sec);
  });
  cols.addEventListener('mouseover', e=>{
    const b=e.target.closest('.mm-only');
    if(b && mmHover.matches && !popPinned) showPop(b, false);
  });
  cols.addEventListener('mouseout', e=>{
    const b=e.target.closest('.mm-only');
    if(b && mmHover.matches && !popPinned && !b.contains(e.relatedTarget)) hidePop();
  });
  /* касание/нажатие на название — фото карточки запрашиваем ещё до клика */
  const touchPrefetch = e=>{ const nb=e.target.closest('.nm-t.has-card'); if(nb) prefetchCard(cardKey(nb.dataset.n, nb.dataset.sec)); };
  cols.addEventListener('pointerdown', touchPrefetch, {passive:true});
  cols.addEventListener('touchstart', touchPrefetch, {passive:true});
  cols.addEventListener('keydown', e=>{
    if(e.key!=='Enter' && e.key!==' ') return;
    const nb=e.target.closest('.nm-t.has-card'); if(!nb) return;
    e.preventDefault(); openCard(nb.dataset.n, nb, nb.dataset.sec);
  });
  /* карточка блюда: крестик, фон; Tab не уходит из карточки (и из меню) */
  const card=document.getElementById('mm-card'), cardBox=document.getElementById('mm-card-box');
  card.addEventListener('click', e=>{ if(e.target.closest('.mm-card-x, .mm-card-bg')) closeCard(); });
  modal.addEventListener('keydown', e=>trapTab(e, cardName?cardBox:modal));
  modal.addEventListener('click', e=>{
    if(!e.target.closest('.mm-only, #mm-pop')) hidePop();
    if(!e.target.closest('.mm-lang')) closeLangMenu();
  });
  /* Esc сначала закрывает карточку / окошко / список языков, а не всё меню */
  window.addEventListener('keydown', e=>{
    if(e.key!=='Escape' || !modal.classList.contains('open')) return;
    if(closeCard()){ e.stopPropagation(); return; }
    const b=popBtn;
    if(hidePop()){ e.stopPropagation(); if(b) b.focus(); }
    else if(closeLangMenu()){ e.stopPropagation(); modal.querySelector('.mm-lang-btn.on').focus(); }
    else if(closeSearch()){ e.stopPropagation(); }
  }, true);
  let lastY=0, spyRaf=0;
  modal.addEventListener('scroll', ()=>{
    const y=modal.scrollTop;
    hidePop();
    closeLangMenu();
    if(!mmMobile.matches || y<120) head.classList.remove('compact');
    else if(y>lastY+6) head.classList.add('compact');
    else if(y<lastY-6) head.classList.remove('compact');
    lastY=y;
    if(spyLock){ clearTimeout(spyTimer); spyTimer=setTimeout(()=>{ spyLock=false; menuSpy(); }, 150); }
    else if(!spyRaf) spyRaf=requestAnimationFrame(()=>{ spyRaf=0; menuSpy(); });
    scheduleIdlePrefetch();
  }, {passive:true});
  window.addEventListener('resize', ()=>{
    hidePop();
    if(modal.classList.contains('open')){ setTopH(); syncLangAria(); }
    if(!mmMobile.matches) head.classList.remove('compact');
  });
})();

/* Акция «Курица гриль»: открыть меню на разделе «Блюда на гриле» (функции меню — зона menu-i18n, здесь только вызовы) */
function openGrill(){ track('cta_grill'); showGrill(); }
/* раздел — по индексу в данных: и в меню ҚАЗ / ENG */
function showGrill(){
  openMenu();
  var i=MENU_KITCHEN.findIndex(function(s){return s.t==='Блюда на гриле'});
  if(i>=0)requestAnimationFrame(function(){goMenuCat(i,true)});
}
menuFromHash(); addEventListener('hashchange',menuFromHash);
/* Видео акции: без autoplay/preload — play() только когда блок виден (IntersectionObserver), пауза вне экрана; reduced-motion — только постер */
(function(){
  var v=document.querySelector('.grill-video'); if(!v)return;
  if(matchMedia('(prefers-reduced-motion:reduce)').matches)return;
  v.muted=true;
  function play(){var p=v.play();if(p&&p.catch)p.catch(function(){})}
  if(!('IntersectionObserver'in window)){play();return}
  new IntersectionObserver(function(es){es.forEach(function(e){e.isIntersecting?play():v.pause()})},{threshold:.25}).observe(v);
})();

/* Ранний клик: пока файл грузился, заглушки из index.html складывали вызовы в window.dcQ — повторить последний
   (меню или окно по #menu в адресе уже открыты — не повторяем: второй menu_open не нужен) */
(function(){
  const q=window.dcQ||[], c=q[q.length-1];
  window.dcQ=null;
  if(c&&!['menu-modal','modal'].some(id=>document.getElementById(id).classList.contains('open'))) window[c[0]].apply(window,c[1]);
})();
