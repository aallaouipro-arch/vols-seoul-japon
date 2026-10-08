import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { BellRing, ExternalLink, RefreshCw, Search, Target, Trash2 } from "lucide-react";
import { LineChart, Sparkline } from "../components/charts";
import { PushCard } from "../components/PushCard";
import { AirlineLogo, Badge, LevelBadge, LinkButton, SectionTitle, Sheet, Skeleton, useToast } from "../components/ui";
import { api, type Watch } from "../lib/api";
import { deviceId } from "../lib/device";
import { ago, dayMonth, euro } from "../lib/format";
import { go, openSearch, useRoute } from "../lib/nav";

function useHistory(id: string | null) {
  const [hist, setHist] = useState<[string, number][] | null>(null);
  useEffect(() => {
    setHist(null);
    if (id) api.history(id).then((h) => setHist(h.history)).catch(() => setHist([]));
  }, [id]);
  return hist;
}

function WatchCard({ w, index, onOpen }: { w: Watch; index: number; onOpen: () => void }) {
  const hist = useHistory(w.id);
  const first = hist?.[0]?.[1];
  const delta = first && w.last_price ? w.last_price - first : 0;
  return (
    <motion.button
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: -40 }}
      transition={{ delay: index * 0.04 }}
      whileTap={{ scale: 0.985 }}
      onClick={onOpen}
      className="glass block w-full rounded-3xl p-4 text-left"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-[17px] font-bold">
            {w.origin_label} → {w.destination_label}
          </div>
          <div className="text-xs text-muted">
            {dayMonth(w.depart)}
            {w.ret ? ` → ${dayMonth(w.ret)}` : " · aller simple"}
            {w.target ? ` · cible ${euro(w.target)}` : ""}
          </div>
        </div>
        <div className="text-right">
          <div className="text-xl font-extrabold tabular">{euro(w.last_price)}</div>
          {delta !== 0 && (
            <div className={`text-xs font-semibold tabular ${delta < 0 ? "text-good" : "text-bad"}`}>
              {delta < 0 ? "▼" : "▲"} {euro(Math.abs(delta))}
            </div>
          )}
        </div>
      </div>
      <div className="mt-3 flex items-end justify-between">
        <div className="flex flex-wrap items-center gap-1.5">
          {w.level && <LevelBadge level={w.level} />}
          <span className="text-[11px] text-faint">vérifié {ago(w.last_check)}</span>
        </div>
        <Sparkline points={(hist || []).map(([, v]) => v)} color={delta <= 0 ? "#34d399" : "#fb7185"} />
      </div>
    </motion.button>
  );
}

function WatchSheet({ w, onClose, onChanged }: { w: Watch | null; onClose: () => void; onChanged: () => void }) {
  const toast = useToast();
  const hist = useHistory(w?.id ?? null);
  const [busy, setBusy] = useState<"check" | "delete" | null>(null);

  const check = async () => {
    if (!w) return;
    setBusy("check");
    try {
      const updated = await api.checkWatch(w.id, deviceId());
      toast(`Prix actuel : ${euro(updated.last_price)}`, "good");
      onChanged();
    } catch (e) {
      toast((e as Error).message, "bad");
    } finally {
      setBusy(null);
    }
  };

  const remove = async () => {
    if (!w) return;
    setBusy("delete");
    try {
      await api.deleteWatch(w.id, deviceId());
      toast("Alerte supprimée");
      onChanged();
      onClose();
    } catch (e) {
      toast((e as Error).message, "bad");
    } finally {
      setBusy(null);
    }
  };

  return (
    <Sheet open={!!w} onClose={onClose} title={w && `${w.origin_label} → ${w.destination_label}`}>
      {w && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <AirlineLogo code={w.airline_code} name={w.airline} size={44} />
            <div className="min-w-0 flex-1">
              <div className="text-3xl font-extrabold tabular">{euro(w.last_price)}</div>
              <div className="truncate text-sm text-muted">{w.airline || "Meilleur prix actuel"}</div>
            </div>
            {w.level && <LevelBadge level={w.level} />}
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="rounded-2xl bg-white/5 p-3 ring-1 ring-white/8">
              <div className="text-[11px] text-muted">Plus bas</div>
              <div className="font-bold tabular">{euro(w.min_price)}</div>
            </div>
            <div className="rounded-2xl bg-white/5 p-3 ring-1 ring-white/8">
              <div className="text-[11px] text-muted">Habituel</div>
              <div className="text-sm font-bold tabular">{w.typical_low ? `${w.typical_low}–${w.typical_high}` : "—"}</div>
            </div>
            <div className="rounded-2xl bg-white/5 p-3 ring-1 ring-white/8">
              <div className="text-[11px] text-muted">Cible</div>
              <div className="font-bold tabular">{w.target ? euro(w.target) : "—"}</div>
            </div>
          </div>
          <div className="rounded-3xl bg-white/5 p-3 ring-1 ring-white/8">
            {hist === null ? <Skeleton className="h-40" /> : <LineChart series={[{ name: "Prix", color: "var(--color-accent-2)", points: hist }]} height={170} />}
          </div>
          <p className="text-xs text-muted">
            {dayMonth(w.depart)}
            {w.ret ? ` → ${dayMonth(w.ret)}` : " · aller simple"} · {w.stops === 0 ? "direct" : w.stops === 1 ? "1 escale max" : "toutes escales"}
            {w.bags_out || w.bags_ret ? ` · valises ${w.bags_out}${w.ret ? `/${w.bags_ret}` : ""}` : ""} · vérifié {ago(w.last_check)}
          </p>
          <div className="grid grid-cols-2 gap-2">
            <div className="col-span-2">
              <LinkButton href={w.booking_url || w.google_url || "#"} primary>
                Réserver · voir les offres
              </LinkButton>
            </div>
            <motion.button whileTap={{ scale: 0.97 }} onClick={check} disabled={!!busy} className="flex items-center justify-center gap-2 rounded-2xl bg-white/8 py-3 text-sm font-semibold ring-1 ring-white/10">
              <RefreshCw size={15} className={busy === "check" ? "animate-spin" : ""} /> Actualiser
            </motion.button>
            <motion.button
              whileTap={{ scale: 0.97 }}
              onClick={() =>
                openSearch({
                  origin: w.origin,
                  destination: w.destination,
                  originLabel: w.origin_label,
                  destinationLabel: w.destination_label,
                  depart: w.depart,
                  ret: w.ret,
                  stops: w.stops === 0 ? "0" : w.stops === 1 ? "1" : "any",
                  bagsOut: w.bags_out,
                  bagsRet: w.bags_ret,
                })
              }
              className="flex items-center justify-center gap-2 rounded-2xl bg-white/8 py-3 text-sm font-semibold ring-1 ring-white/10"
            >
              <Search size={15} /> Tous les vols
            </motion.button>
            {w.google_url && (
              <div className="col-span-2">
                <LinkButton href={w.google_url}>
                  <ExternalLink size={15} /> Ouvrir dans Google Flights
                </LinkButton>
              </div>
            )}
            <motion.button whileTap={{ scale: 0.97 }} onClick={remove} disabled={!!busy} className="col-span-2 flex items-center justify-center gap-2 rounded-2xl py-3 text-sm font-semibold text-bad">
              <Trash2 size={15} /> Supprimer l'alerte
            </motion.button>
          </div>
        </div>
      )}
    </Sheet>
  );
}

