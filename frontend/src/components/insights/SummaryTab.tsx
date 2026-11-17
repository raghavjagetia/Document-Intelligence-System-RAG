import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { BookOpenText, CalendarDays, Clock, Copy, Hash, Layers3, Lightbulb, ListChecks, Quote, RefreshCw, Tags, Type } from "lucide-react";
import { api } from "../../lib/api";
import type { Summary } from "../../types";
import { Button, Card, ErrorState, Segmented, Skeleton, SkeletonText } from "../ui";
import { copyText, MethodPill, SectionTitle } from "./shared";

function wordCount(s: Summary) {
  const text = [s.overview, ...s.key_points, ...(s.sections ?? []).map((x) => x.summary), s.conclusion].join(" ");
  return text.split(/\s+/).filter(Boolean).length;
}

function summaryAsText(s: Summary, filename?: string) {
  const parts: string[] = [];
  if (filename) parts.push(`Summary — ${filename}`, "");
  if (s.overview) parts.push(s.overview, "");
  if (s.key_points.length) parts.push("Key points:", ...s.key_points.map((k, i) => `${i + 1}. ${k}`), "");
  if (s.sections?.length) parts.push("Section by section:", ...s.sections.map((x) => `- ${x.title}: ${x.summary}`), "");
  if (s.conclusion) parts.push(`Conclusion: ${s.conclusion}`, "");
  if (s.main_topics.length) parts.push(`Topics: ${s.main_topics.join(", ")}`);
  if (s.important_dates.length) parts.push(`Dates: ${s.important_dates.join(", ")}`);
  if (s.important_numbers.length) parts.push(`Numbers: ${s.important_numbers.join(", ")}`);
  return parts.join("\n").trim();
}

/** Split "36 months" → ["36", "months"], "₹5,10,000" → ["₹5,10,000", ""]. */
function splitNumber(x: string): [string, string] {
  const m = x.trim().match(/^([₹$€£¥]?\s?[\d][\d.,]*\s?%?)\s*(.*)$/);
  return m ? [m[1].trim(), m[2]] : [x, ""];
}

/** Sort dates chronologically when every entry parses; otherwise keep the extractor's order. */
function sortDates(dates: string[]) {
  const parsed = dates.map((d) => ({ d, t: Date.parse(d) }));
  return parsed.every((p) => !Number.isNaN(p.t)) ? parsed.sort((a, b) => a.t - b.t).map((p) => p.d) : dates;
}

const fade = (i: number) => ({ initial: { opacity: 0, y: 8 }, animate: { opacity: 1, y: 0 }, transition: { delay: i * 0.05, duration: 0.3 } });

