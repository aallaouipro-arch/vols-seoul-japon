"""Notifications Web Push (appli installée sur l'écran d'accueil, iPhone iOS 16.4+ et Android).

Clés VAPID dans les variables d'environnement VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY
(générées par scripts/gen_vapid.py). Les abonnements sont rangés par appareil.
"""

import json
import logging
import os

from .store import Store

log = logging.getLogger("tracker")


def public_key() -> str:
    return os.environ.get("VAPID_PUBLIC_KEY", "")


def save_subscription(store: Store, device: str, sub: dict) -> None:
    subs = [s for s in (store.get(f"subs:{device}") or []) if s.get("endpoint") != sub.get("endpoint")]
    store.set(f"subs:{device}", subs + [sub])
    store.sadd("devices", device)


def send(store: Store, device: str, title: str, body: str, url: str = "/", tag: str | None = None) -> int:
    """Envoie à tous les abonnements d'un appareil ; supprime ceux qui ont expiré. → nb envoyés."""
    from pywebpush import WebPushException, webpush

    private = os.environ.get("VAPID_PRIVATE_KEY")
    if not private:
        log.warning("VAPID_PRIVATE_KEY absente : notification non envoyée")
        return 0
    subs = store.get(f"subs:{device}") or []
    payload = json.dumps({"title": title, "body": body, "url": url, "tag": tag}, ensure_ascii=False)
    sent, alive = 0, []
    for sub in subs:
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=private,
                vapid_claims={"sub": os.environ.get("VAPID_SUBJECT", "https://google-tracker.vercel.app")},
                ttl=24 * 3600,
            )
            sent += 1
            alive.append(sub)
        except WebPushException as e:
            status = getattr(e.response, "status_code", None)
            if status in (404, 410):  # abonnement supprimé (appli désinstallée, permission retirée)
                continue
            log.warning("Push en échec (%s) : %s", status, e)
            alive.append(sub)
    if len(alive) != len(subs):
        store.set(f"subs:{device}", alive)
    return sent


def broadcast(store: Store, title: str, body: str, url: str = "/", tag: str | None = None) -> int:
    return sum(send(store, d, title, body, url, tag) for d in store.smembers("devices"))
