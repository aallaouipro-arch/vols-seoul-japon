"""Génère le site partageable (site/index.html) : un seul fichier, données incluses.

Ouvrable en local (double-clic) et publié tel quel sur GitHub Pages.
"""

import html
import json
from datetime import datetime

from .plan import STRATEGIES

ACTIONS = {  # couleur de statut + icône : jamais la couleur seule
    "ACHETER": ("good", "✅", "C'est le moment d'acheter"),
    "SURVEILLER": ("warning", "👀", "On surveille"),
    "ATTENDRE": ("neutral", "⏳", "Trop tôt, on attend"),
}


def _e(s) -> str:
    return html.escape(str(s))


def _dur(m) -> str:
    return f"{m // 60}h{m % 60:02d}" if m else "?"


def _bags(b) -> str:
    return " / ".join(f"{n} valise{'s' if n > 1 else ''}" for n in b)


def build(path, cfg, advice, best, dvs, timing, db, generated_at: datetime):
    status, icon, label = ACTIONS.get(advice.action, ("neutral", "•", advice.action))
    series = {name: db.combo_series(name) for name in STRATEGIES}
    chart_data = {
        "series": [
            {"name": STRATEGIES[name], "points": [[ts, v] for ts, v in pts]}
            for name, pts in series.items() if pts
        ],
        "weekday": timing["weekday"],
    }

    combos_html = []
    for name, combo in sorted(best.items(), key=lambda kv: kv[1]["total"]):
        legs = "".join(
            f"""<tr>
              <td><a href="{_e(l['url'])}" target="_blank" rel="noopener">{_e(l['search'])}</a></td>
              <td>{_e(l['airlines'])}<br><small>{_e(l['route'])} · {'direct' if l['stops'] == 0 else f"{l['stops']} escale"} · {_dur(l['duration_min'])}</small></td>
              <td>{_e(l['depart'])}</td>
              <td class="num">{l['fare']} €</td>
              <td class="num" title="{_e(l['bag_note'])}">{'+' + str(l['bag_fee']) + ' €' if l['bag_fee'] else 'incluses'}<br><small>{_bags(l['bags'])}</small></td>
              <td class="num"><b>{l['price']} €</b></td>
            </tr>"""
            for l in combo["legs"]
        )
        combos_html.append(f"""
        <details {'open' if not combos_html else ''}>
          <summary><span>{_e(STRATEGIES[name])}</span><b>{combo['total']} €</b></summary>
          <div class="scroll"><table>
            <thead><tr><th>Vol</th><th>Compagnie</th><th>Départ</th><th class="num">Billet</th><th class="num">Valises</th><th class="num">Total</th></tr></thead>
            <tbody>{legs}</tbody>
          </table></div>
        </details>""")

    weekday_rows = "".join(
        f"<tr><td>{r['label']}</td><td class='num'>{r['drop_rate']} %</td><td class='num'>{r['rise_rate']} %</td>"
        f"<td class='num'>{r['avg_change_pct']:+.2f} %</td><td class='num'>{r['n']}</td></tr>"
        for r in timing["weekday"]
    )
    hour_rows = "".join(
        f"<tr><td>{r['label']}</td><td class='num'>{r['drop_rate']} %</td><td class='num'>{r['avg_change_pct']:+.2f} %</td><td class='num'>{r['n']}</td></tr>"
        for r in timing["hours"]
    )
    best_day = timing["best_day"]
    best_hour = timing["best_hour"]
    timing_text = (
        f"Les baisses arrivent le plus souvent le <b>{best_day['label']}</b> ({best_day['drop_rate']} % des variations)."
        if best_day else "Pas encore assez de données."
    )
    timing_text += (
        f" Heure la plus favorable : <b>{best_hour['label']}</b>." if best_hour
        else " L'analyse par heure sera fiable après ~2 semaines de relevés (4 par jour)."
    )

    dvs_html = (
        f"<p>Paris↔Séoul ({_e(dvs['dates'])}), valises comprises : <b>1 escale {dvs['one_stop']} €</b> "
        f"({_e(dvs['one_stop_airlines'])}, {_e(dvs['one_stop_route'])}) contre direct {dvs['direct']} € "
        f"({_e(dvs['direct_airlines'])}) → <b>{dvs['saving']:+d} €</b>.</p>"
        if dvs else ""
    )
    typical = f"{advice.typical_low}–{advice.typical_high} €" if advice.typical_low is not None else "inconnue"
    trend = f"{advice.trend_per_week:+.0f} €/sem" if advice.trend_per_week is not None else "—"
    forecast = f"{advice.forecast_14d} €" if advice.forecast_14d is not None else "—"
    topic = cfg["notify"].get("ntfy_topic", "")

    page = f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Vols Séoul Japon</title>
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" type="image/png" href="icon-192.png">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<meta name="theme-color" content="#1c5cab">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Vols Séoul">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
<style>
:root {{
  color-scheme: light;
  --surface-0: #f4f3f0; --surface-1: #fcfcfb; --border: #e2e0da;
  --text-primary: #0b0b0b; --text-secondary: #52514e; --text-muted: #77756f;
  --link: #1c5cab;
  --series-1: #2a78d6; --series-2: #eb6834; --series-3: #1baf7a;
  --good: #0ca30c; --warning: #fab219; --neutral: #77756f; --grid: #e9e7e2;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    color-scheme: dark;
    --surface-0: #111110; --surface-1: #1a1a19; --border: #383835;
    --text-primary: #ffffff; --text-secondary: #c3c2b7; --text-muted: #9a998f;
    --link: #86b6ef;
    --series-1: #3987e5; --series-2: #d95926; --series-3: #199e70; --grid: #2a2a28;
  }}
}}
:root[data-theme="dark"] {{
  color-scheme: dark;
  --surface-0: #111110; --surface-1: #1a1a19; --border: #383835;
  --text-primary: #ffffff; --text-secondary: #c3c2b7; --text-muted: #9a998f;
  --link: #86b6ef;
  --series-1: #3987e5; --series-2: #d95926; --series-3: #199e70; --grid: #2a2a28;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--surface-0); color: var(--text-primary);
  font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }}
