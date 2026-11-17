import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Building2,
  CalendarDays,
  ClipboardList,
  Contact,
  DollarSign,
  Mail,
  MapPin,
  Phone,
  Search,
  SearchX,
  Tags,
  User,
  Users,
  X,
  type LucideIcon,
} from "lucide-react";
import { api } from "../../lib/api";
import { cn } from "../../lib/utils";
import type { EntityType } from "../../types";
import { Button, Card, Chip, EmptyState, ErrorState, Input, Skeleton } from "../ui";
import { copyText, MethodPill } from "./shared";

interface Meta {
  icon: LucideIcon;
  /** hex used by the proportional bar + legend swatch */
  hex: string;
  /** icon tile classes */
  tile: string;
  /** chip classes */
  chip: string;
}

const ENTITY_META: Record<EntityType, Meta> = {
  Person: {
    icon: User,
    hex: "#3b82f6",
    tile: "bg-blue-500/10 text-blue-600 ring-blue-500/25 dark:text-blue-300",
    chip: "hover:ring-blue-500/40 hover:bg-blue-500/[0.08] dark:hover:bg-blue-400/10",
  },
  Organization: {
    icon: Building2,
    hex: "#8b5cf6",
    tile: "bg-violet-500/10 text-violet-600 ring-violet-500/25 dark:text-violet-300",
    chip: "hover:ring-violet-500/40 hover:bg-violet-500/[0.08] dark:hover:bg-violet-400/10",
  },
  Location: {
    icon: MapPin,
    hex: "#10b981",
    tile: "bg-emerald-500/10 text-emerald-600 ring-emerald-500/25 dark:text-emerald-300",
    chip: "hover:ring-emerald-500/40 hover:bg-emerald-500/[0.08] dark:hover:bg-emerald-400/10",
  },
  Date: {
    icon: CalendarDays,
    hex: "#06b6d4",
    tile: "bg-cyan-500/10 text-cyan-600 ring-cyan-500/25 dark:text-cyan-300",
    chip: "hover:ring-cyan-500/40 hover:bg-cyan-500/[0.08] dark:hover:bg-cyan-400/10",
  },
  Money: {
    icon: DollarSign,
    hex: "#f59e0b",
    tile: "bg-amber-500/10 text-amber-700 ring-amber-500/25 dark:text-amber-300",
    chip: "hover:ring-amber-500/40 hover:bg-amber-500/[0.08] dark:hover:bg-amber-400/10",
  },
  Email: {
    icon: Mail,
    hex: "#ec4899",
    tile: "bg-pink-500/10 text-pink-600 ring-pink-500/25 dark:text-pink-300",
    chip: "hover:ring-pink-500/40 hover:bg-pink-500/[0.08] dark:hover:bg-pink-400/10",
  },
  Phone: {
    icon: Phone,
    hex: "#84cc16",
    tile: "bg-lime-500/10 text-lime-600 ring-lime-500/25 dark:text-lime-300",
    chip: "hover:ring-lime-500/40 hover:bg-lime-500/[0.08] dark:hover:bg-lime-400/10",
  },
  "Employee ID": {
    icon: Contact,
    hex: "#d946ef",
    tile: "bg-fuchsia-500/10 text-fuchsia-600 ring-fuchsia-500/25 dark:text-fuchsia-300",
    chip: "hover:ring-fuchsia-500/40 hover:bg-fuchsia-500/[0.08] dark:hover:bg-fuchsia-400/10",
  },
  "Contract ID": {
    icon: ClipboardList,
    hex: "#f43f5e",
    tile: "bg-rose-500/10 text-rose-600 ring-rose-500/25 dark:text-rose-300",
    chip: "hover:ring-rose-500/40 hover:bg-rose-500/[0.08] dark:hover:bg-rose-400/10",
  },
  Department: {
    icon: Users,
    hex: "#f97316",
    tile: "bg-orange-500/10 text-orange-600 ring-orange-500/25 dark:text-orange-300",
    chip: "hover:ring-orange-500/40 hover:bg-orange-500/[0.08] dark:hover:bg-orange-400/10",
  },
};

const FALLBACK: Meta = {
  icon: Tags,
  hex: "#64748b",
  tile: "bg-slate-500/10 text-slate-600 ring-slate-500/25 dark:text-slate-300",
  chip: "hover:ring-slate-500/40",
};

const meta = (t: EntityType) => ENTITY_META[t] ?? FALLBACK;

function Highlight({ text, query }: { text: string; query: string }) {
  if (!query) return <>{text}</>;
  const i = text.toLowerCase().indexOf(query.toLowerCase());
  if (i < 0) return <>{text}</>;
  return (
    <>
      {text.slice(0, i)}
      <mark className="rounded-sm bg-amber-300/60 px-0.5 text-inherit dark:bg-amber-400/30">{text.slice(i, i + query.length)}</mark>
      {text.slice(i + query.length)}
    </>
  );
}

