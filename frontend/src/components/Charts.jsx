import { useEffect, useState } from "react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

// Read chart tokens from CSS so charts follow the light/dark theme (re-read on toggle).
export function useChartColors() {
  const read = () => {
    const cs = getComputedStyle(document.documentElement);
    const v = (n) => cs.getPropertyValue(n).trim();
    return { series: v("--series-1"), grid: v("--chart-grid"), axis: v("--chart-axis"), surface: `rgb(${v("--surface")})` };
  };
  const [c, setC] = useState(read);
  useEffect(() => {
    const obs = new MutationObserver(() => setC(read()));
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["class", "data-accent"] });
    return () => obs.disconnect();
  }, []);
  return c;
}

function TooltipBox({ active, payload, label, format, labelFormat }) {
  if (!active || !payload?.length) return null;
  const p = payload[0];
  return (
    <div className="rounded-md border border-line bg-surface px-3 py-2 text-xs shadow-lift">
      <div className="text-ink-3">{labelFormat ? labelFormat(label, p.payload) : label}</div>
      <div className="mt-0.5 flex items-center gap-2 font-semibold text-ink">
        <span className="h-2 w-2 rounded-full" style={{ background: p.color || p.fill }} />
        {format ? format(p.value, p.payload) : p.value}
      </div>
    </div>
  );
}

const axisProps = (c) => ({
  tick: { fill: c.axis, fontSize: 11 },
  axisLine: false,
  tickLine: false,
});

export function LatencyChart({ data, format }) {
  const c = useChartColors();
  const rows = data.map((d, i) => ({ ...d, n: i + 1 }));
  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
        <defs>
          <linearGradient id="lat-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor={c.series} stopOpacity={0.18} />
            <stop offset="1" stopColor={c.series} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid vertical={false} stroke={c.grid} />
        <XAxis dataKey="n" {...axisProps(c)} interval="preserveStartEnd" minTickGap={30} />
        <YAxis {...axisProps(c)} width={44} tickFormatter={(v) => Math.round(v)} />
        <Tooltip
          cursor={{ stroke: c.axis, strokeDasharray: "3 3" }}
          content={<TooltipBox format={(v, p) => `${format(v)} · ${p.result_count} results`} labelFormat={(l) => `Search #${l}`} />}
        />
        <Area type="monotone" dataKey="latency_ms" stroke={c.series} strokeWidth={2} fill="url(#lat-fill)"
          activeDot={{ r: 5, stroke: c.surface, strokeWidth: 2 }} dot={false} isAnimationActive={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function ColumnChart({ data, x, y, labelFormat, valueFormat = (v) => v, height = 220 }) {
  const c = useChartColors();
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -18 }} barCategoryGap={4}>
        <CartesianGrid vertical={false} stroke={c.grid} />
        <XAxis dataKey={x} {...axisProps(c)} tickFormatter={labelFormat} minTickGap={24} />
        <YAxis {...axisProps(c)} allowDecimals={false} width={44} />
        <Tooltip cursor={{ fill: c.grid, opacity: 0.5 }} content={<TooltipBox format={valueFormat} labelFormat={labelFormat} />} />
        <Bar dataKey={y} fill={c.series} radius={[4, 4, 0, 0]} maxBarSize={36} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// Horizontal bar list: labels in ink (text tokens), bars in the series colour. Plain HTML,
// with a hover tooltip via title + visible values (no colour-only encoding).
export function BarList({ items, valueFormat = (v) => v, emptyText = "No data yet." }) {
  if (!items.length) return <p className="py-6 text-center text-sm text-ink-3">{emptyText}</p>;
  const max = Math.max(...items.map((i) => i.value), 1);
  return (
    <ul className="space-y-2.5">
      {items.map((it) => (
        <li key={it.label} className="group" title={`${it.label}: ${valueFormat(it.value)}`}>
          <div className="flex items-baseline justify-between gap-3 text-sm">
            <span className="truncate text-ink-2 group-hover:text-ink">{it.label}</span>
            <span className="shrink-0 font-mono text-xs tabular-nums text-ink">{valueFormat(it.value)}</span>
          </div>
          <div className="mt-1 h-1.5 rounded-full bg-surface-2">
            <div className="h-1.5 rounded-full transition-all duration-700 group-hover:brightness-110"
              style={{ width: `${Math.max(2, (it.value / max) * 100)}%`, background: "var(--series-1)" }} />
          </div>
        </li>
      ))}
    </ul>
  );
}
