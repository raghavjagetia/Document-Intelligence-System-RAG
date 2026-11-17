import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { toast } from "sonner";
import { Activity, CheckCircle2, FlaskConical, Layers, Play, Radar as RadarIcon, Scale, Timer, Trophy, XCircle } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, ApiError, errorMessage } from "../lib/api";
import { qk } from "../hooks/queries";
import { useAuth } from "../hooks/useAuth";
import { cn, formatDate } from "../lib/utils";
import { categoryLabel, configLabel } from "../lib/evalLabels";
import type { EvalRow } from "../types";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorState, PageHeader, Progress, Skeleton, Tooltip } from "../components/ui";
import { ChartTooltip, Legend, useChartTheme } from "../components/charts";
import { AdvancedEvaluation } from "../components/evaluation/AdvancedEvaluation";

interface Col {
  key: keyof EvalRow;
  label: string;
  short: string;
  /** lower is better */
  lower?: boolean;
  fmt: (v: number) => string;
}

const pct = (v: number) => `${v.toFixed(1)}`;
const COLS: Col[] = [
  { key: "recall_at_1", short: "Top result right", label: "How often the correct document is the very first search result (%)", fmt: pct },
  { key: "recall_at_3", short: "Found in top 3", label: "How often the correct document is among the first 3 results (%)", fmt: pct },
  { key: "recall_at_5", short: "Found in top 5", label: "How often the correct document is among the first 5 results (%)", fmt: pct },
  { key: "mrr", short: "Ranking score", label: "How high the correct document is ranked: 1.0 = always first, 0.5 = usually second (technical name: MRR)", fmt: (v) => v.toFixed(3) },
  { key: "ndcg_at_5", short: "Ranking quality", label: "Overall quality of the top-5 ordering, 100 = perfect (technical name: nDCG@5)", fmt: pct },
  { key: "answer_correctness", short: "Correct answers", label: "Answers containing the right facts, plus correct refusals for questions the documents can't answer (%)", fmt: pct },
  { key: "answer_correctness_test", short: "Correct (unseen)", label: "Correct answers on the half of the questions that was never used while tuning the system — the fairest score (%)", fmt: pct },
  { key: "faithfulness", short: "Backed by source", label: "How much of each answer is supported by the cited document text (%)", fmt: pct },
  { key: "citation_accuracy", short: "Right source cited", label: "Answers that cite the document the answer really comes from (%)", fmt: pct },
  { key: "abstention_accuracy", short: "Knows when to refuse", label: "Says “not in the documents” exactly when the answer really isn't there (%)", fmt: pct },
  { key: "median_latency", short: "Typical time (s)", label: "Typical seconds per answer (median) on a laptop CPU", lower: true, fmt: (v) => v.toFixed(2) },
  { key: "p95_latency", short: "Slowest 5% (s)", label: "95% of answers are faster than this (seconds)", lower: true, fmt: (v) => v.toFixed(2) },
];

const CHART_METRICS: { key: keyof EvalRow; label: string; scale?: number }[] = [
  { key: "recall_at_5", label: "Found in top 5" },
  { key: "mrr", label: "Ranking score ×100", scale: 100 },
  { key: "ndcg_at_5", label: "Ranking quality" },
  { key: "answer_correctness", label: "Correct answers" },
  { key: "faithfulness", label: "Backed by source" },
  { key: "citation_accuracy", label: "Right source cited" },
];

function num(r: EvalRow, k: keyof EvalRow): number {
  const v = k === "median_latency" ? (r.median_latency ?? r.avg_latency) : r[k];
  return typeof v === "number" ? v : NaN;
}

/** The measures shown by default; the rest appear with "Show all measures" */
const KEY_METRICS: (keyof EvalRow)[] = [
  "recall_at_1",
  "recall_at_5",
  "answer_correctness",
  "answer_correctness_test",
  "citation_accuracy",
  "abstention_accuracy",
  "median_latency",
];

/** Measures grouped by what they tell you */
const GROUPS: { title: string; keys: (keyof EvalRow)[] }[] = [
  { title: "Finding the right document", keys: ["recall_at_1", "recall_at_3", "recall_at_5", "mrr", "ndcg_at_5"] },
  { title: "Answer quality", keys: ["answer_correctness", "answer_correctness_test", "faithfulness", "citation_accuracy", "abstention_accuracy"] },
  { title: "Speed", keys: ["median_latency", "p95_latency"] },
];

