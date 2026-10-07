"""Tracker de prix Google Flights — Paris (CDG/ORY) → Séoul → Japon → Paris, été 2027.

Usage :
    python run.py                relevé + site + alertes push (baisse) + e-mail unique (signal d'achat)
    python run.py --digest       idem + résumé push forcé
    python run.py --no-notify    relevé + site, sans aucune notification
    python run.py --test-notify  envoie une notification push de test
    python run.py --test-email   envoie un e-mail de test aux destinataires
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from tracker.analyze import advise
from tracker.db import DB
from tracker.gflights import GoogleFlights
from tracker.notify import email_recipients, push, send_email
from tracker.plan import STRATEGIES, best_combos, build_followup_searches, build_searches, direct_vs_stop, key
from tracker.site import build as build_site
from tracker.stats import price_timing

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
PARIS = ZoneInfo("Europe/Paris")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(DATA / "tracker.log", encoding="utf-8"),
        *([logging.StreamHandler(sys.stdout)] if sys.stdout else []),
    ],
)
log = logging.getLogger("tracker")


def main_key(cfg) -> str:
    """Recherche dont l'historique Google sert de tendance tant qu'on a peu de relevés."""
    o = cfg["outbound_dates"][len(cfg["outbound_dates"]) // 2]
    r = cfg["return_dates"][len(cfg["return_dates"]) // 2]
    return key([(o, cfg["origin"], cfg["seoul"]), (r, cfg["seoul"], cfg["origin"])])


def collect(cfg, db):
    gf = GoogleFlights(cfg["currency"], cfg["language"], cfg["adults"], cfg.get("max_stops"))
    run_id, ts = db.start_run()
    results, errors = {}, 0

    def run_phase(searches, phase):
        nonlocal errors
        for i, s in enumerate(searches, 1):
            for attempt in (1, 2, 3):  # Google renvoie parfois une erreur passagère
                try:
                    res = gf.search(s.legs, s.max_stops)
                    results[s.key] = res
                    db.save_search(run_id, ts, s.key, res)
                    best = res.best
                    log.info("[%s %d/%d] %s → %s", phase, i, len(searches), s.key,
                             f"{best.price} € (hors valises)" if best else "aucun vol")
                    break
                except Exception as e:
                    log.warning("[%s %d/%d] %s échec (essai %d) : %s", phase, i, len(searches), s.key, attempt, e)
                    time.sleep(15 * attempt)
            else:
                errors += 1
            time.sleep(cfg.get("delay_between_requests_s", 4))

    run_phase(build_searches(cfg), "1")
    run_phase(build_followup_searches(cfg, results), "2")  # direct, pour comparaison
    db.end_run(run_id, errors)
    return run_id, ts, results, errors


def format_summary(advice, best, dvs=None) -> str:
    lines = [
        f"**{advice.action}** — {advice.reason}",
        "",
        f"Meilleur total valises comprises : **{advice.price} €** (plus bas observé : {advice.min_seen} €)",
    ]
    if dvs:
        lines.append(f"Paris↔Séoul : 1 escale {dvs['one_stop']} € vs direct {dvs['direct']} € ({dvs['saving']:+d} €)")
    if advice.typical_low is not None:
        lines.append(f"Fourchette habituelle : {advice.typical_low}–{advice.typical_high} € → niveau {advice.level}")
    if advice.trend_per_week is not None:
        lines.append(f"Tendance : {advice.trend_per_week:+.0f} €/sem · projection 14 j : {advice.forecast_14d} €")
    lines.append(f"Départ dans {advice.days_left} j · fenêtre d'achat conseillée : {advice.window[0]} → {advice.window[1]}")
    lines.append("")
    for name, combo in sorted(best.items(), key=lambda kv: kv[1]["total"]):
        lines.append(f"• {STRATEGIES[name]} : **{combo['total']} €**")
        for l in combo["legs"]:
            stops = "direct" if l["stops"] == 0 else f"{l['stops']} escale"
            bags = f"+{l['bag_fee']} € valises" if l["bag_fee"] else "valises incluses"
            lines.append(f"   - {l['search']} : {l['price']} € ({l['airlines']}, {l['route']}, {stops}, {bags})")
    return "\n".join(lines)


def buy_email(cfg, advice, winner, site_url):
    legs = "\n".join(
        f"  - {l['search']} : {l['price']} € ({l['airlines']}, {l['route']}, départ {l['depart']})\n    {l['url']}"
        for l in winner["legs"]
    )
    text = (
        f"C'est le moment d'acheter vos billets pour « {cfg['trip_name']} ».\n\n"
        f"Prix par personne, valises comprises : {advice.price} €\n"
        f"Pourquoi maintenant : {advice.reason}\n\n"
        f"Le montage le moins cher :\n{legs}\n\n"
        f"Vérifiez le tarif et les valises sur le site de la compagnie avant de payer.\n"
        + (f"Tableau de bord : {site_url}\n" if site_url else "")
        + "\nCet e-mail est envoyé une seule fois."
    )
    return f"✈️ Achetez maintenant : {advice.price} € — {cfg['trip_name']}", text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--digest", action="store_true")
    ap.add_argument("--no-notify", action="store_true")
    ap.add_argument("--test-notify", action="store_true")
    ap.add_argument("--test-email", action="store_true")
    args = ap.parse_args()

    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

    if args.test_notify:
        ok = push(cfg, "✈️ Tracker vols : test", "Les notifications fonctionnent !", priority=4, tags=["airplane"])
        print("push envoyé" if ok else "push non envoyé")
        return
    if args.test_email:
        ok = send_email(cfg, "✈️ Tracker vols : test", "Test : c'est ici que vous recevrez l'unique e-mail « achetez maintenant ».")
        print(f"e-mail envoyé à {email_recipients(cfg)}" if ok else "e-mail non envoyé")
        return

    db = DB(DATA / "prices.db")
    history = db.best_combo_series()
    previous_min = min((t for _, t in history), default=None)
    previous_price = history[-1][1] if history else None
    previous_action = db.get_state("last_action")

    run_id, ts, results, errors = collect(cfg, db)
    best = best_combos(cfg, results)
    if not best:
        log.error("aucune combinaison complète (%d erreurs) — Google bloque peut-être les requêtes", errors)
        if not args.no_notify:
            push(cfg, "⚠️ Tracker vols : relevé en échec", f"{errors} recherches en erreur.", priority=4)
        sys.exit(1)

    for name, combo in best.items():
        db.save_combo(run_id, ts, name, combo["total"], combo)

    winner = min(best.values(), key=lambda c: c["total"])
    advice = advise(cfg, winner, results, db.best_combo_series(), db.google_history(main_key(cfg)))
    dvs = direct_vs_stop(cfg, results)
    build_site(ROOT / "site" / "index.html", cfg, advice, best, dvs, price_timing(db), db, datetime.now(PARIS))
    db.set_state("last_action", advice.action)
    summary = format_summary(advice, best, dvs)
    log.info("Résultat : %s %d € — %s", advice.action, advice.price, advice.reason)

    if args.no_notify:
        print("\n" + summary)
        return

    click = cfg["notify"].get("site_url") or winner["legs"][0]["url"]

    if advice.action == "ACHETER":
        # E-mail : UNE seule fois pour tout le suivi
        if not db.get_state("buy_email_sent"):
            subject, text = buy_email(cfg, advice, winner, cfg["notify"].get("site_url"))
            if send_email(cfg, subject, text):
                db.set_state("buy_email_sent", {"ts": ts, "price": advice.price})
                log.info("E-mail d'achat envoyé à %s", email_recipients(cfg))
        # Push : seulement au moment où le signal apparaît
        if previous_action != "ACHETER":
            push(cfg, f"🟢 ACHÈTE ! {advice.price} €", summary, priority=5, tags=["rotating_light"], click=click)
        return

    # Push : baisse par rapport au relevé précédent
    ba = cfg["booking_advice"]
    dropped = previous_price is not None and (
        previous_price - advice.price >= ba["drop_alert_eur"]
        or (previous_price - advice.price) / previous_price * 100 >= ba["drop_alert_pct"]
    )
    if dropped:
        record = " — plus bas jamais vu !" if previous_min is None or advice.price < previous_min else ""
        push(cfg, f"📉 Le prix baisse : {advice.price} € (avant {previous_price} €){record}", summary,
             priority=4, tags=["chart_with_downwards_trend"], click=click)
    elif args.digest:
        push(cfg, f"✈️ Séoul/Japon : {advice.price} € — {advice.action}", summary, priority=3, tags=["airplane"], click=click)


if __name__ == "__main__":
    main()
