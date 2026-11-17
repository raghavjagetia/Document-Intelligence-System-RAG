import { memo, useMemo, useState, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { AnimatePresence, motion } from "framer-motion";
import { toast } from "sonner";
import { friendlyGeneration } from "../../lib/labels";
import {
  AlertTriangle,
  Bot,
  Check,
  ChevronRight,
  Copy,
  Cpu,
  FileText,
  Gauge,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  ThumbsDown,
  ThumbsUp,
  Timer,
  Wand2,
} from "lucide-react";
import { api, errorMessage } from "../../lib/api";
import { SourceViewer } from "./SourceViewer";
import type { Citation, Message } from "../../types";
import { cn, fmtPct, fmtSeconds, formatStyle, initials, toPct } from "../../lib/utils";
import { Badge, Popover, Tooltip } from "../ui";

export interface UIMessage extends Message {
  streaming?: boolean;
  error?: string;
  stopped?: boolean;
}

// ---------------------------------------------------------------- citations
const CITE_RE = /\[(\d+(?:\s*,\s*\d+)*)\](?!\()/g;

/** Turn `[1]`, `[1, 2]` markers into markdown links `[1](#cite-1)` that the renderer swaps for chips. */
function linkifyCitations(md: string): string {
  // Leave fenced code blocks untouched.
  return md
    .split(/(```[\s\S]*?```)/g)
    .map((part) =>
      part.startsWith("```")
        ? part
        : part.replace(CITE_RE, (_m, nums: string) =>
            nums
              .split(",")
              .map((n) => `[${n.trim()}](#cite-${n.trim()})`)
              .join(""),
          ),
    )
    .join("");
}

function RelevanceBar({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(100, toPct(value)));
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-200 dark:bg-white/10">
        <div className="bg-brand-gradient h-full rounded-full" style={{ width: `${pct}%` }} />
      </div>
      <span className="w-9 text-right font-mono text-[10px] tabular-nums text-slate-500">{pct.toFixed(0)}%</span>
    </div>
  );
}

function CitationCard({ c }: { c: Citation }) {
  return (
    <div className="space-y-2">
      <div className="flex items-start gap-2">
        <span className="bg-brand-gradient flex h-5 min-w-[20px] items-center justify-center rounded-md px-1 text-[10px] font-bold text-white">{c.citation_number}</span>
        <div className="min-w-0">
          <div className="truncate text-xs font-semibold text-slate-900 dark:text-white" title={c.filename}>
            {c.filename}
          </div>
          <div className="text-[11px] text-slate-500">
            Page {c.page_number}
            {c.section ? ` · ${c.section}` : ""}
          </div>
        </div>
      </div>
      {c.source_snippet && (
        <p className="line-clamp-5 rounded-lg bg-slate-100 p-2 text-[11px] leading-relaxed text-slate-600 dark:bg-white/5 dark:text-slate-300">
          “{c.source_snippet}”
        </p>
      )}
      <div>
        <div className="mb-1 text-[10px] uppercase tracking-wide text-slate-400">Relevance</div>
        <RelevanceBar value={c.relevance_score} />
      </div>
      {c.found_by && c.found_by.length > 0 && (
        <div className="text-[11px] text-slate-500">
          <span className="text-[10px] uppercase tracking-wide text-slate-400">Found by </span>
          {foundByText(c.found_by)}
        </div>
      )}
    </div>
  );
}

function foundByText(found: ("meaning" | "words")[]): string {
  if (found.length === 2) return "meaning + exact match";
  return found[0] === "meaning" ? "meaning only" : "exact match only";
}

function FoundByTag({ found }: { found?: ("meaning" | "words")[] }) {
  if (!found || found.length === 0) return null;
  const label = found.length === 2 ? "Meaning + exact match" : found[0] === "meaning" ? "By meaning" : "Exact match";
  return (
    <span className="truncate text-[9px] font-medium text-slate-400" title={`Found by ${foundByText(found)}`}>
      {label}
    </span>
  );
}

function CitationChip({ n, citation, onJump }: { n: number; citation?: Citation; onJump: (n: number) => void }) {
  const chip = (
    <button
      type="button"
      onClick={() => onJump(n)}
      className={cn(
        "mx-0.5 inline-flex h-[18px] min-w-[18px] -translate-y-px items-center justify-center rounded-md px-1 align-middle text-[10px] font-semibold no-underline transition-all",
        citation
          ? "bg-indigo-500/15 text-indigo-600 ring-1 ring-inset ring-indigo-500/25 hover:bg-indigo-500 hover:text-white dark:text-indigo-300"
          : "bg-slate-500/10 text-slate-500",
      )}
      aria-label={citation ? `Citation ${n}: ${citation.filename}, page ${citation.page_number}` : `Citation ${n}`}
    >
      {n}
    </button>
  );
  if (!citation) return chip;
  return (
    <Popover content={<CitationCard c={citation} />} width={320}>
      {chip}
    </Popover>
  );
}

function SourceCard({ c, highlighted, index, onOpen }: { c: Citation; highlighted: boolean; index: number; onOpen: (c: Citation) => void }) {
  const fmt = formatStyle(c.filename.slice(c.filename.lastIndexOf(".")));
  return (
    <motion.div
      id={`source-${c.chunk_id}-${c.citation_number}`}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0, scale: highlighted ? 1.03 : 1 }}
      transition={{ delay: index * 0.04 }}
    >
      <Popover content={<CitationCard c={c} />} width={320}>
        <button
          type="button"
          onClick={() => onOpen(c)}
          aria-label={`Show source ${c.citation_number} in ${c.filename}, page ${c.page_number}`}
          className={cn(
            "flex w-48 shrink-0 flex-col gap-1.5 rounded-xl border bg-white/60 p-2.5 text-left transition-all hover:-translate-y-0.5 hover:border-indigo-500/40 hover:shadow-md dark:bg-white/[0.03]",
            highlighted ? "border-indigo-500 ring-2 ring-indigo-500/30" : "border-slate-200 dark:border-white/[0.08]",
          )}
        >
          <div className="flex items-center gap-1.5">
            <span className="bg-brand-gradient flex h-4 min-w-[16px] items-center justify-center rounded px-1 text-[9px] font-bold text-white">{c.citation_number}</span>
            <span className={cn("rounded px-1 text-[9px] font-semibold", fmt.className)}>{fmt.label}</span>
            <span className="ml-auto text-[10px] text-slate-400">p.{c.page_number}</span>
          </div>
          <div className="truncate text-xs font-medium text-slate-800 dark:text-slate-100" title={c.filename}>
            {c.filename}
          </div>
          <div className="truncate text-[10px] text-slate-500">{c.section || "—"}</div>
          <RelevanceBar value={c.relevance_score} />
          <FoundByTag found={c.found_by} />
        </button>
      </Popover>
    </motion.div>
  );
}

