/** Multi-destinations : jusqu'à 5 vols, chacun cherché en billet séparé + lien Google « billet unique ». */

import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ExternalLink, Luggage, Minus, Plus, Search as SearchIcon, Trash2 } from "lucide-react";
import { api, type Cabin, type MultiResponse, type Offer, type Pax, type SearchQuery, type Stops } from "../lib/api";
import { addDays, euro, shortDate, todayIso } from "../lib/format";
import { AirportPicker } from "./AirportPicker";
import { OfferCard, OfferSheet } from "./Flight";
import { LinkButton, SectionTitle, Skeleton, useToast } from "./ui";

type Leg = { origin: string; originLabel: string; destination: string; destinationLabel: string; date: string; bags: number };

const DEFAULT_LEGS: Leg[] = [
  { origin: "CDG+ORY", originLabel: "Paris", destination: "SEL", destinationLabel: "Séoul", date: "2027-07-21", bags: 1 },
  { origin: "SEL", originLabel: "Séoul", destination: "TYO", destinationLabel: "Tokyo", date: "2027-07-28", bags: 1 },
  { origin: "TYO", originLabel: "Tokyo", destination: "CDG+ORY", destinationLabel: "Paris", date: "2027-08-18", bags: 2 },
];

function load(): Leg[] {
  try {
    const l = JSON.parse(localStorage.getItem("gt-multi") || "null");
    return Array.isArray(l) && l.length >= 2 ? l : DEFAULT_LEGS;
  } catch {
    return DEFAULT_LEGS;
  }
}

