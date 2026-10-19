/* Service worker tap.delcappuccino.kz — повторные заходы из кэша, обновление в фоне, офлайн-оболочка.
 *
 * ПРАВИЛА ПО ПУТЯМ (важно для всех терминалов — menu/ и img/menu/ обновляются без смены имён файлов):
 *   ./  *.html  manifest.webmanifest   — stale-while-revalidate: отдать из кэша, в фоне скачать свежее
 *   любая навигация (/, /ugolok/, 404)  — то же, в кэш оболочки; ответы не 2xx (404) не кэшируются
 *   menu/cards.json                    — stale-while-revalidate (пересобирается скриптом на том же пути)
 *   img/menu/*.webp                    — stale-while-revalidate (перекодируются на том же пути)
 *   assets/* без хэша в имени          — stale-while-revalidate
 *   файлы с хэшем в имени (*.1a2b3c4d.woff2 и т.п.) — cache-first навечно: имя меняется вместе с содержимым
 *   чужие домены (gtag, 2gis, wa.me, карты) и не-GET — мимо service worker
 *
 * Кэши: 'dc-shell-<VERSION>' — оболочка (HTML, cards.json, manifest), 'dc-rt-vN' — картинки и шрифты.
 * VERSION — хэш index.html, его ставит tools/sw_version.py (запускать после правки index.html; тест
 * tests/test_perf.py предупреждает, если забыли). Новый SW ставится сразу (skipWaiting), при активации
 * удаляет старые dc-shell-* и dc-rt-*; кэш картинок между версиями страницы переживает.
 */
var VERSION = 'd367ca465a';
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

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') return;
  var url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  var key = cacheKey(req, url);
  var cacheName = (req.mode === 'navigate' || isShell(url)) ? SHELL : RT;   // навигации (/, /ugolok, 404) — оболочка

  e.respondWith(caches.open(cacheName).then(function (c) {
    return c.match(key).then(function (cached) {
      if (cached && HASHED.test(url.pathname)) return cached;            // cache-first для версионированных
      var update = fetch(req).then(function (res) {
        if (res && res.ok) return c.put(key, res.clone()).then(function () { return res; });
        return res;
      }).catch(function () {
        if (cached) return cached;
        if (req.mode === 'navigate') return caches.open(SHELL).then(function (s) { return s.match('./'); });
        return Response.error();
      });
      if (cached) {                                                      // stale-while-revalidate
        e.waitUntil(update.catch(function () {}));
        return cached;
      }
      return update;
    });
  }));
});
