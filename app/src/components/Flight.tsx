import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { BellPlus, Check, ExternalLink, Luggage, Plane } from "lucide-react";
import { api, type Links, type Offer, type SearchQuery } from "../lib/api";
import { deviceId } from "../lib/device";
import { dayMonth, duration, euro, hhmm, plusDays, shortDate } from "../lib/format";
import { AirlineLogo, Badge, LinkButton, Sheet, Skeleton, useToast } from "./ui";

export function StopsLabel({ offer }: { offer: Offer }) {
  if (offer.stops === 0) return <span className="text-good">Direct</span>;
  const via = offer.layovers.map((l) => `${l.code} ${duration(l.minutes)}`).join(", ");
  return (
    <span>
      {offer.stops} escale{offer.stops > 1 ? "s" : ""}
      {via && <span className="text-muted"> · {via}</span>}
    </span>
  );
}

export function OfferCard({ offer, cheapest, onClick, index = 0 }: { offer: Offer; cheapest?: boolean; onClick: () => void; index?: number }) {
  const [from, ...rest] = offer.route.split("-");
  const to = rest[rest.length - 1];
  return (
    <motion.button
      layout
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index * 0.035, 0.35), type: "spring", damping: 26, stiffness: 260 }}
      whileTap={{ scale: 0.985 }}
      onClick={onClick}
      className={`glass relative block w-full overflow-hidden rounded-3xl p-4 text-left ${cheapest ? "ring-1 ring-good/40" : ""}`}
    >
      {cheapest && <div className="absolute top-0 right-0 rounded-bl-2xl bg-good/15 px-3 py-1 text-[11px] font-semibold text-good">Le moins cher</div>}
      <div className="flex items-center gap-3">
        <AirlineLogo code={offer.airline_code} name={offer.airlines[0]} />
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium text-white/85">{offer.airlines.join(", ")}</div>
          <div className="truncate text-xs text-muted">
            <StopsLabel offer={offer} />
            {offer.co2_kg ? (
              <span className={offer.co2_diff_pct !== null && offer.co2_diff_pct !== undefined && offer.co2_diff_pct < 0 ? "text-good" : ""}>
                {" "}· {offer.co2_kg} kg CO₂{offer.co2_diff_pct ? ` (${offer.co2_diff_pct > 0 ? "+" : ""}${offer.co2_diff_pct} %)` : ""}
              </span>
            ) : null}
          </div>
        </div>
      </div>
      <div className="mt-3 flex items-end justify-between gap-3">
        <div className="flex items-center gap-3">
          <div>
            <div className="text-xl font-bold tabular">{hhmm(offer.depart)}</div>
            <div className="text-xs text-muted">{from}</div>
          </div>
          <div className="flex w-16 flex-col items-center gap-1 text-[10px] text-muted">
            <span>{duration(offer.duration_min)}</span>
            <div className="relative h-px w-full bg-white/25">
              {offer.layovers.map((_, i) => (
                <span key={i} className="absolute top-1/2 size-1.5 -translate-y-1/2 rounded-full bg-white/70" style={{ left: `${((i + 1) / (offer.stops + 1)) * 100}%` }} />
              ))}
            </div>
          </div>
          <div>
            <div className="text-xl font-bold tabular">
              {hhmm(offer.arrive)}
              <sup className="ml-0.5 text-[10px] text-accent-2">{plusDays(offer.depart, offer.arrive)}</sup>
            </div>
            <div className="text-xs text-muted">{to}</div>
          </div>
        </div>
        <div className="text-right">
          <div className={`text-2xl font-extrabold tracking-tight tabular ${cheapest ? "text-good" : ""}`}>{euro(offer.total)}</div>
          {offer.bag_fee > 0 && (
            <div className="flex items-center justify-end gap-1 text-[11px] text-muted">
              <Luggage size={11} /> dont {euro(offer.bag_fee)}
            </div>
          )}
        </div>
      </div>
    </motion.button>
  );
}

