import { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "motion/react";
import { Globe2, History, MapPin, Search } from "lucide-react";
import { api, type GPlace } from "../lib/api";
import { countryIso, loadPlaces, searchPlaces, shortLabel, type Place } from "../lib/airports";
import { flag } from "../lib/format";
import { Sheet } from "./ui";

const RECENT_KEY = "gt-recent-places-v2";

/** Une ligne de la liste : aéroport, ville (identifiant Google) ou pays / région. */
type Row = {
  key: string;
  code: string;
  label: string; // libellé court gardé dans la recherche (« Tokyo », « Japon », « Tokyo HND »)
  detail: string; // texte secondaire gardé dans la recherche
  title: string;
  sub: string;
  icon: "airport" | "city" | "region";
  iso: string;
  child?: boolean; // aéroport listé sous sa ville
};

function recent(): Row[] {
  try {
    return JSON.parse(localStorage.getItem(RECENT_KEY) || "[]");
  } catch {
    return [];
  }
}

const countryOf = (name: string) => (name.includes(", ") ? name.split(", ").pop()! : name);

// Résultats locaux (liste d'aéroports embarquée) : instantanés et disponibles hors ligne
function localRow(p: Place): Row {
  const multi = p.rank === 3;
  return {
    key: `l-${p.code}`,
    code: p.code,
    label: shortLabel(p),
    detail: multi ? p.code.replace(/\+/g, " + ") : p.name,
    title: multi ? p.name : p.city,
    sub: multi ? `Tous les aéroports · ${p.code.replace(/\+/g, " + ")}` : p.name,
    icon: multi ? "city" : "airport",
    iso: p.country,
  };
}

// Propositions de Google Flights : pays, régions, villes (et leurs aéroports), aéroports
function googleRows(list: GPlace[], local: Place[]): Row[] {
  const isoOfAirport = (code: string) => local.find((p) => p.code === code)?.country || "";
  const rows: Row[] = [];
  for (const p of list) {
    if (p.kind === "region") {
      const detail = p.detail ? `${p.detail} · tous les aéroports` : "Tous les aéroports";
      rows.push({ key: `g-${p.code}`, code: p.code, label: p.name.split(", ")[0], detail, title: p.name, sub: detail, icon: "region", iso: countryIso(countryOf(p.name)) });
    } else if (p.kind === "city") {
      const iso = countryIso(countryOf(p.name)) || isoOfAirport(p.airports[0]?.code || "");
      const near = p.airports.map((a) => a.code).join(" · ");
      rows.push({
        key: `g-${p.code}`,
        code: p.code,
        label: p.city || p.name.split(", ")[0],
        detail: near ? `Aéroports : ${near}` : p.detail || "Aéroports proches",
        title: p.name,
        sub: p.airports.length ? p.airports.map((a) => `${a.code} ${a.distance}`).join(" · ") : p.detail || "Aéroports proches",
        icon: "city",
        iso,
      });
      for (const a of p.airports)
        rows.push({
          key: `g-${p.code}-${a.code}`,
          code: a.code,
          label: `${p.city || p.name.split(", ")[0]} ${a.code}`,
          detail: a.name,
          title: a.name,
          sub: `à ${a.distance} de ${p.city || p.name}`,
          icon: "airport",
          iso: isoOfAirport(a.code) || iso,
          child: true,
        });
    } else {
      rows.push({ key: `g-${p.code}`, code: p.code, label: `${p.city || p.name} ${p.code}`, detail: p.name, title: p.name, sub: p.detail || p.city || "", icon: "airport", iso: isoOfAirport(p.code) });
    }
  }
  return rows;
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
  onPick: (code: string, label: string, detail?: string) => void;
}) {
  const [places, setPlaces] = useState<Place[]>([]);
  const [q, setQ] = useState("");
  const [google, setGoogle] = useState<{ q: string; list: GPlace[] } | null>(null);
  const [loading, setLoading] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setQ("");
    setGoogle(null);
    loadPlaces().then(setPlaces);
    const t = setTimeout(() => input.current?.focus(), 250);
    return () => clearTimeout(t);
  }, [open]);

  // Autocomplétion Google (après 200 ms sans frappe)
  useEffect(() => {
    const query = q.trim();
    if (!query) {
      setLoading(false);
      return;
    }
    const ctl = new AbortController();
    setLoading(true);
    const t = setTimeout(() => {
      api
        .places(query, ctl.signal)
        .then((r) => setGoogle({ q: query, list: r.places }))
        .catch(() => {})
        .finally(() => !ctl.signal.aborted && setLoading(false));
    }, 200);
    return () => {
      clearTimeout(t);
      ctl.abort();
    };
  }, [q]);

  const rows = useMemo(() => {
    const query = q.trim();
    if (!query) return recent();
    const local = searchPlaces(places, query);
    const fromGoogle = google && google.list.length ? googleRows(google.list, places) : null;
    if (!fromGoogle) return local.map(localRow);
    // Raccourcis « tous les aéroports » (ex. Paris CDG + Orly) en tête, puis les propositions de Google
    const shortcuts = local.filter((p) => p.rank === 3).slice(0, 2).map(localRow);
    const seen = new Set(shortcuts.map((r) => r.code));
    return [...shortcuts, ...fromGoogle.filter((r) => !seen.has(r.code))];
  }, [q, places, google]);

  const pick = (r: Row) => {
    const next = [{ ...r, child: false, key: `r-${r.code}` }, ...recent().filter((x) => x.code !== r.code)].slice(0, 6);
    localStorage.setItem(RECENT_KEY, JSON.stringify(next));
    onPick(r.code, r.label, r.detail);
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
          placeholder="Pays, ville, aéroport (ex. Japon, Kyoto, CDG)"
          className="w-full bg-transparent text-base outline-none placeholder:text-faint"
          autoComplete="off"
          autoCorrect="off"
          spellCheck={false}
        />
        {loading && <motion.span animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: "linear" }} className="size-4 shrink-0 rounded-full border-2 border-white/25 border-t-white" />}
      </label>
      {!q && rows.length > 0 && (
        <div className="mb-2 flex items-center gap-2 px-1 text-xs font-medium text-muted">
          <History size={14} /> Récents
        </div>
      )}
      {q && !loading && rows.length === 0 && <p className="py-8 text-center text-sm text-muted">Aucun lieu trouvé pour « {q} »</p>}
      <ul className="space-y-0.5">
        {rows.map((r, i) => (
          <motion.li key={r.key} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i * 0.015, 0.15) }}>
            <button onClick={() => pick(r)} className={`flex w-full items-center gap-3 rounded-2xl py-2.5 pr-3 text-left active:bg-white/8 ${r.child ? "pl-9" : "pl-3"}`}>
              <div className={`grid shrink-0 place-items-center rounded-xl bg-white/6 font-bold tracking-wide text-white ${r.child ? "size-9 text-[11px]" : "size-11 text-[13px]"}`}>
                {r.icon === "region" ? <Globe2 size={19} className="text-accent-2" /> : r.icon === "city" ? <MapPin size={18} className="text-accent-2" /> : r.code}
              </div>
              <div className="min-w-0 flex-1">
                <div className={`truncate font-semibold ${r.child ? "text-sm" : ""}`}>
                  {!r.child && r.iso ? `${flag(r.iso)} ` : ""}
                  {r.title}
                </div>
                <div className="truncate text-sm text-muted">{r.sub}</div>
              </div>
            </button>
          </motion.li>
        ))}
      </ul>
      {q && google && <p className="mt-3 px-1 text-[11px] text-faint">Propositions de Google Flights : un pays ou une ville cherche dans tous ses aéroports.</p>}
    </Sheet>
  );
}