export function SummaryTab({ docId }: { docId: string }) {
  const [type, setType] = useState<"short" | "detailed">("short");
  const q = useQuery({ queryKey: ["summary", docId, type], queryFn: () => api.summarize(docId, type), staleTime: Infinity });
  const qc = useQueryClient();
  // the server remembers summaries; Regenerate explicitly asks for a fresh one
  const regen = useMutation({
    mutationFn: () => api.summarize(docId, type, true),
    onSuccess: (data) => qc.setQueryData(["summary", docId, type], data),
  });
  const s = q.data?.summary;
  const words = s ? wordCount(s) : 0;
  const minutes = Math.max(1, Math.round(words / 200));
  const dates = useMemo(() => sortDates(s?.important_dates ?? []), [s]);

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-3">
          <Segmented
            ariaLabel="Summary length"
            value={type}
            onChange={setType}
            items={[
              { value: "short", label: "Short" },
              { value: "detailed", label: "Detailed" },
            ]}
          />
          <span className="hidden text-xs text-slate-500 dark:text-slate-400 md:inline">
            {type === "short" ? "Quick glance · 3 key points" : "Full breakdown · key points, every section, conclusion"}
          </span>
          {s && (
            <div className="flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
              <span className="inline-flex items-center gap-1">
                <Type className="h-3.5 w-3.5" />
                <b className="font-semibold tabular-nums text-slate-700 dark:text-slate-200">{words}</b> words
              </span>
              <span className="inline-flex items-center gap-1">
                <Clock className="h-3.5 w-3.5" />
                <b className="font-semibold tabular-nums text-slate-700 dark:text-slate-200">{minutes}</b> min read
              </span>
            </div>
          )}
        </div>
        <div className="flex min-w-0 items-center gap-2">
          {s?.method && <MethodPill method={s.method} />}
          <Button
            variant="outline"
            size="sm"
            disabled={!s}
            onClick={() => s && copyText(summaryAsText(s, q.data?.filename), "Summary copied")}
            leftIcon={<Copy className="h-3.5 w-3.5" />}
          >
            Copy
          </Button>
          <Button variant="ghost" size="sm" onClick={() => regen.mutate()} loading={regen.isPending || q.isFetching} leftIcon={<RefreshCw className="h-3.5 w-3.5" />}>
            Regenerate
          </Button>
        </div>
      </div>

      {q.isLoading && (
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="space-y-4 lg:col-span-2">
            <Card className="p-6">
              <Skeleton className="mb-4 h-3 w-24" />
              <SkeletonText lines={4} />
            </Card>
            <Card className="space-y-5 p-6">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="flex gap-3">
                  <Skeleton className="h-7 w-7 shrink-0 rounded-full" />
                  <SkeletonText lines={2} className="flex-1" />
                </div>
              ))}
            </Card>
          </div>
          <Card className="space-y-4 p-5">
            <Skeleton className="h-3 w-20" />
            <div className="flex flex-wrap gap-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-6 w-20 rounded-full" />
              ))}
            </div>
            <div className="grid grid-cols-2 gap-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-16 rounded-xl" />
              ))}
            </div>
          </Card>
        </div>
      )}
      {q.isError && (
        <Card>
          <ErrorState error={q.error} onRetry={() => q.refetch()} />
        </Card>
      )}

      {s && (
        <div key={type} className="grid gap-4 lg:grid-cols-3">
          {/* ---------------------------------------------------- main column */}
          <div className="min-w-0 space-y-4 lg:col-span-2">
            <motion.div {...fade(0)}>
              <Card className="relative overflow-hidden p-5 pl-6 sm:p-6 sm:pl-7">
                <span aria-hidden className="absolute inset-y-0 left-0 w-1 bg-gradient-to-b from-indigo-500 via-violet-500 to-cyan-500" />
                <Quote aria-hidden className="absolute right-5 top-4 h-12 w-12 text-indigo-500/[0.08] dark:text-indigo-300/[0.08]" />
                <SectionTitle icon={<BookOpenText />}>Overview</SectionTitle>
                <p className="mt-3 whitespace-pre-line sm:pr-12 text-[0.97rem] leading-7 text-slate-800 dark:text-slate-100 sm:text-[1.02rem] sm:leading-8">
                  {s.overview || "—"}
                </p>
              </Card>
            </motion.div>

            <motion.div {...fade(1)}>
              <Card className="p-5 sm:p-6">
                <SectionTitle
                  icon={<ListChecks />}
                  aside={<span className="rounded-full bg-slate-100 px-2 py-0.5 font-mono text-[11px] tabular-nums text-slate-500 dark:bg-white/5 dark:text-slate-400">{s.key_points.length}</span>}
                >
                  Key points
                </SectionTitle>
                {s.key_points.length === 0 ? (
                  <p className="muted mt-3 text-sm">No key points extracted.</p>
                ) : (
                  <ol className="relative mt-4">
                    {s.key_points.map((k, i) => {
                      const last = i === s.key_points.length - 1;
                      return (
                        <motion.li
                          key={i}
                          initial={{ opacity: 0, x: -6 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: 0.1 + Math.min(i, 12) * 0.05 }}
                          className="relative flex gap-3.5 pb-4 last:pb-0"
                        >
                          {!last && <span aria-hidden className="absolute bottom-0 left-[13px] top-8 w-px bg-gradient-to-b from-indigo-500/40 to-slate-200 dark:to-white/10" />}
                          <span className="relative z-[1] flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white text-[11px] font-bold tabular-nums text-indigo-600 ring-2 ring-indigo-500/30 dark:bg-[#15151f] dark:text-indigo-300 dark:ring-indigo-400/30">
                            {i + 1}
                          </span>
                          <p className="min-w-0 pt-1 text-sm leading-relaxed text-slate-700 dark:text-slate-200">{k}</p>
                        </motion.li>
                      );
                    })}
                  </ol>
                )}
              </Card>
            </motion.div>

            {(s.sections?.length ?? 0) > 0 ? (
              <motion.div {...fade(2)}>
                <Card className="p-5 sm:p-6">
                  <SectionTitle
                    icon={<Layers3 />}
                    aside={<span className="rounded-full bg-slate-100 px-2 py-0.5 font-mono text-[11px] tabular-nums text-slate-500 dark:bg-white/5 dark:text-slate-400">{s.sections!.length}</span>}
                  >
                    Section by section
                  </SectionTitle>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    {s.sections!.map((x, i) => (
                      <motion.div
                        key={`${x.title}-${i}`}
                        initial={{ opacity: 0, y: 6 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.1 + Math.min(i, 12) * 0.04 }}
                        className="rounded-xl border border-slate-200/80 border-l-[3px] border-l-indigo-500/60 bg-white/60 p-3.5 dark:border-white/[0.07] dark:border-l-indigo-400/50 dark:bg-white/[0.02]"
                      >
                        <div className="text-sm font-semibold text-slate-900 dark:text-white">{x.title}</div>
                        <p className="mt-1 text-[13px] leading-relaxed text-slate-600 dark:text-slate-300">{x.summary}</p>
                      </motion.div>
                    ))}
                  </div>
                </Card>
              </motion.div>
            ) : (
              type === "short" && (
                <motion.div {...fade(2)}>
                  <button
                    onClick={() => setType("detailed")}
                    className="flex w-full items-center justify-between gap-3 rounded-2xl border border-dashed border-indigo-500/30 px-5 py-3.5 text-left text-sm text-slate-600 transition hover:border-indigo-500/60 hover:bg-indigo-500/[0.04] dark:text-slate-300"
                  >
                    <span className="inline-flex items-center gap-2">
                      <Layers3 className="h-4 w-4 text-indigo-500" /> Want more? The detailed summary covers every section and adds a conclusion.
                    </span>
                    <span className="shrink-0 font-medium text-indigo-600 dark:text-indigo-300">Show detailed →</span>
                  </button>
                </motion.div>
              )
            )}

            {s.conclusion && (
              <motion.div {...fade(3)}>
                <Card className="border-indigo-500/25 bg-gradient-to-br from-indigo-500/[0.07] via-violet-500/[0.04] to-cyan-500/[0.05] p-5 dark:border-indigo-400/20 sm:p-6">
                  <div className="flex gap-3.5">
                    <span className="bg-brand-gradient flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-white shadow-lg shadow-indigo-500/25">
                      <Lightbulb className="h-4 w-4" />
                    </span>
                    <div className="min-w-0">
                      <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-indigo-600 dark:text-indigo-300">Conclusion</div>
                      <p className="mt-1.5 text-sm leading-relaxed text-slate-800 dark:text-slate-100">{s.conclusion}</p>
                    </div>
                  </div>
                </Card>
              </motion.div>
            )}
          </div>

          {/* ---------------------------------------------------- side column */}
          <div className="min-w-0 space-y-4">
            <motion.div {...fade(1)}>
              <Card className="p-5">
                <SectionTitle icon={<Tags />}>Main topics</SectionTitle>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {s.main_topics.length ? (
                    s.main_topics.map((t) => (
                      <span
                        key={t}
                        className="max-w-full truncate rounded-lg bg-indigo-500/[0.08] px-2.5 py-1 text-xs font-medium text-indigo-700 ring-1 ring-inset ring-indigo-500/20 dark:bg-indigo-400/10 dark:text-indigo-200 dark:ring-indigo-400/20"
                        title={t}
                      >
                        {t}
                      </span>
                    ))
                  ) : (
                    <p className="muted text-sm">None found</p>
                  )}
                </div>
              </Card>
            </motion.div>

            <motion.div {...fade(2)}>
              <Card className="p-5">
                <SectionTitle icon={<CalendarDays />}>Important dates</SectionTitle>
                {dates.length === 0 ? (
                  <p className="muted mt-3 text-sm">None found</p>
                ) : (
                  <ol className="mt-3">
                    {dates.map((d, i) => (
                      <li key={i} className="relative flex items-center gap-3 pb-2.5 last:pb-0">
                        {i < dates.length - 1 && <span aria-hidden className="absolute bottom-0 left-[13px] top-7 w-px bg-slate-200 dark:bg-white/10" />}
                        <span className="relative flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-sky-500/10 text-sky-600 ring-1 ring-inset ring-sky-500/20 dark:text-sky-300">
                          <CalendarDays className="h-3.5 w-3.5" />
                        </span>
                        <span className="min-w-0 truncate text-sm font-medium text-slate-800 dark:text-slate-100" title={d}>
                          {d}
                        </span>
                      </li>
                    ))}
                  </ol>
                )}
              </Card>
            </motion.div>

            <motion.div {...fade(3)}>
              <Card className="p-5">
                <SectionTitle icon={<Hash />}>Important numbers</SectionTitle>
                {s.important_numbers.length === 0 ? (
                  <p className="muted mt-3 text-sm">None found</p>
                ) : (
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    {s.important_numbers.map((n, i) => {
                      const [v, unit] = splitNumber(n);
                      return (
                        <div
                          key={i}
                          title={n}
                          className="min-w-0 rounded-xl border border-slate-200/80 bg-gradient-to-br from-white to-slate-50 px-3 py-2.5 dark:border-white/[0.06] dark:from-white/[0.04] dark:to-white/[0.01]"
                        >
                          <div className="truncate text-base font-semibold tabular-nums tracking-tight text-slate-900 dark:text-white">{v}</div>
                          <div className="truncate text-[11px] text-slate-500 dark:text-slate-400">{unit || "value"}</div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </Card>
            </motion.div>
          </div>
        </div>
      )}
    </div>
  );
}