main {{ max-width: 1040px; margin: 0 auto; padding: max(24px, env(safe-area-inset-top)) max(16px, env(safe-area-inset-right)) 48px max(16px, env(safe-area-inset-left)); }}
.install {{ display: grid; grid-template-columns: 1fr 1fr auto; gap: 16px; }}
.install h3 {{ margin: 0 0 6px; font-size: 1rem; }} .install ol {{ margin: 0; padding-left: 20px; }}
#qr {{ background: #fff; padding: 8px; border-radius: 8px; width: max-content; height: max-content; }}
@media (max-width: 760px) {{ .install {{ grid-template-columns: 1fr; }} .qr-box {{ display: none; }} }}
@media (display-mode: standalone) {{ .only-browser {{ display: none; }} }}
h1 {{ font-size: 1.6rem; margin: 0 0 4px; }} h2 {{ font-size: 1.15rem; margin: 32px 0 12px; }}
.sub {{ color: var(--text-secondary); margin: 0; }}
a {{ color: var(--link); }}
.card {{ background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px; padding: 16px; }}
.verdict {{ display: flex; gap: 16px; align-items: center; margin-top: 20px; border-left: 6px solid var(--{status}); }}
.verdict .icon {{ font-size: 2rem; }}
.verdict h2 {{ margin: 0; font-size: 1.3rem; }}
.verdict p {{ margin: 4px 0 0; color: var(--text-secondary); }}
.kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-top: 12px; }}
.kpi small {{ display: block; color: var(--text-secondary); }}
.kpi b {{ font-size: 1.35rem; font-variant-numeric: tabular-nums; }}
details {{ background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px; margin-bottom: 10px; }}
summary {{ display: flex; justify-content: space-between; gap: 12px; padding: 12px 16px; cursor: pointer; }}
summary b {{ font-variant-numeric: tabular-nums; white-space: nowrap; }}
.scroll {{ overflow-x: auto; padding: 0 16px 12px; }}
table {{ width: 100%; border-collapse: collapse; font-size: .92rem; }}
th, td {{ text-align: left; padding: 8px 6px; border-top: 1px solid var(--border); vertical-align: top; }}
th {{ color: var(--text-secondary); font-weight: 500; }}
td small {{ color: var(--text-muted); }}
.num {{ text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }}
.chart {{ position: relative; height: 320px; }}
.note {{ color: var(--text-secondary); font-size: .9rem; }}
code {{ background: var(--surface-0); padding: 2px 6px; border-radius: 4px; }}
</style></head>
<body><main>
<h1>✈️ {_e(cfg["trip_name"])}</h1>
<p class="sub">Départ CDG/Orly · 1 escale max · {_bags([cfg["bags"]["outbound"]])} à l'aller, {_bags([cfg["bags"]["return"]])} au retour (23 kg)
 · mis à jour le {generated_at.strftime("%d/%m/%Y à %H:%M")} (heure de Paris)</p>

