/** Filtres et tri des résultats (appliqués instantanément sur la liste reçue). */

import { useMemo } from "react";
import { motion } from "motion/react";
import { Leaf } from "lucide-react";
import type { Offer } from "../lib/api";
import { duration, euro } from "../lib/format";
import { AirlineLogo, Sheet } from "./ui";

export type Sort = "price" | "duration" | "depart" | "arrive" | "co2";
export type Slot = "night" | "morning" | "afternoon" | "evening";

export type Filters = {
  stops: "any" | "0" | "1";
  alliance: "" | "STAR" | "ONEWORLD" | "SKYTEAM";
  airlines: string[]; // codes cochés (vide = toutes)
  depSlots: Slot[];
  arrSlots: Slot[];
  maxDuration: number | null;
  maxPrice: number | null;
  lessCO2: boolean;
};

export const emptyFilters: Filters = { stops: "any", alliance: "", airlines: [], depSlots: [], arrSlots: [], maxDuration: null, maxPrice: null, lessCO2: false };

const SLOTS: [Slot, string, number, number][] = [
  ["night", "Nuit 0-5 h", 0, 5],
  ["morning", "Matin 5-12 h", 5, 12],
  ["afternoon", "Après-midi 12-18 h", 12, 18],
  ["evening", "Soir 18-24 h", 18, 24],
];

// Membres des alliances (codes IATA)
export const ALLIANCES: Record<string, [string, string[]]> = {
  STAR: ["Star Alliance", ["A3", "AC", "AI", "AV", "BR", "CA", "CM", "ET", "LH", "VL", "EN", "4Y", "LO", "LX", "MS", "NH", "NZ", "OS", "OU", "OZ", "SA", "SN", "SQ", "TG", "TK", "TP", "UA", "ZH"]],
  ONEWORLD: ["Oneworld", ["AA", "AS", "AT", "AY", "BA", "CX", "FJ", "IB", "JL", "MH", "QF", "QR", "RJ", "UL", "WY"]],
  SKYTEAM: ["SkyTeam", ["AF", "AM", "AR", "CI", "DL", "GA", "KE", "KL", "KQ", "ME", "MF", "MU", "RO", "SK", "SV", "UX", "VN", "VS"]],
};

const hour = (s: string) => Number(s.slice(11, 13)) + Number(s.slice(14, 16)) / 60;
const inSlots = (h: number, slots: Slot[]) => !slots.length || slots.some((s) => SLOTS.some(([k, , a, b]) => k === s && h >= a && h < b));

export function applyFilters(offers: Offer[], f: Filters, sort: Sort): Offer[] {
  const out = offers.filter(
    (o) =>
      (f.stops === "any" || o.stops <= Number(f.stops)) &&
      (!f.alliance || ALLIANCES[f.alliance][1].includes(o.airline_code)) &&
      (!f.airlines.length || f.airlines.includes(o.airline_code)) &&
      inSlots(hour(o.depart), f.depSlots) &&
      inSlots(hour(o.arrive), f.arrSlots) &&
      (!f.maxDuration || o.duration_min <= f.maxDuration) &&
      (!f.maxPrice || o.total <= f.maxPrice) &&
      (!f.lessCO2 || (o.co2_diff_pct ?? 0) < 0),
  );
  const key: Record<Sort, (o: Offer) => number | string> = {
    price: (o) => o.total,
    duration: (o) => o.duration_min,
    depart: (o) => o.depart,
    arrive: (o) => o.arrive,
    co2: (o) => o.co2_kg ?? 1e9,
  };
  return out.sort((a, b) => (key[sort](a) < key[sort](b) ? -1 : key[sort](a) > key[sort](b) ? 1 : a.total - b.total));
}

export const activeCount = (f: Filters) =>
  [f.stops !== "any", !!f.alliance, f.airlines.length > 0, f.depSlots.length > 0, f.arrSlots.length > 0, !!f.maxDuration, !!f.maxPrice, f.lessCO2].filter(Boolean).length;

function Chip({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <motion.button
      whileTap={{ scale: 0.95 }}
      onClick={onClick}
      className={`rounded-full px-3 py-1.5 text-sm font-medium ring-1 ${on ? "bg-accent/20 text-white ring-accent" : "bg-white/5 text-white/75 ring-white/10"}`}
    >
      {children}
    </motion.button>
  );
}

function Title({ children }: { children: React.ReactNode }) {
  return <div className="mt-5 mb-2 text-sm font-semibold">{children}</div>;
}

