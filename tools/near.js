/* Ближайшая точка — сверху (владелец 11.11.2026: «по гео определялась самая ближайшая точка, и карточки с заведениями
   поднимались по отдалённости: в самый верх ближайшая точка, чтобы клиент не искал»).
   Исходник общего файла assets/near.<хэш>.js. Собирает tools/seo_jsonld.py: вписывает точки вместо __POINTS__, снимает
   комментарии и отступы, имя — по хэшу содержимого (sw.js держит такие файлы в кэше навсегда), и ставит
   <script src="/assets/near.<хэш>.js" defer> на /, /kk/, /en/ (за блоком #locations) и /otzyv/ (за карточками).
   Собранный файл руками не править: правка здесь → python3 tools/seo_jsonld.py → python3 tools/sw_version.py.
   В исходнике — только комментарии-блоки и целые строки //: сборка снимает их без разбора JS.

   window.dcNear — то, что раньше жило в окне выбора филиала главной (openModal):
     dist(a, b)     — расстояние по прямой, км, между [широта, долгота] (гаверсинус — бывшая dist() из index.html);
     km(x, lang)    — подпись «1,2 км» (ru, kk) или «1.2 km» (en): одна и та же в окне и на карточках;
     locate(cb, ms) — место человека: cb([широта, долгота]) или cb(null, 'denied' | 'error'); тайм-аут ms, по умолчанию 10 с.
   Карточки (точка карточки — по её ссылке tel:, ключ в P):
     .fb-grid (/otzyv) — спрашиваем сразу при открытии: человек пришёл выбрать филиал, часто по QR прямо в кафе;
     .loc-grid (/, /kk/, /en/) — не при входе, а когда блок попал в экран (IntersectionObserver); если разрешение уже
       дано (Permissions API, где он есть) — сразу, без ожидания блока (запроса браузер не покажет).
     Ближайшая — первой, на каждой — расстояние; точка без координат — в конце. Перестановка: блок на экране — FLIP
     (transform) или проявление (opacity), иначе и при reduced-motion — мгновенно. Без JS порядок исходный.
     Отказ, ошибка, тайм-аут, нет геолокации — порядок прежний, в блоке ничего; на /otzyv — одна спокойная строка .fb-geo
     (её текст — tools/pages_i18n.json, otzyv.geo; без JS скрыта).
   Приватность (строгое правило владельца): координаты человека нигде не сохраняются (ни localStorage, ни cookie, ни
   атрибуты страницы) и никуда не отправляются (ни аналитика, ни сервер, ни логи); в аналитику — одно событие geo_sort
   {result: 'ok' | 'denied' | 'error'}, без координат и расстояний; подписи расстояний — с классом ym-hide-content
   (вебвизор Яндекс Метрики, когда её включат, их не запишет). */
