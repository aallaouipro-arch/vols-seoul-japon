import { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "motion/react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { CalendarDays, ChevronRight, MapPin } from "lucide-react";
import { AirportPicker } from "../components/AirportPicker";
import { Badge, Skeleton, useToast } from "../components/ui";
import { api, type ExploreItem } from "../lib/api";
import { addDays, ago, daysBetween, duration, euro, flag, shortDate, todayIso } from "../lib/format";
import { openSearch } from "../lib/nav";

type Region = "all" | "europe" | "long";
type Preset = { id: string; label: string; depart: string; ret: string };

const nextFriday = (from: string) => {
  const d = new Date(`${from}T12:00:00`);
  d.setDate(d.getDate() + ((5 - d.getDay() + 7) % 7 || 7));
  return d.toISOString().slice(0, 10);
};

function presets(): Preset[] {
  const today = todayIso();
  const we = nextFriday(today);
  const we4 = nextFriday(addDays(today, 25));
  const w1 = addDays(nextFriday(addDays(today, 27)), 1);
  const w2 = addDays(nextFriday(addDays(today, 85)), 1);
  return [
    { id: "we", label: "Week-end prochain", depart: we, ret: addDays(we, 2) },
    { id: "we4", label: "Week-end dans 1 mois", depart: we4, ret: addDays(we4, 2) },
    { id: "w1", label: "1 semaine dans 1 mois", depart: w1, ret: addDays(w1, 7) },
    { id: "w2", label: "2 semaines dans 3 mois", depart: w2, ret: addDays(w2, 14) },
  ];
}

const isDeal = (i: ExploreItem) => i.level === "bas" || (i.discount ?? 0) >= 20;

function PriceMap({ items, origin, region }: { items: ExploreItem[]; origin: string; region: Region }) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);
  const data = useRef<ExploreItem[]>([]);
  const originRef = useRef(origin);
  originRef.current = origin;

  // Étiquettes de prix sans chevauchement : de la moins chère à la plus chère, une étiquette
  // seulement s'il reste de la place à l'écran ; sinon un point (prix au toucher).
  const draw = () => {
    const m = map.current;
    const lg = layer.current;
    if (!m || !lg) return;
    lg.clearLayers();
    const boxes: [number, number, number, number][] = [];
    const free = (x: number, y: number, w: number, h: number) => !boxes.some(([a, b, c, d]) => x < c && x + w > a && y < d && y + h > b);
    const goTo = (i: ExploreItem) => () => document.getElementById(`dest-${i.code}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    if (originRef.current === "CDG+ORY") {
      const p = m.latLngToContainerPoint([48.86, 2.35]);
      boxes.push([p.x - 26, p.y - 12, p.x + 26, p.y + 12]);
      L.marker([48.86, 2.35], { icon: L.divIcon({ className: "", html: '<div class="gt-pin gt-pin-origin">Paris</div>', iconSize: undefined }), interactive: false, zIndexOffset: 2000 }).addTo(lg);
    }
    const sorted = [...data.current].sort((a, b) => Number(isDeal(b)) - Number(isDeal(a)) || a.price - b.price);
    sorted.forEach((i, rank) => {
      const p = m.latLngToContainerPoint([i.lat, i.lon]);
      const w = `${i.price} €`.length * 7 + 18;
      if (free(p.x - w / 2, p.y - 12, w, 24)) {
        boxes.push([p.x - w / 2, p.y - 12, p.x + w / 2, p.y + 12]);
        L.marker([i.lat, i.lon], {
          icon: L.divIcon({ className: "", html: `<div class="gt-pin ${isDeal(i) ? "gt-pin-deal" : ""}">${i.price} €</div>`, iconSize: undefined }),
          title: `${i.city} : ${i.price} €`,
          zIndexOffset: 1000 - rank,
        })
          .on("click", goTo(i))
          .addTo(lg);
      } else {
        L.circleMarker([i.lat, i.lon], { radius: 4.5, color: "#0b0d14", weight: 2, fillColor: isDeal(i) ? "#34d399" : "#8b5cf6", fillOpacity: 0.95 })
          .bindTooltip(`${i.city} · ${i.price} €`, { direction: "top", offset: [0, -4] })
          .on("click", goTo(i))
          .addTo(lg);
      }
    });
  };

  useEffect(() => {
    if (!el.current || map.current) return;
    map.current = L.map(el.current, {
      zoomControl: false,
      attributionControl: true,
      worldCopyJump: true,
      minZoom: 2,
      maxBounds: [[-75, -200], [85, 200]],
    }).setView([45, 10], 3);
    // Tuiles OpenStreetMap (sans clé), assombries en CSS pour le thème sombre
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 10,
      className: "gt-tiles-dark",
    }).addTo(map.current);
    L.control.zoom({ position: "bottomright" }).addTo(map.current);
    layer.current = L.layerGroup().addTo(map.current);
    map.current.on("zoomend", draw);
    return () => {
      map.current?.remove();
      map.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const m = map.current;
    if (!m) return;
    data.current = items;
    // Cadrage : Europe & Méditerranée par défaut (la majorité des destinations), long-courrier si filtré
    const focus = region === "long" ? items : items.filter((i) => i.region === "europe");
    const pts = (focus.length ? focus : items).map((i) => [i.lat, i.lon] as [number, number]);
    if (origin === "CDG+ORY" && region !== "long") pts.push([48.86, 2.35]);
    m.stop();
    if (pts.length) m.fitBounds(L.latLngBounds(pts), { padding: [24, 24], maxZoom: 5, animate: false });
    draw();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, origin, region]);

  return <div ref={el} className="h-[340px] w-full overflow-hidden rounded-[24px]" />;
}

export default function ExploreScreen() {
  const toast = useToast();
  const ps = useMemo(presets, []);
  const [origin, setOrigin] = useState({ code: "CDG+ORY", label: "Paris" });
  const [preset, setPreset] = useState<string>("w1");
  const [custom, setCustom] = useState({ depart: ps[2].depart, ret: ps[2].ret });
  const [region, setRegion] = useState<Region>("all");
  const [budget, setBudget] = useState<number | null>(null);
  const [items, setItems] = useState<ExploreItem[] | null>(null);
  const [meta, setMeta] = useState<{ fetched_at?: string; stale?: boolean }>({});
  const [loading, setLoading] = useState(false);
  const [picker, setPicker] = useState(false);

  const dates = preset === "custom" ? custom : ps.find((p) => p.id === preset)!;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setItems(null);
    api
      .explore({ origin: origin.code, depart: dates.depart, ret: dates.ret, stops: "1" })
      .then((r) => {
        if (cancelled) return;
        setItems(r.items);
        setMeta({ fetched_at: r.fetched_at, stale: r.stale });
      })
      .catch((e) => !cancelled && toast(e.message, "bad"))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [origin.code, dates.depart, dates.ret, toast]);

  const maxPrice = Math.max(100, ...(items || []).map((i) => i.price));
  const shown = (items || []).filter((i) => (region === "all" || i.region === region) && (!budget || i.price <= budget));

  return (
    <div>
      <header className="pt-safe px-1">
        <p className="text-sm font-medium text-muted">Explorer</p>
        <h1 className="text-[30px] leading-tight font-extrabold tracking-tight">
          Où partir depuis{" "}
          <button onClick={() => setPicker(true)} className="text-gradient underline decoration-white/20 decoration-2 underline-offset-4">
            {origin.label}
          </button>{" "}
          ?
        </h1>
      </header>

      <div className="no-scrollbar -mx-4 mt-4 flex gap-2 overflow-x-auto px-4">
        {ps.map((p) => (
          <motion.button
            key={p.id}
            whileTap={{ scale: 0.95 }}
            onClick={() => setPreset(p.id)}
            className={`shrink-0 rounded-2xl px-3.5 py-2 text-left ring-1 ${preset === p.id ? "bg-accent/18 ring-accent" : "bg-white/5 ring-white/10"}`}
          >
            <div className="text-sm font-semibold whitespace-nowrap">{p.label}</div>
            <div className="text-[11px] whitespace-nowrap text-muted">
              {shortDate(p.depart)} → {shortDate(p.ret)}
            </div>
          </motion.button>
        ))}
        <motion.button
          whileTap={{ scale: 0.95 }}
          onClick={() => setPreset("custom")}
          className={`flex shrink-0 items-center gap-1.5 rounded-2xl px-3.5 py-2 text-sm font-semibold ring-1 ${preset === "custom" ? "bg-accent/18 ring-accent" : "bg-white/5 ring-white/10"}`}
        >
          <CalendarDays size={15} /> Dates précises
        </motion.button>
      </div>

      {preset === "custom" && (
        <div className="mt-3 grid grid-cols-2 gap-2">
          {(["depart", "ret"] as const).map((k) => (
            <label key={k} className="relative rounded-2xl bg-white/5 px-4 py-2.5 ring-1 ring-white/8">
              <span className="text-[11px] text-muted">{k === "depart" ? "Aller" : "Retour"}</span>
              <span className="block text-[15px] font-semibold">{shortDate(custom[k])}</span>
              <input
                type="date"
                value={custom[k]}
                min={k === "ret" ? custom.depart : todayIso()}
                onChange={(e) => e.target.value && setCustom((c) => ({ ...c, [k]: e.target.value, ...(k === "depart" && e.target.value >= c.ret ? { ret: addDays(e.target.value, 7) } : {}) }))}
                className="absolute inset-0 opacity-0"
                aria-label={k === "depart" ? "Date aller" : "Date retour"}
              />
            </label>
          ))}
        </div>
      )}

      <div className="mt-3 flex rounded-2xl bg-white/6 p-1 ring-1 ring-white/8">
        {(
          [
            ["all", "Tout"],
            ["europe", "Europe & Méditerranée"],
            ["long", "Long-courrier"],
          ] as const
        ).map(([v, l]) => (
          <button key={v} onClick={() => setRegion(v)} className="relative flex-1 rounded-xl px-2 py-2 text-[13px] font-semibold">
            {region === v && <motion.span layoutId="explore-region" className="absolute inset-0 rounded-xl bg-white/12 ring-1 ring-white/15" />}
            <span className={`relative ${region === v ? "text-white" : "text-muted"}`}>{l}</span>
          </button>
        ))}
      </div>

      <div className="mt-4 px-1">
        <div className="flex justify-between text-sm">
          <span className="font-semibold">Budget max</span>
          <span className="font-semibold text-accent-2 tabular">{budget ? euro(budget) : "illimité"}</span>
        </div>
        <input
          type="range"
          min={50}
          max={maxPrice}
          step={10}
          value={budget ?? maxPrice}
          onChange={(e) => setBudget(Number(e.target.value) >= maxPrice ? null : Number(e.target.value))}
          className="w-full accent-violet-500"
          aria-label="Budget maximum"
        />
      </div>

      <div className="glass mt-3 overflow-hidden rounded-[26px] p-1">
        {loading ? (
          <div className="relative">
            <Skeleton className="h-[320px] !rounded-[24px]" />
            <div className="absolute inset-0 grid place-items-center text-center text-sm text-muted">
              <div>
                <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1.2, ease: "linear" }} className="mx-auto mb-3 size-8 rounded-full border-2 border-white/20 border-t-accent-2" />
                Recherche des prix vers 86 destinations…
                <br />
                <span className="text-xs text-faint">~10 s la première fois, instantané ensuite</span>
              </div>
            </div>
          </div>
        ) : (
          <PriceMap items={shown} origin={origin.code} region={region} />
        )}
      </div>

      <p className="mt-2 px-2 text-[11px] text-faint">Pince ou dézoome la carte pour voir le long-courrier · touche un point pour son prix.</p>

      <div className="mt-5 mb-3 flex items-end justify-between px-1">
        <h2 className="text-[15px] font-semibold">
          {shown.length} destination{shown.length > 1 ? "s" : ""} · {daysBetween(dates.depart, dates.ret)} j
        </h2>
        {meta.fetched_at && <span className="text-xs text-muted">{meta.stale ? "données anciennes · " : ""}prix {ago(meta.fetched_at)}</span>}
      </div>

      {loading && (
        <div className="space-y-2.5">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-16" />
          ))}
        </div>
      )}
      <div className="space-y-2.5">
        {shown.map((i, k) => (
          <motion.button
            key={i.code}
            id={`dest-${i.code}`}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: Math.min(k * 0.02, 0.4) }}
            whileTap={{ scale: 0.985 }}
            onClick={() =>
              openSearch({
                origin: origin.code,
                originLabel: origin.label,
                destination: i.code,
                destinationLabel: i.city,
                depart: dates.depart,
                ret: dates.ret,
                stops: "1",
                bagsOut: 0,
                bagsRet: 0,
              })
            }
            className="glass flex w-full items-center gap-3 rounded-3xl p-3.5 text-left"
          >
            <div className="grid size-11 shrink-0 place-items-center rounded-2xl bg-white/6 text-xl">{flag(i.country)}</div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="truncate font-semibold">{i.city}</span>
                {isDeal(i) && <Badge tone="good">Bon plan</Badge>}
              </div>
              <div className="truncate text-xs text-muted">
                {i.airline} · {i.stops === 0 ? "direct" : `${i.stops} escale`} · {duration(i.duration_min)}
              </div>
            </div>
            <div className="text-right">
              <div className="font-bold tabular">{euro(i.price)}</div>
              {i.discount !== null && i.discount > 0 && <div className="text-[11px] font-semibold text-good tabular">-{i.discount} %</div>}
            </div>
            <ChevronRight size={16} className="shrink-0 text-faint" />
          </motion.button>
        ))}
      </div>
      {!loading && items && shown.length === 0 && (
        <div className="glass rounded-3xl p-6 text-center text-sm text-muted">
          <MapPin className="mx-auto mb-2" size={20} /> Aucune destination dans ce budget.
        </div>
      )}
      <p className="mt-4 px-1 text-[11px] leading-relaxed text-faint">
        Prix aller-retour pour 1 adulte, hors valises, 1 escale max, relevés sur Google Flights (mis en cache 6 h). Touche une destination pour voir tous les vols.
      </p>

      <AirportPicker open={picker} title="Ville de départ" onClose={() => setPicker(false)} onPick={(code, label) => setOrigin({ code, label })} />
    </div>
  );
}
