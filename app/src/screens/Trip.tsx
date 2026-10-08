import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { ArrowLeftRight, CalendarClock, ChevronRight, Luggage, RefreshCw, TrendingDown, TrendingUp } from "lucide-react";
import { LineChart, WeekBars, type Series } from "../components/charts";
import { PushCard } from "../components/PushCard";
import { AirlineLogo, AnimatedNumber, Badge, Card, LinkButton, SectionTitle, Skeleton, type Tone } from "../components/ui";
import { api, type Trip, type TripLeg } from "../lib/api";
import { ago, dayMonth, daysBetween, duration, euro, hhmm, todayIso } from "../lib/format";
import { openSearch } from "../lib/nav";

const ACTION: Record<string, { tone: Tone; emoji: string; label: string }> = {
  ACHETER: { tone: "good", emoji: "✅", label: "C'est le moment d'acheter" },
  SURVEILLER: { tone: "warn", emoji: "👀", label: "On surveille" },
  ATTENDRE: { tone: "neutral", emoji: "⏳", label: "Trop tôt, on attend" },
};

const PLACE: Record<string, string> = { "CDG+ORY": "Paris", SEL: "Séoul", TYO: "Tokyo" };
const place = (c: string) => PLACE[c] || c;

function BuyWindow({ window: [start, end], departure }: { window: [string, string]; departure: string }) {
  const today = todayIso();
  const origin = "2026-10-01";
  const total = daysBetween(origin, departure);
  const pct = (d: string) => Math.min(100, Math.max(0, (daysBetween(origin, d) / total) * 100));
  return (
    <div>
      <div className="relative h-2.5 rounded-full bg-white/8">
        <div className="absolute inset-y-0 rounded-full bg-good/45" style={{ left: `${pct(start)}%`, width: `${pct(end) - pct(start)}%` }} />
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          className="absolute top-1/2 size-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-[3px] border-ink-2 bg-white"
          style={{ left: `${pct(today)}%` }}
        />
      </div>
      <div className="mt-2 flex justify-between text-[11px] text-muted">
        <span>Aujourd'hui</span>
        <span className="text-good">
          Fenêtre d'achat : {dayMonth(start)} → {dayMonth(end)}
        </span>
        <span>Départ</span>
      </div>
    </div>
  );
}

function LegCard({ leg, title, index }: { leg: TripLeg; title: string; index: number }) {
  const best = leg.booking[0];
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 + index * 0.08 }} className="glass overflow-hidden rounded-[28px]">
      <div className="flex items-center gap-3 p-4 pb-3">
        <AirlineLogo code={leg.airline_code} name={leg.airlines} size={42} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 font-semibold">
            {title} <ArrowLeftRight size={14} className="text-muted" />
          </div>
          <div className="truncate text-xs text-muted">
            {leg.airlines} · {leg.stops === 0 ? "direct" : `${leg.stops} escale`} · {duration(leg.duration_min)}
          </div>
        </div>
        <div className="text-right">
          <div className="text-xl font-extrabold tabular">{euro(leg.total)}</div>
          <div className="flex items-center justify-end gap-1 text-[11px] text-muted">
            <Luggage size={11} /> valises incl.
          </div>
        </div>
      </div>
      <div className="mx-4 grid grid-cols-2 gap-2 rounded-2xl bg-white/5 p-3 text-sm ring-1 ring-white/8">
        <div>
          <div className="text-[11px] text-muted">Aller</div>
          <div className="font-semibold capitalize">
            {dayMonth(leg.depart_date)} · {hhmm(leg.depart)}
          </div>
        </div>
        <div>
          <div className="text-[11px] text-muted">Retour</div>
          <div className="font-semibold capitalize">
            {leg.return_date ? dayMonth(leg.return_date) : "—"}
            {leg.return_flight ? ` · ${leg.return_flight.replace("retour ", "").split(" · ")[0]}` : ""}
          </div>
        </div>
      </div>
      {leg.booking.length > 0 && (
        <div className="px-4 pt-3">
          <div className="mb-2 text-[11px] font-medium text-muted">Où réserver · billet seul</div>
          <div className="no-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4">
            {leg.booking.slice(0, 6).map((o, i) => (
              <a
                key={i}
                href={leg.booking_url || leg.google_url}
                target="_blank"
                rel="noopener noreferrer"
                className={`shrink-0 rounded-2xl px-3 py-2 ring-1 ${o === best ? "bg-good/12 ring-good/40" : "bg-white/5 ring-white/10"}`}
              >
                <div className="text-[11px] whitespace-nowrap text-muted">
                  {o.site}
                  {o.airline ? " ✈" : ""}
                </div>
                <div className={`text-sm font-bold tabular ${o === best ? "text-good" : ""}`}>{euro(o.price)}</div>
              </a>
            ))}
          </div>
        </div>
      )}
      <div className="grid grid-cols-2 gap-2 p-4">
        <div className="col-span-2">
          <LinkButton href={leg.booking_url || leg.google_url} primary>
            Réserver ce billet
          </LinkButton>
        </div>
        {leg.links.trip && <LinkButton href={leg.links.trip}>Trip.com</LinkButton>}
        <motion.button
          whileTap={{ scale: 0.97 }}
          onClick={() =>
            openSearch({
              origin: leg.origin,
              destination: leg.destination,
              originLabel: place(leg.origin),
              destinationLabel: place(leg.destination),
              depart: leg.depart_date,
              ret: leg.return_date,
              stops: "1",
              bagsOut: leg.bags[0] ?? 0,
              bagsRet: leg.bags[1] ?? 0,
            })
          }
          className="flex items-center justify-center gap-1 rounded-2xl bg-white/8 px-4 py-3 text-sm font-semibold ring-1 ring-white/10"
        >
          Autres vols <ChevronRight size={15} />
        </motion.button>
      </div>
    </motion.div>
  );
}

