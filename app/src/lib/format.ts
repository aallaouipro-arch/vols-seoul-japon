const euroFmt = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });

export const euro = (n: number | null | undefined) => (n === null || n === undefined ? "—" : euroFmt.format(n));

export const duration = (min: number) => {
  if (!min) return "";
  const h = Math.floor(min / 60);
  const m = min % 60;
  return h ? `${h} h${m ? ` ${String(m).padStart(2, "0")}` : ""}` : `${m} min`;
};

/** "2027-07-21 06:25" → "06:25" */
export const hhmm = (s: string) => s.slice(-5);

const day = (s: string) => new Date(`${s.slice(0, 10)}T12:00:00`);

/** "2027-07-21" → "mer. 21 juil." */
export const shortDate = (s: string) =>
  day(s).toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short" });

/** "2027-07-21" → "21 juil." */
export const dayMonth = (s: string) => day(s).toLocaleDateString("fr-FR", { day: "numeric", month: "short" });

/** Jours entre deux dates ISO (heure ignorée). */
export const daysBetween = (a: string, b: string) => Math.round((day(b).getTime() - day(a).getTime()) / 86_400_000);

export const plusDays = (depart: string, arrive: string) => {
  const d = daysBetween(depart, arrive);
  return d > 0 ? `+${d}` : "";
};

export const ago = (iso: string | null | undefined) => {
  if (!iso) return "jamais";
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "à l'instant";
  if (s < 3600) return `il y a ${Math.round(s / 60)} min`;
  if (s < 86400) return `il y a ${Math.round(s / 3600)} h`;
  return `il y a ${Math.round(s / 86400)} j`;
};

export const todayIso = () => new Date().toISOString().slice(0, 10);

export const addDays = (iso: string, n: number) => {
  const d = day(iso);
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
};

export const levelInfo = (level: string | null | undefined) =>
  ({
    bas: { label: "Prix bas", tone: "good" as const },
    habituel: { label: "Prix habituel", tone: "warn" as const },
    élevé: { label: "Prix élevé", tone: "bad" as const },
  })[level || ""] || { label: "Niveau inconnu", tone: "neutral" as const };

export const flag = (iso: string) =>
  iso && iso.length === 2 ? String.fromCodePoint(...[...iso.toUpperCase()].map((c) => 0x1f1a5 + c.charCodeAt(0))) : "🌍";
