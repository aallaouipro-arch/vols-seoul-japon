import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Bell, ChevronRight, Flame, Plane, RefreshCw } from "lucide-react";
import { AirlineLogo, Badge, SectionTitle, Skeleton, type Tone } from "../components/ui";
import { api, type Deal, type Deals, type Trip, type Watch } from "../lib/api";
import { deviceId } from "../lib/device";
import { ago, cap, daysBetween, euro, flag, shortDate } from "../lib/format";
import { go, openSearch } from "../lib/nav";

type Filter = "all" | "europe" | "long";

const ACTION_TONE: Record<string, Tone> = { ACHETER: "good", SURVEILLER: "warn", ATTENDRE: "neutral" };

function cached<T>(key: string): T | null {
  try {
    return JSON.parse(localStorage.getItem(key) || "null");
  } catch {
    return null;
  }
}

const searchDeal = (d: Deal) =>
  openSearch({
    origin: "CDG+ORY",
    destination: d.code,
    originLabel: "Paris",
    destinationLabel: d.city,
    depart: d.depart,
    ret: d.ret,
    stops: "1",
    bagsOut: 0,
    bagsRet: 0,
  });

function TripPin({ trip }: { trip: Trip | null }) {
  return (
    <motion.button whileTap={{ scale: 0.985 }} onClick={() => go("/voyage")} className="glass flex w-full items-center gap-3 rounded-3xl p-3.5 text-left">
      <div className="bg-gradient-accent grid size-11 shrink-0 place-items-center rounded-2xl">
        <Plane size={19} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-[11px] font-medium text-muted">Voyage prioritaire · été 2027</div>
        <div className="truncate font-semibold">Séoul & Tokyo</div>
        {trip && <div className="text-xs text-muted">Départ de Paris dans {trip.advice.days_left} jours</div>}
      </div>
      {trip ? (
        <div className="flex flex-col items-end gap-1">
          <span className="font-bold tabular">{euro(trip.advice.price)}</span>
          <Badge tone={ACTION_TONE[trip.advice.action]} className="!px-2 !py-0.5 !text-[10px]">
            {trip.advice.action}
          </Badge>
        </div>
      ) : (
        <Skeleton className="h-9 w-16" />
      )}
      <ChevronRight size={18} className="shrink-0 text-faint" />
    </motion.button>
  );
}

function AlertsPin({ watches }: { watches: Watch[] }) {
  const below = watches.filter((w) => w.last_price && w.min_price && w.last_price <= w.min_price).length;
  return (
    <motion.button whileTap={{ scale: 0.985 }} onClick={() => go("/alertes")} className="glass flex w-full items-center gap-3 rounded-3xl p-3.5 text-left">
      <div className="grid size-11 shrink-0 place-items-center rounded-2xl bg-white/8">
        <Bell size={19} className="text-accent-2" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="font-semibold">
          {watches.length} alerte{watches.length > 1 ? "s" : ""} suivie{watches.length > 1 ? "s" : ""}
        </div>
        <div className="truncate text-xs text-muted">
          {below ? `${below} au plus bas en ce moment` : watches.map((w) => w.destination_label).join(" · ")}
        </div>
      </div>
      <ChevronRight size={18} className="shrink-0 text-faint" />
    </motion.button>
  );
}

function FeaturedDeal({ d }: { d: Deal }) {
  return (
    <motion.button
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      whileTap={{ scale: 0.985 }}
      onClick={() => searchDeal(d)}
      className="relative block w-full overflow-hidden rounded-[28px] p-[1.5px] text-left"
    >
      <div className="bg-gradient-accent absolute inset-0 opacity-70" />
      <div className="relative rounded-[26.5px] bg-[#10121b] p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-1.5 text-[11px] font-semibold tracking-wide text-accent-2 uppercase">
              <Flame size={13} /> Meilleur plan du moment
            </div>
            <div className="mt-1 text-[26px] leading-tight font-extrabold tracking-tight">
              {flag(d.country)} {d.city}
            </div>
            <div className="text-sm text-muted">
              {shortDate(d.depart)} → {shortDate(d.ret)} · {daysBetween(d.depart, d.ret)} j
            </div>
          </div>
          {d.discount !== null && d.discount > 0 && <Badge tone="good">-{d.discount} %</Badge>}
        </div>
        <div className="mt-4 flex items-end justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2.5">
            <AirlineLogo code={d.airline_code} name={d.airline} size={32} />
            <div className="min-w-0 text-xs text-muted">
              <div className="truncate text-white/85">{d.airline}</div>
              {d.stops === 0 ? "Direct" : `${d.stops} escale`}
            </div>
          </div>
          <div className="text-right">
            <div className="text-[30px] leading-none font-extrabold tabular">{euro(d.price)}</div>
            <div className="mt-1 text-[11px] text-muted">aller-retour</div>
          </div>
        </div>
      </div>
    </motion.button>
  );
}

function DealRow({ d, index }: { d: Deal; index: number }) {
  return (
    <motion.button
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ delay: Math.min(index * 0.03, 0.3) }}
      whileTap={{ scale: 0.985 }}
      onClick={() => searchDeal(d)}
      className="glass flex w-full items-center gap-3 rounded-3xl p-3.5 text-left"
    >
      <div className="grid size-11 shrink-0 place-items-center rounded-2xl bg-white/6 text-xl">{flag(d.country)}</div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate font-semibold">{d.city}</span>
          {d.new && <span className="rounded-full bg-accent-2/15 px-1.5 py-0.5 text-[10px] font-bold text-accent-2">NOUVEAU</span>}
        </div>
        <div className="truncate text-xs text-muted">
          {shortDate(d.depart)} → {shortDate(d.ret)} · {d.stops === 0 ? "direct" : `${d.stops} escale`}
        </div>
      </div>
      <div className="text-right">
        <div className="font-bold tabular">{euro(d.price)}</div>
        {d.discount !== null && d.discount > 0 ? (
          <div className={`text-[11px] font-semibold tabular ${d.is_deal ? "text-good" : "text-muted"}`}>-{d.discount} %</div>
        ) : (
          <div className="text-[11px] text-faint">prix habituel</div>
        )}
      </div>
    </motion.button>
  );
}

