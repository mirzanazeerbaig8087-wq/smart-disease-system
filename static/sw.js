// Predict AI - Service Worker
const CACHE_NAME = "predict-ai-v1";
const urlsToCache = [
  "/",
  "/login",
  "/icon-192.png",
  "/icon-512.png",
  "/static/cover-bg.jpg"
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener("fetch", event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        return response || fetch(event.request);
      })
  );
});