import { motion } from "motion/react";
import { Minus, Plus } from "lucide-react";
import type { Cabin, Pax } from "../lib/api";
import { Sheet } from "./ui";

export const CABINS: [Cabin, string][] = [
  ["economy", "Économique"],
  ["premium-economy", "Premium éco"],
  ["business", "Affaires"],
  ["first", "Première"],
];

export const defaultPax: Pax = { adults: 1, children: 0, infantsSeat: 0, infantsLap: 0 };

export function paxLabel(pax: Pax = defaultPax, cabin: Cabin = "economy") {
  const n = pax.adults + pax.children + pax.infantsSeat + pax.infantsLap;
  const who = n === 1 ? "1 passager" : `${n} passagers`;
  return `${who} · ${CABINS.find(([c]) => c === cabin)?.[1] || "Économique"}`;
}

function Row({ label, hint, value, min, max, onChange }: { label: string; hint: string; value: number; min: number; max: number; onChange: (v: number) => void }) {
  return (
    <div className="flex items-center justify-between py-3">
      <div>
        <div className="font-semibold">{label}</div>
        <div className="text-xs text-muted">{hint}</div>
      </div>
      <div className="flex items-center gap-3">
        <button onClick={() => onChange(Math.max(min, value - 1))} disabled={value <= min} className="grid size-9 place-items-center rounded-xl bg-white/8 disabled:opacity-30" aria-label={`Moins : ${label}`}>
          <Minus size={16} />
        </button>
        <span className="w-5 text-center text-lg font-bold tabular">{value}</span>
        <button onClick={() => onChange(Math.min(max, value + 1))} disabled={value >= max} className="grid size-9 place-items-center rounded-xl bg-white/8 disabled:opacity-30" aria-label={`Plus : ${label}`}>
          <Plus size={16} />
        </button>
      </div>
    </div>
  );
}

export function PaxCabinSheet({
  open,
  onClose,
  pax,
  cabin,
  onChange,
}: {
  open: boolean;
  onClose: () => void;
  pax: Pax;
  cabin: Cabin;
  onChange: (pax: Pax, cabin: Cabin) => void;
}) {
  const total = pax.adults + pax.children + pax.infantsSeat + pax.infantsLap;
  const set = (patch: Partial<Pax>) => {
    const next = { ...pax, ...patch };
    if (next.adults + next.children + next.infantsSeat + next.infantsLap > 9) return;
    if (next.infantsLap > next.adults) next.infantsLap = next.adults;
    onChange(next, cabin);
  };
  return (
    <Sheet open={open} onClose={onClose} title="Passagers et classe">
      <div className="divide-y divide-white/8">
        <Row label="Adultes" hint="12 ans et plus" value={pax.adults} min={1} max={9} onChange={(v) => set({ adults: v })} />
        <Row label="Enfants" hint="2 à 11 ans" value={pax.children} min={0} max={8} onChange={(v) => set({ children: v })} />
        <Row label="Bébés avec siège" hint="Moins de 2 ans" value={pax.infantsSeat} min={0} max={4} onChange={(v) => set({ infantsSeat: v })} />
        <Row label="Bébés sur les genoux" hint="1 par adulte maximum" value={pax.infantsLap} min={0} max={Math.min(4, pax.adults)} onChange={(v) => set({ infantsLap: v })} />
      </div>
      <div className="mt-4 mb-2 text-sm font-semibold">Classe</div>
      <div className="grid grid-cols-2 gap-2">
        {CABINS.map(([c, label]) => (
          <motion.button
            key={c}
            whileTap={{ scale: 0.97 }}
            onClick={() => onChange(pax, c)}
            className={`rounded-2xl px-3 py-3 text-sm font-semibold ring-1 ${cabin === c ? "bg-accent/18 text-white ring-accent" : "bg-white/5 text-white/80 ring-white/10"}`}
          >
            {label}
          </motion.button>
        ))}
      </div>
      <p className="mt-3 text-xs text-muted">
        {total} passager{total > 1 ? "s" : ""} au total (9 maximum). Les prix affichés sont pour tout le groupe ; les valises sont comptées pour les adultes et
        les enfants.
      </p>
      <motion.button whileTap={{ scale: 0.97 }} onClick={onClose} className="bg-gradient-accent mt-4 w-full rounded-2xl py-3.5 font-bold">
        Valider
      </motion.button>
    </Sheet>
  );
}
