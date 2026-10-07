# Tracker de prix de vols — Paris (CDG/ORY) → Séoul → Japon → Paris (été 2027)

Voyage (l'utilisateur + un ami, même voyage) : aller 21-23/07/2027, 1 semaine à Séoul, ~3 semaines au Japon, retour 18-20/08/2027. Éco, EUR.

## Contraintes de l'utilisateur (à respecter partout)
- Départ et retour **uniquement CDG ou Orly** → code `CDG+ORY` (jamais `PAR`, qui inclut Beauvais).
- **1 escale max**.
- Valises 23 kg : **1 à l'aller, 2 au retour** (`config.json` → `bags`). Les prix sont comparés valises comprises ; Google ne fournit pas les frais → estimation par compagnie dans `tracker/bags.py`.
- E-mail : **un seul**, au signal d'achat (`state.buy_email_sent` dans la base). Les baisses passent par l'appli ntfy, jamais par e-mail.

## Fonctionnement
- `run.py` : ~37 recherches Google Flights → meilleure combinaison par stratégie (`open_jaw`, `rt_seoul`, `rt_tokyo`) → avis ACHETER / SURVEILLER / ATTENDRE → `site/index.html` (site partageable, données incluses) → notifications.
- En ligne : `.github/workflows/tracker.yml` (GitHub Actions 4×/jour, TZ Europe/Paris, commit de `data/prices.db` + publication GitHub Pages). Secrets : `EMAIL_TO`, `SMTP_USER`, `SMTP_PASSWORD`.
- En local (secours) : tâches planifiées Windows `VolsSeoulJapon-*` (`install_task.ps1`). Ne pas faire tourner local + GitHub en même temps (bases divergentes).
- `tracker/gflights.py` : requête directe à Google Flights (cookie RGPD, `gl=FR`, plusieurs aéroports encodés à la main dans `tfs`), parsing de `payload[5]` = Price insights (fourchette `[4]`/`[5]`, historique ~60 j `[10][0]`). Le multi-destinations n'est pas rendu côté serveur → combinaisons d'allers simples / A/R (`tracker/plan.py`).
- `tracker/stats.py` : quand les prix baissent (jour de semaine via l'historique Google, heure via nos relevés).

## Accès direct Google Flights
Serveur MCP `google-flights` (`mcp_server.py`, `.mcp.json`) : `search_flights` (valises comprises), `compare_stops`, `flexible_dates`, `trip_tracker_status`, `price_history`. À utiliser pour toute question de prix en temps réel.

## Données (SQLite `data/prices.db`)
- `searches` : meilleur tarif (hors valises) par recherche et par relevé (`key` ex. `RT CDG+ORY-SEL 2027-07-21/2027-08-18`, `OW SEL-TYO 2027-07-29`).
- `combos` : meilleur total (valises comprises) par stratégie et par relevé, détail JSON des vols.
- `google_history` : historique quotidien fourni par Google, par recherche.
- `state` : `last_action`, `buy_email_sent`.
- `data/prices_v1_archive.db` : ancienne base (aéroport PAR, sans valises), non comparable.

## Quand l'utilisateur demande "où en sont les prix ?"
`trip_tracker_status` (ou lire `data/prices.db`) plutôt que relancer un relevé complet ; pour un prix précis, `search_flights` en direct.
