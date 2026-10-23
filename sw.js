/* Service worker tap.delcappuccino.kz — повторные заходы из кэша, обновление в фоне, офлайн-оболочка.
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
 *
 * Кэши: 'dc-shell-<VERSION>' — оболочка (HTML, cards.json, manifest), 'dc-rt-vN' — картинки и шрифты.
 * VERSION — хэш index.html, его ставит tools/sw_version.py (запускать после правки index.html; тест
 * tests/test_perf.py предупреждает, если забыли). Новый SW ставится сразу (skipWaiting), при активации
 * удаляет старые dc-shell-* и dc-rt-*; кэш картинок между версиями страницы переживает.
 */
var VERSION = '60d5ee2d0a';
var SHELL = 'dc-shell-' + VERSION;
var RT = 'dc-rt-v1';
var PRECACHE = [
  './',
  'manifest.webmanifest',
  'menu/cards.json',
  'assets/fonts/comfortaa-700-cyrillic.52a4b41d.woff2',
  'assets/fonts/comfortaa-700-latin.ed9f328c.woff2',
  'assets/fonts/golos-400-800-cyrillic.17d048ca.woff2',
  'assets/fonts/golos-400-800-latin.9a69d0aa.woff2',
  'assets/logo-lockup-256.webp',
  'assets/logo-mono-192.webp',
  'assets/halal-104.webp',
  'assets/photo_01-800.webp',
  'assets/photo_01-1200.webp'
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

// сначала сеть: свежая страница сразу после выкладки; медленно или офлайн — из кэша
function networkFirst(e, c, req, key) {
  var stored = null;
  var net = fetch(req).then(function (res) {
    if (res && res.ok) stored = c.put(key, res.clone());
    return res;
  });
  e.waitUntil(net.then(function () { return stored; }).catch(function () {}));   // запись в кэш доживёт, даже если ответили кэшем
  var slow = new Promise(function (resolve) { setTimeout(resolve, NET_TIMEOUT); }).then(function () {
    return c.match(key).then(function (cached) { return cached || net; });       // в кэше нет — ждём сеть дальше
  });
  slow.catch(function () {});                                                      // проигравший гонку не шумит в консоли
  return Promise.race([net, slow]).catch(function () {                             // сети нет
    return c.match(key).then(function (cached) {
      if (cached) return cached;
      if (req.mode !== 'navigate') return Response.error();
      return caches.open(SHELL).then(function (s) { return s.match('./'); }).then(function (r) { return r || Response.error(); });
    });
  });
}

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') return;
  var url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (/\.(mp4|webm|m4v)$/.test(url.pathname) || req.headers.get('range')) return;   // видео и Range-запросы — браузеру

  var key = cacheKey(req, url);
  if (req.mode === 'navigate' || isShell(url)) {                                   // страницы, HTML, cards.json, manifest
    e.respondWith(caches.open(SHELL).then(function (c) { return networkFirst(e, c, req, key); }));
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
