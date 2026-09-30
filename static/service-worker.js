/**
 * service-worker.js
 * -----------------
 * Service Worker for PhishingHunter PWA
 * 
 * Strategy:
 * - Cache static shell (HTML, CSS, JS, fonts) for offline viewing
 * - Network-first for API calls (always fresh data)
 * - Never cache scan results (always fresh from server)
 */

const CACHE_NAME = 'phishinghunter-v2.0.0';
const STATIC_CACHE_NAME = 'phishinghunter-static-v2.0.0';

// Static assets to cache (shell only, not data)
const STATIC_ASSETS = [
  '/',
  '/static/manifest.json',
  // Add other static assets here if they exist
  // Note: We don't cache API endpoints or dynamic data
];

/**
 * Install event - cache static shell
 */
self.addEventListener('install', (event) => {
  console.log('[ServiceWorker] Installing...');
  
  event.waitUntil(
    caches.open(STATIC_CACHE_NAME)
      .then((cache) => {
        console.log('[ServiceWorker] Caching static shell');
        // We'll cache selectively - HTML is dynamic, so skip for now
        return cache.addAll(['/static/manifest.json']);
      })
      .then(() => {
        console.log('[ServiceWorker] Installed successfully');
        return self.skipWaiting(); // Activate immediately
      })
      .catch((error) => {
        console.error('[ServiceWorker] Install failed:', error);
      })
  );
});

/**
 * Activate event - clean up old caches
 */
self.addEventListener('activate', (event) => {
  console.log('[ServiceWorker] Activating...');
  
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames.map((cacheName) => {
            if (cacheName !== STATIC_CACHE_NAME && cacheName !== CACHE_NAME) {
              console.log('[ServiceWorker] Deleting old cache:', cacheName);
              return caches.delete(cacheName);
            }
          })
        );
      })
      .then(() => {
        console.log('[ServiceWorker] Activated successfully');
        return self.clients.claim(); // Take control immediately
      })
  );
});

/**
 * Fetch event - network-first strategy for everything
 * 
 * Why network-first for PhishingHunter?
 * - Scan results must ALWAYS be fresh (security-critical)
 * - Dashboard stats must be up-to-date
 * - We can't serve stale security data
 * 
 * We only cache the static shell (manifest.json) for offline
 * installability, but actual functionality requires network.
 */
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  
  // Skip non-GET requests
  if (event.request.method !== 'GET') {
    return;
  }
  
  // Skip cross-origin requests
  if (url.origin !== location.origin) {
    return;
  }
  
  // For manifest.json, serve from cache (enables offline install prompt)
  if (url.pathname === '/static/manifest.json') {
    event.respondWith(
      caches.match(event.request)
        .then((response) => {
          return response || fetch(event.request);
        })
    );
    return;
  }
  
  // For API endpoints, ALWAYS go to network (never cache)
  if (url.pathname.startsWith('/api/') || 
      url.pathname.startsWith('/hunt') ||
      url.pathname.startsWith('/stats') ||
      url.pathname.startsWith('/history') ||
      url.pathname.startsWith('/feedback')) {
    event.respondWith(fetch(event.request));
    return;
  }
  
  // For everything else, network-first with cache fallback
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // Only cache successful responses
        if (response && response.status === 200) {
          const responseClone = response.clone();
          caches.open(CACHE_NAME)
            .then((cache) => {
              cache.put(event.request, responseClone);
            });
        }
        return response;
      })
      .catch(() => {
        // Network failed, try cache
        return caches.match(event.request)
          .then((response) => {
            if (response) {
              return response;
            }
            // If no cache and network failed, return offline page
            return new Response(
              `<html>
                <head>
                  <title>Offline - PhishingHunter</title>
                  <style>
                    body {
                      font-family: 'Courier New', monospace;
                      background: #0a0e1a;
                      color: #00ff88;
                      display: flex;
                      align-items: center;
                      justify-content: center;
                      height: 100vh;
                      margin: 0;
                      text-align: center;
                    }
                    .container {
                      max-width: 500px;
                      padding: 40px;
                    }
                    h1 {
                      font-size: 48px;
                      margin-bottom: 20px;
                      color: #00d4ff;
                    }
                    p {
                      font-size: 16px;
                      line-height: 1.6;
                      color: #00ff8888;
                    }
                  </style>
                </head>
                <body>
                  <div class="container">
                    <h1>📡 OFFLINE</h1>
                    <p>PhishingHunter requires an active network connection to scan URLs and access threat intelligence.</p>
                    <p>Please check your connection and try again.</p>
                  </div>
                </body>
              </html>`,
              {
                headers: { 'Content-Type': 'text/html' }
              }
            );
          });
      })
  );
});

/**
 * Message event - handle messages from app
 */
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

console.log('[ServiceWorker] Loaded');