/** 0..1 share of the bar to fill: percentages and the 0–1 ranking score get a bar, times do not */
function barShare(c: Col, v: number): number | null {
  if (c.lower) return null;
  return c.key === "mrr" ? v : v / 100;
}

function DeltaChip({ c, delta }: { c: Col; delta: number }) {
  if (Math.abs(delta) < 1e-9) return null;
  const good = c.lower ? delta < 0 : delta > 0;
  return (
    <span
      className={cn(
        "inline-flex rounded-full px-1.5 py-px font-mono text-[10px] font-medium tabular-nums",
        good ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" : "bg-rose-500/10 text-rose-600 dark:text-rose-400",
      )}
    >
      {delta > 0 ? "+" : "−"}
      {c.fmt(Math.abs(delta))}
    </span>
  );
}

function MetricValue({
  c,
  v,
  isBest,
  delta,
  align = "right",
  compact,
}: {
  c: Col;
  v: number;
  isBest: boolean;
  delta: number | null;
  align?: "right" | "left";
  compact?: boolean;
}) {
  const share = Number.isFinite(v) ? barShare(c, v) : null;
  return (
    <div className={cn("flex flex-col gap-1", align === "right" ? "items-end" : "items-start")}>
      <span
        className={cn(
          "font-mono tabular-nums",
          compact ? "text-[12px]" : "text-[13px]",
          isBest ? "font-semibold text-emerald-600 dark:text-emerald-400" : "text-slate-800 dark:text-slate-100",
        )}
      >
        {Number.isFinite(v) ? c.fmt(v) : "—"}
        {Number.isFinite(v) && c.key !== "mrr" && !c.lower && <span className="text-[10px] text-slate-400">%</span>}
        {Number.isFinite(v) && c.lower && <span className="text-[10px] text-slate-400"> s</span>}
      </span>
      {share !== null && (
        <span className={cn("h-1 w-full overflow-hidden rounded-full bg-slate-200/80 dark:bg-white/[0.07]", compact ? "max-w-[52px]" : "max-w-[72px]")}>
          <span
            className={cn("block h-full rounded-full", isBest ? "bg-emerald-500" : "bg-indigo-500/80 dark:bg-indigo-400/80")}
            style={{ width: `${Math.max(0, Math.min(1, share)) * 100}%` }}
          />
        </span>
      )}
      {delta !== null && <DeltaChip c={c} delta={delta} />}
    </div>
  );
}

