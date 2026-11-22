// 仅用于满足 PWA 安装条件，不缓存任何资源。
// 页面、API、照片全部交给浏览器按正常网络请求处理。
self.addEventListener('install', (event) => {
  event.waitUntil(self.skipWaiting())
})

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim())
})

self.addEventListener('fetch', () => {
  // 故意留空：不调用 respondWith，也不读写 Cache Storage。
})
