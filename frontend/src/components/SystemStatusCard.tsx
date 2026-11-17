import { motion } from "framer-motion";
import { AlertTriangle, Brain, CheckCircle2, Cpu, Database, Info, Layers, ScanText, ServerCog } from "lucide-react";
import type { ReactNode } from "react";
import { useSystemStatus } from "../hooks/queries";
import type { SystemStatus } from "../types";
import { cn } from "../lib/utils";
import { Badge, Card, CardHeader, ErrorState, Skeleton, Tooltip } from "./ui";

interface Row {
  key: string;
  label: string;
  icon: ReactNode;
  value: string;
  detail?: string;
  ok: boolean;
  note?: string;
  /** Optional component: when inactive it is shown as a neutral mode, not a warning */
  inactiveLabel?: string;
}

export function statusRows(s: SystemStatus): Row[] {
  return [
    {
      key: "embedding",
      label: "Meaning search",
      icon: <Brain className="h-4 w-4" />,
      value: s.embedding.model,
      detail: `AI model · ${s.embedding.dimension} dimensions`,
      ok: s.embedding.type === "neural",
      note: "The AI meaning-search model is not available, so a simpler word-based fallback is used. Search quality is reduced.",
    },
    {
      key: "reranker",
      label: "AI re-ranker",
      icon: <Layers className="h-4 w-4" />,
      value: s.reranker.model,
      detail: s.reranker.type === "cross-encoder" ? "double-checks the best matches" : "simple fallback",
      ok: s.reranker.type === "cross-encoder",
      note: "The AI re-ranking model is not available, so results are ordered by word overlap instead.",
    },
    {
      key: "llm",
      label: "AI answers",
      icon: <Cpu className="h-4 w-4" />,
      value: s.llm.available ? s.llm.model : "Quotes from your documents",
      detail: s.llm.available ? s.llm.provider : "no API key set",
      ok: s.llm.available && !(s.llm.paused_seconds ?? 0),
      inactiveLabel: s.llm.available ? "Paused" : "Offline mode",
      note: s.llm.available
        ? `The AI service's free-tier limit is used up for now, so answers are quoted directly from your documents. It resumes automatically in about ${Math.max(1, Math.ceil((s.llm.paused_seconds ?? 0) / 60))} min.`
        : "No AI service key is set, so answers are quoted directly from your documents (works fully offline). Add GROQ_API_KEY, GEMINI_API_KEY or ANTHROPIC_API_KEY to .env and restart to get written answers.",
    },
    {
      key: "ocr",
      label: "Reads scanned pages",
      icon: <ScanText className="h-4 w-4" />,
      value: s.ocr.engine || "—",
      detail: s.ocr.available ? "available" : "unavailable",
      ok: s.ocr.available,
      note: "The text-recognition (OCR) engine is not installed, so scanned PDFs and images cannot be read.",
    },
    {
      key: "vector",
      label: "Search index",
      icon: <Database className="h-4 w-4" />,
      value: s.vector_index === "faiss" ? "FAISS" : "NumPy",
      detail: s.vector_index === "faiss" ? "exact search" : "basic search",
      ok: s.vector_index === "faiss",
      note: "FAISS is not installed, so a basic search is used (fine for small libraries, slower for large ones).",
    },
  ];
}

export function StatusPill({ ok, note, inactiveLabel }: { ok: boolean; note?: string; inactiveLabel?: string }) {
  if (ok)
    return (
      <Badge tone="green">
        <CheckCircle2 className="h-3 w-3" /> Active
      </Badge>
    );
  if (inactiveLabel)
    return (
      <Tooltip label={note ?? inactiveLabel} width={280}>
        <span tabIndex={0} className="rounded-full" aria-label={`${inactiveLabel}: ${note ?? ""}`}>
          <Badge tone="indigo" className="cursor-help">
            <Info className="h-3 w-3" /> {inactiveLabel}
          </Badge>
        </span>
      </Tooltip>
    );
  return (
    <Tooltip label={note ?? "Fallback in use"} width={260}>
      <span tabIndex={0} className="rounded-full" aria-label={`Fallback: ${note ?? ""}`}>
        <Badge tone="amber" className="cursor-help">
          <AlertTriangle className="h-3 w-3" /> Fallback
        </Badge>
      </span>
    </Tooltip>
  );
}

export function SystemStatusCard({ className, showFormats = false }: { className?: string; showFormats?: boolean }) {
  const q = useSystemStatus();
  const rows = q.data ? statusRows(q.data) : [];
  const healthy = rows.filter((r) => r.ok || r.inactiveLabel).length;
  return (
    <Card className={cn("flex flex-col", className)}>
      <CardHeader
        icon={<ServerCog className="h-4 w-4" />}
        title="System status"
        description={q.data ? `${healthy}/${rows.length} components at full capability` : "AI pipeline components"}
        action={
          q.data && (
            <span className="relative flex h-2.5 w-2.5" aria-hidden>
              <span
                className={cn(
                  "absolute inline-flex h-full w-full animate-ping rounded-full opacity-60",
                  healthy === rows.length ? "bg-emerald-400" : "bg-amber-400",
                )}
              />
              <span className={cn("relative inline-flex h-2.5 w-2.5 rounded-full", healthy === rows.length ? "bg-emerald-500" : "bg-amber-500")} />
            </span>
          )
        }
      />
      <div className="flex-1 p-3">
        {q.isLoading &&
          Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-center gap-3 px-2 py-2.5">
              <Skeleton className="h-8 w-8 rounded-lg" />
              <div className="flex-1 space-y-1.5">
                <Skeleton className="h-3 w-24" />
                <Skeleton className="h-2.5 w-36" />
              </div>
            </div>
          ))}
        {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} className="py-6" />}
        {rows.map((r, i) => (
          <motion.div
            key={r.key}
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.05 }}
            className="flex items-center gap-3 rounded-xl px-2 py-2.5 transition-colors hover:bg-slate-100/70 dark:hover:bg-white/[0.03]"
          >
            <div
              className={cn(
                "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
                r.ok
                  ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                  : r.inactiveLabel
                    ? "bg-indigo-500/10 text-indigo-600 dark:text-indigo-300"
                    : "bg-amber-500/10 text-amber-600 dark:text-amber-400",
              )}
            >
              {r.icon}
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-xs text-slate-500 dark:text-slate-400">{r.label}</div>
              <div className="truncate text-sm font-medium text-slate-900 dark:text-white" title={r.value}>
                {r.value}
                {r.detail && <span className="ml-1.5 text-xs font-normal text-slate-400">· {r.detail}</span>}
              </div>
            </div>
            <StatusPill ok={r.ok} note={r.note} inactiveLabel={r.inactiveLabel} />
          </motion.div>
        ))}
        {showFormats && q.data && (
          <div className="mt-2 border-t border-slate-200 px-2 pt-3 dark:border-white/10">
            <div className="mb-2 text-xs text-slate-500 dark:text-slate-400">Supported formats</div>
            <div className="flex flex-wrap gap-1.5">
              {q.data.supported_formats.map((f) => (
                <Badge key={f} tone="indigo">
                  {f}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