export default function AlertsScreen() {
  const route = useRoute();
  const [watches, setWatches] = useState<Watch[] | null>(null);
  const [error, setError] = useState("");
  const openId = route.startsWith("/alertes/") ? route.split("/")[2] : null;
  const open = watches?.find((w) => w.id === openId) || null;

  const load = useCallback(() => {
    api
      .watches(deviceId())
      .then((r) => setWatches(r.watches))
      .catch((e) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  return (
    <div>
      <header className="pt-safe px-1">
        <p className="text-sm font-medium text-muted">Suivi automatique toutes les heures</p>
        <h1 className="text-[32px] leading-tight font-extrabold tracking-tight">
          Mes <span className="text-gradient">alertes</span>
        </h1>
      </header>

      <div className="mt-5">
        <PushCard />
      </div>

      <SectionTitle action={watches && watches.length > 0 && <Badge tone="accent">{watches.length}</Badge>}>Vols suivis</SectionTitle>
      {error && <p className="text-sm text-bad">{error}</p>}
      {!watches && !error && (
        <div className="space-y-3">
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
        </div>
      )}
      {watches?.length === 0 && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="glass rounded-[28px] p-6 text-center">
          <div className="bg-gradient-accent mx-auto mb-4 grid size-14 place-items-center rounded-2xl">
            <BellRing size={24} />
          </div>
          <div className="font-semibold">Aucune alerte pour l'instant</div>
          <p className="mt-1 text-sm text-muted">Cherche un vol, ouvre-le et touche « M'alerter si le prix baisse ». Tu recevras une notification à chaque vraie baisse.</p>
          <motion.button whileTap={{ scale: 0.97 }} onClick={() => go("/recherche")} className="bg-gradient-accent mt-4 inline-flex items-center gap-2 rounded-2xl px-5 py-3 text-sm font-bold">
            <Search size={16} /> Chercher un vol
          </motion.button>
        </motion.div>
      )}
      <div className="space-y-3">
        <AnimatePresence>
          {watches?.map((w, i) => (
            <WatchCard key={w.id} w={w} index={i} onOpen={() => go(`/alertes/${w.id}`)} />
          ))}
        </AnimatePresence>
      </div>

      <div className="mt-6 flex items-start gap-3 rounded-3xl bg-white/4 p-4 text-xs leading-relaxed text-muted ring-1 ring-white/6">
        <Target size={16} className="mt-0.5 shrink-0 text-accent-2" />
        <p>
          Tu reçois une notification quand le prix baisse d'au moins 10 € (ou 3 %), quand il passe sous ta cible, ou quand Google Flights le juge « bas ». Jamais
          de notification pour une hausse.
        </p>
      </div>

      <WatchSheet w={open} onClose={() => go("/alertes")} onChanged={load} />
    </div>
  );
}
