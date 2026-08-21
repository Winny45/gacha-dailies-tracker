/* Service worker: makes the app open instantly and keep working offline.
 *
 * Two strategies, because the two kinds of file want opposite things:
 *   - app shell + images: cache-first (they rarely change, and speed wins)
 *   - data/*.json: network-first (a daily rebuild publishes new data, so
 *     prefer fresh, but fall back to the last copy when there's no signal)
 */
const VERSION = 'gdt-v1';
const SHELL = `${VERSION}-shell`;
const DATA = `${VERSION}-data`;

const SHELL_FILES = [
  './',
  './index.html',
  './styles.css',
  './app.js',
  './manifest.webmanifest',
  './icons/icon-192.png',
  './icons/icon-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL)
      // don't let one 404 abort the whole install
      .then((cache) => Promise.allSettled(SHELL_FILES.map((f) => cache.add(f))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => !k.startsWith(VERSION)).map((k) => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;  // let CDN/source links pass through

  if (url.pathname.includes('/data/')) {
    event.respondWith(
      fetch(request)
        .then((resp) => {
          const copy = resp.clone();
          caches.open(DATA).then((c) => c.put(request, copy));
          return resp;
        })
        .catch(() => caches.match(request, { ignoreSearch: true }))
    );
    return;
  }

  event.respondWith(
    caches.match(request, { ignoreSearch: true }).then((hit) => hit || fetch(request).then((resp) => {
      const copy = resp.clone();
      caches.open(SHELL).then((c) => c.put(request, copy));
      return resp;
    }))
  );
});