export function FilterSheet({
  open,
  onClose,
  offers,
  filters,
  onChange,
}: {
  open: boolean;
  onClose: () => void;
  offers: Offer[];
  filters: Filters;
  onChange: (f: Filters) => void;
}) {
  const f = filters;
  const set = (patch: Partial<Filters>) => onChange({ ...f, ...patch });
  const toggle = <T,>(list: T[], v: T) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

  const airlines = useMemo(() => {
    const m = new Map<string, { name: string; min: number }>();
    for (const o of offers) {
      const cur = m.get(o.airline_code);
      if (!cur || o.total < cur.min) m.set(o.airline_code, { name: o.airlines[0], min: o.total });
    }
    return [...m.entries()].sort((a, b) => a[1].min - b[1].min);
  }, [offers]);
  const durMin = Math.min(...offers.map((o) => o.duration_min), 0) || 60;
  const durMax = Math.max(...offers.map((o) => o.duration_min), 60);
  const priceMin = Math.min(...offers.map((o) => o.total), 0);
  const priceMax = Math.max(...offers.map((o) => o.total), 100);
  const shown = applyFilters(offers, f, "price").length;

  return (
    <Sheet open={open} onClose={onClose} title="Filtres">
      <Title>Escales</Title>
      <div className="flex flex-wrap gap-2">
        {(
          [
            ["any", "Toutes"],
            ["0", "Direct uniquement"],
            ["1", "1 escale max"],
          ] as const
        ).map(([v, l]) => (
          <Chip key={v} on={f.stops === v} onClick={() => set({ stops: v })}>
            {l}
          </Chip>
        ))}
      </div>

      <Title>Heure de départ (aller)</Title>
      <div className="flex flex-wrap gap-2">
        {SLOTS.map(([k, l]) => (
          <Chip key={k} on={f.depSlots.includes(k)} onClick={() => set({ depSlots: toggle(f.depSlots, k) })}>
            {l}
          </Chip>
        ))}
      </div>
      <Title>Heure d'arrivée (aller)</Title>
      <div className="flex flex-wrap gap-2">
        {SLOTS.map(([k, l]) => (
          <Chip key={k} on={f.arrSlots.includes(k)} onClick={() => set({ arrSlots: toggle(f.arrSlots, k) })}>
            {l}
          </Chip>
        ))}
      </div>

      <Title>
        Durée maximale : <span className="text-accent-2">{f.maxDuration ? duration(f.maxDuration) : "toutes"}</span>
      </Title>
      <input
        type="range"
        min={durMin}
        max={durMax}
        step={15}
        value={f.maxDuration ?? durMax}
        onChange={(e) => set({ maxDuration: Number(e.target.value) >= durMax ? null : Number(e.target.value) })}
        className="w-full accent-violet-500"
        aria-label="Durée maximale"
      />

      <Title>
        Prix maximal : <span className="text-accent-2">{f.maxPrice ? euro(f.maxPrice) : "tous"}</span>
      </Title>
      <input
        type="range"
        min={priceMin}
        max={priceMax}
        step={10}
        value={f.maxPrice ?? priceMax}
        onChange={(e) => set({ maxPrice: Number(e.target.value) >= priceMax ? null : Number(e.target.value) })}
        className="w-full accent-violet-500"
        aria-label="Prix maximal"
      />

      <Title>Émissions</Title>
      <Chip on={f.lessCO2} onClick={() => set({ lessCO2: !f.lessCO2 })}>
        <span className="flex items-center gap-1.5">
          <Leaf size={14} /> Moins d'émissions que la moyenne
        </span>
      </Chip>

      <Title>Alliances</Title>
      <div className="flex flex-wrap gap-2">
        <Chip on={!f.alliance} onClick={() => set({ alliance: "" })}>
          Toutes
        </Chip>
        {Object.entries(ALLIANCES).map(([k, [label]]) => (
          <Chip key={k} on={f.alliance === k} onClick={() => set({ alliance: f.alliance === k ? "" : (k as Filters["alliance"]) })}>
            {label}
          </Chip>
        ))}
      </div>

      <Title>Compagnies</Title>
      <div className="space-y-1">
        {airlines.map(([code, { name, min }]) => {
          const on = f.airlines.includes(code);
          return (
            <button key={code} onClick={() => set({ airlines: toggle(f.airlines, code) })} className="flex w-full items-center gap-3 rounded-2xl px-2 py-2 active:bg-white/6">
              <span className={`grid size-5 place-items-center rounded-md ring-1 ${on ? "bg-accent ring-accent" : "ring-white/30"}`}>{on && "✓"}</span>
              <AirlineLogo code={code} name={name} size={26} />
              <span className="flex-1 truncate text-left text-sm">{name}</span>
              <span className="text-sm text-muted tabular">dès {euro(min)}</span>
            </button>
          );
        })}
      </div>

      <div className="sticky bottom-0 -mx-5 -mb-6 mt-5 flex gap-2 bg-[#11131c] px-5 pt-3 pb-6">
        <button onClick={() => onChange(emptyFilters)} className="rounded-2xl bg-white/8 px-4 py-3.5 text-sm font-semibold">
          Effacer
        </button>
        <motion.button whileTap={{ scale: 0.97 }} onClick={onClose} className="bg-gradient-accent flex-1 rounded-2xl py-3.5 font-bold">
          Voir {shown} vol{shown > 1 ? "s" : ""}
        </motion.button>
      </div>
    </Sheet>
  );
}
