/** Autocomplétion des aéroports (liste OurAirports embarquée, voir scripts/build_airports.py). */

export type Place = { code: string; name: string; city: string; country: string; rank: number; alias: string };

let cache: Place[] | null = null;
let loading: Promise<Place[]> | null = null;

export function loadPlaces(): Promise<Place[]> {
  if (cache) return Promise.resolve(cache);
  loading ??= fetch("/airports.json")
    .then((r) => r.json())
    .then((rows: [string, string, string, string, number, string][]) => {
      cache = rows.map(([code, name, city, country, rank, alias]) => ({ code, name, city, country, rank, alias }));
      return cache;
    });
  return loading;
}

const norm = (s: string) =>
  s
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .trim();

export function searchPlaces(places: Place[], query: string, limit = 12): Place[] {
  const q = norm(query);
  if (!q) return [];
  const scored: [number, Place][] = [];
  for (const p of places) {
    const code = p.code.toLowerCase();
    const city = norm(p.city);
    const alias = norm(p.alias);
    const name = norm(p.name);
    let s = 0;
    if (code === q) s = 100;
    else if (city === q || alias === q) s = 90;
    else if (city.startsWith(q) || alias.startsWith(q)) s = 70;
    else if (code.startsWith(q) && q.length >= 2) s = 60;
    else if (name.includes(q)) s = 30;
    else if (city.includes(q)) s = 25;
    if (s) scored.push([s + p.rank * 6, p]);
  }
  return scored
    .sort((a, b) => b[0] - a[0])
    .slice(0, limit)
    .map(([, p]) => p);
}

/** Libellé court pour l'affichage : "Séoul", "Paris (CDG + Orly)" → "Paris". */
export const shortLabel = (p: Place) => (p.rank === 3 ? p.city : `${p.city.split(" (")[0]} ${p.code}`);

/** Pays, région ou ville Google (identifiant /m/… ou /g/…), par opposition à un code IATA. */
export const isPlaceId = (code: string) => /^\/[mg]\//.test(code);

/** Texte secondaire sous un lieu choisi : aéroports, ou « Tous les aéroports » pour un pays. */
export const placeDetail = (code: string, detail?: string) => detail || (isPlaceId(code) ? "Tous les aéroports" : code.replace(/\+/g, " + "));

let countries: Map<string, string> | null = null;

/** Code pays ISO d'après son nom en français (« Japon » → JP), pour afficher le drapeau. */
export function countryIso(name: string | null | undefined): string {
  if (!name) return "";
  if (!countries) {
    countries = new Map();
    try {
      const dn = new Intl.DisplayNames(["fr"], { type: "region" });
      const A = 65;
      for (let i = 0; i < 26; i++)
        for (let j = 0; j < 26; j++) {
          const iso = String.fromCharCode(A + i, A + j);
          const label = dn.of(iso);
          if (label && label !== iso) countries.set(norm(label), iso);
        }
    } catch {
      // navigateur sans Intl.DisplayNames : pas de drapeau
    }
  }
  return countries.get(norm(name)) || "";
}
