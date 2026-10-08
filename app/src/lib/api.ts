export type Layover = { code: string; minutes: number; city: string };

export type Offer = {
  price: number;
  bag_fee: number;
  bag_note: string;
  total: number;
  airlines: string[];
  airline_code: string;
  route: string;
  depart: string;
  arrive: string;
  duration_min: number;
  stops: number;
  layovers: Layover[];
  segments: string[][];
  booking_url?: string;
};

export type Insights = {
  current: number | null;
  typical_low: number | null;
  typical_high: number | null;
  level: string;
  history: [string, number][];
};

export type Links = { trip: string; kayak: string; skyscanner: string };

export type Stops = "0" | "1" | "any";

export type SearchQuery = {
  origin: string;
  destination: string;
  originLabel: string;
  destinationLabel: string;
  depart: string;
  ret: string | null;
  stops: Stops;
  bagsOut: number;
  bagsRet: number;
};

export type SearchResponse = {
  offers: Offer[];
  insights: Insights | null;
  google_url: string;
  links: Links;
};

export type FlexDay = { depart: string; ret: string | null; price: number | null };

export type Watch = {
  id: string;
  origin: string;
  destination: string;
  origin_label: string;
  destination_label: string;
  depart: string;
  ret: string | null;
  stops: number | null;
  bags_out: number;
  bags_ret: number;
  target: number | null;
  created: string;
  last_price: number | null;
  min_price: number | null;
  level: string | null;
  typical_low?: number | null;
  typical_high?: number | null;
  last_check: string | null;
  airline?: string;
  airline_code?: string;
  google_url?: string;
  booking_url?: string | null;
};

export type BookingOption = { site: string; price: number; airline: boolean };

export type TripLeg = {
  search: string;
  origin: string;
  destination: string;
  depart_date: string;
  return_date: string | null;
  total: number;
  fare: number;
  bag_fee: number;
  bag_note: string;
  bags: number[];
  airlines: string;
  airline_code: string;
  route: string;
  depart: string;
  arrive: string;
  stops: number;
  duration_min: number;
  return_flight: string | null;
  booking: BookingOption[];
  booking_url: string | null;
  google_url: string;
  links: Partial<Links>;
};

export type Trip = {
  generated_at: string;
  trip_name: string;
  plan: {
    outbound_dates: string[];
    return_dates: string[];
    seoul_to_tokyo_dates: string[];
    tokyo_to_seoul_dates: string[];
    bags: { outbound: number; return: number };
  };
  advice: {
    action: "ACHETER" | "SURVEILLER" | "ATTENDRE";
    reason: string;
    price: number;
    min_seen: number;
    typical_low: number | null;
    typical_high: number | null;
    level: string;
    trend_per_week: number | null;
    forecast_14d: number | null;
    days_left: number;
    window: [string, string];
  };
  best: { strategy: string; label: string; total: number; legs: TripLeg[] };
  strategies: { name: string; label: string; total: number }[];
  direct_vs_stop: { dates: string; direct: number; one_stop: number; saving: number; direct_airlines: string } | null;
  series: Record<string, [string, number][]>;
  google_history: [string, number][];
  timing: {
    weekday: { label: string; n: number; drop_rate: number; rise_rate: number; avg_change_pct: number }[];
    best_day: { label: string; drop_rate: number } | null;
  };
};

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers || {}) } });
  } catch {
    throw new Error("Pas de connexion internet");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Erreur ${res.status}`);
  return data as T;
}

const qs = (o: Record<string, string | number | null | undefined>) =>
  new URLSearchParams(Object.entries(o).filter(([, v]) => v !== null && v !== undefined && v !== "") as [string, string][]).toString();

const searchParams = (q: SearchQuery) => ({
  origin: q.origin,
  destination: q.destination,
  depart: q.depart,
  ret: q.ret,
  stops: q.stops,
  bags_out: q.bagsOut,
  bags_ret: q.ret ? q.bagsRet : 0,
});

export const api = {
  config: () => call<{ vapid_public_key: string }>("/api/config"),
  search: (q: SearchQuery) => call<SearchResponse>(`/api/search?${qs(searchParams(q))}`),
  returns: (q: SearchQuery, out: string[][]) =>
    call<{ offers: Offer[]; google_url: string }>(`/api/returns?${qs({ ...searchParams(q), out: JSON.stringify(out) })}`),
  flex: (q: SearchQuery) =>
    call<{ days: FlexDay[] }>(`/api/flex?${qs({ origin: q.origin, destination: q.destination, depart: q.depart, ret: q.ret, stops: q.stops })}`),
  watches: (device: string) => call<{ watches: Watch[] }>(`/api/watches?${qs({ device })}`),
  createWatch: (body: Record<string, unknown>) => call<Watch>("/api/watches", { method: "POST", body: JSON.stringify(body) }),
  deleteWatch: (id: string, device: string) => call(`/api/watches/${id}?${qs({ device })}`, { method: "DELETE" }),
  checkWatch: (id: string, device: string) => call<Watch>(`/api/watches/${id}/check?${qs({ device })}`, { method: "POST" }),
  history: (id: string) => call<{ history: [string, number][] }>(`/api/watches/${id}/history`),
  subscribe: (device: string, subscription: PushSubscriptionJSON) =>
    call("/api/push/subscribe", { method: "POST", body: JSON.stringify({ device, subscription }) }),
  testPush: (device: string) => call<{ sent: number }>(`/api/push/test?${qs({ device })}`, { method: "POST" }),
  trip: () => call<Trip>("/api/trip"),
};