function MetricsTable({ rows, highlightBest = true, baseline }: { rows: EvalRow[]; highlightBest?: boolean; baseline?: EvalRow }) {
  const [showAll, setShowAll] = useState(false);
  const visible = (k: keyof EvalRow) => showAll || KEY_METRICS.includes(k);
  const groups = GROUPS.map((g) => ({ ...g, cols: COLS.filter((c) => g.keys.includes(c.key) && visible(c.key)) })).filter(
    (g) => g.cols.length,
  );
  const cols = groups.flatMap((g) => g.cols);
  const groupStart = new Set(groups.map((g) => g.cols[0].key));
  const best = useMemo(() => {
    const m = new Map<keyof EvalRow, number>();
    for (const c of COLS) {
      const vals = rows.map((r) => num(r, c.key)).filter(Number.isFinite);
      if (vals.length) m.set(c.key, c.lower ? Math.min(...vals) : Math.max(...vals));
    }
    return m;
  }, [rows]);
  const cell = (r: EvalRow, c: Col) => {
    const v = num(r, c.key);
    const isBest = highlightBest && rows.length > 1 && Number.isFinite(v) && best.get(c.key) === v;
    const base = baseline ? num(baseline, c.key) : NaN;
    const delta = baseline && r !== baseline && Number.isFinite(base) && Number.isFinite(v) ? v - base : null;
    return { v, isBest, delta };
  };
  const divider = "border-l border-slate-200/70 dark:border-white/[0.06]";

  return (
    <div>
      {/* laptop and wider: grouped table that always fits the card - no sideways scrolling */}
      <div className="hidden lg:block">
        <table className="w-full table-fixed text-sm">
          <colgroup>
            <col className={showAll ? "w-[18%]" : "w-[26%]"} />
            {cols.map((c) => (
              <col key={c.key} />
            ))}
          </colgroup>
          <thead>
            <tr className="text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-400">
              <th />
              {groups.map((g) => (
                <th key={g.title} colSpan={g.cols.length} className={cn("px-2 pb-1 pt-3 text-center font-semibold", divider)}>
                  {g.title}
                </th>
              ))}
            </tr>
            <tr className="border-b border-slate-200 text-xs text-slate-500 dark:border-white/[0.07]">
              <th className="px-5 py-2.5 text-left font-medium">Version of the system</th>
              {cols.map((c) => (
                <th
                  key={c.key}
                  className={cn(
                    "py-2.5 text-right align-bottom font-medium leading-tight",
                    showAll ? "px-1.5 text-[11px]" : "px-2",
                    groupStart.has(c.key) && divider,
                  )}
                >
                  <Tooltip label={c.label} width={240}>
                    <span tabIndex={0} className="cursor-help border-b border-dotted border-slate-400">
                      {c.short}
                    </span>
                  </Tooltip>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const label = configLabel(r.config_name);
              const isBaseline = baseline !== undefined && r === baseline;
              return (
                <motion.tr
                  key={r.config_name}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: i * 0.04 }}
                  className={cn(
                    "border-b border-slate-100 align-top transition-colors last:border-0 hover:bg-indigo-500/[0.03] dark:border-white/[0.04]",
                    isBaseline && "bg-indigo-500/[0.04]",
                  )}
                >
                  <td className={cn("py-3.5", showAll ? "px-4" : "px-5")}>
                    <div className={cn("font-medium text-slate-900 dark:text-white", showAll && "text-[13px] leading-snug")} title={`Technical name: ${r.config_name}`}>
                      {label.name}
                    </div>
                    <div className={cn("mt-0.5 leading-snug text-slate-500", showAll ? "line-clamp-2 text-[10.5px]" : "text-[11px]")} title={label.hint}>
                      {label.hint || r.description}
                    </div>
                  </td>
                  {cols.map((c) => {
                    const { v, isBest, delta } = cell(r, c);
                    return (
                      <td key={c.key} className={cn("py-3.5", showAll ? "px-1.5" : "px-2", groupStart.has(c.key) && divider)}>
                        <MetricValue c={c} v={v} isBest={isBest} delta={delta} compact={showAll} />
                      </td>
                    );
                  })}
                </motion.tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* tablets and phones: one card per version, measures grouped the same way */}
      <div className="grid gap-3 p-3 sm:grid-cols-2 lg:hidden">
        {rows.map((r) => {
          const label = configLabel(r.config_name);
          return (
            <div key={r.config_name} className="rounded-2xl border border-slate-200/80 bg-white/60 p-4 dark:border-white/[0.07] dark:bg-white/[0.02]">
              <div className="font-medium text-slate-900 dark:text-white">{label.name}</div>
              <div className="mt-0.5 text-[11px] leading-snug text-slate-500">{label.hint || r.description}</div>
              {groups.map((g) => (
                <div key={g.title} className="mt-3">
                  <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-400">{g.title}</div>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-3">
                    {g.cols.map((c) => {
                      const { v, isBest, delta } = cell(r, c);
                      return (
                        <div key={c.key}>
                          <div className="mb-1 text-[11px] text-slate-500">{c.short}</div>
                          <MetricValue c={c} v={v} isBest={isBest} delta={delta} align="left" />
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          );
        })}
      </div>

      <div className="flex items-center justify-between gap-3 border-t border-slate-100 px-5 py-2.5 text-xs dark:border-white/[0.05]">
        <span className="text-slate-500">
          {showAll ? `All ${COLS.length} measures` : `${cols.length} key measures`} · hover a measure for its meaning
        </span>
        <button onClick={() => setShowAll((s) => !s)} className="font-medium text-indigo-600 hover:underline dark:text-indigo-300">
          {showAll ? "Show key measures only" : `Show all ${COLS.length} measures`}
        </button>
      </div>
    </div>
  );
}

export default function EvaluationPage() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin"; // only administrators may start a run (it keeps the CPU busy for minutes)
  const ct = useChartTheme();
  const results = useQuery({ queryKey: qk.evalResults, queryFn: api.evalResults });
  const status = useQuery({
    queryKey: qk.evalStatus,
    queryFn: api.evalStatus,
    refetchInterval: (q) => (q.state.data?.status === "running" ? 2000 : false),
  });
  const prevStatus = useRef<string | undefined>(undefined);

  const st = status.data?.status;
  const running = st === "running";

  useEffect(() => {
    const prev = prevStatus.current;
    prevStatus.current = st;
    if (prev === "running" && st === "done") {
      toast.success("Benchmark complete", { description: status.data?.message });
      qc.invalidateQueries({ queryKey: qk.evalResults });
    } else if (prev === "running" && st === "error") {
      toast.error("Benchmark failed", { description: status.data?.message });
    }
  }, [st, status.data?.message, qc]);

  const run = useMutation({
    mutationFn: api.evalRun,
    onSuccess: () => {
      toast.message("Benchmark started", { description: "This can take a few minutes." });
      prevStatus.current = "running";
      qc.setQueryData(qk.evalStatus, { status: "running", progress: 0, message: "Starting…" });
      qc.invalidateQueries({ queryKey: qk.evalStatus });
    },
    onError: (e) => {
      if (e instanceof ApiError && e.status === 409) {
        toast.info("A benchmark is already running");
        prevStatus.current = "running";
        qc.invalidateQueries({ queryKey: qk.evalStatus });
      } else toast.error("Couldn't start benchmark", { description: errorMessage(e) });
    },
  });

  const report = results.data?.latest ?? null;
  const experiments = report?.experiments ?? [];
  const ablations = report?.ablations ?? [];
  const full =
    [...experiments, ...ablations].find((r) => /full/i.test(r.config_name)) ?? experiments[experiments.length - 1] ?? experiments[0];

  const seriesNames = experiments.slice(0, 8).map((e) => configLabel(e.config_name).short);
  const grouped = useMemo(
    () =>
      CHART_METRICS.map((m) => {
        const row: Record<string, number | string> = { metric: m.label };
        for (const e of experiments.slice(0, 8)) row[configLabel(e.config_name).short] = +(num(e, m.key) * (m.scale ?? 1)).toFixed(2);
        return row;
      }),
    [experiments],
  );
  const radarSeries = experiments.slice(0, 4);
  const perCategory = useMemo(
    () =>
      Object.entries(report?.per_category ?? {}).map(([k, v]) => ({
        category: categoryLabel(k),
        // unanswerable questions have no right document, so "found in top 5" does not apply to them
        "Right document in top 5": k === "unanswerable" ? null : v.recall_at_5,
        "Correct answer": v.answer_correctness,
        count: v.count,
      })),
    [report],
  );
  const latency = useMemo(
    // the ablation table repeats the full system as its baseline row; plot it only once
    () =>
      [...experiments, ...ablations.filter((r) => r.config_name !== "Full system")].map((r) => ({
        config: configLabel(r.config_name).short,
        "Typical time": num(r, "median_latency"),
        "Slowest 5%": r.p95_latency,
      })),
    [experiments, ablations],
  );

  const progress = Math.round((status.data?.progress ?? 0) * 100);

  return (
    <div>
      <PageHeader
        icon={<FlaskConical />}
        title="Evaluation"
        description="How well DocuMind finds the right document and answers correctly, measured on test questions whose answers are known."
        actions={
          isAdmin ? (
            <Button variant="gradient" onClick={() => run.mutate()} loading={run.isPending} disabled={running} leftIcon={<Play className="h-4 w-4" />}>
              {running ? "Running…" : "Run benchmark"}
            </Button>
          ) : undefined
        }
      />

      <AnimatePresence>
        {(running || st === "error") && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="mb-6 overflow-hidden">
            <Card className={cn("p-5", st === "error" && "border-rose-500/30")}>
              <div className="mb-3 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-sm font-medium text-slate-900 dark:text-white">
                  {running ? (
                    <span className="relative flex h-2.5 w-2.5">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-indigo-400 opacity-70" />
                      <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-indigo-500" />
                    </span>
                  ) : (
                    <XCircle className="h-4 w-4 text-rose-500" />
                  )}
                  {running ? "Benchmark in progress" : "Last benchmark failed"}
                </div>
                {running && <span className="font-mono text-sm tabular-nums text-slate-500">{progress}%</span>}
              </div>
              {running && <Progress value={progress} className="h-2" />}
              <p className="muted mt-2 text-xs" aria-live="polite">
                {status.data?.message}
              </p>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {results.isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-64 w-full rounded-2xl" />
          <div className="grid gap-4 lg:grid-cols-2">
            <Skeleton className="h-72 rounded-2xl" />
            <Skeleton className="h-72 rounded-2xl" />
          </div>
        </div>
      ) : results.isError ? (
        <Card>
          <ErrorState error={results.error} onRetry={() => results.refetch()} />
        </Card>
      ) : !report ? (
        <Card>
          <EmptyState
            icon={<FlaskConical />}
            title="No benchmark results yet"
            description="Run the benchmark to measure how often DocuMind finds the right document, answers correctly, cites the right source and refuses when the answer isn't in the documents."
            action={
              isAdmin ? (
                <Button variant="gradient" onClick={() => run.mutate()} loading={run.isPending} disabled={running} leftIcon={<Play className="h-4 w-4" />}>
                  Run benchmark
                </Button>
              ) : undefined
            }
          />
        </Card>
      ) : (
        <div className="space-y-5">
          {/* headline result first: DocuMind vs standard approaches */}
          <AdvancedEvaluation />

          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <Badge tone="indigo">
              <CheckCircle2 className="h-3 w-3" /> {report.total_queries} test questions
            </Badge>
            {report.corpus_documents ? <Badge>{report.corpus_documents} documents</Badge> : null}
            <Badge>{experiments.length} versions, built up one feature at a time</Badge>
            <Badge>{Math.max(0, ablations.length - 1)} features switched off one at a time</Badge>
            <span>Last run {formatDate(report.created_at, true)}</span>
          </div>

          <Card className="overflow-hidden">
            <CardHeader
              icon={<Trophy className="h-4 w-4" />}
              title="Building up the system"
              description="Starting from basic search, each row adds one feature to the row above, so you can see what every feature adds. The best value in each column is highlighted; hover a column name for its meaning."
            />
            <div className="mt-3">
              {experiments.length ? <MetricsTable rows={experiments} /> : <EmptyState icon={<Layers />} title="No experiments in this report" className="py-8" />}
            </div>
          </Card>

          {experiments.length > 0 && (
            <div className="grid gap-4 xl:grid-cols-5">
              <Card className="xl:col-span-3">
                <CardHeader icon={<Activity className="h-4 w-4" />} title="Scores as features are added" description="All scores out of 100 (ranking score multiplied by 100)" />
                <div className="px-5 pt-3">
                  <Legend items={seriesNames.map((n, i) => ({ label: n, color: ct.series[i] }))} />
                </div>
                <div className="p-3">
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={grouped} margin={{ top: 10, right: 8, left: -18, bottom: 0 }} barGap={2}>
                      <CartesianGrid vertical={false} stroke={ct.grid} />
                      <XAxis dataKey="metric" {...ct.axisProps} interval={0} tick={{ ...ct.axisProps.tick, fontSize: 10 }} />
                      <YAxis domain={[0, 100]} {...ct.axisProps} />
                      <RTooltip cursor={{ fill: ct.cursor }} content={<ChartTooltip formatter={(v) => v.toFixed(1)} />} />
                      {seriesNames.map((n, i) => (
                        <Bar key={n} dataKey={n} fill={ct.series[i]} radius={[4, 4, 0, 0]} maxBarSize={22} />
                      ))}
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </Card>
              <Card className="xl:col-span-2">
                <CardHeader icon={<RadarIcon className="h-4 w-4" />} title="Quality at a glance" description={experiments.length > 4 ? "First four versions; a bigger shape is better" : "A bigger shape is better"} />
                <div className="px-5 pt-3">
                  <Legend items={radarSeries.map((e, i) => ({ label: configLabel(e.config_name).short, color: ct.series[i] }))} />
                </div>
                <div className="p-3">
                  <ResponsiveContainer width="100%" height={300}>
                    <RadarChart data={grouped} outerRadius="72%">
                      <PolarGrid stroke={ct.grid} />
                      <PolarAngleAxis dataKey="metric" tick={{ fill: ct.axis, fontSize: 10 }} />
                      <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
                      {radarSeries.map((e, i) => (
                        <Radar key={e.config_name} dataKey={configLabel(e.config_name).short} stroke={ct.series[i]} fill={ct.series[i]} fillOpacity={0.12} strokeWidth={2} />
                      ))}
                      <RTooltip content={<ChartTooltip formatter={(v) => v.toFixed(1)} />} />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>
              </Card>
            </div>
          )}

          {ablations.length > 0 && (
            <Card className="overflow-hidden">
              <CardHeader
                icon={<Scale className="h-4 w-4" />}
                title="What each feature contributes"
                description="Each row is the full system with one feature switched off. Small numbers show the change versus the full system: green = better, red = worse. Big red drops mean the feature matters."
              />
              <div className="mt-3">
                <MetricsTable rows={ablations} highlightBest={false} baseline={full} />
              </div>
            </Card>
          )}

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader icon={<Layers className="h-4 w-4" />} title="Accuracy by question type" description="Full system, in % — e.g. reworded questions avoid the document's exact words" />
              <div className="px-5 pt-3">
                <Legend
                  items={[
                    { label: "Right document in top 5", color: ct.series[0] },
                    { label: "Correct answer", color: ct.series[1] },
                  ]}
                />
              </div>
              <div className="p-3">
                {perCategory.length === 0 ? (
                  <EmptyState icon={<Layers />} title="No category data" className="py-8" />
                ) : (
                  <ResponsiveContainer width="100%" height={320}>
                    <BarChart data={perCategory} margin={{ top: 10, right: 8, left: -18, bottom: 8 }} barGap={2}>
                      <CartesianGrid vertical={false} stroke={ct.grid} />
                      <XAxis
                        dataKey="category"
                        {...ct.axisProps}
                        interval={0}
                        angle={-30}
                        textAnchor="end"
                        height={64}
                        tick={{ ...ct.axisProps.tick, fontSize: 10 }}
                      />
                      <YAxis domain={[0, 100]} {...ct.axisProps} />
                      <RTooltip cursor={{ fill: ct.cursor }} content={<ChartTooltip formatter={(v) => `${v.toFixed(1)}%`} />} />
                      <Bar dataKey="Right document in top 5" fill={ct.series[0]} radius={[4, 4, 0, 0]} maxBarSize={22} />
                      <Bar dataKey="Correct answer" fill={ct.series[1]} radius={[4, 4, 0, 0]} maxBarSize={22} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
            </Card>
            <Card>
              <CardHeader
                icon={<Timer className="h-4 w-4" />}
                title="How long an answer takes"
                description="Seconds per question on a laptop CPU. The top rows build the system up from basic search to the full system; the rows below are the full system with one feature switched off."
              />
              <div className="px-5 pt-3">
                <Legend
                  items={[
                    { label: "Typical time", color: ct.series[0] },
                    { label: "Slowest 5%", color: ct.series[1] },
                  ]}
                />
              </div>
              <div className="p-3">
                <ResponsiveContainer width="100%" height={Math.max(220, latency.length * 34)}>
                  <BarChart data={latency} layout="vertical" margin={{ top: 4, right: 16, left: 4, bottom: 0 }} barGap={2}>
                    <CartesianGrid horizontal={false} stroke={ct.grid} />
                    <XAxis type="number" {...ct.axisProps} />
                    <YAxis type="category" dataKey="config" width={170} {...ct.axisProps} tick={{ ...ct.axisProps.tick, fontSize: 10 }} />
                    <RTooltip cursor={{ fill: ct.cursor }} content={<ChartTooltip formatter={(v) => `${v.toFixed(2)} s`} />} />
                    <Bar dataKey="Typical time" fill={ct.series[0]} radius={[0, 4, 4, 0]} maxBarSize={12} />
                    <Bar dataKey="Slowest 5%" fill={ct.series[1]} radius={[0, 4, 4, 0]} maxBarSize={12} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