function Segments({ offer }: { offer: Offer }) {
  return (
    <ol className="relative ml-2 space-y-4 border-l border-white/15 pl-5">
      {offer.segments.map(([from, date, to, airline, num], i) => (
        <li key={i} className="relative">
          <span className="absolute -left-[26px] top-1 grid size-3 place-items-center rounded-full bg-accent-2 ring-4 ring-ink-2" />
          <div className="text-sm font-semibold">
            {from} → {to}
          </div>
          <div className="text-xs text-muted">
            {shortDate(date)} · vol {airline} {num}
          </div>
          {offer.layovers[i] && (
            <div className="mt-2 inline-block rounded-lg bg-white/6 px-2 py-1 text-xs text-white/70">
              Escale à {offer.layovers[i].city} ({offer.layovers[i].code}) · {duration(offer.layovers[i].minutes)}
            </div>
          )}
        </li>
      ))}
    </ol>
  );
}

function PartnerLinks({ links, google }: { links: Links; google?: string }) {
  return (
    <div className="grid grid-cols-3 gap-2">
      <LinkButton href={links.trip}>Trip.com</LinkButton>
      <LinkButton href={links.kayak}>Kayak</LinkButton>
      <LinkButton href={links.skyscanner}>Skyscanner</LinkButton>
      {google && (
        <div className="col-span-3">
          <LinkButton href={google}>
            <ExternalLink size={15} /> Voir la recherche sur Google Flights
          </LinkButton>
        </div>
      )}
    </div>
  );
}