(function () {
  var P = __POINTS__,
    d = document, H = d.documentElement, EZ = 'cubic-bezier(.2,.8,.2,1)';

  function dist(a, b) {
    var R = 6371, dLat = (b[0] - a[0]) * Math.PI / 180, dLon = (b[1] - a[1]) * Math.PI / 180;
    var s = Math.pow(Math.sin(dLat / 2), 2) + Math.cos(a[0] * Math.PI / 180) * Math.cos(b[0] * Math.PI / 180) * Math.pow(Math.sin(dLon / 2), 2);
    return R * 2 * Math.atan2(Math.sqrt(s), Math.sqrt(1 - s));
  }

  function km(x, lang) {
    var s = x.toFixed(1);
    return lang === 'en' ? s + ' km' : s.replace('.', ',') + ' км';
  }

  function locate(cb, ms) {
    var g = navigator.geolocation;
    if (!g) return cb(null, 'error');
    try {
      g.getCurrentPosition(function (p) { cb([p.coords.latitude, p.coords.longitude]); },
        function (e) { cb(null, e && e.code === 1 ? 'denied' : 'error'); },
        { timeout: ms || 1e4, maximumAge: 3e5 });
    } catch (e) { cb(null, 'error'); }
  }

  window.dcNear = { dist: dist, km: km, locate: locate };

  var grid = d.querySelector('.fb-grid'), now = !!grid, asked = false;
  grid = grid || d.querySelector('.loc-grid');
  if (!grid) return;
  var cards = [].slice.call(grid.children).filter(function (c) { return c.querySelector('a[href^="tel:"]'); });
  if (cards.length < 2) return;

  function sort() {
    if (asked) return;
    asked = true;
    locate(function (here, why) {
      if (typeof track === 'function') track('geo_sort', { result: here ? 'ok' : why });
      var calm = !!grid.animate && !(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);
      if (!here) {
        var s = d.querySelector('.fb-geo');
        if (s) {
          s.hidden = false;
          if (calm) s.animate({ opacity: [0, 1] }, { duration: 240, easing: EZ });
        }
        return;
      }
      var list = cards.map(function (c, i) {
        var p = P[c.querySelector('a[href^="tel:"]').getAttribute('href').slice(4)];
        return { c: c, i: i, d: p ? dist(here, p) : Infinity };
      }).sort(function (a, b) { return a.d - b.d || a.i - b.i; });
      var r = grid.getBoundingClientRect(),
        anim = calm && r.bottom > 0 && r.top < (window.innerHeight || H.clientHeight),
        first = anim && cards.map(function (c) { return c.getBoundingClientRect(); }),
        end = cards[cards.length - 1].nextSibling, focus = d.activeElement, labels = [];
      /* стили подписи — здесь, а не в страницах (их вес на пределе); overflow-anchor — браузер не «едет» за карточкой */
      var st = d.createElement('style');
      st.textContent = '.loc-grid,.fb-grid{overflow-anchor:none}' +
        '.near-d{margin:var(--s-2) 0 var(--s-8);font-size:15px;font-weight:600;line-height:1.3;color:var(--c-accent);white-space:nowrap;font-variant-numeric:tabular-nums}' +
        '.fb-card .near-d{margin:var(--s-4) 0 0}';
      d.head.appendChild(st);
      list.forEach(function (x) {
        var a = x.d < Infinity && x.c.querySelector('h3,.fb-addr');
        if (a) {
          var l = d.createElement('p');
          l.className = 'near-d ym-hide-content';
          a.parentNode.insertBefore(l, a.nextSibling);
          labels.push([l, x.d]);
        }
        grid.insertBefore(x.c, end);
      });
      function paint() {
        labels.forEach(function (x) { x[0].textContent = km(x[1], H.lang); });
      }
      paint();
      /* /otzyv меняет язык без перезагрузки (<html lang>) — подписи следом: «км» ↔ «km» */
      if (window.MutationObserver) new MutationObserver(paint).observe(H, { attributes: true, attributeFilter: ['lang'] });
      if (focus && focus !== d.activeElement && focus.focus) try { focus.focus({ preventScroll: true }); } catch (e) {}
      if (!anim) return;
      cards.forEach(function (c, i) {
        var f = first[i], b = c.getBoundingClientRect(), dx = f.left - b.left, dy = f.top - b.top;
        if (Math.abs(f.width - b.width) > 1) c.animate({ opacity: [0, 1] }, { duration: 240, easing: EZ });
        else if (dx || dy) c.animate({ transform: ['translate(' + dx + 'px,' + dy + 'px)', 'none'] }, { duration: 320, easing: EZ });
      });
      labels.forEach(function (x) { x[0].animate({ opacity: [0, 1] }, { duration: 240, easing: EZ }); });
    });
  }

  if (now) return sort();
  function onView() {
    if (!window.IntersectionObserver) return;
    var io = new IntersectionObserver(function (es) {
      if (es[es.length - 1].isIntersecting) { io.disconnect(); sort(); }
    }, { rootMargin: '0px 0px -25% 0px' });
    io.observe(grid);
  }
  try {
    navigator.permissions.query({ name: 'geolocation' }).then(function (s) { s.state === 'granted' ? sort() : onView(); }, onView);
  } catch (e) { onView(); }
})();
