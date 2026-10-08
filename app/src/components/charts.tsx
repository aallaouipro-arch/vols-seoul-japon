/** Graphiques SVG légers : courbe interactive (survol / doigt), mini-courbe, fourchette de prix. */

import { useMemo, useRef, useState } from "react";
import { euro } from "../lib/format";

export type Series = { name: string; color: string; points: [string, number][] };

const dateLabel = (iso: string) =>
  new Date(iso.length <= 10 ? `${iso}T12:00:00` : iso).toLocaleDateString("fr-FR", { day: "numeric", month: "short" });

export function LineChart({ series, height = 190 }: { series: Series[]; height?: number }) {
  const ref = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const W = 340;
  const pad = { l: 44, r: 10, t: 12, b: 24 };

  const { xs, scaleX, scaleY, ticks, all } = useMemo(() => {
    const all = series.flatMap((s) => s.points.map(([t, v]) => ({ t: new Date(t.length <= 10 ? `${t}T12:00:00` : t).getTime(), v })));
    const tMin = Math.min(...all.map((p) => p.t));
    const tMax = Math.max(...all.map((p) => p.t));
    const vMin = Math.min(...all.map((p) => p.v));
    const vMax = Math.max(...all.map((p) => p.v));
    // Écart minimal de 8 % du prix : évite un axe « 1467 € / 1468 € / 1468 € » quand le prix bouge peu
    const span = Math.max(vMax - vMin, vMax * 0.08, 10);
    const mid = (vMax + vMin) / 2;
    const lo = Math.max(0, mid - span * 0.65);
    const hi = mid + span * 0.65;
    const scaleX = (t: number) => pad.l + ((t - tMin) / (tMax - tMin || 1)) * (W - pad.l - pad.r);
    const scaleY = (v: number) => pad.t + (1 - (v - lo) / (hi - lo)) * (height - pad.t - pad.b);
    const ticks = [lo + (hi - lo) * 0.15, (lo + hi) / 2, hi - (hi - lo) * 0.15];
    const xs = [...new Set(all.map((p) => p.t))].sort((a, b) => a - b);
    return { xs, scaleX, scaleY, ticks, all };
  }, [series, height]);

  if (!all.length) return <div className="grid h-40 place-items-center text-sm text-muted">Pas encore de données</div>;

  const onMove = (clientX: number) => {
    const box = ref.current?.getBoundingClientRect();
    if (!box) return;
    const x = ((clientX - box.left) / box.width) * W;
    let best = 0;
    xs.forEach((t, i) => {
      if (Math.abs(scaleX(t) - x) < Math.abs(scaleX(xs[best]) - x)) best = i;
    });
    setHover(best);
  };

  const hoverT = hover !== null ? xs[hover] : null;
  const valuesAt = (t: number) =>
    series
      .map((s) => {
        const p = s.points.find(([pt]) => new Date(pt.length <= 10 ? `${pt}T12:00:00` : pt).getTime() === t);
        return p ? { s, v: p[1] } : null;
      })
      .filter(Boolean) as { s: Series; v: number }[];

  return (
    <div className="relative">
      <svg
        ref={ref}
        viewBox={`0 0 ${W} ${height}`}
        className="w-full touch-none select-none"
        onPointerMove={(e) => onMove(e.clientX)}
        onPointerDown={(e) => onMove(e.clientX)}
        onPointerLeave={() => setHover(null)}
        role="img"
        aria-label="Évolution du prix"
      >
        {ticks.map((v) => (
          <g key={v}>
            <line x1={pad.l} x2={W - pad.r} y1={scaleY(v)} y2={scaleY(v)} stroke="rgb(255 255 255 / 0.07)" />
            <text x={pad.l - 6} y={scaleY(v) + 3.5} textAnchor="end" fontSize="9.5" fill="#8b8d9c">
              {Math.round(v)} €
            </text>
          </g>
        ))}
        {[xs[0], xs[xs.length - 1]].map((t, i) => (
          <text key={i} x={scaleX(t)} y={height - 6} textAnchor={i ? "end" : "start"} fontSize="9.5" fill="#8b8d9c">
            {dateLabel(new Date(t).toISOString())}
          </text>
        ))}
        {series.map((s) => {
          const pts = s.points.map(([t, v]) => [scaleX(new Date(t.length <= 10 ? `${t}T12:00:00` : t).getTime()), scaleY(v)] as const);
          if (!pts.length) return null;
          const d = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
          const area = `${d} L${pts[pts.length - 1][0]},${height - pad.b} L${pts[0][0]},${height - pad.b} Z`;
          return (
            <g key={s.name}>
              {series.length === 1 && (
                <>
                  <defs>
                    <linearGradient id={`fill-${s.name}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0" stopColor={s.color} stopOpacity="0.28" />
                      <stop offset="1" stopColor={s.color} stopOpacity="0" />
                    </linearGradient>
                  </defs>
                  <path d={area} fill={`url(#fill-${s.name})`} />
                </>
              )}
              <path d={d} fill="none" stroke={s.color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
              {pts.length === 1 && <circle cx={pts[0][0]} cy={pts[0][1]} r="4" fill={s.color} />}
            </g>
          );
        })}
        {hoverT !== null && (
          <g>
            <line x1={scaleX(hoverT)} x2={scaleX(hoverT)} y1={pad.t} y2={height - pad.b} stroke="rgb(255 255 255 / 0.35)" strokeDasharray="3 3" />
            {valuesAt(hoverT).map(({ s, v }) => (
              <circle key={s.name} cx={scaleX(hoverT)} cy={scaleY(v)} r="4.5" fill={s.color} stroke="#0e1018" strokeWidth="2" />
            ))}
          </g>
        )}
      </svg>
      {hoverT !== null && (
        <div
          className="glass-strong pointer-events-none absolute top-1 rounded-xl px-3 py-2 text-xs shadow-xl"
          style={{ left: `clamp(8px, calc(${(scaleX(hoverT) / W) * 100}% - 70px), calc(100% - 150px))` }}
        >
          <div className="mb-1 text-muted">{dateLabel(new Date(hoverT).toISOString())}</div>
          {valuesAt(hoverT).map(({ s, v }) => (
            <div key={s.name} className="flex items-center gap-2 whitespace-nowrap">
              <span className="h-0.5 w-3 rounded" style={{ background: s.color }} />
              <span className="tabular font-semibold text-white">{euro(v)}</span>
              {series.length > 1 && <span className="text-muted">{s.name}</span>}
            </div>
          ))}
        </div>
      )}
      {series.length > 1 && (
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 px-1 text-xs text-muted">
          {series.map((s) => (
            <span key={s.name} className="flex items-center gap-1.5">
              <span className="h-0.5 w-3 rounded" style={{ background: s.color }} />
              {s.name}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function Sparkline({ points, color = "#22d3ee", width = 84, height = 30 }: { points: number[]; color?: string; width?: number; height?: number }) {
  if (points.length < 2) return <div style={{ width, height }} />;
  const lo = Math.min(...points);
  const hi = Math.max(...points);
  const x = (i: number) => (i / (points.length - 1)) * (width - 4) + 2;
  const y = (v: number) => 3 + (1 - (v - lo) / (hi - lo || 1)) * (height - 6);
  const d = points.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  return (
    <svg width={width} height={height} aria-hidden>
      <path d={d} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={x(points.length - 1)} cy={y(points[points.length - 1])} r="2.5" fill={color} />
    </svg>
  );
}

/** Où se situe le prix actuel par rapport à la fourchette habituelle de Google. */
export function RangeBar({ low, high, value }: { low: number; high: number; value: number }) {
  const min = Math.min(low, value) - (high - low) * 0.35;
  const max = Math.max(high, value) + (high - low) * 0.35;
  const pct = (v: number) => ((v - min) / (max - min)) * 100;
  return (
    <div>
      <div className="relative h-2 rounded-full bg-white/8">
        <div className="absolute inset-y-0 rounded-full bg-gradient-to-r from-good/70 via-warn/70 to-bad/70" style={{ left: `${pct(low)}%`, width: `${pct(high) - pct(low)}%` }} />
        <div
          className="absolute top-1/2 size-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-[3px] border-ink-2 bg-white shadow"
          style={{ left: `${pct(value)}%` }}
        />
      </div>
      <div className="mt-2 flex justify-between text-[11px] text-muted tabular">
        <span>Habituel : {euro(low)}</span>
        <span>{euro(high)}</span>
      </div>
    </div>
  );
}

export function WeekBars({ rows }: { rows: { label: string; drop_rate: number; n: number }[] }) {
  const max = Math.max(...rows.map((r) => r.drop_rate), 1);
  const best = rows.reduce((a, b) => (b.drop_rate > a.drop_rate ? b : a), rows[0]);
  return (
    <div className="flex h-32 items-end gap-2">
      {rows.map((r) => (
        <div key={r.label} className="flex flex-1 flex-col items-center gap-1.5" title={`${r.drop_rate} % de baisses (${r.n} mesures)`}>
          <span className="text-[10px] text-muted tabular">{r.drop_rate}%</span>
          <div
            className={`w-full rounded-t-[4px] ${r === best ? "bg-accent-2" : "bg-series-1/70"}`}
            style={{ height: `${Math.max(6, (r.drop_rate / max) * 80)}px` }}
          />
          <span className={`text-[10px] ${r === best ? "font-semibold text-white" : "text-muted"}`}>{r.label.slice(0, 3)}</span>
        </div>
      ))}
    </div>
  );
}
