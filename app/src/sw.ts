/// <reference lib="webworker" />
/** Service worker : appli disponible hors ligne + notifications push. */

import { clientsClaim } from "workbox-core";
import { cleanupOutdatedCaches, createHandlerBoundToURL, precacheAndRoute } from "workbox-precaching";
import { NavigationRoute, registerRoute } from "workbox-routing";
import { CacheFirst, NetworkFirst, StaleWhileRevalidate } from "workbox-strategies";

declare const self: ServiceWorkerGlobalScope;

self.skipWaiting();
clientsClaim();
cleanupOutdatedCaches();
precacheAndRoute(self.__WB_MANIFEST);

// Pages : toujours l'appli (navigation par hash)
registerRoute(new NavigationRoute(createHandlerBoundToURL("/index.html"), { denylist: [/^\/api\//] }));

// Données du voyage et alertes : réseau d'abord, dernière version si hors ligne
registerRoute(({ url }) => url.pathname === "/api/trip" || url.pathname === "/api/watches", new NetworkFirst({ cacheName: "api", networkTimeoutSeconds: 8 }));

// Liste des aéroports et logos des compagnies
registerRoute(({ url }) => url.pathname === "/airports.json", new StaleWhileRevalidate({ cacheName: "static" }));
registerRoute(({ url }) => url.hostname === "www.gstatic.com" && url.pathname.includes("airline_logos"), new CacheFirst({ cacheName: "logos" }));

type PushData = { title?: string; body?: string; url?: string; tag?: string };

self.addEventListener("push", (event) => {
  let data: PushData = {};
  try {
    data = event.data?.json() ?? {};
  } catch {
    data = { body: event.data?.text() };
  }
  event.waitUntil(
    self.registration.showNotification(data.title || "Google Tracker", {
      body: data.body || "",
      icon: "/icons/icon-192.png",
      badge: "/icons/icon-192.png",
      tag: data.tag || undefined,
      data: { url: data.url || "/" },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const path = (event.notification.data?.url as string) || "/";
  const target = new URL(path, self.location.origin).href;
  event.waitUntil(
    (async () => {
      const wins = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      for (const w of wins) {
        if ("focus" in w) {
          await (w as WindowClient).navigate(target).catch(() => undefined);
          return (w as WindowClient).focus();
        }
      }
      return self.clients.openWindow(target);
    })(),
  );
});
