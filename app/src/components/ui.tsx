import { animate, AnimatePresence, motion, useMotionValue, useTransform } from "motion/react";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { levelInfo } from "../lib/format";

/* ---------- Fiche glissante (bottom sheet) ---------- */

export function Sheet({ open, onClose, title, children }: { open: boolean; onClose: () => void; title?: ReactNode; children: ReactNode }) {
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  // Portail vers <body> : sinon les animations d'écran (transform) enferment la fiche sous la barre d'onglets
  return createPortal(
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50">
          <motion.div
            className="absolute inset-0 bg-black/60"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            role="dialog"
            aria-modal="true"
            className="absolute inset-x-0 bottom-0 mx-auto flex max-h-[92dvh] max-w-xl flex-col rounded-t-[28px] border-t border-white/10 bg-[#11131c] pb-[env(safe-area-inset-bottom)] shadow-[0_-20px_60px_rgba(0,0,0,0.6)]"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", damping: 32, stiffness: 320 }}
            drag="y"
            dragConstraints={{ top: 0, bottom: 0 }}
            dragElastic={{ top: 0, bottom: 0.6 }}
            onDragEnd={(_, info) => (info.offset.y > 120 || info.velocity.y > 600) && onClose()}
          >
            <div className="flex cursor-grab justify-center pt-3 pb-1">
              <div className="h-1.5 w-10 rounded-full bg-white/25" />
            </div>
            <div className="flex items-center justify-between gap-3 px-5 pb-3">
              <div className="min-w-0 text-lg font-semibold">{title}</div>
              <button onClick={onClose} className="grid size-9 shrink-0 place-items-center rounded-full bg-white/8 text-white/80 active:scale-95" aria-label="Fermer">
                <X size={18} />
              </button>
            </div>
            <div className="no-scrollbar min-h-0 flex-1 overflow-y-auto px-5 pb-6" onPointerDownCapture={(e) => e.stopPropagation()}>
              {children}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  );
}

/* ---------- Logo de compagnie ---------- */

export function AirlineLogo({ code, name, size = 36 }: { code?: string; name?: string; size?: number }) {
  const [failed, setFailed] = useState(false);
  const initials = (name || code || "?").replace(/[^A-Za-z ]/g, "").split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase();
  return (
    <div className="grid shrink-0 place-items-center overflow-hidden rounded-xl bg-white" style={{ width: size, height: size }}>
      {code && !failed ? (
        <img
          src={`https://www.gstatic.com/flights/airline_logos/70px/${code}.png`}
          alt={name || code}
          className="size-[78%] object-contain"
          onError={() => setFailed(true)}
          loading="lazy"
        />
      ) : (
        <span className="text-xs font-bold text-slate-700">{initials}</span>
      )}
    </div>
  );
}

/* ---------- Pastilles ---------- */

const TONES = {
  good: "bg-good/15 text-good ring-good/30",
  warn: "bg-warn/15 text-warn ring-warn/30",
  bad: "bg-bad/15 text-bad ring-bad/30",
  accent: "bg-accent/18 text-violet-200 ring-accent/35",
  neutral: "bg-white/8 text-white/75 ring-white/12",
};
export type Tone = keyof typeof TONES;

export function Badge({ tone = "neutral", children, className = "" }: { tone?: Tone; children: ReactNode; className?: string }) {
  return <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${TONES[tone]} ${className}`}>{children}</span>;
}

export function LevelBadge({ level }: { level: string | null | undefined }) {
  const { label, tone } = levelInfo(level);
  const icon = tone === "good" ? "🔥" : tone === "bad" ? "⬆" : "•";
  return (
    <Badge tone={tone}>
      <span aria-hidden>{icon}</span> {label}
    </Badge>
  );
}

/* ---------- Nombre animé (prix) ---------- */

export function AnimatedNumber({ value, format }: { value: number; format: (n: number) => string }) {
  const mv = useMotionValue(value);
  const text = useTransform(mv, (v) => format(Math.round(v)));
  useEffect(() => {
    const c = animate(mv, value, { duration: 0.9, ease: [0.16, 1, 0.3, 1] });
    return () => c.stop();
  }, [value, mv]);
  return <motion.span className="tabular">{text}</motion.span>;
}

/* ---------- Toasts ---------- */

type Toast = { id: number; text: string; tone: Tone };
const ToastCtx = createContext<(text: string, tone?: Tone) => void>(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const show = (text: string, tone: Tone = "neutral") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, text, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3200);
  };
  return (
    <ToastCtx.Provider value={show}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 top-[max(12px,env(safe-area-inset-top))] z-[60] flex flex-col items-center gap-2 px-4">
        <AnimatePresence>
          {toasts.map((t) => (
            <motion.div
              key={t.id}
              initial={{ opacity: 0, y: -16, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -12 }}
              className={`glass-strong rounded-2xl px-4 py-3 text-sm font-medium shadow-2xl ${t.tone === "bad" ? "text-bad" : t.tone === "good" ? "text-good" : "text-white"}`}
            >
              {t.text}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastCtx.Provider>
  );
}

/* ---------- Divers ---------- */

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton rounded-2xl ${className}`} />;
}

export function Card({ children, className = "", onClick }: { children: ReactNode; className?: string; onClick?: () => void }) {
  const Comp = onClick ? motion.button : motion.div;
  return (
    <Comp
      onClick={onClick}
      whileTap={onClick ? { scale: 0.985 } : undefined}
      className={`glass block w-full rounded-3xl p-4 text-left ${className}`}
    >
      {children}
    </Comp>
  );
}

export function SectionTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="mt-7 mb-3 flex items-end justify-between px-1">
      <h2 className="text-[15px] font-semibold tracking-tight text-white/90">{children}</h2>
      {action}
    </div>
  );
}

export function LinkButton({ href, children, primary = false }: { href: string; children: ReactNode; primary?: boolean }) {
  return (
    <motion.a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      whileTap={{ scale: 0.97 }}
      className={`flex items-center justify-center gap-2 rounded-2xl px-4 py-3 text-sm font-semibold ${
        primary ? "bg-gradient-accent text-white shadow-lg shadow-violet-900/40" : "bg-white/8 text-white/90 ring-1 ring-white/10"
      }`}
    >
      {children}
    </motion.a>
  );
}
