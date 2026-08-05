// Genere automatiquement par generer_site.py
const CACHE = "mmaradar-v65";
const SOCLE = ["./", "./index.html", "./fond.jpg",
               "./icones/icone-192.png", "./icones/icone-512.png"];

self.addEventListener("install", function (e) {
  e.waitUntil(
    caches.open(CACHE)
      .then(function (c) { return c.addAll(SOCLE).catch(function () {}); })
      .then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener("activate", function (e) {
  e.waitUntil(
    caches.keys().then(function (cles) {
      return Promise.all(cles.map(function (k) {
        if (k !== CACHE) { return caches.delete(k); }
      }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener("fetch", function (e) {
  const req = e.request;
  if (req.method !== "GET") { return; }

  const url = new URL(req.url);
  const donnee = req.mode === "navigate"
    || url.pathname.endsWith(".html")
    || url.pathname.endsWith(".json")
    || url.pathname.endsWith(".ics");

  if (donnee) {
    // reseau d'abord : le calendrier doit toujours etre a jour
    e.respondWith(
      fetch(req).then(function (rep) {
        const copie = rep.clone();
        caches.open(CACHE).then(function (c) { c.put(req, copie); });
        return rep;
      }).catch(function () { return caches.match(req); })
    );
    return;
  }

  // images, icones, polices : cache d'abord, mise a jour en arriere-plan
  e.respondWith(
    caches.match(req).then(function (garde) {
      const reseau = fetch(req).then(function (rep) {
        const copie = rep.clone();
        caches.open(CACHE).then(function (c) { c.put(req, copie); });
        return rep;
      }).catch(function () { return garde; });
      return garde || reseau;
    })
  );
});
