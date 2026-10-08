import { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "motion/react";
import { History, MapPin, Search } from "lucide-react";
import { loadPlaces, searchPlaces, shortLabel, type Place } from "../lib/airports";
import { flag } from "../lib/format";
import { Sheet } from "./ui";

const RECENT_KEY = "gt-recent-places";

function recent(): Place[] {
  try {
    return JSON.parse(localStorage.getItem(RECENT_KEY) || "[]");
  } catch {
    return [];
  }
}

export function AirportPicker({
  open,
  title,
  onClose,
  onPick,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  onPick: (code: string, label: string) => void;
}) {
  const [places, setPlaces] = useState<Place[]>([]);
  const [q, setQ] = useState("");
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setQ("");
    loadPlaces().then(setPlaces);
    const t = setTimeout(() => input.current?.focus(), 250);
    return () => clearTimeout(t);
  }, [open]);

  const results = useMemo(() => searchPlaces(places, q), [places, q]);
  const shown = q ? results : recent();

  const pick = (p: Place) => {
    const next = [p, ...recent().filter((r) => r.code !== p.code)].slice(0, 6);
    localStorage.setItem(RECENT_KEY, JSON.stringify(next));
    onPick(p.code, shortLabel(p));
    onClose();
  };

  return (
    <Sheet open={open} onClose={onClose} title={title}>
      <label className="sticky top-0 z-10 mb-3 flex items-center gap-3 rounded-2xl bg-white/8 px-4 py-3 ring-1 ring-white/10 focus-within:ring-accent">
        <Search size={18} className="text-muted" />
        <input
          ref={input}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Ville, aéroport ou code (ex. Séoul, CDG)"
          className="w-full bg-transparent text-base outline-none placeholder:text-faint"
          autoComplete="off"
          autoCorrect="off"
          spellCheck={false}
        />
      </label>
      {!q && shown.length > 0 && (
        <div className="mb-2 flex items-center gap-2 px-1 text-xs font-medium text-muted">
          <History size={14} /> Récents
        </div>
      )}
      {q && places.length > 0 && results.length === 0 && <p className="py-8 text-center text-sm text-muted">Aucun aéroport trouvé pour « {q} »</p>}
      <ul className="space-y-1">
        {shown.map((p, i) => (
          <motion.li key={p.code} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i * 0.02, 0.2) }}>
            <button onClick={() => pick(p)} className="flex w-full items-center gap-3 rounded-2xl px-3 py-3 text-left active:bg-white/8">
              <div className="grid size-11 shrink-0 place-items-center rounded-xl bg-white/6 text-[13px] font-bold tracking-wide text-white">
                {p.rank === 3 ? <MapPin size={18} className="text-accent-2" /> : p.code}
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate font-semibold">
                  {flag(p.country)} {p.rank === 3 ? p.name : p.city}
                </div>
                <div className="truncate text-sm text-muted">{p.rank === 3 ? `Tous les aéroports · ${p.code.replace(/\+/g, " + ")}` : p.name}</div>
              </div>
            </button>
          </motion.li>
        ))}
      </ul>
    </Sheet>
  );
}
