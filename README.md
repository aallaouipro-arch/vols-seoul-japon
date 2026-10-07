# ✈️ Tracker de prix — Paris (CDG/Orly) → Séoul → Japon → Paris, été 2027

Surveille Google Flights 4 fois par jour, publie un **site à partager**, envoie les petites baisses sur l'appli **ntfy** et **un seul e-mail** quand c'est le moment d'acheter.

Conditions suivies : départ/retour CDG ou Orly · 1 escale max · 1 valise 23 kg à l'aller, 2 au retour (prix comparés valises comprises) · aller 21/22/23 juillet, retour 18/19/20 août 2027.

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
