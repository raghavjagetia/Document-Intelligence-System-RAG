import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ArrowUpRight, BadgeCheck, Clock, Info, Scale, Sparkles, TrendingUp, Trophy } from "lucide-react";
import { api } from "../../lib/api";
import { cn } from "../../lib/utils";
import { Badge, Card, CardHeader, EmptyState, ErrorState, Segmented, Skeleton } from "../ui";

// ---------------------------------------------------------------- report shape (backend/advanced_eval.py)
type CI = [number, number];
interface SystemRow {
  key: string;
  name: string;
  description: string;
  done: boolean;
  answer_correctness?: number;
  ci?: CI;
  answer_correctness_test?: number;
  ci_test?: CI;
  abstention_accuracy?: number | null;
  recall_at_1?: number | null;
  faithfulness?: number | null;
}
interface Significance {
  first: string;
  second: string;
  only_first_correct: number;
  only_second_correct: number;
  p_value: number;
}
export interface AdvancedReport {
  created_at: string;
  llm: string;
  questions: number;
  status: { complete: boolean; finished_stages: string[]; pending_stages: string[]; paused_reason: string | null };
  systems: SystemRow[];
  significance: Significance[];
}

const OURS = "documind_llm";
/** Short, friendly names and one-line explanations shown under each bar */
const SYSTEM_INFO: Record<string, { short: string; blurb: string; bar: string }> = {
  llm_only: { short: "AI model alone", blurb: "No documents — answers from its own knowledge", bar: "bg-slate-400 dark:bg-slate-500" },
  langchain: { short: "Standard RAG (LangChain)", blurb: "The textbook pipeline, same AI model", bar: "bg-amber-400" },
  documind_offline: { short: "DocuMind, offline", blurb: "No AI model — answers quoted from documents", bar: "bg-cyan-500" },
  documind_llm: { short: "DocuMind + AI", blurb: "Full pipeline with the same AI model", bar: "bg-gradient-to-r from-indigo-500 via-violet-500 to-cyan-400" },
};

function pValueText(p: number) {
  return p < 0.001 ? "p < 0.001" : `p = ${p.toFixed(p < 0.01 ? 4 : 3)}`;
}

function useAdvancedReport() {
  const q = useQuery({ queryKey: ["eval-advanced"], queryFn: api.evalAdvanced, refetchInterval: 60_000 });
  return { q, r: q.data?.report as AdvancedReport | null | undefined };
}

/** Headline numbers: our score, the lead over standard LangChain RAG and whether it is significant */
function headline(r: AdvancedReport) {
  const ours = r.systems.find((s) => s.key === OURS && s.done);
  const lc = r.systems.find((s) => s.key === "langchain" && s.done);
  const sig = r.significance.find((s) => s.second.includes("LangChain"));
  const lead = ours?.answer_correctness != null && lc?.answer_correctness != null ? ours.answer_correctness - lc.answer_correctness : null;
  return { ours, lc, sig, lead };
}

// ---------------------------------------------------------------- one score bar
function ScoreBar({
  row,
  split,
  compact,
  index,
}: {
  row: SystemRow;
  split: "all" | "test";
  compact?: boolean;
  index: number;
}) {
  const info = SYSTEM_INFO[row.key] ?? { short: row.name, blurb: row.description, bar: "bg-indigo-500" };
  const ours = row.key === OURS;
  const value = split === "all" ? row.answer_correctness : row.answer_correctness_test;
  const ci = split === "all" ? row.ci : row.ci_test;

  if (!row.done || value == null || !ci) {
    return (
      <div className="flex items-center justify-between py-1 text-sm text-slate-400">
        <span>{info.short}</span>
        <span className="flex items-center gap-1 text-xs">
          <Clock className="h-3 w-3" /> pending
        </span>
      </div>
    );
  }
  return (
    <div className={cn("group rounded-xl transition-colors", ours && !compact && "bg-indigo-500/[0.04] p-3 ring-1 ring-indigo-500/15 dark:bg-indigo-400/[0.06]", !ours && !compact && "px-3 py-2")}>
      <div className="mb-1.5 flex items-end justify-between gap-3">
        <div className="min-w-0">
          <div className={cn("flex items-center gap-1.5 truncate font-medium", compact ? "text-[13px]" : "text-sm", ours ? "text-slate-900 dark:text-white" : "text-slate-700 dark:text-slate-200")}>
            {ours && <Trophy className="h-3.5 w-3.5 shrink-0 text-amber-500" />}
            {info.short}
            {ours && !compact && <Badge tone="indigo" className="ml-1">this project</Badge>}
          </div>
          {!compact && <div className="truncate text-[11px] text-slate-400">{info.blurb}</div>}
        </div>
        <div className="shrink-0 text-right" title={`95% range: ${ci[0]}–${ci[1]}%`}>
          <span className={cn("font-semibold tabular-nums", compact ? "text-sm" : "text-lg", ours ? "text-indigo-600 dark:text-indigo-300" : "text-slate-800 dark:text-slate-100")}>
            {value.toFixed(1)}%
          </span>
          {!compact && <div className="text-[10px] tabular-nums text-slate-400">range {ci[0].toFixed(0)}–{ci[1].toFixed(0)}%</div>}
        </div>
      </div>
      <div className={cn("relative overflow-visible rounded-full bg-slate-100 dark:bg-white/[0.06]", compact ? "h-2.5" : "h-3.5")}>
        <motion.div
          className={cn("absolute inset-y-0 left-0 rounded-full", info.bar, ours && "shadow-[0_0_12px_rgba(99,102,241,0.45)]")}
          initial={{ width: 0 }}
          animate={{ width: `${value}%` }}
          transition={{ duration: 0.9, delay: 0.1 + index * 0.08, ease: [0.22, 1, 0.36, 1] }}
        />
        {/* 95% range: where the true score plausibly lies */}
        <motion.div
          className="absolute -inset-y-1 rounded-full border border-slate-900/25 bg-slate-900/[0.07] dark:border-white/30 dark:bg-white/[0.08]"
          style={{ left: `${ci[0]}%`, width: `${Math.max(0.8, ci[1] - ci[0])}%` }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 + index * 0.08 }}
        />
      </div>
    </div>
  );
}

