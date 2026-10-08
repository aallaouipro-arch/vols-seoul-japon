"""Notifications.

- Push (appli ntfy, gratuite) : baisses de prix, résumé du matin, pannes.
- E-mail : réservé au signal d'achat, envoyé une seule fois (voir run.py).
  Destinataires et identifiants via variables d'environnement (secrets GitHub) :
  EMAIL_TO="a@x.com,b@y.com", SMTP_USER, SMTP_PASSWORD (mot de passe d'application Gmail).
"""

import json
import os
import smtplib
import urllib.request
from email.message import EmailMessage


def app_push(title, message) -> bool:
    """Notification dans l'appli Google Tracker (tous les appareils abonnés).
    Variables d'environnement : APP_URL (ex. https://google-tracker.vercel.app) et APP_SECRET."""
    url, secret = os.environ.get("APP_URL"), os.environ.get("APP_SECRET")
    if not (url and secret):
        return False
    lines = [l.replace("**", "").strip() for l in message.splitlines() if l.strip()]
    body = {"title": title, "body": " · ".join(lines[:2])[:220], "url": "/", "tag": "trip"}
    req = urllib.request.Request(
        url.rstrip("/") + "/api/broadcast",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {secret}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status == 200
    except Exception as e:
        print(f"[notify] échec notification appli : {e}")
        return False


def push(cfg, title, message, priority=3, tags=(), click=None) -> bool:
    if priority >= 4:  # baisses, signal d'achat, pannes : aussi dans l'appli (pas le résumé du matin)
        app_push(title, message)
    n = cfg["notify"]
    topic = os.environ.get("NTFY_TOPIC") or n.get("ntfy_topic")
    if not topic:
        return False
    body = {"topic": topic, "title": title, "message": message, "priority": priority,
            "tags": list(tags), "markdown": True}
    if click:
        body["click"] = click
    req = urllib.request.Request(
        n.get("ntfy_server", "https://ntfy.sh").rstrip("/"),
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status == 200
    except Exception as e:  # une notif ratée ne doit pas casser le relevé
        print(f"[notify] échec push : {e}")
        return False


def email_recipients(cfg) -> list[str]:
    raw = os.environ.get("EMAIL_TO") or ",".join(cfg["notify"].get("email_to", []))
    return [a.strip() for a in raw.split(",") if a.strip()]


def send_email(cfg, subject, text, html=None, to=None) -> bool:
    n = cfg["notify"]
    to = to or email_recipients(cfg)
    user, password = os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASSWORD")
    if not (to and user and password):
        print("[notify] e-mail non configuré (EMAIL_TO / SMTP_USER / SMTP_PASSWORD)")
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = ", ".join(to)
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    with smtplib.SMTP(n.get("smtp_host", "smtp.gmail.com"), n.get("smtp_port", 587), timeout=30) as s:
        s.starttls()
        s.login(user, password)
        s.send_message(msg)
    return True
