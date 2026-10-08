import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { BellRing, Download, Share } from "lucide-react";
import { api } from "../lib/api";
import { canPromptInstall, deviceId, enablePush, isIOS, isStandalone, onInstallAvailable, promptInstall, pushState, type PushState } from "../lib/device";
import { useToast } from "./ui";

/** Carte « Activer les notifications » (ou comment installer l'appli sur iPhone). */
export function PushCard({ compact = false }: { compact?: boolean }) {
  const toast = useToast();
  const [state, setState] = useState<PushState | null>(null);
  const [installable, setInstallable] = useState(canPromptInstall());
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    pushState().then(setState);
    return onInstallAvailable(() => setInstallable(true));
  }, []);

  if (state === null || (state === "on" && compact)) return null;

  const enable = async () => {
    setBusy(true);
    try {
      const s = await enablePush();
      setState(s);
      if (s === "on") {
        await api.testPush(deviceId());
        toast("Notifications activées ✅", "good");
      } else if (s === "denied") toast("Notifications refusées : active-les dans les réglages du téléphone", "bad");
    } catch (e) {
      toast((e as Error).message, "bad");
    } finally {
      setBusy(false);
    }
  };

  const box = "glass relative overflow-hidden rounded-3xl p-4";

  if (state === "needs-install") {
    return (
      <div className={box}>
        <div className="flex items-start gap-3">
          <div className="grid size-10 shrink-0 place-items-center rounded-2xl bg-gradient-accent">
            <Download size={18} />
          </div>
          <div className="text-sm">
            <div className="font-semibold">Installe l'appli pour recevoir les alertes</div>
            <p className="mt-1 text-muted">
              Sur iPhone, les notifications ne marchent que depuis l'appli installée : dans Safari, touche{" "}
              <Share size={13} className="inline -translate-y-0.5" /> <b className="text-white">Partager</b> puis{" "}
              <b className="text-white">Sur l'écran d'accueil</b>, et ouvre Google Tracker depuis l'icône.
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (state === "unsupported") {
    return (
      <div className={box}>
        <p className="text-sm text-muted">Ce navigateur ne gère pas les notifications. Ouvre l'appli dans Chrome (Android) ou Safari (iPhone).</p>
      </div>
    );
  }

  return (
    <div className={box}>
      <div className="flex items-center gap-3">
        <div className={`grid size-10 shrink-0 place-items-center rounded-2xl ${state === "on" ? "bg-good/20 text-good" : "bg-gradient-accent"}`}>
          <BellRing size={18} />
        </div>
        <div className="min-w-0 flex-1 text-sm">
          <div className="font-semibold">{state === "on" ? "Notifications activées" : "Active les notifications"}</div>
          <p className="text-muted">
            {state === "on"
              ? "Tu es prévenu à chaque baisse de prix de tes alertes et du voyage."
              : state === "denied"
                ? "Refusées : autorise-les dans Réglages → Notifications → Google Tracker."
                : "Pour être prévenu dès qu'un prix baisse, même appli fermée."}
          </p>
        </div>
        {state === "off" && (
          <motion.button whileTap={{ scale: 0.95 }} onClick={enable} disabled={busy} className="rounded-xl bg-white px-3.5 py-2 text-sm font-semibold text-ink disabled:opacity-60">
            {busy ? "…" : "Activer"}
          </motion.button>
        )}
      </div>
      {installable && !isStandalone() && !isIOS() && (
        <motion.button whileTap={{ scale: 0.97 }} onClick={promptInstall} className="mt-3 flex w-full items-center justify-center gap-2 rounded-2xl bg-white/8 py-2.5 text-sm font-semibold ring-1 ring-white/10">
          <Download size={16} /> Installer l'appli sur ce téléphone
        </motion.button>
      )}
    </div>
  );
}
