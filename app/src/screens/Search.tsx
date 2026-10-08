import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowUpDown, CalendarDays, Luggage, Minus, Plus, Search as SearchIcon, Sparkles } from "lucide-react";
import { AirportPicker } from "../components/AirportPicker";
import { OfferCard, OfferSheet } from "../components/Flight";
import { RangeBar } from "../components/charts";
import { LevelBadge, SectionTitle, Skeleton, useToast } from "../components/ui";
import { api, type FlexDay, type Offer, type SearchQuery, type SearchResponse, type Stops } from "../lib/api";
import { addDays, dayMonth, daysBetween, euro, shortDate, todayIso } from "../lib/format";
import { saveQuery, savedQuery } from "../lib/nav";

type Sort = "price" | "duration" | "depart";

function Segmented<T extends string>({ value, options, onChange, layoutId }: { value: T; options: [T, string][]; onChange: (v: T) => void; layoutId: string }) {
  return (
    <div className="flex rounded-2xl bg-white/6 p-1 ring-1 ring-white/8">
      {options.map(([v, label]) => (
        <button key={v} onClick={() => onChange(v)} className="relative flex-1 rounded-xl px-3 py-2 text-sm font-semibold">
          {value === v && <motion.span layoutId={layoutId} className="absolute inset-0 rounded-xl bg-white/12 ring-1 ring-white/15" transition={{ type: "spring", damping: 30, stiffness: 380 }} />}
          <span className={`relative ${value === v ? "text-white" : "text-muted"}`}>{label}</span>
        </button>
      ))}
    </div>
  );
}

function Stepper({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <div className="flex items-center justify-between gap-1 rounded-2xl bg-white/5 py-2 pr-2 pl-3 ring-1 ring-white/8">
      <span className="truncate text-sm text-white/85">{label}</span>
      <div className="flex shrink-0 items-center gap-1.5">
        <button onClick={() => onChange(Math.max(0, value - 1))} className="grid size-7 place-items-center rounded-lg bg-white/8 active:scale-90" aria-label={`Moins de valises ${label}`}>
          <Minus size={14} />
        </button>
        <span className="w-4 text-center font-semibold tabular">{value}</span>
        <button onClick={() => onChange(Math.min(3, value + 1))} className="grid size-7 place-items-center rounded-lg bg-white/8 active:scale-90" aria-label={`Plus de valises ${label}`}>
          <Plus size={14} />
        </button>
      </div>
    </div>
  );
}

function DateField({ label, value, min, onChange }: { label: string; value: string; min: string; onChange: (v: string) => void }) {
  return (
    <label className="relative flex-1 rounded-2xl bg-white/5 px-4 py-2.5 ring-1 ring-white/8">
      <span className="flex items-center gap-1.5 text-[11px] font-medium text-muted">
        <CalendarDays size={12} /> {label}
      </span>
      <span className="block text-[15px] font-semibold">{value ? shortDate(value) : "—"}</span>
      <input type="date" value={value} min={min} onChange={(e) => e.target.value && onChange(e.target.value)} className="absolute inset-0 opacity-0" aria-label={label} />
    </label>
  );
}

