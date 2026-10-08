# ✈️ Google Tracker — appli de suivi des prix des vols

**Appli : https://google-tracker-self.vercel.app** (à installer sur l'écran d'accueil)

- **Voyage** : Paris ⇄ Séoul ⇄ Tokyo, été 2027 (verdict, prix valises comprises, prix par site, historique).
- **Rechercher** : n'importe quel vol en direct sur Google Flights, dates proches, choix du retour,
  liens de réservation (page Google qui compare les sites : compagnie, Trip.com…, + Trip.com, Kayak, Skyscanner).
- **Alertes** : n'importe quel vol, vérifié toutes les heures, notification à chaque vraie baisse.

## Installer sur le téléphone
- **iPhone** : ouvrir le lien dans **Safari** → Partager → **Sur l'écran d'accueil**, puis ouvrir l'appli depuis l'icône
  et toucher « Activer » dans l'onglet Alertes (les notifications iPhone ne marchent que depuis l'appli installée).
- **Android / Samsung** : ouvrir le lien dans Chrome → menu ⋮ → **Installer l'appli**, puis « Activer » les notifications.

## Architecture
| Partie | Où | Rôle |
|---|---|---|
| `app/` | Vercel (statique) | Appli React installable (PWA), notifications Web Push |
| `api/index.py` | Vercel (Python, région Paris `cdg1`) | Recherche Google Flights en direct, alertes, envoi des notifications |
| Upstash Redis (`google-tracker-db`, Francfort) | Vercel Marketplace | Alertes et abonnements aux notifications |
| `run.py` + `.github/workflows/tracker.yml` | GitHub Actions, 4×/jour | Suivi du voyage → `site/trip.json` (GitHub Pages) lu par l'appli |
| `.github/workflows/alerts.yml` | GitHub Actions, toutes les heures | Déclenche `POST /api/cron/check` |

Secrets : Vercel (`VAPID_*`, `CRON_SECRET`, `KV_*` posés par l'intégration) ; GitHub (`APP_URL`, `APP_SECRET` = `CRON_SECRET`, e-mail).
Développement local : `uvicorn api.index:app --port 8787` + `cd app && npm run dev`. Mise en ligne : `vercel deploy --prod`.

---

# Tracker du voyage — Paris ↔ Séoul + Séoul ↔ Tokyo, été 2027

Surveille Google Flights 4 fois par jour, publie un **site à partager**, envoie les petites baisses sur l'appli **ntfy** et **un seul e-mail** quand c'est le moment d'acheter.

Plan suivi (chacun achète son billet) :
- **A/R Paris (CDG/Orly) ↔ Séoul** : aller 21/22/23 juillet, retour depuis Séoul 18/19/20 août 2027 ;
- **A/R Séoul ↔ Tokyo** : aller 28/29/30 juillet, retour à Séoul 16/17 août.

1 escale max · 1 valise 23 kg à l'aller, 2 au retour (prix comparés valises comprises) · prix du même billet site par site (compagnie, agences).

## Mise en ligne (une seule fois, ~10 min)
1. Créer un compte gratuit sur https://github.com puis un dépôt **public** vide (ex. `vols-seoul-japon`), sans README.
2. Dans ce dossier : `git remote add origin https://github.com/<ton-pseudo>/vols-seoul-japon.git` puis `git push -u origin main` (une fenêtre de connexion GitHub s'ouvre).
3. Sur GitHub → **Settings → Pages** → Source : **GitHub Actions**.
4. **Settings → Secrets and variables → Actions → New repository secret** :
   - `EMAIL_TO` : `ton@mail.com,ami@mail.com`
   - `SMTP_USER` : l'adresse Gmail qui envoie
   - `SMTP_PASSWORD` : mot de passe d'application Gmail (https://myaccount.google.com/apppasswords, validation en 2 étapes requise)
5. **Actions → Relevé des prix → Run workflow** pour un premier relevé. Le site est ensuite à `https://<ton-pseudo>.github.io/vols-seoul-japon/` : c'est ce lien que tu partages.
6. Mettre ce lien dans `config.json` → `notify.site_url` (les notifications ouvriront le site).

Une fois en ligne, arrêter le suivi local : `Unregister-ScheduledTask -TaskName "VolsSeoulJapon*" -Confirm:$false`.

## Alertes
| Canal | Quand |
|---|---|
| 📱 Appli ntfy (sujet dans `config.json`) | résumé chaque matin + chaque baisse ≥ 3 % ou 25 € |
| ✉️ E-mail (toi + ton ami) | **une seule fois**, au signal d'achat |

Signal d'achat : prix sous la fourchette habituelle de Google, ou au plus bas / en hausse pendant la fenêtre conseillée (≈ janvier → avril 2027), ou au plus tard 60 jours avant le départ.

## Jours et heures
- Le jour de **départ** compte (mardi/mercredi ≈ 12 % moins cher que le week-end) → les départs du mercredi 21/07 et retours du mercredi 18/08 sont suivis.
- Le jour d'**achat** compte peu en moyenne (~1-2 %), mais le site mesure sur tes propres trajets quels jours et quelles heures les baisses arrivent.

## Claude connecté à Google Flights (MCP)
Serveur `google-flights` déclaré dans `.mcp.json` : demander à Claude, dans ce dossier, « cherche Paris → Séoul le 21/07 retour 18/08 », « où en est le tracker ? »…

## Commandes locales
```
python run.py --no-notify   # relevé + site, sans notification
python run.py --test-notify # teste l'appli
python run.py --test-email  # teste l'e-mail (variables EMAIL_TO, SMTP_USER, SMTP_PASSWORD)
```
