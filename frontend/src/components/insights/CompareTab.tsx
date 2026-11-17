import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ArrowRight, CalendarMinus, CalendarPlus, FileDiff, Minus, Plus, RefreshCw } from "lucide-react";
import { api } from "../../lib/api";
import { useDocuments } from "../../hooks/queries";
import { cn } from "../../lib/utils";
import { Badge, Card, CardBody, CardHeader, EmptyState, ErrorState, Skeleton, SkeletonText } from "../ui";
import { DocCombobox } from "../DocCombobox";

function RadialGauge({ value }: { value: number }) {
  const v = Math.max(0, Math.min(100, value));
  const r = 52;
  const c = 2 * Math.PI * r;
  const tone = v >= 75 ? "#10b981" : v >= 40 ? "#f59e0b" : "#f43f5e";
  return (
    <div className="relative h-36 w-36">
      <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90">
        <defs>
          <linearGradient id="gauge" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#6366f1" />
            <stop offset="55%" stopColor="#8b5cf6" />
            <stop offset="100%" stopColor="#06b6d4" />
          </linearGradient>
        </defs>
        <circle cx="60" cy="60" r={r} fill="none" strokeWidth="10" className="stroke-slate-200 dark:stroke-white/[0.07]" />
        <motion.circle
          cx="60"
          cy="60"
          r={r}
          fill="none"
          stroke="url(#gauge)"
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: c - (v / 100) * c }}
          transition={{ duration: 1.2, ease: [0.22, 1, 0.36, 1] }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-semibold tabular-nums text-slate-900 dark:text-white">{v.toFixed(0)}%</span>
        <span className="text-[11px] font-medium" style={{ color: tone }}>
          {v >= 75 ? "Very similar" : v >= 40 ? "Partially similar" : "Different"}
        </span>
      </div>
    </div>
  );
}

function ClauseList({ items, tone, icon, empty }: { items: string[]; tone: "green" | "red"; icon: ReactNode; empty: string }) {
  if (!items.length) return <p className="muted px-1 text-sm">{empty}</p>;
  return (
    <ul className="space-y-2">
      {items.map((t, i) => (
        <motion.li
          key={i}
          initial={{ opacity: 0, x: -6 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: Math.min(i, 10) * 0.03 }}
          className={cn(
            "flex gap-2.5 rounded-xl border-l-[3px] px-3 py-2.5 text-sm leading-relaxed",
            tone === "green"
              ? "border-emerald-500 bg-emerald-500/[0.06] text-slate-700 dark:text-slate-200"
              : "border-rose-500 bg-rose-500/[0.06] text-slate-700 dark:text-slate-200",
          )}
        >
          <span className={cn("mt-0.5 shrink-0", tone === "green" ? "text-emerald-500" : "text-rose-500")}>{icon}</span>
          <span>{t}</span>
        </motion.li>
      ))}
    </ul>
  );
}

