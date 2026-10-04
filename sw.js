// Brier PWA service worker
// Strategy: cache the app shell (index.html) so it opens offline/instantly;
// live data (bugun.json, dun.json, memory JSONs) is always network-first so
// the terminal never shows stale prices — falls back to last cache only if offline.

const SURUM = 'brier-v2';
const KABUK = [
  './',
  './index.html',
  './manifest.json'
];

// install: cache the shell
self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(SURUM).then((c) => c.addAll(KABUK)).catch(() => {})
  );
  self.skipWaiting();
});

// activate: drop old caches
self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((anahtarlar) =>
      Promise.all(anahtarlar.filter((k) => k !== SURUM).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// fetch:
//  - data JSONs + worker API → network-first (fresh prices), cache fallback offline
//  - everything else (shell, fonts) → cache-first, then network
self.addEventListener('fetch', (e) => {
  const url = e.request.url;
  // index.html + kok de network-first (her acilista taze build) + canli veri
  const kabukTaze = /\/index\.html$|\/$/.test(new URL(url).pathname);
  const canliVeri = kabukTaze || /bugun\.json|dun\.json|brier_.*\.json|\.up\.railway\.app/.test(url);

  if (canliVeri) {
    // network-first: always try live, cache only as offline fallback
    e.respondWith(
      fetch(e.request)
        .then((r) => {
          const kopya = r.clone();
          caches.open(SURUM).then((c) => c.put(e.request, kopya)).catch(() => {});
          return r;
        })
        .catch(() => caches.match(e.request))
    );
    return;
  }

  // shell/static: cache-first
  e.respondWith(
    caches.match(e.request).then((cached) => cached || fetch(e.request).then((r) => {
      // cache same-origin GETs opportunistically
      if (e.request.method === 'GET' && r.status === 200 && url.startsWith(self.location.origin)) {
        const kopya = r.clone();
        caches.open(SURUM).then((c) => c.put(e.request, kopya)).catch(() => {});
      }
      return r;
    }).catch(() => cached))
  );
});