function RangeLegend() {
  return (
    <div className="flex items-center gap-2 text-[11px] text-slate-400">
      <span className="inline-block h-2.5 w-6 rounded-full border border-slate-900/25 bg-slate-900/[0.07] dark:border-white/30 dark:bg-white/[0.08]" />
      shaded band = 95% range (where the true score plausibly lies)
    </div>
  );
}

// ---------------------------------------------------------------- dashboard card
/** Compact Dashboard version: the four systems' scores with their 95% ranges */
export function EvaluationSummaryCard() {
  const { q, r } = useAdvancedReport();
  const h = r ? headline(r) : null;
  return (
    <Card className="flex flex-col">
      <CardHeader
        icon={<Scale className="h-4 w-4" />}
        title="How DocuMind compares"
        description={r ? `% of ${r.questions} test questions answered correctly` : "Benchmark against standard approaches"}
        action={
          <div className="flex items-center gap-2">
            {h?.lead != null && (
              <span className="hidden items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-600 sm:inline-flex dark:text-emerald-400">
                <TrendingUp className="h-3 w-3" /> +{h.lead.toFixed(1)} pts vs LangChain
              </span>
            )}
            <Link to="/evaluation" className="inline-flex items-center gap-0.5 text-xs font-medium text-indigo-600 hover:underline dark:text-indigo-400">
              Details <ArrowUpRight className="h-3 w-3" />
            </Link>
          </div>
        }
      />
      <div className="flex-1 space-y-3.5 p-5 pt-4">
        {q.isLoading ? (
          <Skeleton className="h-36 w-full" />
        ) : !r ? (
          <EmptyState icon={<Clock />} title="Not run yet" description="Run python evaluation/run_advanced.py to compare DocuMind with standard approaches." className="py-6" />
        ) : (
          <>
            {r.systems.map((s, i) => (
              <ScoreBar key={s.key} row={s} split="all" compact index={i} />
            ))}
            <RangeLegend />
          </>
        )}
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------- evaluation page section
function StatTile({ icon, label, value, sub, tone }: { icon: JSX.Element; label: string; value: string; sub: string; tone: "indigo" | "emerald" | "violet" }) {
  const tones = {
    indigo: "from-indigo-500/15 to-indigo-500/[0.03] text-indigo-600 dark:text-indigo-300",
    emerald: "from-emerald-500/15 to-emerald-500/[0.03] text-emerald-600 dark:text-emerald-400",
    violet: "from-violet-500/15 to-violet-500/[0.03] text-violet-600 dark:text-violet-300",
  }[tone];
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn("rounded-2xl border border-slate-200/70 bg-gradient-to-br p-4 dark:border-white/[0.08]", tones)}
    >
      <div className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide opacity-80 [&>svg]:h-3.5 [&>svg]:w-3.5">
        {icon}
        {label}
      </div>
      <div className="mt-1.5 text-3xl font-semibold tabular-nums tracking-tight">{value}</div>
      <div className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{sub}</div>
    </motion.div>
  );
}

/** A metric value as a pill whose colour strength follows the score */
function MetricPill({ value }: { value: number | null | undefined }) {
  if (value == null) return <span className="text-xs text-slate-300 dark:text-slate-600">n/a</span>;
  const strong = value >= 95 ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300" : value >= 85 ? "bg-lime-500/15 text-lime-700 dark:text-lime-300" : value >= 60 ? "bg-amber-500/15 text-amber-700 dark:text-amber-300" : "bg-rose-500/15 text-rose-700 dark:text-rose-300";
  return <span className={cn("inline-block min-w-[58px] rounded-full px-2 py-0.5 text-center text-xs font-semibold tabular-nums", strong)}>{value.toFixed(1)}%</span>;
}

