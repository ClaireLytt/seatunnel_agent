// Self-destroying service worker: an earlier build registered a PWA SW at
// this path; this replacement unregisters it and clears its caches so stale
// precached pages stop shadowing new builds. Keep until ~2027.
self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys()
      await Promise.all(keys.map((k) => caches.delete(k)))
      await self.registration.unregister()
      const clients = await self.clients.matchAll({ type: 'window' })
      clients.forEach((c) => c.navigate(c.url))
    })(),
  )
})