/** Single stacked bar of entity counts per type, with hover labels + a text legend. */
function DistributionBar({ groups, total }: { groups: { type: EntityType; values: string[] }[]; total: number }) {
  const [hover, setHover] = useState<number | null>(null);
  const shown = groups.filter((g) => g.values.length > 0);
  return (
    <div>
      <div className="relative flex h-3 w-full gap-[2px]" role="img" aria-label={shown.map((g) => `${g.type} ${g.values.length}`).join(", ")}>
        {shown.map((g, i) => {
          const first = i === 0;
          const last = i === shown.length - 1;
          const pct = (g.values.length / total) * 100;
          return (
            <div
              key={g.type}
              className="relative h-full min-w-[6px]"
              style={{ flexGrow: g.values.length, flexBasis: 0 }}
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
            >
              <motion.div
                initial={{ scaleX: 0 }}
                animate={{ scaleX: 1 }}
                transition={{ delay: 0.05 * i, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
                className={cn("h-full origin-left transition-opacity", first && "rounded-l-full", last && "rounded-r-full", hover !== null && hover !== i && "opacity-35")}
                style={{ backgroundColor: meta(g.type).hex }}
              />
              {hover === i && (
                <div
                  role="tooltip"
                  className={cn(
                    "glass-strong pointer-events-none absolute bottom-full z-20 mb-2 whitespace-nowrap rounded-lg px-2.5 py-1.5 text-xs font-medium text-slate-800 dark:text-slate-100",
                    first ? "left-0" : last ? "right-0" : "left-1/2 -translate-x-1/2",
                  )}
                >
                  {g.type} · <span className="tabular-nums">{g.values.length}</span>
                  <span className="ml-1.5 text-slate-400 tabular-nums">{pct.toFixed(0)}%</span>
                </div>
              )}
            </div>
          );
        })}
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
        {shown.map((g, i) => {
          const Icon = meta(g.type).icon;
          return (
            <li
              key={g.type}
              className={cn("flex items-center gap-1.5 text-xs transition-opacity", hover !== null && hover !== i && "opacity-50")}
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
            >
              <span className="h-2.5 w-2.5 shrink-0 rounded-[3px]" style={{ backgroundColor: meta(g.type).hex }} />
              <Icon className="h-3.5 w-3.5 text-slate-400" aria-hidden />
              <span className="text-slate-600 dark:text-slate-300">{g.type}</span>
              <span className="font-semibold tabular-nums text-slate-900 dark:text-white">{g.values.length}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function EntitiesTab({ docId }: { docId: string }) {
  const q = useQuery({ queryKey: ["entities", docId], queryFn: () => api.entities(docId), staleTime: Infinity });
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<EntityType | "all">("all");

  const groups = useMemo(
    () =>
      Object.entries(q.data?.entities ?? {})
        .map(([k, v]) => ({ type: k as EntityType, values: Array.from(new Set(v ?? [])) }))
        .sort((a, b) => b.values.length - a.values.length),
    [q.data],
  );
  const total = groups.reduce((n, g) => n + g.values.length, 0);
  const nonEmpty = groups.filter((g) => g.values.length);
  const missing = groups.filter((g) => !g.values.length).map((g) => g.type);

  const needle = query.trim().toLowerCase();
  const visible = nonEmpty
    .filter((g) => typeFilter === "all" || g.type === typeFilter)
    .map((g) => ({ ...g, values: needle ? g.values.filter((v) => v.toLowerCase().includes(needle)) : g.values }))
    .filter((g) => g.values.length);
  const matchCount = visible.reduce((n, g) => n + g.values.length, 0);
  const filtered = !!needle || typeFilter !== "all";

  if (q.isLoading)
    return (
      <div className="space-y-4">
        <Card className="p-5">
          <Skeleton className="mb-3 h-6 w-40" />
          <Skeleton className="h-3 w-full rounded-full" />
          <div className="mt-3 flex gap-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-3 w-20" />
            ))}
          </div>
        </Card>
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="p-5">
              <Skeleton className="mb-4 h-4 w-32" />
              <div className="flex flex-wrap gap-2">
                {Array.from({ length: 6 }).map((_, j) => (
                  <Skeleton key={j} className="h-7 w-20 rounded-lg" />
                ))}
              </div>
            </Card>
          ))}
        </div>
      </div>
    );
  if (q.isError)
    return (
      <Card>
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      </Card>
    );
  if (!total)
    return (
      <Card>
        <EmptyState icon={<Tags />} title="Nothing found" description="No names, places, dates or amounts were found in this document." />
      </Card>
    );

  return (
    <div className="space-y-4">
      {/* overview strip */}
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
        <Card className="p-5">
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <div>
              <div className="flex items-baseline gap-2">
                <span className="text-gradient text-3xl font-semibold tabular-nums tracking-tight">{total}</span>
                <span className="text-sm font-medium text-slate-700 dark:text-slate-200">names, places, dates and other facts found</span>
              </div>
              <div className="muted mt-0.5 text-xs">
                across {nonEmpty.length} of {groups.length} types
              </div>
            </div>
            {q.data?.method && <MethodPill method={q.data.method} />}
          </div>
          <DistributionBar groups={groups} total={total} />
        </Card>
      </motion.div>

      {/* filters */}
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start">
        <div className="lg:w-72 lg:shrink-0">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search names, places, dates…"
            aria-label="Search names, places and dates"
            icon={<Search />}
            rightSlot={
              query ? (
                <button
                  type="button"
                  aria-label="Clear filter"
                  onClick={() => setQuery("")}
                  className="flex h-6 w-6 items-center justify-center rounded-md text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-white/10 dark:hover:text-slate-200"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              ) : undefined
            }
          />
        </div>
        <div className="-mx-1 flex gap-1.5 overflow-x-auto px-1 py-0.5 [scrollbar-width:none] lg:flex-wrap" role="group" aria-label="Type">
          <Chip active={typeFilter === "all"} onClick={() => setTypeFilter("all")}>
            All <span className="tabular-nums opacity-70">{total}</span>
          </Chip>
          {nonEmpty.map((g) => {
            const Icon = meta(g.type).icon;
            return (
              <Chip key={g.type} active={typeFilter === g.type} onClick={() => setTypeFilter(typeFilter === g.type ? "all" : g.type)}>
                <Icon className="h-3 w-3" />
                {g.type} <span className="tabular-nums opacity-70">{g.values.length}</span>
              </Chip>
            );
          })}
        </div>
      </div>

      {filtered && (
        <div className="muted -mt-1 text-xs">
          Showing <b className="font-semibold tabular-nums text-slate-700 dark:text-slate-200">{matchCount}</b> of {total} entities
          {needle && (
            <>
              {" "}
              matching “<span className="text-slate-700 dark:text-slate-200">{query.trim()}</span>”
            </>
          )}
        </div>
      )}

      {visible.length === 0 ? (
        <Card>
          <EmptyState
            icon={<SearchX />}
            title="No matches"
            description="Try a different word or another type."
            action={
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setQuery("");
                  setTypeFilter("all");
                }}
              >
                Clear filters
              </Button>
            }
          />
        </Card>
      ) : (
        <div className="grid items-start gap-4 md:grid-cols-2">
          {visible.map((g, gi) => {
            const m = meta(g.type);
            const Icon = m.icon;
            return (
              <motion.div key={g.type} layout initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(gi, 8) * 0.04 }}>
                <Card className="overflow-hidden">
                  <div className="flex items-center justify-between gap-3 border-b border-slate-200/70 px-5 py-3.5 dark:border-white/[0.05]">
                    <div className="flex min-w-0 items-center gap-2.5">
                      <span className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-xl ring-1 ring-inset", m.tile)}>
                        <Icon className="h-4 w-4" />
                      </span>
                      <span className="truncate text-sm font-semibold text-slate-900 dark:text-white">{g.type}</span>
                    </div>
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 font-mono text-[11px] tabular-nums text-slate-600 dark:bg-white/5 dark:text-slate-300">{g.values.length}</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5 p-4">
                    {g.values.map((v, i) => (
                      <motion.button
                        type="button"
                        key={v}
                        initial={{ opacity: 0, scale: 0.94 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ delay: Math.min(i, 20) * 0.012 }}
                        onClick={() => copyText(v, `${g.type} copied`)}
                        title="Click to copy"
                        className={cn(
                          "max-w-full truncate rounded-lg bg-white/70 px-2.5 py-1 text-left text-xs font-medium text-slate-700 ring-1 ring-inset ring-slate-200 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/50 dark:bg-white/[0.03] dark:text-slate-200 dark:ring-white/10",
                          m.chip,
                        )}
                      >
                        <Highlight text={v} query={needle} />
                      </motion.button>
                    ))}
                  </div>
                </Card>
              </motion.div>
            );
          })}
        </div>
      )}

      {!filtered && missing.length > 0 && (
        <p className="muted text-xs">
          <span className="font-medium">Not detected:</span> {missing.join(", ")}
        </p>
      )}
    </div>
  );
}