function Comparison({ r }: { r: AdvancedReport }) {
  const [split, setSplit] = useState<"all" | "test">("all");
  const { ours, sig, lead } = headline(r);
  const done = r.systems.filter((s) => s.done);
  return (
    <Card className="overflow-hidden">
      <CardHeader
        icon={<Scale className="h-4 w-4" />}
        title="Compared with standard approaches"
        description={`The same ${r.questions} questions and documents, answered with the same AI model (${r.llm.split("/").pop()}).`}
        action={
          !r.status.complete ? (
            <Badge tone="amber">
              <Clock className="h-3 w-3" /> in progress
            </Badge>
          ) : undefined
        }
      />
      <div className="space-y-6 p-5">
        {/* headline tiles */}
        <div className="grid gap-3 sm:grid-cols-3">
          <StatTile
            icon={<Trophy />}
            label="DocuMind + AI"
            value={ours?.answer_correctness != null ? `${ours.answer_correctness.toFixed(1)}%` : "–"}
            sub={ours?.ci ? `correct · range ${ours.ci[0].toFixed(0)}–${ours.ci[1].toFixed(0)}%` : "pending"}
            tone="indigo"
          />
          <StatTile
            icon={<TrendingUp />}
            label="Lead over LangChain"
            value={lead != null ? `+${lead.toFixed(1)}` : "–"}
            sub={lead != null ? "percentage points, same AI model" : "pending"}
            tone="emerald"
          />
          <StatTile
            icon={<BadgeCheck />}
            label="Is it real?"
            value={sig ? (sig.p_value < 0.05 ? "Yes" : "Not yet") : "–"}
            sub={sig ? `${sig.only_first_correct} wins vs ${sig.only_second_correct} losses · ${pValueText(sig.p_value)}` : "pending"}
            tone="violet"
          />
        </div>

        {/* score bars */}
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="text-sm font-medium text-slate-700 dark:text-slate-200">Correct answers</div>
            <Segmented
              size="sm"
              ariaLabel="Which questions"
              value={split}
              onChange={setSplit}
              items={[
                { value: "all", label: "All questions", hint: "All benchmark questions" },
                { value: "test", label: "Held-out", hint: "Only questions never used while tuning the system" },
              ]}
            />
          </div>
          <div className="space-y-1.5">
            {r.systems.map((s, i) => (
              <ScoreBar key={`${s.key}-${split}`} row={s} split={split} index={i} />
            ))}
          </div>
          <RangeLegend />
        </div>

        {/* other quality metrics */}
        {done.length > 0 && (
          <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-white/10">
            <table className="w-full min-w-[560px] text-sm">
              <thead>
                <tr className="bg-slate-50 text-left text-[11px] uppercase tracking-wide text-slate-400 dark:bg-white/[0.03]">
                  <th className="px-4 py-2.5 font-medium">System</th>
                  <th className="px-3 py-2.5 text-center font-medium" title="Refuses exactly when the documents do not contain the answer">Refuses correctly</th>
                  <th className="px-3 py-2.5 text-center font-medium" title="The right document is the first one found">Right document first</th>
                  <th className="px-3 py-2.5 text-center font-medium" title="Share of answer statements backed by the retrieved text">Backed by sources</th>
                </tr>
              </thead>
              <tbody>
                {done.map((s) => (
                  <tr key={s.key} className={cn("border-t border-slate-100 dark:border-white/[0.06]", s.key === OURS && "bg-indigo-500/[0.04] dark:bg-indigo-400/[0.05]")}>
                    <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-200">
                      <span className="flex items-center gap-1.5">
                        {s.key === OURS && <Sparkles className="h-3.5 w-3.5 text-indigo-500" />}
                        {SYSTEM_INFO[s.key]?.short ?? s.name}
                      </span>
                    </td>
                    <td className="px-3 text-center">
                      <MetricPill value={s.abstention_accuracy} />
                    </td>
                    <td className="px-3 text-center">
                      <MetricPill value={s.recall_at_1} />
                    </td>
                    <td className="px-3 text-center">
                      <MetricPill value={s.faithfulness} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <p className="flex items-start gap-1.5 text-[11px] leading-relaxed text-slate-400">
          <Info className="mt-px h-3.5 w-3.5 shrink-0" />
          Ranges are 95% Wilson confidence intervals. "Is it real?" uses an exact McNemar test on the questions one system answered correctly and the other did not; p below 0.05 means the difference is very unlikely to be luck.
        </p>
      </div>
    </Card>
  );
}

/** Evaluation page: the comparison with standard approaches */
export function AdvancedEvaluation() {
  const { q, r } = useAdvancedReport();
  if (q.isLoading) return <Skeleton className="h-64 w-full rounded-2xl" />;
  if (q.error) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!r) {
    return (
      <Card>
        <CardHeader icon={<Scale className="h-4 w-4" />} title="Compared with standard approaches" />
        <EmptyState
          icon={<Clock />}
          title="Not run yet"
          description="Run  python evaluation/run_advanced.py  to compare DocuMind with the AI model alone and a standard LangChain pipeline."
          className="py-10"
        />
      </Card>
    );
  }
  return <Comparison r={r} />;
}