export default function SearchScreen() {
  const toast = useToast();
  const [q, setQ] = useState<SearchQuery>(savedQuery);
  const [picker, setPicker] = useState<"origin" | "destination" | null>(null);
  const [res, setRes] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [flex, setFlex] = useState<FlexDay[] | null>(null);
  const [sort, setSort] = useState<Sort>("price");
  const [selected, setSelected] = useState<Offer | null>(null);
  const [ranQuery, setRanQuery] = useState<SearchQuery | null>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

  const update = (patch: Partial<SearchQuery>) =>
    setQ((cur) => {
      const next = { ...cur, ...patch };
      if (next.ret && next.ret < next.depart) next.ret = addDays(next.depart, Math.max(1, cur.ret ? daysBetween(cur.depart, cur.ret) : 7));
      saveQuery(next);
      return next;
    });

  const run = useCallback(
    async (query: SearchQuery = q) => {
      if (query.origin === query.destination) return toast("Choisis deux villes différentes", "bad");
      setLoading(true);
      setError("");
      setRes(null);
      setFlex(null);
      setRanQuery(query);
      setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
      try {
        const r = await api.search(query);
        setRes(r);
        api.flex(query).then((f) => setFlex(f.days)).catch(() => setFlex([]));
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setLoading(false);
      }
    },
    [q, toast],
  );

  // Préremplissage depuis l'onglet Voyage ou une alerte
  useEffect(() => {
    const onPrefill = () => {
      const next = savedQuery();
      setQ(next);
      if (sessionStorage.getItem("gt-autorun")) {
        sessionStorage.removeItem("gt-autorun");
        run(next);
      }
    };
    onPrefill();
    window.addEventListener("gt-search-prefill", onPrefill);
    return () => window.removeEventListener("gt-search-prefill", onPrefill);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const offers = useMemo(() => {
    const list = [...(res?.offers || [])];
    if (sort === "duration") list.sort((a, b) => a.duration_min - b.duration_min);
    else if (sort === "depart") list.sort((a, b) => a.depart.localeCompare(b.depart));
    else list.sort((a, b) => a.total - b.total);
    return list;
  }, [res, sort]);
  const cheapest = res?.offers.length ? Math.min(...res.offers.map((o) => o.total)) : null;
  const flexMin = flex?.length ? Math.min(...flex.filter((d) => d.price).map((d) => d.price!)) : null;
  const today = todayIso();

  return (
    <div>
      <header className="pt-safe px-1">
        <p className="text-sm font-medium text-muted">Recherche en direct</p>
        <h1 className="text-[32px] leading-tight font-extrabold tracking-tight">
          Où veux-tu <span className="text-gradient">aller</span> ?
        </h1>
      </header>

      <div className="glass mt-5 space-y-3 rounded-[28px] p-4">
        <Segmented
          layoutId="trip-type"
          value={q.ret ? "rt" : "ow"}
          options={[["rt", "Aller-retour"], ["ow", "Aller simple"]]}
          onChange={(v) => update({ ret: v === "rt" ? addDays(q.depart, 14) : null })}
        />

        <div className="relative space-y-2">
          {(["origin", "destination"] as const).map((k) => (
            <button key={k} onClick={() => setPicker(k)} className="flex w-full items-center gap-3 rounded-2xl bg-white/5 px-4 py-3 text-left ring-1 ring-white/8 active:bg-white/8">
              <span className="w-8 text-[11px] font-medium text-muted">{k === "origin" ? "De" : "Vers"}</span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[17px] font-semibold">{k === "origin" ? q.originLabel : q.destinationLabel}</span>
                <span className="block text-xs text-muted">{(k === "origin" ? q.origin : q.destination).replace(/\+/g, " + ")}</span>
              </span>
            </button>
          ))}
          <motion.button
            whileTap={{ rotate: 180, scale: 0.9 }}
            onClick={() => update({ origin: q.destination, destination: q.origin, originLabel: q.destinationLabel, destinationLabel: q.originLabel })}
            className="absolute top-1/2 right-4 grid size-10 -translate-y-1/2 place-items-center rounded-full bg-ink-2 text-white ring-1 ring-white/15"
            aria-label="Inverser départ et arrivée"
          >
            <ArrowUpDown size={17} />
          </motion.button>
        </div>

        <div className="flex gap-2">
          <DateField label="Aller" value={q.depart} min={today} onChange={(v) => update({ depart: v })} />
          {q.ret && <DateField label="Retour" value={q.ret} min={q.depart} onChange={(v) => update({ ret: v })} />}
        </div>

        <Segmented
          layoutId="stops"
          value={q.stops}
          options={[["0", "Direct"], ["1", "1 escale"], ["any", "Toutes"]]}
          onChange={(v) => update({ stops: v as Stops })}
        />

        <div className="flex items-center gap-1.5 px-1 text-xs font-medium text-muted">
          <Luggage size={13} /> Valises en soute (23 kg) · prix comparés valises comprises
        </div>
        <div className={`grid gap-2 ${q.ret ? "grid-cols-2" : "grid-cols-1"}`}>
          <Stepper label={q.ret ? "Aller" : "Valises"} value={q.bagsOut} onChange={(v) => update({ bagsOut: v })} />
          {q.ret && <Stepper label="Retour" value={q.bagsRet} onChange={(v) => update({ bagsRet: v })} />}
        </div>

        <motion.button
          whileTap={{ scale: 0.97 }}
          onClick={() => run()}
          disabled={loading}
          className="bg-gradient-accent flex w-full items-center justify-center gap-2 rounded-2xl py-4 text-base font-bold shadow-lg shadow-violet-900/40 disabled:opacity-70"
        >
          {loading ? (
            <motion.span animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: "linear" }} className="size-5 rounded-full border-2 border-white/40 border-t-white" />
          ) : (
            <SearchIcon size={19} />
          )}
          {loading ? "Recherche sur Google Flights…" : "Rechercher les vols"}
        </motion.button>
      </div>

      <div ref={resultsRef} className="scroll-mt-4">
        {error && <div className="glass mt-5 rounded-3xl p-4 text-sm text-bad">{error}</div>}

        {loading && (
          <div className="mt-5 space-y-3">
            <Skeleton className="h-28" />
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-32" />
            ))}
          </div>
        )}

        <AnimatePresence>
          {res && ranQuery && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              {res.insights?.typical_low && res.insights.current ? (
                <div className="glass mt-5 rounded-3xl p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm font-semibold">
                      <Sparkles size={16} className="text-accent-2" /> Tendance Google Flights
                    </div>
                    <LevelBadge level={res.insights.level} />
                  </div>
                  <RangeBar low={res.insights.typical_low} high={res.insights.typical_high!} value={res.insights.current} />
                  <p className="mt-2 text-xs text-muted">Prix habituels pour ce trajet à ces dates (hors valises).</p>
                </div>
              ) : null}

              {flex && flex.length > 1 && (
                <>
                  <SectionTitle>Dates proches</SectionTitle>
                  <div className="no-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4 pb-1">
                    {flex.map((d) => {
                      const current = d.depart === ranQuery.depart;
                      const best = d.price !== null && d.price === flexMin;
                      return (
                        <motion.button
                          key={d.depart}
                          whileTap={{ scale: 0.95 }}
                          onClick={() => {
                            const next = { ...ranQuery, depart: d.depart, ret: d.ret };
                            setQ(next);
                            saveQuery(next);
                            run(next);
                          }}
                          className={`shrink-0 rounded-2xl px-3.5 py-2.5 text-left ring-1 ${current ? "bg-white/12 ring-white/30" : "bg-white/5 ring-white/8"}`}
                        >
                          <div className="text-[11px] text-muted">{shortDate(d.depart)}</div>
                          <div className={`text-sm font-bold tabular ${best ? "text-good" : ""}`}>{d.price ? euro(d.price) : "—"}</div>
                        </motion.button>
                      );
                    })}
                  </div>
                  <p className="mt-1.5 px-1 text-[11px] text-faint">Prix hors valises{ranQuery.ret ? `, même durée de séjour (${daysBetween(ranQuery.depart, ranQuery.ret)} j)` : ""}.</p>
                </>
              )}

              <SectionTitle
                action={
                  <span className="text-xs text-muted">
                    {res.offers.length} vols · {dayMonth(ranQuery.depart)}
                    {ranQuery.ret ? ` → ${dayMonth(ranQuery.ret)}` : ""}
                  </span>
                }
              >
                Vols {ranQuery.originLabel} → {ranQuery.destinationLabel}
              </SectionTitle>
              <div className="mb-3">
                <Segmented
                  layoutId="sort"
                  value={sort}
                  options={[["price", "Prix"], ["duration", "Durée"], ["depart", "Départ"]]}
                  onChange={setSort}
                />
              </div>
              {ranQuery.ret && <p className="mb-3 px-1 text-xs text-muted">Prix aller-retour. Touche un vol aller pour choisir le retour.</p>}
              {res.offers.length === 0 && <div className="glass rounded-3xl p-6 text-center text-sm text-muted">Aucun vol trouvé avec ces critères. Essaie « Toutes » les escales.</div>}
              <div className="space-y-3">
                {offers.map((o, i) => (
                  <OfferCard key={`${o.depart}-${o.route}-${o.price}-${i}`} offer={o} index={i} cheapest={o.total === cheapest} onClick={() => setSelected(o)} />
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <AirportPicker
        open={picker !== null}
        title={picker === "origin" ? "Départ" : "Destination"}
        onClose={() => setPicker(null)}
        onPick={(code, label) => update(picker === "origin" ? { origin: code, originLabel: label } : { destination: code, destinationLabel: label })}
      />
      {res && ranQuery && <OfferSheet offer={selected} query={ranQuery} links={res.links} googleUrl={res.google_url} onClose={() => setSelected(null)} />}
    </div>
  );
}