export function OfferSheet({
  offer,
  query,
  links,
  googleUrl,
  onClose,
}: {
  offer: Offer | null;
  query: SearchQuery;
  links: Links;
  googleUrl: string;
  onClose: () => void;
}) {
  const toast = useToast();
  const [returns, setReturns] = useState<Offer[] | null>(null);
  const [ret, setRet] = useState<Offer | null>(null);
  const [error, setError] = useState("");
  const [alerted, setAlerted] = useState(false);
  const isRT = !!query.ret;

  useEffect(() => {
    setReturns(null);
    setRet(null);
    setError("");
    setAlerted(false);
    if (offer && isRT) {
      api
        .returns(query, offer.segments)
        .then((r) => setReturns(r.offers))
        .catch((e) => setError(e.message));
    }
  }, [offer, isRT, query]);

  const createAlert = async () => {
    try {
      await api.createWatch({
        device: deviceId(),
        origin: query.origin,
        destination: query.destination,
        origin_label: query.originLabel,
        destination_label: query.destinationLabel,
        depart: query.depart,
        ret: query.ret,
        stops: query.stops === "any" ? null : Number(query.stops),
        bags_out: query.bagsOut,
        bags_ret: query.bagsRet,
        current_price: (ret ?? offer)?.total,
      });
      setAlerted(true);
      toast("🔔 Alerte créée : tu seras prévenu si le prix baisse", "good");
    } catch (e) {
      toast((e as Error).message, "bad");
    }
  };

  const bookingUrl = isRT ? ret?.booking_url : offer?.booking_url;
  const total = isRT ? ret?.total : offer?.total;

  return (
    <Sheet
      open={!!offer}
      onClose={onClose}
      title={
        offer && (
          <span className="flex items-center gap-2">
            <Plane size={18} className="text-accent-2" /> {query.originLabel} → {query.destinationLabel}
          </span>
        )
      }
    >
      {offer && (
        <div className="space-y-5">
          <div className="flex items-center gap-3">
            <AirlineLogo code={offer.airline_code} name={offer.airlines[0]} size={44} />
            <div className="min-w-0">
              <div className="font-semibold">{offer.airlines.join(", ")}</div>
              <div className="text-sm text-muted">
                Aller · {shortDate(offer.depart)} · {hhmm(offer.depart)} → {hhmm(offer.arrive)} {plusDays(offer.depart, offer.arrive)} · {duration(offer.duration_min)}
              </div>
            </div>
          </div>
          <Segments offer={offer} />

          {isRT && (
            <div>
              <div className="mb-2 text-sm font-semibold">Choisis ton vol retour · {dayMonth(query.ret!)}</div>
              {error && <p className="text-sm text-bad">{error}</p>}
              {!returns && !error && (
                <div className="space-y-2">
                  <Skeleton className="h-16" />
                  <Skeleton className="h-16" />
                </div>
              )}
              <div className="space-y-2">
                {returns?.slice(0, 8).map((r, i) => {
                  const active = ret === r;
                  return (
                    <motion.button
                      key={i}
                      whileTap={{ scale: 0.98 }}
                      onClick={() => setRet(r)}
                      className={`flex w-full items-center gap-3 rounded-2xl p-3 text-left ring-1 transition ${active ? "bg-accent/15 ring-accent" : "bg-white/5 ring-white/10"}`}
                    >
                      <AirlineLogo code={r.airline_code} name={r.airlines[0]} size={32} />
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-semibold tabular">
                          {hhmm(r.depart)} → {hhmm(r.arrive)} <sup className="text-accent-2">{plusDays(r.depart, r.arrive)}</sup>
                        </div>
                        <div className="truncate text-xs text-muted">
                          {r.airlines.join(", ")} · <StopsLabel offer={r} />
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-bold tabular">{euro(r.total)}</div>
                        <div className="text-[10px] text-muted">A/R total</div>
                      </div>
                      {active && <Check size={18} className="text-accent" />}
                    </motion.button>
                  );
                })}
              </div>
            </div>
          )}

          <div className="rounded-3xl bg-white/5 p-4 ring-1 ring-white/10">
            <div className="flex items-end justify-between">
              <div>
                <div className="text-xs text-muted">{isRT ? "Total aller-retour" : "Prix"} · 1 passager</div>
                <div className="text-3xl font-extrabold tabular">{total ? euro(total) : "—"}</div>
              </div>
              {(isRT ? ret : offer)?.bag_fee ? (
                <Badge tone="neutral">
                  <Luggage size={12} /> valises ≈ {euro((isRT ? ret : offer)!.bag_fee)}
                </Badge>
              ) : null}
            </div>
            <div className="mt-4 space-y-2">
              {bookingUrl ? (
                <LinkButton href={bookingUrl} primary>
                  Réserver · comparer les sites (Trip.com, compagnie…)
                </LinkButton>
              ) : (
                <div className="rounded-2xl bg-white/5 px-4 py-3 text-center text-sm text-muted">Choisis un vol retour pour voir les offres</div>
              )}
              {(isRT ? ret : offer)?.bag_policy_url && (
                <a
                  href={(isRT ? ret : offer)!.bag_policy_url!}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-center gap-1.5 py-1 text-xs font-semibold text-accent-2"
                >
                  <Luggage size={13} /> Vérifier les frais de valises chez {(isRT ? ret : offer)!.airlines[0]} <ExternalLink size={12} />
                </a>
              )}
              <p className="px-1 text-[11px] leading-relaxed text-faint">
                La page Google Flights liste les sites partenaires qui vendent ce billet, avec leur prix (compagnie, agences…). Google ne référence pas
                tous les sites et ne calcule pas les frais de valises en soute : ils sont estimés ici, vérifie-les avant de payer.
                {(isRT ? ret : offer)?.local_currency && " Cette compagnie facture dans la devise locale (wons, yens) : ta banque peut ajouter des frais de change."}
              </p>
            </div>
          </div>

          <div>
            <div className="mb-2 text-sm font-semibold">Comparer ailleurs</div>
            <PartnerLinks links={links} google={googleUrl} />
          </div>

          <motion.button
            whileTap={{ scale: 0.97 }}
            onClick={createAlert}
            disabled={alerted}
            className="flex w-full items-center justify-center gap-2 rounded-2xl bg-white/8 px-4 py-3.5 font-semibold ring-1 ring-white/10 disabled:text-good"
          >
            {alerted ? <Check size={18} /> : <BellPlus size={18} />}
            {alerted ? "Alerte créée" : "M'alerter si le prix baisse"}
          </motion.button>
        </div>
      )}
    </Sheet>
  );
}
