/* REL-UNITY mobile — service worker. Precache the shell so the app opens offline on the floor;
   never cache /api (always live); network-first for other /m/ assets with a cache fallback. */
const CACHE = "relunity-m-v4";
const SHELL = ["/m/", "/m/index.html", "/m/m.css", "/m/m.js", "/m/manifest.webmanifest", "/m/icon.svg"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()).catch(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET") return;              // writes go straight to the network
  if (url.pathname.startsWith("/api")) return;         // API is always live, never cached
  e.respondWith(
    fetch(e.request).then(resp => {
      if (resp && resp.ok && url.pathname.startsWith("/m/")) {
        const copy = resp.clone(); caches.open(CACHE).then(c => c.put(e.request, copy));
      }
      return resp;
    }).catch(() => caches.match(e.request).then(r => r || caches.match("/m/index.html")))
  );
});