export function CompareTab({ a, b, setA, setB }: { a: string | null; b: string | null; setA: (v: string) => void; setB: (v: string) => void }) {
  const docs = useDocuments();
  const list = docs.data?.documents ?? [];
  const q = useQuery({ queryKey: ["compare", a, b], queryFn: () => api.compare(a!, b!), enabled: !!a && !!b && a !== b, staleTime: Infinity });
  const r = q.data;

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="grid items-end gap-3 md:grid-cols-[1fr_auto_1fr]">
          <DocCombobox label="Document A (original)" documents={list} value={a} onChange={setA} exclude={b} loading={docs.isLoading} />
          <div className="hidden pb-3 md:block">
            <ArrowRight className="h-5 w-5 text-slate-400" />
          </div>
          <DocCombobox label="Document B (revised)" documents={list} value={b} onChange={setB} exclude={a} loading={docs.isLoading} />
        </div>
      </Card>
      {(!a || !b) && <Card><EmptyState icon={<FileDiff />} title="Pick two documents to compare" description="Ideal for contract revisions, policy updates and versioned reports." /></Card>}
      {q.isLoading && (
        <div className="grid gap-4 lg:grid-cols-3">
          <Card className="flex items-center justify-center p-8">
            <Skeleton className="h-36 w-36 rounded-full" />
          </Card>
          <Card className="p-5 lg:col-span-2">
            <SkeletonText lines={6} />
          </Card>
        </div>
      )}
      {q.isError && (
        <Card>
          <ErrorState error={q.error} onRetry={() => q.refetch()} />
        </Card>
      )}
      {r && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="flex flex-col items-center justify-center p-6">
              <RadialGauge value={r.similarity_score} />
              <div className="mt-3 text-center text-xs text-slate-500">
                <div className="truncate">
                  <b className="text-slate-700 dark:text-slate-200">A:</b> {r.label_a}
                </div>
                <div className="truncate">
                  <b className="text-slate-700 dark:text-slate-200">B:</b> {r.label_b}
                </div>
              </div>
            </Card>
            <div className="grid grid-cols-3 gap-3 lg:col-span-2">
              {[
                { label: "Added", n: r.added_count, cls: "text-emerald-600 dark:text-emerald-400", bg: "from-emerald-500/10", icon: <Plus className="h-4 w-4" /> },
                { label: "Removed", n: r.removed_count, cls: "text-rose-600 dark:text-rose-400", bg: "from-rose-500/10", icon: <Minus className="h-4 w-4" /> },
                { label: "Modified", n: r.modified_count, cls: "text-amber-600 dark:text-amber-400", bg: "from-amber-500/10", icon: <RefreshCw className="h-4 w-4" /> },
              ].map((x) => (
                <Card key={x.label} className={cn("flex flex-col justify-between bg-gradient-to-br to-transparent p-4", x.bg)}>
                  <div className={cn("flex items-center gap-1.5 text-xs font-medium", x.cls)}>
                    {x.icon}
                    {x.label}
                  </div>
                  <div className="mt-4 text-3xl font-semibold tabular-nums text-slate-900 dark:text-white">{x.n}</div>
                  <div className="text-[11px] text-slate-500">clauses</div>
                </Card>
              ))}
              <Card className="col-span-3 grid gap-4 p-4 sm:grid-cols-2">
                <div>
                  <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
                    <CalendarPlus className="h-3.5 w-3.5" /> New dates
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {r.new_dates.length ? r.new_dates.map((d) => <Badge key={d} tone="green">{d}</Badge>) : <span className="muted text-xs">None</span>}
                  </div>
                </div>
                <div>
                  <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-rose-600 dark:text-rose-400">
                    <CalendarMinus className="h-3.5 w-3.5" /> Removed dates
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {r.removed_dates.length ? r.removed_dates.map((d) => <Badge key={d} tone="red">{d}</Badge>) : <span className="muted text-xs">None</span>}
                  </div>
                </div>
              </Card>
            </div>
          </div>

          <Card>
            <CardHeader icon={<RefreshCw className="h-4 w-4" />} title={`Modified clauses (${r.modified_clauses.length})`} />
            <CardBody className="space-y-3">
              {r.modified_clauses.length === 0 && <p className="muted text-sm">No modified clauses.</p>}
              {r.modified_clauses.map((m, i) => (
                <motion.div key={i} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i, 10) * 0.04 }} className="rounded-xl border border-amber-500/25 bg-amber-500/[0.04] p-3">
                  <div className="grid gap-2 md:grid-cols-[1fr_auto_1fr] md:items-start">
                    <p className="rounded-lg bg-rose-500/[0.06] px-3 py-2 text-sm leading-relaxed text-slate-600 line-through decoration-rose-500/40 dark:text-slate-300">{m.from_text}</p>
                    <ArrowRight className="mx-auto hidden h-4 w-4 text-amber-500 md:mt-3 md:block" />
                    <p className="rounded-lg bg-emerald-500/[0.06] px-3 py-2 text-sm leading-relaxed text-slate-800 dark:text-slate-100">{m.to_text}</p>
                  </div>
                  {m.deltas.length > 0 && (
                    <div className="mt-2.5 flex flex-wrap gap-1.5">
                      {m.deltas.map((d, j) => {
                        const s = String(d.change_delta);
                        const neg = s.trim().startsWith("-");
                        return (
                          <span key={j} className="inline-flex items-center gap-1.5 rounded-full bg-white/70 px-2.5 py-1 text-xs ring-1 ring-inset ring-amber-500/30 dark:bg-white/[0.04]">
                            <span className="font-mono text-slate-500">{d.original_value}</span>
                            <ArrowRight className="h-3 w-3 text-slate-400" />
                            <span className="font-mono font-medium text-slate-900 dark:text-white">{d.new_value}</span>
                            <span className={cn("rounded-full px-1.5 font-mono text-[10px] font-semibold", neg ? "bg-rose-500/15 text-rose-600 dark:text-rose-400" : "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400")}>
                              {s}
                            </span>
                          </span>
                        );
                      })}
                    </div>
                  )}
                </motion.div>
              ))}
            </CardBody>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader icon={<Plus className="h-4 w-4" />} title={`Added clauses (${r.added_clauses.length})`} />
              <CardBody>
                <ClauseList items={r.added_clauses} tone="green" icon={<Plus className="h-3.5 w-3.5" />} empty="Nothing added." />
              </CardBody>
            </Card>
            <Card>
              <CardHeader icon={<Minus className="h-4 w-4" />} title={`Removed clauses (${r.removed_clauses.length})`} />
              <CardBody>
                <ClauseList items={r.removed_clauses} tone="red" icon={<Minus className="h-3.5 w-3.5" />} empty="Nothing removed." />
              </CardBody>
            </Card>
          </div>
        </motion.div>
      )}
    </div>
  );
}
