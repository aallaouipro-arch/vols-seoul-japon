/** Calendrier + graphique des prix : prix le plus bas pour chaque date de départ sur 30 jours. */

import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { api, type Calendar, type SearchQuery } from "../lib/api";
import { addDays, daysBetween, euro, todayIso } from "../lib/format";
import { Sheet, Skeleton } from "./ui";

const WEEK = ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"];

export function CalendarSheet({
  open,
  onClose,
  query,
  onPick,
}: {
  open: boolean;
  onClose: () => void;
  query: SearchQuery;
  onPick: (depart: string, ret: string | null) => void;
}) {
  const stay = query.ret ? daysBetween(query.depart, query.ret) : null;
  const initial = () => {
    const s = addDays(query.depart, -14);
    return s < todayIso() ? todayIso() : s;
  };
  const [start, setStart] = useState(initial);
  const [data, setData] = useState<Calendar | null>(null);
  const [error, setError] = useState("");
  const [hover, setHover] = useState<string | null>(null);

  useEffect(() => {
    if (open) setStart(initial());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, query.depart]);

  useEffect(() => {
    if (!open) return;
    setData(null);
    setError("");
    api
      .calendar(query, start, stay)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [open, start, query, stay]);

  const tone = (p: number | null) => {
    if (!p || !data?.min || !data.max) return "text-faint";
    const r = (p - data.min) / (data.max - data.min || 1);
    return r < 0.2 ? "text-good" : r > 0.7 ? "text-bad" : "text-white/85";
  };
  const offset = (new Date(`${start}T12:00:00`).getDay() + 6) % 7; // lundi = 0
  const shown = hover ? data?.days.find((d) => d.depart === hover) : null;

  return (
    <Sheet open={open} onClose={onClose} title="Calendrier des prix">
      <p className="mb-3 text-xs text-muted">
        Prix le plus bas pour chaque jour de départ{stay ? `, séjour de ${stay} jours` : ", aller simple"} · {query.originLabel} → {query.destinationLabel}
      </p>
      <div className="mb-3 flex items-center justify-between">
        <button onClick={() => setStart((s) => (addDays(s, -30) < todayIso() ? todayIso() : addDays(s, -30)))} disabled={start <= todayIso()} className="grid size-9 place-items-center rounded-xl bg-white/8 disabled:opacity-30" aria-label="30 jours plus tôt">
          <ChevronLeft size={18} />
        </button>
        <span className="text-sm font-semibold">
          {new Date(`${start}T12:00:00`).toLocaleDateString("fr-FR", { day: "numeric", month: "short" })} →{" "}
          {new Date(`${addDays(start, 29)}T12:00:00`).toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" })}
        </span>
        <button onClick={() => setStart((s) => addDays(s, 30))} className="grid size-9 place-items-center rounded-xl bg-white/8" aria-label="30 jours plus tard">
          <ChevronRight size={18} />
        </button>
      </div>

      {error && <p className="text-sm text-bad">{error}</p>}
      {!data && !error && (
        <div className="space-y-2">
          <Skeleton className="h-64" />
          <p className="text-center text-xs text-muted">Recherche de 30 dates sur Google Flights…</p>
        </div>
      )}

      {data && (
        <>
          <div className="grid grid-cols-7 gap-1 text-center">
            {WEEK.map((w) => (
              <div key={w} className="pb-1 text-[10px] font-medium text-muted uppercase">
                {w}
              </div>
            ))}
            {Array.from({ length: offset }).map((_, i) => (
              <div key={`e${i}`} />
            ))}
            {data.days.map((d) => {
              const sel = d.depart === query.depart;
              const best = d.price !== null && d.price === data.min;
              return (
                <motion.button
                  key={d.depart}
                  whileTap={{ scale: 0.92 }}
                  disabled={!d.price}
                  onClick={() => {
                    onPick(d.depart, d.ret);
                    onClose();
                  }}
                  className={`rounded-xl py-1.5 ring-1 ${sel ? "bg-accent/25 ring-accent" : best ? "bg-good/12 ring-good/40" : "bg-white/4 ring-white/6"} disabled:opacity-40`}
                >
                  <div className="text-[11px] text-white/70">{Number(d.depart.slice(8))}</div>
                  <div className={`text-[11px] font-bold tabular ${tone(d.price)}`}>{d.price ? d.price : "—"}</div>
                </motion.button>
              );
            })}
          </div>

          <div className="mt-6 mb-2 flex items-end justify-between">
            <span className="text-sm font-semibold">Graphique des prix</span>
            <span className="text-xs text-muted tabular">
              {shown ? `${new Date(`${shown.depart}T12:00:00`).toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short" })} : ${euro(shown.price)}` : `de ${euro(data.min)} à ${euro(data.max)}`}
            </span>
          </div>
          <div className="flex h-28 items-end gap-[3px]" onPointerLeave={() => setHover(null)}>
            {data.days.map((d) => {
              const h = d.price && data.max ? 12 + ((d.price - (data.min || 0)) / ((data.max - (data.min || 0)) || 1)) * 88 : 4;
              const best = d.price !== null && d.price === data.min;
              return (
                <button
                  key={d.depart}
                  onPointerEnter={() => setHover(d.depart)}
                  onClick={() => d.price && (onPick(d.depart, d.ret), onClose())}
                  className={`flex-1 rounded-t-[3px] ${best ? "bg-good" : d.depart === query.depart ? "bg-accent" : "bg-series-1/70"} ${hover === d.depart ? "opacity-100" : "opacity-85"}`}
                  style={{ height: `${h}%` }}
                  aria-label={`${d.depart} : ${d.price ? euro(d.price) : "pas de prix"}`}
                />
              );
            })}
          </div>
          <p className="mt-3 text-[11px] text-faint">Touche une date pour relancer la recherche. Prix hors valises, pour tous les passagers.</p>
        </>
      )}
    </Sheet>
  );
}
