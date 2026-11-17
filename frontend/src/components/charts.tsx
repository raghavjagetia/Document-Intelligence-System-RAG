import type { ReactNode } from "react";
import { useTheme } from "../hooks/useTheme";

/**
 * Validated categorical palette (fixed order, never cycled), stepped separately for
 * light and dark surfaces. Single-series charts use the brand accent instead.
 */
const SERIES_LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];
const SERIES_DARK = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"];

export function useChartTheme() {
  const { theme } = useTheme();
  const dark = theme === "dark";
  return {
    dark,
    series: dark ? SERIES_DARK : SERIES_LIGHT,
    accent: dark ? "#818cf8" : "#6366f1",
    accent2: dark ? "#22d3ee" : "#0891b2",
    grid: dark ? "rgba(255,255,255,0.06)" : "rgba(15,23,42,0.07)",
    axis: dark ? "#94a3b8" : "#64748b",
    cursor: dark ? "rgba(255,255,255,0.05)" : "rgba(15,23,42,0.04)",
    good: dark ? "#34d399" : "#059669",
    bad: dark ? "#fb7185" : "#e11d48",
    warn: dark ? "#fbbf24" : "#d97706",
    axisProps: {
      tick: { fill: dark ? "#94a3b8" : "#64748b", fontSize: 11 },
      tickLine: false,
      axisLine: false,
    },
  };
}

interface TooltipEntry {
  name?: string | number;
  value?: number | string | (number | string)[];
  color?: string;
  payload?: Record<string, unknown>;
  dataKey?: string | number;
}

/** Glass tooltip for recharts. Text uses ink tokens; series colour is shown as a swatch only. */
export function ChartTooltip({
  active,
  payload,
  label,
  formatter,
  labelFormatter,
}: {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: ReactNode;
  formatter?: (v: number, name: string) => string;
  labelFormatter?: (l: unknown) => ReactNode;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="glass-strong min-w-[140px] rounded-xl px-3 py-2 text-xs">
      {label !== undefined && label !== "" && (
        <div className="mb-1.5 font-medium text-slate-900 dark:text-white">{labelFormatter ? labelFormatter(label) : label}</div>
      )}
      <div className="space-y-1">
        {payload.map((p, i) => {
          const raw = Array.isArray(p.value) ? p.value[0] : p.value;
          if (raw === null || raw === undefined) return null; // "not applicable" values are not shown as 0
          const num = typeof raw === "number" ? raw : Number(raw);
          const name = String(p.name ?? p.dataKey ?? "");
          return (
            <div key={i} className="flex items-center justify-between gap-4">
              <span className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400">
                <span className="h-2 w-2 rounded-full" style={{ background: p.color }} />
                {name}
              </span>
              <span className="font-mono font-medium tabular-nums text-slate-900 dark:text-white">
                {formatter ? formatter(num, name) : Number.isFinite(num) ? num.toLocaleString(undefined, { maximumFractionDigits: 2 }) : String(raw)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-slate-600 dark:text-slate-300">
      {items.map((it) => (
        <span key={it.label} className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm" style={{ background: it.color }} />
          {it.label}
        </span>
      ))}
    </div>
  );
}
