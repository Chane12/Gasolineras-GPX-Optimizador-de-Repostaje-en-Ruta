// Service Worker mínimo para Gasolineras en Ruta PWA
// Solo gestiona la instalación y activación para habilitar "Add to Home Screen"
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));
