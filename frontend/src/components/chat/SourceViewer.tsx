import { Fragment, useEffect, useRef, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Download, ExternalLink, Highlighter, Info } from "lucide-react";
import { api, downloadDocumentFile } from "../../lib/api";
import type { Citation, SourceView } from "../../types";
import { cn } from "../../lib/utils";
import { Button, Drawer, ErrorState, Skeleton } from "../ui";

/**
 * Shows a cited passage inside its original document: the rendered PDF page with the supporting sentence
 * highlighted, or (for Word, HTML, spreadsheets, slides, text) the passage text with the sentence marked.
 */
export function SourceViewer({
  citation,
  focus,
  onClose,
}: {
  citation: Citation | null;
  /** the answer text that cites this source; decides which sentence gets highlighted */
  focus: string;
  onClose: () => void;
}) {
  const view = useQuery({
    queryKey: ["source-view", citation?.doc_id, citation?.chunk_id, citation?.page_number, focus],
    queryFn: () =>
      api.sourceView(citation!.doc_id, { chunk_id: citation!.chunk_id, page_number: citation!.page_number, focus }),
    enabled: !!citation,
    staleTime: Infinity,
    retry: false,
  });
  const v = view.data;

  return (
    <Drawer
      open={!!citation}
      onClose={onClose}
      className="max-w-3xl"
      title={citation?.filename ?? ""}
      subtitle={
        v
          ? v.kind === "pdf"
            ? `Page ${v.page_number} of ${v.page_count}${v.found ? " · cited sentence highlighted" : ""}`
            : `${v.page_number ? `Page ${v.page_number} · ` : ""}cited passage${v.found ? " · sentence highlighted" : ""}`
          : "Opening the source…"
      }
    >
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          {view.isLoading && <Skeleton className="aspect-[1/1.41] w-full rounded-xl" />}
          {view.error && <ErrorState error={view.error} onRetry={() => view.refetch()} />}
          {v && v.highlights.length > 0 && (
            <div className="mb-3 flex gap-2 rounded-xl border border-amber-400/40 bg-amber-300/10 px-3 py-2 text-xs text-slate-700 dark:text-slate-200">
              <Highlighter className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" />
              <div>
                <div className="font-medium text-amber-700 dark:text-amber-400">Supporting text</div>
                {v.highlights.map((h, i) => (
                  <div key={i} className="mt-0.5 italic">“{h}”</div>
                ))}
              </div>
            </div>
          )}
          {v && v.kind === "pdf" && <PdfPage v={v} />}
          {v && v.kind === "text" && <TextPassage v={v} />}
          {v && !v.found && (
            <p className="mt-3 flex items-center gap-1.5 text-xs text-slate-500">
              <Info className="h-3.5 w-3.5" />
              {v.kind === "pdf"
                ? "The exact sentence could not be located on the page (for example a scanned page without a text layer), so the cited page is shown."
                : "Showing the cited passage."}
            </p>
          )}
        </div>
        {citation && (
          <div className="flex flex-wrap gap-2 border-t border-slate-200 px-5 py-3 dark:border-white/10">
            <Link to={`/documents?doc=${encodeURIComponent(citation.doc_id)}`} onClick={onClose}>
              <Button variant="secondary" size="sm">
                <ExternalLink className="h-3.5 w-3.5" /> Document details
              </Button>
            </Link>
            <Button variant="ghost" size="sm" onClick={() => downloadDocumentFile(citation.doc_id, citation.filename)}>
              <Download className="h-3.5 w-3.5" /> Download original
            </Button>
          </div>
        )}
      </div>
    </Drawer>
  );
}

function PdfPage({ v }: { v: SourceView }) {
  const first = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // bring the highlight into view once the page image has laid out
    const t = setTimeout(() => first.current?.scrollIntoView({ behavior: "smooth", block: "center" }), 250);
    return () => clearTimeout(t);
  }, [v.image]);
  return (
    <div
      className="relative w-full overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm dark:border-white/10"
      style={{ aspectRatio: `1 / ${v.aspect_ratio ?? 1.414}` }}
    >
      <img src={v.image} alt={`Page ${v.page_number} of ${v.filename}`} className="absolute inset-0 h-full w-full" />
      {(v.boxes ?? []).map((b, i) => (
        <motion.div
          key={i}
          ref={i === 0 ? first : undefined}
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.15 + i * 0.05 }}
          className="pointer-events-none absolute rounded-sm bg-yellow-300/45 mix-blend-multiply ring-2 ring-amber-400/70"
          style={{ left: `${b.x * 100}%`, top: `${b.y * 100}%`, width: `${b.w * 100}%`, height: `${b.h * 100}%` }}
        />
      ))}
    </div>
  );
}

const norm = (s: string) => s.toLowerCase().replace(/[|*_`]/g, " ").replace(/\s+/g, " ").trim();

/** Marks the highlight sentences inside one line of passage text */
function markLine(line: string, highlights: string[]): ReactNode {
  // table rows ("| Total | 4,72,000 |") are highlighted whole when their cells make up a highlight
  if (line.trim().startsWith("|") && highlights.some((h) => norm(line) === norm(h))) {
    return <mark className="rounded bg-yellow-300/60 px-0.5 text-inherit dark:bg-yellow-400/30">{line}</mark>;
  }
  const lower = line.toLowerCase();
  const spans: [number, number][] = [];
  for (const h of highlights) {
    const i = lower.indexOf(h.toLowerCase());
    if (i >= 0) spans.push([i, i + h.length]);
  }
  if (!spans.length) return line;
  spans.sort((a, b) => a[0] - b[0]);
  const out: ReactNode[] = [];
  let pos = 0;
  spans.forEach(([s, e], k) => {
    if (s < pos) return;
    out.push(line.slice(pos, s));
    out.push(
      <mark key={k} className="rounded bg-yellow-300/60 px-0.5 text-inherit dark:bg-yellow-400/30">
        {line.slice(s, e)}
      </mark>,
    );
    pos = e;
  });
  out.push(line.slice(pos));
  return out;
}

function TextPassage({ v }: { v: SourceView }) {
  return (
    <div className="space-y-3">
      {(v.chunks ?? []).map((c) => (
        <div
          key={c.chunk_id}
          className={cn(
            "rounded-xl border p-3 text-sm leading-relaxed",
            c.cited
              ? "border-indigo-500/40 bg-indigo-500/[0.04] text-slate-800 dark:text-slate-100"
              : "border-slate-200 text-slate-500 dark:border-white/10 dark:text-slate-400",
          )}
        >
          <div className="mb-1.5 flex items-center gap-2 text-[10px] uppercase tracking-wide text-slate-400">
            {c.section && <span className="truncate">{c.section}</span>}
            {c.page_number ? <span>· page {c.page_number}</span> : null}
            {c.cited && <span className="ml-auto font-semibold text-indigo-500">cited passage</span>}
          </div>
          <div className="whitespace-pre-wrap break-words">
            {c.content.split("\n").map((line, i) => (
              <Fragment key={i}>
                {i > 0 && "\n"}
                {c.cited ? markLine(line, v.highlights) : line}
              </Fragment>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
