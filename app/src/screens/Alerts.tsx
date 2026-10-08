import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { BellRing, ExternalLink, Luggage, RefreshCw, Search, Target, Trash2, Users } from "lucide-react";
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

const routeLabel = (w: Watch) => `${w.origin_label} ${w.ret ? "⇄" : "→"} ${w.destination_label}`;

/** "21 juil. → 19 août" : meilleures dates trouvées (dates flexibles) ou dates de l'alerte. */
const datesLabel = (w: Watch) => {
  const d = w.best_depart || w.depart;
  const r = w.best_ret ?? w.ret;
  return `${dayMonth(d)}${r ? ` → ${dayMonth(r)}` : " · aller simple"}`;
};

const flexLabel = (w: Watch) => {
  const n = (w.depart_options?.length || 1) * (w.ret_options?.length || 1);
  return n > 1 ? `${n} combinaisons de dates testées` : null;
};

const bagsLabel = (w: Watch) => (w.bags_out || w.bags_ret ? `${w.bags_out} valise${w.bags_out > 1 ? "s" : ""} aller · ${w.bags_ret} retour` : null);

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
          <div className="truncate text-[17px] font-bold">{routeLabel(w)}</div>
          <div className="text-xs text-muted">
            {w.shared ? "Meilleur : " : ""}
            {datesLabel(w)}
            {w.target ? ` · cible ${euro(w.target)}` : ""}
          </div>
          {bagsLabel(w) && (
            <div className="mt-0.5 flex items-center gap-1 text-[11px] text-faint">
              <Luggage size={11} /> {bagsLabel(w)} · valises comprises
            </div>
          )}
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
          {w.shared && (
            <Badge tone="accent">
              <Users size={11} /> Partagé
            </Badge>
          )}
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
    <Sheet open={!!w} onClose={onClose} title={w && routeLabel(w)}>
      {w && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <AirlineLogo code={w.airline_code} name={w.airline} size={44} />
            <div className="min-w-0 flex-1">
              <div className="text-3xl font-extrabold tabular">{euro(w.last_price)}</div>
              <div className="text-sm leading-snug text-muted">
                {w.bag_fee ? `billet ${euro(w.fare)} + valises ≈ ${euro(w.bag_fee)}` : w.airline || "Meilleur prix actuel"}
              </div>
            </div>
            {w.level && <LevelBadge level={w.level} />}
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="rounded-2xl bg-white/5 p-3 ring-1 ring-white/8">
              <div className="text-[11px] text-muted">Plus bas</div>
              <div className="font-bold tabular">{euro(w.min_price)}</div>
            </div>
            <div className="rounded-2xl bg-white/5 p-3 ring-1 ring-white/8">
              <div className="text-[11px] text-muted">{w.bag_fee ? "Habituel (billet)" : "Habituel"}</div>
              <div className="text-sm font-bold tabular">{w.typical_low ? `${w.typical_low}–${w.typical_high}` : "—"}</div>
            </div>
            <div className="rounded-2xl bg-white/5 p-3 ring-1 ring-white/8">
              <div className="text-[11px] text-muted">Cible</div>
              <div className="font-bold tabular">{w.target ? euro(w.target) : "—"}</div>
            </div>
          </div>
          {w.best_depart && (
            <div className="rounded-3xl bg-white/5 p-4 ring-1 ring-white/8">
              <div className="mb-2 text-[11px] font-medium text-muted">Meilleur billet trouvé · 1 passager</div>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <div className="text-[11px] text-muted">Aller</div>
                  <div className="font-semibold">
                    {dayMonth(w.best_depart)}
                    {w.depart_time ? ` · ${w.depart_time}` : ""}
                  </div>
                </div>
                {w.best_ret && (
                  <div>
                    <div className="text-[11px] text-muted">Retour</div>
                    <div className="font-semibold">
                      {dayMonth(w.best_ret)}
                      {w.return_flight ? ` · ${w.return_flight.split(" · ")[0]}` : ""}
                    </div>
                  </div>
                )}
              </div>
              <div className="mt-2 text-xs leading-snug text-muted">
                {w.airline} · {w.stops === 0 ? "direct" : "1 escale max"}
                {bagsLabel(w) ? ` · ${bagsLabel(w)}` : ""}
              </div>
              {flexLabel(w) && <div className="mt-1 text-[11px] text-faint">{flexLabel(w)} à chaque vérification</div>}
              {w.bag_note && <div className="mt-2 text-[11px] text-faint">Valises : {w.bag_note} (estimation)</div>}
              {w.bag_policy_url && (
                <a href={w.bag_policy_url} target="_blank" rel="noopener noreferrer" className="mt-1 inline-flex items-center gap-1 text-xs font-semibold text-accent-2">
                  <Luggage size={12} /> Vérifier les frais de valises sur le site de la compagnie <ExternalLink size={11} />
                </a>
              )}
              {w.local_currency && (
                <div className="mt-2 text-[11px] leading-relaxed text-faint">
                  Billets séparés aller et retour, facturés en wons et en yens : Google propose un bouton « Continuer » par billet. Ta banque peut
                  ajouter des frais de change.
                </div>
              )}
            </div>
          )}
          <div className="rounded-3xl bg-white/5 p-3 ring-1 ring-white/8">
            {hist === null ? <Skeleton className="h-40" /> : <LineChart series={[{ name: "Prix", color: "var(--color-accent-2)", points: hist }]} height={170} />}
          </div>
          <p className="text-xs text-muted">
            Vérifié {ago(w.last_check)} · relevé toutes les heures
            {w.shared ? " · notifications envoyées sur vos deux téléphones" : ""}
          </p>
          {w.note && <p className="rounded-2xl bg-accent/10 px-3 py-2 text-xs leading-relaxed text-violet-100 ring-1 ring-accent/25">{w.note}</p>}
          <div className="grid grid-cols-2 gap-2">
            <div className="col-span-2">
              <LinkButton href={w.booking_url || w.google_url || "#"} primary>
                Réserver ce billet · comparer les sites
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
                  depart: w.best_depart || w.depart,
                  ret: w.best_ret ?? w.ret,
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
            {!w.shared && (
              <motion.button whileTap={{ scale: 0.97 }} onClick={remove} disabled={!!busy} className="col-span-2 flex items-center justify-center gap-2 rounded-2xl py-3 text-sm font-semibold text-bad">
                <Trash2 size={15} /> Supprimer l'alerte
              </motion.button>
            )}
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
  const shared = (watches || []).filter((w) => w.shared);
  const mine = (watches || []).filter((w) => !w.shared);

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

      {shared.length > 0 && (
        <>
          <SectionTitle action={<Badge tone="accent">{shared.length}</Badge>}>Voyage · partagé</SectionTitle>
          <div className="space-y-3">
            {shared.map((w, i) => (
              <WatchCard key={w.id} w={w} index={i} onOpen={() => go(`/alertes/${w.id}`)} />
            ))}
          </div>
          <p className="mt-2 px-1 text-[11px] leading-relaxed text-faint">
            Suivies pour vous deux : chacun réserve son propre billet (1 passager) avec le lien « Réserver ». Prix valises comprises : 1 valise 23 kg à
            l'aller, 2 au retour.
          </p>
        </>
      )}

      <SectionTitle action={mine.length > 0 && <Badge tone="accent">{mine.length}</Badge>}>Mes alertes</SectionTitle>
      {error && <p className="text-sm text-bad">{error}</p>}
      {!watches && !error && (
        <div className="space-y-3">
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
        </div>
      )}
      {watches && mine.length === 0 && (
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
          {mine.map((w, i) => (
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