export function MultiCity({ stops, cabin, pax }: { stops: Stops; cabin: Cabin; pax: Pax }) {
  const toast = useToast();
  const [legs, setLegs] = useState<Leg[]>(load);
  const [picker, setPicker] = useState<{ i: number; field: "origin" | "destination" } | null>(null);
  const [res, setRes] = useState<MultiResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [open, setOpen] = useState<{ offer: Offer; leg: number } | null>(null);
  const [expanded, setExpanded] = useState<number[]>([]);

  const save = (next: Leg[]) => {
    setLegs(next);
    localStorage.setItem("gt-multi", JSON.stringify(next));
  };
  const patch = (i: number, p: Partial<Leg>) => save(legs.map((l, k) => (k === i ? { ...l, ...p } : l)));

  const run = async () => {
    for (let i = 0; i < legs.length; i++) {
      if (legs[i].origin === legs[i].destination) return toast(`Vol ${i + 1} : choisis deux villes différentes`, "bad");
      if (i && legs[i].date < legs[i - 1].date) return toast(`Vol ${i + 1} : la date doit suivre celle du vol ${i}`, "bad");
    }
    setLoading(true);
    setError("");
    setRes(null);
    try {
      setRes(
        await api.multi({
          legs: legs.map((l) => ({ origin: l.origin, destination: l.destination, date: l.date, bags: l.bags })),
          stops,
          cabin,
          adults: pax.adults,
          children: pax.children,
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const legQuery = (i: number): SearchQuery => ({
    origin: legs[i].origin,
    destination: legs[i].destination,
    originLabel: legs[i].originLabel,
    destinationLabel: legs[i].destinationLabel,
    depart: legs[i].date,
    ret: null,
    stops,
    bagsOut: legs[i].bags,
    bagsRet: 0,
    cabin,
    pax,
  });

  return (
    <div>
      <div className="space-y-3">
        {legs.map((l, i) => (
          <motion.div layout key={i} className="rounded-2xl bg-white/4 p-3 ring-1 ring-white/8">
            <div className="mb-2 flex items-center justify-between text-xs font-semibold text-muted">
              <span>Vol {i + 1}</span>
              {legs.length > 2 && (
                <button onClick={() => save(legs.filter((_, k) => k !== i))} className="flex items-center gap-1 text-bad" aria-label={`Supprimer le vol ${i + 1}`}>
                  <Trash2 size={13} /> Retirer
                </button>
              )}
            </div>
            <div className="grid grid-cols-2 gap-2">
              {(["origin", "destination"] as const).map((f) => (
                <button key={f} onClick={() => setPicker({ i, field: f })} className="rounded-xl bg-white/5 px-3 py-2 text-left ring-1 ring-white/8">
                  <div className="text-[10px] text-muted">{f === "origin" ? "De" : "Vers"}</div>
                  <div className="truncate text-sm font-semibold">{f === "origin" ? l.originLabel : l.destinationLabel}</div>
                </button>
              ))}
              <label className="relative rounded-xl bg-white/5 px-3 py-2 ring-1 ring-white/8">
                <div className="text-[10px] text-muted">Date</div>
                <div className="text-sm font-semibold">{shortDate(l.date)}</div>
                <input type="date" value={l.date} min={i ? legs[i - 1].date : todayIso()} onChange={(e) => e.target.value && patch(i, { date: e.target.value })} className="absolute inset-0 opacity-0" aria-label={`Date du vol ${i + 1}`} />
              </label>
              <div className="flex items-center justify-between rounded-xl bg-white/5 px-3 py-2 ring-1 ring-white/8">
                <span className="flex items-center gap-1 text-[11px] text-muted">
                  <Luggage size={12} /> Valises
                </span>
                <span className="flex items-center gap-1.5">
                  <button onClick={() => patch(i, { bags: Math.max(0, l.bags - 1) })} className="grid size-6 place-items-center rounded-md bg-white/8" aria-label="Moins de valises">
                    <Minus size={12} />
                  </button>
                  <span className="w-3 text-center text-sm font-bold">{l.bags}</span>
                  <button onClick={() => patch(i, { bags: Math.min(3, l.bags + 1) })} className="grid size-6 place-items-center rounded-md bg-white/8" aria-label="Plus de valises">
                    <Plus size={12} />
                  </button>
                </span>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
      {legs.length < 5 && (
        <button
          onClick={() => {
            const last = legs[legs.length - 1];
            save([...legs, { origin: last.destination, originLabel: last.destinationLabel, destination: last.origin, destinationLabel: last.originLabel, date: addDays(last.date, 7), bags: last.bags }]);
          }}
          className="mt-3 flex w-full items-center justify-center gap-2 rounded-2xl py-2.5 text-sm font-semibold text-accent-2 ring-1 ring-accent-2/30 ring-dashed"
        >
          <Plus size={16} /> Ajouter un vol
        </button>
      )}
      <motion.button whileTap={{ scale: 0.97 }} onClick={run} disabled={loading} className="bg-gradient-accent mt-3 flex w-full items-center justify-center gap-2 rounded-2xl py-4 text-base font-bold shadow-lg shadow-violet-900/40 disabled:opacity-70">
        {loading ? <motion.span animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: "linear" }} className="size-5 rounded-full border-2 border-white/40 border-t-white" /> : <SearchIcon size={19} />}
        {loading ? "Recherche des vols…" : `Rechercher les ${legs.length} vols`}
      </motion.button>

      {error && <div className="glass mt-5 rounded-3xl p-4 text-sm text-bad">{error}</div>}
      {loading && (
        <div className="mt-5 space-y-3">
          <Skeleton className="h-24" />
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
        </div>
      )}

      <AnimatePresence>
        {res && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <div className="glass mt-5 rounded-3xl p-4">
              <div className="text-xs text-muted">Total en billets séparés (le moins cher de chaque vol)</div>
              <div className="text-3xl font-extrabold tabular">{res.total_separate ? euro(res.total_separate) : "—"}</div>
              <p className="mt-1 text-xs text-muted">
                Valises comprises (estimation), pour {pax.adults + pax.children + pax.infantsSeat + pax.infantsLap}{" "}
                {pax.adults + pax.children + pax.infantsSeat + pax.infantsLap > 1 ? "passagers" : "passager"}.
              </p>
              <div className="mt-3">
                <LinkButton href={res.google_multicity_url}>
                  <ExternalLink size={15} /> Comparer avec un billet unique sur Google Flights
                </LinkButton>
              </div>
              <p className="mt-2 text-[11px] leading-relaxed text-faint">
                Billets séparés : si un vol est annulé ou retardé, les autres compagnies ne sont pas tenues de vous réacheminer. Laisse de la marge entre deux vols.
              </p>
            </div>
            {res.legs.map((l, i) => {
              const showAll = expanded.includes(i);
              return (
                <div key={i}>
                  <SectionTitle action={<span className="text-xs text-muted">{l.offers.length} vols</span>}>
                    Vol {i + 1} · {legs[i]?.originLabel} → {legs[i]?.destinationLabel} · {shortDate(l.date)}
                  </SectionTitle>
                  <div className="space-y-3">
                    {(showAll ? l.offers : l.offers.slice(0, 3)).map((o, k) => (
                      <OfferCard key={k} offer={o} index={k} cheapest={k === 0} onClick={() => setOpen({ offer: o, leg: i })} />
                    ))}
                  </div>
                  {l.offers.length > 3 && (
                    <button onClick={() => setExpanded((e) => (showAll ? e.filter((x) => x !== i) : [...e, i]))} className="mt-2 w-full py-2 text-sm font-semibold text-accent-2">
                      {showAll ? "Voir moins" : `Voir les ${l.offers.length} vols`}
                    </button>
                  )}
                  {l.offers.length === 0 && <p className="text-sm text-muted">Aucun vol trouvé pour ce trajet.</p>}
                </div>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>

      <AirportPicker
        open={picker !== null}
        title={picker?.field === "origin" ? "Départ" : "Destination"}
        onClose={() => setPicker(null)}
        onPick={(code, label) => picker && patch(picker.i, picker.field === "origin" ? { origin: code, originLabel: label } : { destination: code, destinationLabel: label })}
      />
      {res && open && (
        <OfferSheet offer={open.offer} query={legQuery(open.leg)} links={res.legs[open.leg].links} googleUrl={res.legs[open.leg].google_url} onClose={() => setOpen(null)} />
      )}
    </div>
  );
}