<div class="card verdict">
  <div class="icon" aria-hidden="true">{icon}</div>
  <div><h2>{_e(advice.action)} · {advice.price} € par personne</h2><p><b>{_e(label)}</b> : {_e(advice.reason)}</p></div>
</div>

<div class="kpis">
  <div class="card kpi"><small>Meilleur total (valises incl.)</small><b>{advice.price} €</b></div>
  <div class="card kpi"><small>Plus bas observé</small><b>{advice.min_seen} €</b></div>
  <div class="card kpi"><small>Fourchette habituelle (Google + valises)</small><b>{typical}</b></div>
  <div class="card kpi"><small>Tendance</small><b>{trend}</b></div>
  <div class="card kpi"><small>Projection à 14 jours</small><b>{forecast}</b></div>
  <div class="card kpi"><small>Fenêtre d'achat conseillée</small><b>{advice.window[0][8:]}/{advice.window[0][5:7]} → {advice.window[1][8:]}/{advice.window[1][5:7]}</b></div>
</div>

<h2>Meilleur montage par stratégie</h2>
{"".join(combos_html)}
{dvs_html}

<h2>Évolution du meilleur prix (valises incluses)</h2>
<div class="card"><div class="chart"><canvas id="history" aria-label="Évolution du prix par stratégie"></canvas></div></div>

<h2>Quand les prix bougent-ils ?</h2>
<p>{timing_text}</p>
<div class="card"><div class="chart" style="height:240px"><canvas id="weekday" aria-label="Part des baisses de prix par jour de la semaine"></canvas></div></div>
<details><summary><span>Tableau par jour de la semaine</span></summary><div class="scroll"><table>
<thead><tr><th>Jour</th><th class="num">Baisses</th><th class="num">Hausses</th><th class="num">Variation moy.</th><th class="num">Mesures</th></tr></thead>
<tbody>{weekday_rows}</tbody></table></div></details>
<details><summary><span>Tableau par heure de relevé</span></summary><div class="scroll"><table>
<thead><tr><th>Heure</th><th class="num">Baisses</th><th class="num">Variation moy.</th><th class="num">Mesures</th></tr></thead>
<tbody>{hour_rows or '<tr><td colspan=4>Pas encore de données</td></tr>'}</tbody></table></div></details>
<p class="note">À savoir : d'après les données Google Flights, le jour où l'on <i>achète</i> change peu le prix (~1-2 %),
alors que le jour où l'on <i>part</i> compte beaucoup (départs lundi-mercredi ≈ 12 % moins chers que le week-end) :
c'est pour ça que les départs du mercredi 21/07 et retours du mercredi 18/08 sont suivis.</p>

