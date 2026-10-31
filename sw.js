/* Service worker tap.delcappuccino.kz — страницы сначала из сети (свежие сразу после выкладки), офлайн — из кэша;
 * картинки и шрифты — из кэша.
 *
 * ПРАВИЛА ПО ПУТЯМ (важно для всех терминалов — menu/ и img/menu/ обновляются без смены имён файлов):
 *   любая навигация (/, /kk/, /en/, /menyu, /ugolok, 404), ./  *.html  *.json (menu/cards.json)  manifest.webmanifest
 *                                      — network-first с тайм-аутом NET_TIMEOUT: сначала сеть, свежий ответ — в кэш
 *                                        оболочки; сеть молчит дольше NET_TIMEOUT или её нет — из кэша (офлайн
 *                                        работает), страницы нет в кэше — главная из кэша; ответы не 2xx не кэшируются.
 *                                        Раньше было stale-while-revalidate — после выкладки все, кто уже заходил,
 *                                        видели прошлую версию до следующего захода (владелец не видел новую кнопку, 23.10)
 *   img/menu/*.webp                    — stale-while-revalidate (перекодируются на том же пути)
 *   assets/* без хэша в имени          — stale-while-revalidate
 *   файлы с хэшем в имени (*.1a2b3c4d.woff2 и т.п.) — cache-first навечно: имя меняется вместе с содержимым
 *   видео (*.mp4, *.webm) и Range-запросы    — мимо service worker, кэширует сам браузер
 *   чужие домены (gtag, 2gis, wa.me, карты) и не-GET — мимо service worker
 *   /legal/* (оферта, политика, контакты мобильного приложения) — мимо service worker: не кэшируются и не
 *                                        перехватываются, браузер всегда берёт их из сети (страницы вне сайта, noindex)
 *
 * Кэши: 'dc-shell-<VERSION>' — оболочка (HTML, cards.json, manifest), 'dc-rt-vN' — картинки и шрифты.
 * VERSION — хэш index.html, его ставит tools/sw_version.py (запускать после правки index.html; тест
 * tests/test_perf.py предупреждает, если забыли). Новый SW ставится сразу (skipWaiting), при активации
 * удаляет старые dc-shell-* и dc-rt-*; кэш картинок между версиями страницы переживает.
 */
var VERSION = '95354e16f3';
var SHELL = 'dc-shell-' + VERSION;
var RT = 'dc-rt-v1';
var PRECACHE = [
  './',
  'manifest.webmanifest',
  'menu/cards.json',
  'assets/fonts/geologica-700-cyrillic.646d6acf.woff2',
  'assets/fonts/geologica-700-latin.7f7f79c5.woff2',
  'assets/fonts/montserrat-400-700-cyrillic.a187b077.woff2',
  'assets/fonts/montserrat-400-700-latin.06b16db7.woff2',
  'assets/logo-text.73de0587.svg',
  'assets/moped-side.5c84289d.svg',
  'assets/logo-lockup-256.webp',
  'assets/logo-mono-192.webp',
  'assets/halal-104.webp'
];
var HASHED = new RegExp('\\.[0-9a-f]{8}\\.(woff2|webp|png|jpg|svg|js|css)$');
var NET_TIMEOUT = 3000;   // мс: дольше ждать сеть для страницы не стоит — отдаём из кэша, свежее допишется в кэш в фоне

function isShell(url) {
  var p = url.pathname;
  return p === '/' || p.slice(-1) === '/' || /\.(html|json|webmanifest)$/.test(p);
}

function cacheKey(req, url) {
  // '/', '/index.html', '/?utm=…' — один и тот же документ
  if (req.mode === 'navigate' && (url.pathname === '/' || url.pathname === '/index.html')) return './';
  return url.origin + url.pathname;
}

self.addEventListener('install', function (e) {
  e.waitUntil(
    Promise.all(PRECACHE.map(function (u) {
      var req = new Request(u, { cache: 'reload' });
      return fetch(req).then(function (res) {
        if (!res.ok) throw new Error('precache ' + u + ': ' + res.status);
        var url = new URL(req.url);
        return caches.open(isShell(url) ? SHELL : RT).then(function (c) { return c.put(cacheKey(req, url), res); });
      });
    })).then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.map(function (k) {
        var stale = (k.indexOf('dc-shell-') === 0 && k !== SHELL) || (k.indexOf('dc-rt-') === 0 && k !== RT);
        return stale ? caches.delete(k) : null;
      }));
    }).then(function () { return self.clients.claim(); })
  );
});

// сначала сеть: свежая страница сразу после выкладки; медленно, офлайн или сбой хостинга (5xx) — из кэша.
// Сеть стартует сразу, не дожидаясь открытия кэша; e.waitUntil — синхронно в обработчике fetch (позже браузер может
// бросить InvalidStateError), поэтому запись свежего ответа в кэш доживёт, даже если посетителю уже отдали кэш.
function networkFirst(e, req, key) {
  var cacheP = caches.open(SHELL), copy = null;
  var net = fetch(req).then(function (res) {
    if (res && res.ok) copy = res.clone();                                         // клон до того, как тело прочтут
    return res;
  });
  e.waitUntil(Promise.all([cacheP, net]).then(function (v) { return copy && v[0].put(key, copy); }).catch(function () {}));
  var fromCache = function () { return cacheP.then(function (c) { return c.match(key); }); };
  var fresh = net.then(function (res) {                                           // 5xx при живом кэше — кэш
    return res.status >= 500 ? fromCache().then(function (cached) { return cached || res; }) : res;
  });
  var slow = new Promise(function (resolve) { setTimeout(resolve, NET_TIMEOUT); }).then(function () {
    return fromCache().then(function (cached) { return cached || fresh; });       // в кэше нет — ждём сеть дальше
  });
  slow.catch(function () {});                                                      // проигравший гонку не шумит в консоли
  return Promise.race([fresh, slow]).catch(function () {                           // сети нет
    return fromCache().then(function (cached) {
      if (cached) return cached;
      if (req.mode !== 'navigate') return Response.error();
      return cacheP.then(function (c) { return c.match('./'); }).then(function (r) { return r || Response.error(); });
    });
  });
}

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') return;
  var url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (/\.(mp4|webm|m4v)$/.test(url.pathname) || req.headers.get('range')) return;   // видео и Range-запросы — браузеру
  if (url.pathname.indexOf('/legal/') === 0) return;                               // юр. страницы приложения — всегда из сети

  var key = cacheKey(req, url);
  if (req.mode === 'navigate' || isShell(url)) {                                   // страницы, HTML, cards.json, manifest
    e.respondWith(networkFirst(e, req, key));
    return;
  }

  e.respondWith(caches.open(RT).then(function (c) {
    return c.match(key).then(function (cached) {
      if (cached && HASHED.test(url.pathname)) return cached;            // cache-first для версионированных
      var update = fetch(req).then(function (res) {
        if (res && res.ok) return c.put(key, res.clone()).then(function () { return res; });
        return res;
      }).catch(function () {
        return cached || Response.error();
      });
      if (cached) {                                                      // stale-while-revalidate: картинки и ассеты без хэша
        e.waitUntil(update.catch(function () {}));
        return cached;
      }
      return update;
    });
  }));
});
