const CACHE = "cajui-v1";
const ASSETS = [
  "/static/style.css", "/static/app.js", "/static/pwa.js", "/static/login.js",
  "/static/icon-192.png", "/static/icon-512.png", "/static/manifest.webmanifest",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  if (url.pathname.startsWith("/api/")) return; // dados pessoais nunca passam pelo cache do SW

  // assets estáticos: cache primeiro, atualiza em segundo plano
  if (url.pathname.startsWith("/static/")) {
    e.respondWith(
      caches.match(req).then((hit) => {
        const rede = fetch(req).then((res) => {
          if (res.ok) caches.open(CACHE).then((c) => c.put(req, res.clone()));
          return res;
        }).catch(() => hit);
        return hit || rede;
      })
    );
    return;
  }

  // navegação: rede primeiro; se offline, abre a casca do /painel (os dados vêm do localStorage)
  if (req.mode === "navigate") {
    e.respondWith(
      fetch(req).then((res) => {
        if (url.pathname === "/painel" && res.ok && !res.redirected) {
          caches.open(CACHE).then((c) => c.put("/painel", res.clone()));
        }
        return res;
      }).catch(() => caches.match("/painel").then((r) => r || Response.error()))
    );
  }
});