<h2 class="only-browser">📲 Installer l'appli sur ton téléphone</h2>
<div class="card install only-browser">
  <div><h3>iPhone (Safari)</h3><ol>
    <li>Ouvrir ce site dans <b>Safari</b></li>
    <li>Bouton <b>Partager</b> (carré avec flèche ↑)</li>
    <li><b>Sur l'écran d'accueil</b> → <b>Ajouter</b></li></ol></div>
  <div><h3>Android / Samsung (Chrome ou Samsung Internet)</h3><ol>
    <li>Ouvrir ce site dans <b>Chrome</b></li>
    <li>Menu <b>⋮</b> → <b>Ajouter à l'écran d'accueil</b> (ou <b>Installer l'appli</b>)</li>
    <li>Confirmer <b>Installer</b></li></ol></div>
  <div class="qr-box"><div id="qr" aria-label="QR code vers ce site"></div><small class="note">Scanne avec ton téléphone</small></div>
</div>

<h2>Recevoir les alertes</h2>
<div class="card">
<p>📱 <b>Notifications</b> : installer <b>ntfy</b> (gratuit, sans compte) —
<a href="https://apps.apple.com/app/ntfy/id1625396347" target="_blank" rel="noopener">App Store (iPhone)</a> ·
<a href="https://play.google.com/store/apps/details?id=io.heckel.ntfy" target="_blank" rel="noopener">Google Play (Samsung)</a>
→ « + » → sujet <code>{_e(topic)}</code> → <b>S'abonner</b>, puis autoriser les notifications. Tu reçois les baisses de prix et le résumé du matin.</p>
<p style="margin-bottom:0">✉️ <b>E-mail</b> : un seul e-mail, envoyé quand c'est le moment d'acheter.</p>
</div>
<p class="note">Valises : Google Flights n'inclut pas les frais de bagages ; ils sont estimés par compagnie (survoler la colonne « Valises »). Vérifier le tarif exact avant d'acheter.</p>
</main>
<script>
if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(() => {{}});
if (window.QRCode && document.getElementById('qr'))
  new QRCode(document.getElementById('qr'), {{ text: location.href.startsWith('http') ? location.href : {json.dumps(cfg["notify"].get("site_url", ""))},
    width: 132, height: 132, colorDark: '#000000', colorLight: '#ffffff' }});
const DATA = {json.dumps(chart_data, ensure_ascii=False)};
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const ink = css('--text-secondary'), grid = css('--grid');
Chart.defaults.color = ink; Chart.defaults.font.family = 'system-ui, sans-serif';
const fmt = v => v.toLocaleString('fr-FR') + ' €';
const labels = [...new Set(DATA.series.flatMap(s => s.points.map(p => p[0])))].sort();
new Chart(document.getElementById('history'), {{
  type: 'line',
  data: {{ labels,
    datasets: DATA.series.map((s, i) => {{
      const c = css('--series-' + (i + 1)), byTs = Object.fromEntries(s.points);
      return {{ label: s.name, borderColor: c, backgroundColor: c, borderWidth: 2, pointRadius: 3, pointHoverRadius: 5,
        spanGaps: true, tension: 0, data: labels.map(l => byTs[l] ?? null) }};
    }}) }},
  options: {{ maintainAspectRatio: false, interaction: {{ mode: 'index', intersect: false }},
    plugins: {{ legend: {{ position: 'bottom', labels: {{ boxWidth: 12, boxHeight: 2 }} }},
      tooltip: {{ callbacks: {{ label: c => ' ' + c.dataset.label + ' : ' + fmt(c.parsed.y) }} }} }},
    scales: {{ x: {{ grid: {{ display: false }}, ticks: {{ maxTicksLimit: 8,
        callback(v) {{ const t = this.getLabelForValue(v); return t.slice(8, 10) + '/' + t.slice(5, 7) + ' ' + t.slice(11, 13) + 'h'; }} }} }},
      y: {{ grid: {{ color: grid }}, ticks: {{ callback: fmt }} }} }} }}
}});
new Chart(document.getElementById('weekday'), {{
  type: 'bar',
  data: {{ labels: DATA.weekday.map(r => r.label),
    datasets: [{{ label: 'Part des variations qui sont des baisses', data: DATA.weekday.map(r => r.drop_rate),
      backgroundColor: css('--series-1'), borderRadius: 4, maxBarThickness: 36 }}] }},
  options: {{ maintainAspectRatio: false, plugins: {{ legend: {{ display: false }},
      tooltip: {{ callbacks: {{ label: c => ' ' + c.parsed.y + ' % de baisses (' + DATA.weekday[c.dataIndex].n + ' mesures)' }} }} }},
    scales: {{ x: {{ grid: {{ display: false }} }}, y: {{ grid: {{ color: grid }}, ticks: {{ callback: v => v + ' %' }} }} }} }}
}});
</script>
</body></html>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")