// ---------------------------------------------------------------- user message
export function UserBubble({ m, username }: { m: UIMessage; username: string }) {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex justify-end gap-3">
      <div className="max-w-[85%] rounded-2xl rounded-tr-md bg-gradient-to-br from-indigo-500 to-violet-600 px-4 py-2.5 text-[0.94rem] leading-relaxed text-white shadow-lg shadow-indigo-500/20">
        <p className="whitespace-pre-wrap break-words">{m.content}</p>
      </div>
      <div className="hidden h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-200 text-[11px] font-semibold text-slate-600 dark:bg-white/10 dark:text-slate-200 sm:flex" aria-hidden>
        {initials(username)}
      </div>
    </motion.div>
  );
}

// ---------------------------------------------------------------- assistant message
function MetaBadge({ icon, children, tone = "neutral", tip }: { icon: ReactNode; children: ReactNode; tone?: "neutral" | "green" | "amber" | "indigo"; tip?: ReactNode }) {
  const b = (
    <Badge tone={tone} className="[&>svg]:h-3 [&>svg]:w-3">
      {icon}
      {children}
    </Badge>
  );
  return tip ? (
    <Tooltip label={tip}>
      <span tabIndex={0} className="rounded-full">
        {b}
      </span>
    </Tooltip>
  ) : (
    b
  );
}

