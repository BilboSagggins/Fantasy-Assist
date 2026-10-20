// RosterIQ service worker: makes the site installable and opens instantly.
// Bump VERSION whenever index.html changes so phones pick up the update.
const VERSION = 'rosteriq-v12';
const SHELL = ['./', './index.html', './manifest.webmanifest', './icons/icon-192.png', './icons/icon-512.png', './icons/logo.png'];
const STATIC_HOSTS = ['cdn.tailwindcss.com', 'cdnjs.cloudflare.com', 'cdn.jsdelivr.net', 'fonts.googleapis.com', 'fonts.gstatic.com'];

self.addEventListener('install', event => {
    event.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys()
            .then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k))))
            .then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', event => {
    const req = event.request;
    if (req.method !== 'GET') return;
    const url = new URL(req.url);

    // The app page: always try the network first so you get the newest version
    if (req.mode === 'navigate' || (url.origin === location.origin && url.pathname.endsWith('/index.html'))) {
        event.respondWith(
            fetch(req)
                .then(res => { const copy = res.clone(); caches.open(VERSION).then(c => c.put('./index.html', copy)); return res; })
                .catch(() => caches.match('./index.html'))
        );
        return;
    }

    // Libraries and fonts: serve from cache, refresh in the background
    if (STATIC_HOSTS.includes(url.hostname)) {
        event.respondWith(
            caches.open(VERSION).then(async cache => {
                const hit = await cache.match(req);
                const net = fetch(req).then(res => { if (res && (res.ok || res.type === 'opaque')) cache.put(req, res.clone()); return res; }).catch(() => hit);
                return hit || net;
            })
        );
        return;
    }

    // Icons and manifest from this site
    if (url.origin === location.origin) {
        event.respondWith(caches.match(req).then(hit => hit || fetch(req)));
    }
    // Everything else (Sleeper, ESPN, headshots) goes straight to the network: live data only
});