export default function TripScreen() {
  const [trip, setTrip] = useState<Trip | null>(null);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const load = () => {
    setRefreshing(true);
    api
      .trip()
      .then((t) => {
        setTrip(t);
        localStorage.setItem("gt-trip", JSON.stringify(t));
      })
      .catch((e) => setError(e.message))
      .finally(() => setRefreshing(false));
  };

  useEffect(() => {
    try {
      const cached = localStorage.getItem("gt-trip");
      if (cached) setTrip(JSON.parse(cached));
    } catch {
      /* cache illisible : on attend le réseau */
    }
    load();
  }, []);

  if (!trip)
    return (
      <div className="pt-safe space-y-4">
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-64" />
        <Skeleton className="h-52" />
        {error && <p className="text-sm text-bad">{error}</p>}
      </div>
    );

  const a = trip.advice;
  const act = ACTION[a.action] || ACTION.SURVEILLER;
  const departure = trip.plan.outbound_dates[0];
  const titles = ["Paris – Séoul", "Séoul – Tokyo"];
  const colors = ["var(--color-series-1)", "var(--color-series-2)"];
  const series: Series[] = Object.entries(trip.series)
    .filter(([, pts]) => pts.length)
    .map(([name, pts], i) => ({ name: trip.strategies.find((s) => s.name === name)?.label || name, color: colors[i % 2], points: pts }));
  const hasHistory = series.some((s) => s.points.length > 1);
  const googleSeries: Series[] = [{ name: "Paris ⇄ Séoul (billet seul)", color: "var(--color-accent-2)", points: trip.google_history }];

  return (
    <div>
      <header className="pt-safe flex items-start justify-between px-1">
        <div>
          <p className="text-sm font-medium text-muted">Votre voyage · été 2027</p>
          <h1 className="text-[30px] leading-tight font-extrabold tracking-tight">
            Paris <span className="text-gradient">⇄ Séoul ⇄</span> Tokyo
          </h1>
        </div>
        <motion.button whileTap={{ rotate: 180 }} onClick={load} className="glass mt-1 grid size-10 place-items-center rounded-full" aria-label="Actualiser">
          <RefreshCw size={17} className={refreshing ? "animate-spin" : ""} />
        </motion.button>
      </header>

      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="relative mt-5 overflow-hidden rounded-[30px] p-5">
        <div className="bg-gradient-accent absolute inset-0 opacity-90" />
        <div className="absolute inset-0 bg-[radial-gradient(80%_60%_at_100%_0%,rgba(255,255,255,0.25),transparent_60%)]" />
        <div className="relative">
          <div className="flex items-center justify-between">
            <span className="rounded-full bg-black/25 px-3 py-1 text-xs font-bold tracking-wide">
              {act.emoji} {a.action}
            </span>
            <span className="flex items-center gap-1.5 rounded-full bg-black/25 px-3 py-1 text-xs font-semibold">
              <CalendarClock size={13} /> J-{a.days_left}
            </span>
          </div>
          <div className="mt-5 text-sm text-white/85">Prix par personne · 2 billets · valises comprises</div>
          <div className="text-[52px] leading-none font-extrabold tracking-tight">
            <AnimatedNumber value={a.price} format={euro} />
          </div>
          <p className="mt-3 text-sm leading-snug text-white/90">
            <b>{act.label}</b> : {a.reason}
          </p>
        </div>
      </motion.div>

      <div className="mt-3 grid grid-cols-3 gap-2">
        <Card className="!p-3">
          <div className="text-[11px] text-muted">Plus bas vu</div>
          <div className="font-bold tabular">{euro(a.min_seen)}</div>
        </Card>
        <Card className="!p-3">
          <div className="text-[11px] text-muted">Habituel</div>
          <div className="text-sm font-bold tabular">{a.typical_low ? `${a.typical_low}–${a.typical_high}` : "—"}</div>
        </Card>
        <Card className="!p-3">
          <div className="text-[11px] text-muted">Tendance</div>
          <div className={`flex items-center gap-1 font-bold tabular ${a.trend_per_week && a.trend_per_week > 0 ? "text-bad" : "text-good"}`}>
            {a.trend_per_week && a.trend_per_week > 0 ? <TrendingUp size={15} /> : <TrendingDown size={15} />}
            {a.trend_per_week !== null ? `${a.trend_per_week > 0 ? "+" : ""}${Math.round(a.trend_per_week)} €/s` : "—"}
          </div>
        </Card>
      </div>

      <Card className="mt-3">
        <BuyWindow window={a.window} departure={departure} />
      </Card>

      <SectionTitle action={<span className="text-xs text-muted">mis à jour {ago(trip.generated_at)}</span>}>Vos 2 billets</SectionTitle>
      <div className="space-y-3">
        {trip.best.legs.map((leg, i) => (
          <LegCard key={leg.search} leg={leg} title={titles[i] || leg.search} index={i} />
        ))}
      </div>

      {trip.direct_vs_stop && (
        <Card className="mt-3">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted">Direct Paris ⇄ Séoul</span>
            <span className="font-semibold tabular">{euro(trip.direct_vs_stop.direct)}</span>
          </div>
          <div className="mt-1 flex items-center justify-between text-sm">
            <span className="text-muted">Avec 1 escale</span>
            <span className="font-semibold tabular">{euro(trip.direct_vs_stop.one_stop)}</span>
          </div>
          <div className="mt-2">
            <Badge tone="good">Économie avec escale : {euro(trip.direct_vs_stop.saving)}</Badge>
          </div>
        </Card>
      )}

      <SectionTitle>Évolution du prix</SectionTitle>
      <Card>
        {hasHistory ? <LineChart series={series} /> : <LineChart series={googleSeries} />}
        <p className="mt-2 text-[11px] text-faint">
          {hasHistory ? "Total valises comprises, relevé 4 fois par jour." : "Historique Google Flights du billet Paris ⇄ Séoul (hors valises), en attendant nos propres relevés."}
        </p>
      </Card>

      {trip.timing.weekday.length > 0 && (
        <>
          <SectionTitle>Quand les prix baissent</SectionTitle>
          <Card>
            <WeekBars rows={trip.timing.weekday} />
            {trip.timing.best_day && (
              <p className="mt-3 text-sm text-muted">
                Les baisses tombent le plus souvent le <b className="text-white">{trip.timing.best_day.label}</b>.
              </p>
            )}
          </Card>
        </>
      )}

      <div className="mt-6">
        <PushCard compact />
      </div>
    </div>
  );
}
