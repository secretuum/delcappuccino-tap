/* Ближайшая точка — сверху. Собран tools/seo_jsonld.py из tools/near.js, руками не править */
(function () {
var P = {"+77025672332":[43.20471,76.893091],"+77053673232":[43.201349,76.899537],"+77770355617":[43.240193,76.924982],"+77769079070":[43.254679,76.945854],"+77773278566":[43.220416,76.885263],"+77478839057":[43.21216,76.842353]},
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
