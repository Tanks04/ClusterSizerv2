/* Service worker: "network-first" - uvijek pokušaj dohvatiti svježu
 * datoteku s mreže, a keš koristi samo kao rezervu kad nema interneta.
 * (Ranije je bio "cache-first", što je znalo servirati zastarjelu verziju
 * aplikacije nakon što bi se fileovi ažurirali na hostingu.) */
"use strict";

const CACHE_NAME = "skolski-raspored-v4";
const CORE_ASSETS = [
  "./",
  "./index.html",
  "./css/styles.css",
  "./js/models.js",
  "./js/storage.js",
  "./js/ui.js",
  "./manifest.webmanifest",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./icons/icon-512-maskable.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(CORE_ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response && response.status === 200 && response.type === "basic") {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