function Segmented({ value, onChange }: { value: Filter; onChange: (f: Filter) => void }) {
  const opts: [Filter, string][] = [
    ["all", "Tout"],
    ["europe", "Week-ends"],
    ["long", "Long-courrier"],
  ];
  return (
    <div className="flex rounded-2xl bg-white/6 p-1 ring-1 ring-white/8">
      {opts.map(([v, label]) => (
        <button key={v} onClick={() => onChange(v)} className="relative flex-1 rounded-xl px-2 py-2 text-sm font-semibold">
          {value === v && <motion.span layoutId="deal-filter" className="absolute inset-0 rounded-xl bg-white/12 ring-1 ring-white/15" />}
          <span className={`relative ${value === v ? "text-white" : "text-muted"}`}>{label}</span>
        </button>
      ))}
    </div>
  );
}

export default function HomeScreen() {
  const [deals, setDeals] = useState<Deals | null>(() => cached("gt-deals"));
  const [trip, setTrip] = useState<Trip | null>(() => cached("gt-trip"));
  const [watches, setWatches] = useState<Watch[]>([]);
  const [filter, setFilter] = useState<Filter>("all");
  const [refreshing, setRefreshing] = useState(false);
  const [showAll, setShowAll] = useState(false);

  const load = () => {
    setRefreshing(true);
    Promise.allSettled([
      api.deals().then((d) => {
        setDeals(d);
        localStorage.setItem("gt-deals", JSON.stringify(d));
      }),
      api.trip().then((t) => {
        setTrip(t);
        localStorage.setItem("gt-trip", JSON.stringify(t));
      }),
      api.watches(deviceId()).then((r) => setWatches(r.watches)),
    ]).finally(() => setRefreshing(false));
  };
  useEffect(load, []);

  const items = useMemo(() => (deals?.items || []).filter((d) => filter === "all" || d.region === filter), [deals, filter]);
  const good = items.filter((d) => d.is_deal);
  const others = items.filter((d) => !d.is_deal).sort((a, b) => a.price - b.price);
  const [featured, ...rest] = good;
  const today = new Date().toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });

  return (
    <div>
      <header className="pt-safe flex items-center justify-between px-1">
        <div className="flex items-center gap-2.5">
          <img src="/icons/icon.svg" alt="" className="size-8 rounded-[10px]" />
          <span className="text-[15px] font-bold tracking-tight">Google Tracker</span>
        </div>
        <motion.button whileTap={{ rotate: 180 }} onClick={load} className="glass grid size-9 place-items-center rounded-full" aria-label="Actualiser">
          <RefreshCw size={16} className={refreshing ? "animate-spin" : ""} />
        </motion.button>
      </header>

      <div className="mt-5 px-1">
        <p className="text-sm text-muted">{cap(today)}</p>
        <h1 className="text-[30px] leading-tight font-extrabold tracking-tight">Bons plans</h1>
        <p className="text-sm text-muted">
          Au départ de Paris · {deals?.generated_at ? `mis à jour ${ago(deals.generated_at)}` : "premier scan en cours"}
        </p>
      </div>

      <div className="mt-5 space-y-2.5">
        <TripPin trip={trip} />
        {watches.length > 0 && <AlertsPin watches={watches} />}
      </div>

      <div className="mt-6">
        <Segmented value={filter} onChange={setFilter} />
      </div>

      {!deals && (
        <div className="mt-4 space-y-3">
          <Skeleton className="h-44" />
          <Skeleton className="h-16" />
          <Skeleton className="h-16" />
        </div>
      )}

      {deals && (
        <AnimatePresence mode="popLayout">
          <motion.div key={filter} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-4 space-y-2.5">
            {featured ? (
              <FeaturedDeal d={featured} />
            ) : (
              <div className="glass rounded-3xl p-5 text-center text-sm text-muted">
                Pas de prix vraiment sous la normale pour l'instant. Les destinations sont re-scannées chaque jour.
              </div>
            )}
            {rest.map((d, i) => (
              <DealRow key={d.code} d={d} index={i} />
            ))}
          </motion.div>
        </AnimatePresence>
      )}

      {others.length > 0 && (
        <>
          <SectionTitle action={<span className="text-xs text-muted">du moins cher</span>}>Prix du moment</SectionTitle>
          <div className="space-y-2.5">
            {(showAll ? others : others.slice(0, 8)).map((d, i) => (
              <DealRow key={d.code} d={d} index={i} />
            ))}
          </div>
          {others.length > 8 && (
            <motion.button whileTap={{ scale: 0.97 }} onClick={() => setShowAll((v) => !v)} className="mt-3 w-full rounded-2xl bg-white/6 py-3 text-sm font-semibold text-white/85 ring-1 ring-white/8">
              {showAll ? "Voir moins" : `Voir les ${others.length} destinations`}
            </motion.button>
          )}
        </>
      )}

      <p className="mt-5 px-1 text-[11px] leading-relaxed text-faint">
        Prix aller-retour par personne, hors valises, 1 escale max, relevés chaque jour sur Google Flights. Bon plan = prix sous la fourchette habituelle de
        Google ou au moins 20 % sous sa moyenne. Résumé envoyé en notification chaque lundi.
      </p>
    </div>
  );
}