export const AssistantMessage = memo(function AssistantMessage({
  m,
  question,
  onRegenerate,
  canRegenerate,
  canRate,
}: {
  m: UIMessage;
  question?: string;
  onRegenerate?: () => void;
  canRegenerate?: boolean;
  /** the viewer asked this question and may rate the answer (not in an administrator's read-only view) */
  canRate?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const [viewing, setViewing] = useState<Citation | null>(null);
  const [rating, setRating] = useState<1 | -1 | null>(m.feedback ?? null);
  const [savingRating, setSavingRating] = useState(false);

  const rate = async (value: 1 | -1) => {
    const next = rating === value ? 0 : value; // clicking the active thumb again clears it
    setSavingRating(true);
    try {
      await api.feedback(m.message_id, next);
      setRating(next === 0 ? null : next);
      if (next !== 0) toast.success(next === 1 ? "Thanks — marked as helpful" : "Thanks — marked as not helpful");
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setSavingRating(false);
    }
  };

  /** The parts of the answer that cite source n (what the viewer should highlight support for) */
  const focusFor = (c: Citation) => {
    const marker = `[${c.citation_number}]`;
    const parts = m.content.split(/\n+|(?<=[.!?।])\s+/).filter((p) => p.includes(marker));
    return (parts.length ? parts.join(" ") : m.content).slice(0, 5000);
  };
  const [showRewrite, setShowRewrite] = useState(false);
  const [highlight, setHighlight] = useState<number | null>(null);
  const byNum = useMemo(() => new Map(m.citations.map((c) => [c.citation_number, c])), [m.citations]);
  const md = useMemo(() => linkifyCitations(m.content), [m.content]);

  const jump = (n: number) => {
    const c = byNum.get(n);
    if (!c) return;
    setHighlight(n);
    setViewing(c);
    document.getElementById(`source-${c.chunk_id}-${c.citation_number}`)?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
    setTimeout(() => setHighlight((h) => (h === n ? null : h)), 1600);
  };

  const components = useMemo<Components>(
    () => ({
      a: ({ href, children, ...rest }) => {
        if (href?.startsWith("#cite-")) {
          const n = Number(href.slice(6));
          return <CitationChip n={n} citation={byNum.get(n)} onJump={jump} />;
        }
        return (
          <a href={href} target="_blank" rel="noreferrer noopener" {...rest}>
            {children}
          </a>
        );
      },
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [byNum],
  );

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(m.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("Couldn't copy to clipboard");
    }
  };

  const rewritten =
    m.rewritten_query && question && m.rewritten_query.trim().toLowerCase() !== question.trim().toLowerCase() ? m.rewritten_query : null;
  const finished = !m.streaming;
  const thinking = m.streaming && !m.content;
  const genMode = m.generation_mode ?? m.model_name;

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex gap-3">
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-white shadow-md",
          m.abstained ? "bg-amber-500 shadow-amber-500/30" : "bg-gradient-to-br from-indigo-500 via-violet-500 to-cyan-500 shadow-indigo-500/30",
        )}
        aria-hidden
      >
        {m.abstained ? <ShieldAlert className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>
      <div className="min-w-0 flex-1">
        {rewritten && (
          <button
            onClick={() => setShowRewrite((s) => !s)}
            className="mb-2 flex max-w-full items-center gap-1.5 text-[11px] text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
            aria-expanded={showRewrite}
          >
            <Wand2 className="h-3 w-3 shrink-0" />
            <span className="shrink-0">Understood as</span>
            <ChevronRight className={cn("h-3 w-3 shrink-0 transition-transform", showRewrite && "rotate-90")} />
            {!showRewrite && <span className="truncate italic">{rewritten}</span>}
          </button>
        )}
        <AnimatePresence>
          {rewritten && showRewrite && (
            <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
              <div className="mb-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs italic text-slate-600 dark:border-white/10 dark:bg-white/[0.03] dark:text-slate-300">
                {rewritten}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <div
          className={cn(
            "rounded-2xl rounded-tl-md px-4 py-3",
            m.abstained
              ? "border border-amber-500/30 bg-amber-500/[0.06]"
              : m.error
                ? "border border-rose-500/30 bg-rose-500/[0.05]"
                : "glass",
          )}
        >
          {m.abstained && finished && (
            <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-amber-700 dark:text-amber-400">
              <AlertTriangle className="h-3.5 w-3.5" /> Not enough evidence in your documents to answer confidently
            </div>
          )}
          {thinking ? (
            <div className="flex items-center gap-2 py-1 text-sm text-slate-500" role="status">
              <span className="flex gap-1">
                {[0, 1, 2].map((i) => (
                  <motion.span
                    key={i}
                    className="h-1.5 w-1.5 rounded-full bg-indigo-500"
                    animate={{ opacity: [0.3, 1, 0.3], y: [0, -3, 0] }}
                    transition={{ duration: 0.9, repeat: Infinity, delay: i * 0.15 }}
                  />
                ))}
              </span>
              {m.citations.length ? `Reading ${m.citations.length} sources…` : "Searching your documents…"}
            </div>
          ) : (
            <div className={cn("markdown break-words", m.streaming && "cursor-blink")}>
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
                {md}
              </ReactMarkdown>
            </div>
          )}
          {m.error && (
            <div className="mt-2 flex items-center gap-1.5 text-xs text-rose-600 dark:text-rose-400">
              <AlertTriangle className="h-3.5 w-3.5" /> {m.error}
            </div>
          )}
          {m.stopped && <div className="mt-2 text-xs italic text-slate-400">Generation stopped.</div>}
        </div>

        {m.citations.length > 0 && (
          <div className="mt-3">
            <div className="mb-1.5 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-slate-400">
              <FileText className="h-3 w-3" /> Sources
            </div>
            <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-2">
              {m.citations.map((c, i) => (
                <SourceCard key={`${c.chunk_id}-${c.citation_number}`} c={c} index={i} highlighted={highlight === c.citation_number} onOpen={setViewing} />
              ))}
            </div>
          </div>
        )}

        {finished && !m.error && m.message_id && !m.message_id.startsWith("tmp-") && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-2 flex flex-wrap items-center gap-1.5">
            <MetaBadge icon={<Gauge />} tone="indigo" tip="How sure DocuMind is that this answer is right">
              {fmtPct(m.confidence_score)} confidence
            </MetaBadge>
            {m.grounded ? (
              <MetaBadge icon={<ShieldCheck />} tone="green" tip="How much of the answer is backed by the cited sources (technical name: grounding)">
                Backed by sources {fmtPct(m.grounding_score)}
              </MetaBadge>
            ) : (
              <MetaBadge icon={<ShieldAlert />} tone="amber" tip="Some statements could not be matched to the cited sources - check them before relying on them">
                Partly backed by sources {fmtPct(m.grounding_score)}
              </MetaBadge>
            )}
            <MetaBadge icon={<Timer />}>{fmtSeconds(m.latency_seconds)}</MetaBadge>
            {genMode && (
              <MetaBadge icon={<Cpu />} tip={`Technical detail: ${genMode}${m.model_name ? ` · model ${m.model_name}` : ""}`}>
                <span className="max-w-[220px] truncate">{friendlyGeneration(genMode)}</span>
              </MetaBadge>
            )}
            <div className="ml-auto flex gap-0.5">
              {canRate && !m.abstained && (
                <>
                  <Tooltip label={rating === 1 ? "Marked helpful (click to undo)" : "Helpful"}>
                    <button
                      onClick={() => rate(1)}
                      disabled={savingRating}
                      aria-pressed={rating === 1}
                      aria-label="Mark answer as helpful"
                      className={cn(
                        "rounded-lg p-1.5 transition hover:bg-slate-500/10",
                        rating === 1 ? "text-emerald-500" : "text-slate-400 hover:text-slate-700 dark:hover:text-slate-200",
                      )}
                    >
                      <ThumbsUp className={cn("h-3.5 w-3.5", rating === 1 && "fill-current")} />
                    </button>
                  </Tooltip>
                  <Tooltip label={rating === -1 ? "Marked not helpful (click to undo)" : "Not helpful"}>
                    <button
                      onClick={() => rate(-1)}
                      disabled={savingRating}
                      aria-pressed={rating === -1}
                      aria-label="Mark answer as not helpful"
                      className={cn(
                        "rounded-lg p-1.5 transition hover:bg-slate-500/10",
                        rating === -1 ? "text-rose-500" : "text-slate-400 hover:text-slate-700 dark:hover:text-slate-200",
                      )}
                    >
                      <ThumbsDown className={cn("h-3.5 w-3.5", rating === -1 && "fill-current")} />
                    </button>
                  </Tooltip>
                </>
              )}
              <Tooltip label={copied ? "Copied!" : "Copy answer"}>
                <button onClick={copy} className="rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-500/10 hover:text-slate-700 dark:hover:text-slate-200" aria-label="Copy answer">
                  {copied ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
                </button>
              </Tooltip>
              {canRegenerate && onRegenerate && (
                <Tooltip label="Regenerate">
                  <button onClick={onRegenerate} className="rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-500/10 hover:text-slate-700 dark:hover:text-slate-200" aria-label="Regenerate answer">
                    <RefreshCw className="h-3.5 w-3.5" />
                  </button>
                </Tooltip>
              )}
            </div>
          </motion.div>
        )}
        {finished && (m.error || m.stopped) && canRegenerate && onRegenerate && (
          <button onClick={onRegenerate} className="mt-2 inline-flex items-center gap-1.5 text-xs font-medium text-indigo-600 hover:underline dark:text-indigo-400">
            <RefreshCw className="h-3 w-3" /> Retry
          </button>
        )}
      </div>
      <SourceViewer citation={viewing} focus={viewing ? focusFor(viewing) : ""} onClose={() => setViewing(null)} />
    </motion.div>
  );
});

