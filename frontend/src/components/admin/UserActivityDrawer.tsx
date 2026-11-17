import { useEffect, useMemo, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  Bot,
  CalendarClock,
  ChevronRight,
  Clock3,
  Eye,
  FileText,
  Gauge,
  HardDrive,
  MessageSquareText,
  MessagesSquare,
  ShieldCheck,
  ShieldOff,
  Timer,
  X,
} from "lucide-react";
import { Bar, BarChart, ResponsiveContainer, Tooltip as RTooltip, XAxis, YAxis } from "recharts";
import { api } from "../../lib/api";
import { capitalize, cn, fmtPct, fmtSeconds, formatBytes, formatDate, initials, timeAgo } from "../../lib/utils";
import type { AdminUserRow, Message } from "../../types";
import { Badge, DomainBadge, Drawer, EmptyState, ErrorState, Skeleton, Tabs } from "../ui";
import { FileIcon } from "../Brand";
import { ChartTooltip, useChartTheme } from "../charts";

const shortDay = (d: unknown) => {
  const dt = new Date(String(d));
  return Number.isNaN(dt.getTime()) ? String(d) : dt.toLocaleDateString(undefined, { day: "numeric", month: "short" });
};

function Stat({ icon, label, value, hint, delay }: { icon: ReactNode; label: string; value: ReactNode; hint?: string; delay: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.3 }}
      className="rounded-2xl border border-slate-200/80 bg-white/70 p-3.5 dark:border-white/[0.07] dark:bg-white/[0.03]"
    >
      <div className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
        <span className="text-indigo-500 dark:text-indigo-300 [&>svg]:h-3.5 [&>svg]:w-3.5">{icon}</span>
        {label}
      </div>
      <div className="mt-1.5 text-xl font-semibold tabular-nums text-slate-900 dark:text-white">{value}</div>
      {hint && <div className="muted mt-0.5 text-[11px]">{hint}</div>}
    </motion.div>
  );
}

function Transcript({ cid, owner, onBack }: { cid: string; owner: string; onBack?: () => void }) {
  const q = useQuery({ queryKey: ["admin-conv", cid], queryFn: () => api.adminConversation(cid) });
  const msgs: Message[] = q.data?.messages ?? [];
  return (
    <div className="flex min-h-full flex-col">
      <div className="sticky top-0 z-10 border-b border-slate-200/70 bg-white/80 px-5 py-3 backdrop-blur dark:border-white/[0.06] dark:bg-[#0c0c14]/80">
        {onBack && (
          <button
            onClick={onBack}
            className="mb-2 inline-flex items-center gap-1.5 text-xs font-medium text-indigo-600 hover:underline dark:text-indigo-300"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Back to profile
          </button>
        )}
        <div className="truncate text-sm font-semibold text-slate-900 dark:text-white">
          {q.data?.conversation.title ?? (q.isLoading ? "Loading…" : "Conversation")}
        </div>
        <div className="muted mt-0.5 flex items-center gap-1.5 text-xs">
          <Eye className="h-3.5 w-3.5" /> Read-only transcript · {owner} · {msgs.length} messages
        </div>
      </div>
      <div className="flex-1 space-y-5 p-5">
        {q.isLoading &&
          Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className={cn("h-16 rounded-2xl", i % 2 ? "w-4/5" : "ml-auto w-3/5")} />
          ))}
        {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
        {msgs.map((m, i) => {
          const mine = m.role === "user";
          return (
            <motion.div
              key={m.message_id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: Math.min(i, 12) * 0.03 }}
              className={cn("flex items-end gap-2.5", mine && "flex-row-reverse")}
            >
              <div
                className={cn(
                  "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold",
                  mine
                    ? "bg-gradient-to-br from-indigo-500 to-violet-500 text-white"
                    : "bg-slate-100 text-slate-500 ring-1 ring-slate-200 dark:bg-white/[0.06] dark:text-slate-300 dark:ring-white/10",
                )}
              >
                {mine ? initials(owner) : <Bot className="h-4 w-4" />}
              </div>
              <div className={cn("max-w-[82%]", mine && "text-right")}>
                <div
                  className={cn(
                    "inline-block rounded-2xl px-4 py-2.5 text-left text-sm leading-relaxed",
                    mine
                      ? "rounded-br-md bg-gradient-to-br from-indigo-500 to-violet-500 text-white shadow-lg shadow-indigo-500/20"
                      : "rounded-bl-md border border-slate-200 bg-white text-slate-800 dark:border-white/[0.08] dark:bg-white/[0.04] dark:text-slate-100",
                  )}
                >
                  <div className="whitespace-pre-wrap">{m.content}</div>
                </div>
                {!mine && (
                  <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                    {m.abstained ? (
                      <Badge tone="amber">refused - not in documents</Badge>
                    ) : (
                      <>
                        <Badge tone="green">confidence {fmtPct(m.confidence_score)}</Badge>
                        {m.grounded && <Badge tone="indigo">backed by sources</Badge>}
                      </>
                    )}
                    {m.latency_seconds > 0 && <Badge tone="neutral">{fmtSeconds(m.latency_seconds)}</Badge>}
                    {m.citations.slice(0, 3).map((c) => (
                      <span
                        key={c.citation_number}
                        title={c.source_snippet}
                        className="inline-flex max-w-[180px] items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-600 dark:bg-white/[0.06] dark:text-slate-300"
                      >
                        <FileText className="h-3 w-3 shrink-0" />
                        <span className="truncate">{c.filename}</span>
                        <span className="shrink-0 text-slate-400">p.{c.page_number}</span>
                      </span>
                    ))}
                  </div>
                )}
                <div className={cn("muted mt-1 text-[10px]", mine && "text-right")}>{formatDate(m.timestamp, true)}</div>
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}

/** Administrator's view of one account: profile, KPIs, 14-day activity, chats, documents and transcripts */
export function UserActivityDrawer({
  user,
  initialConversation,
  onClose,
}: {
  user: AdminUserRow | null;
  initialConversation?: string | null;
  onClose: () => void;
}) {
  const [cid, setCid] = useState<string | null>(null);
  const [tab, setTab] = useState("chats");
  useEffect(() => {
    setCid(initialConversation ?? null);
    setTab("chats");
  }, [user, initialConversation]);
  const ct = useChartTheme();
  const q = useQuery({
    queryKey: ["admin-user", user?.user_id],
    queryFn: () => api.adminUserDetail(user!.user_id),
    enabled: !!user,
  });
  const d = q.data;
  const u = d?.user ?? user;
  const total14 = useMemo(() => (d?.activity ?? []).reduce((a, x) => a + x.count, 0), [d]);
  const peak = useMemo(() => Math.max(0, ...(d?.activity ?? []).map((x) => x.count)), [d]);

  return (
    <Drawer open={!!user} onClose={onClose} className="max-w-2xl">
      <AnimatePresence mode="wait" initial={false}>
        {cid && u ? (
          <motion.div key="t" initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 24 }} className="min-h-full">
            <button
              onClick={onClose}
              aria-label="Close panel"
              className="absolute right-4 top-3 z-20 rounded-lg p-1.5 text-slate-500 hover:bg-slate-500/10"
            >
              <X className="h-4 w-4" />
            </button>
            <Transcript cid={cid} owner={u.username} onBack={() => setCid(null)} />
          </motion.div>
        ) : (
          <motion.div key="p" initial={{ opacity: 0, x: -24 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -24 }}>
            {/* Profile header */}
            <div className="relative overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-br from-indigo-600 via-violet-600 to-cyan-500" />
              <div className="absolute -right-16 -top-20 h-56 w-56 rounded-full bg-white/10 blur-2xl" />
              <div className="absolute -bottom-24 left-10 h-48 w-48 rounded-full bg-cyan-300/20 blur-2xl" />
              <button
                onClick={onClose}
                aria-label="Close panel"
                className="absolute right-4 top-4 z-10 rounded-lg p-1.5 text-white/80 transition hover:bg-white/15 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
              <div className="relative flex items-center gap-4 px-6 pb-6 pt-8">
                <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-white/15 text-2xl font-semibold text-white shadow-xl ring-1 ring-white/30 backdrop-blur">
                  {u ? initials(u.username) : ""}
                </div>
                <div className="min-w-0 text-white">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="truncate text-xl font-semibold">{u?.username}</h2>
                    {u && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-white/15 px-2 py-0.5 text-[11px] font-medium ring-1 ring-white/25">
                        {u.role === "admin" ? <ShieldCheck className="h-3 w-3" /> : null}
                        {capitalize(u.role)}
                      </span>
                    )}
                    {u?.disabled ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-rose-500/30 px-2 py-0.5 text-[11px] font-medium ring-1 ring-rose-200/40">
                        <ShieldOff className="h-3 w-3" /> Suspended
                      </span>
                    ) : (
                      u &&
                      u.sessions > 0 && (
                        <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-400/25 px-2 py-0.5 text-[11px] font-medium ring-1 ring-emerald-200/40">
                          <span className="h-1.5 w-1.5 rounded-full bg-emerald-300" /> Online
                        </span>
                      )
                    )}
                  </div>
                  <div className="mt-0.5 truncate text-sm text-white/80">{u?.email}</div>
                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-white/75">
                    <span className="inline-flex items-center gap-1">
                      <CalendarClock className="h-3.5 w-3.5" /> Joined {u ? formatDate(u.created_at) : "—"}
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <Clock3 className="h-3.5 w-3.5" /> Last active {u?.last_active ? timeAgo(u.last_active) : "never"}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <div className="space-y-5 p-5">
              {/* KPI tiles */}
              <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
                <Stat delay={0.02} icon={<FileText />} label="Documents" value={u?.documents ?? "—"} hint={u ? `${u.chunks} passages` : undefined} />
                <Stat delay={0.06} icon={<MessagesSquare />} label="Chats" value={u?.conversations ?? "—"} />
                <Stat delay={0.1} icon={<MessageSquareText />} label="Questions" value={u?.questions ?? "—"} hint={d ? `${d.stats.abstained} refused` : undefined} />
                <Stat delay={0.14} icon={<HardDrive />} label="Storage" value={u ? formatBytes(u.storage_bytes) : "—"} />
              </div>
              <div className="grid grid-cols-3 gap-2.5">
                <Stat delay={0.18} icon={<Gauge />} label="Avg confidence" value={d ? fmtPct(d.stats.avg_confidence) : "—"} />
                <Stat delay={0.22} icon={<ShieldCheck />} label="Backed by sources" value={d ? fmtPct(d.stats.grounded_rate) : "—"} />
                <Stat delay={0.26} icon={<Timer />} label="Avg answer time" value={d ? fmtSeconds(d.stats.avg_latency) : "—"} />
              </div>

              {/* 14-day activity */}
              <div className="rounded-2xl border border-slate-200/80 bg-white/70 p-4 dark:border-white/[0.07] dark:bg-white/[0.03]">
                <div className="flex items-baseline justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-slate-900 dark:text-white">Questions asked, last 14 days</div>
                    <div className="muted text-xs">Peak {peak} in a day</div>
                  </div>
                  <div className="text-2xl font-semibold tabular-nums text-slate-900 dark:text-white">{d ? total14 : "—"}</div>
                </div>
                <div className="mt-3 h-28">
                  {q.isLoading ? (
                    <Skeleton className="h-full w-full rounded-xl" />
                  ) : (
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={d?.activity ?? []} margin={{ top: 4, right: 0, left: 0, bottom: 0 }} barCategoryGap={3}>
                        <XAxis dataKey="date" tickFormatter={shortDay} {...ct.axisProps} interval={3} />
                        <YAxis hide allowDecimals={false} />
                        <RTooltip cursor={{ fill: ct.cursor }} content={<ChartTooltip labelFormatter={shortDay} />} />
                        <Bar dataKey="count" name="Questions" fill={ct.accent} radius={[4, 4, 0, 0]} maxBarSize={18} minPointSize={2} />
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                </div>
              </div>

              {/* Chats / Documents */}
              <div>
                <Tabs
                  value={tab}
                  onChange={setTab}
                  items={[
                    { value: "chats", label: `Chats (${d?.conversations.length ?? u?.conversations ?? 0})` },
                    { value: "documents", label: `Documents (${d?.documents.length ?? u?.documents ?? 0})` },
                  ]}
                />
                <div className="mt-3">
                  {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
                  {q.isLoading &&
                    Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="mb-2 h-16 w-full rounded-2xl" />)}
                  {d && tab === "chats" &&
                    (d.conversations.length === 0 ? (
                      <EmptyState icon={<MessagesSquare />} title="No chats yet" description="This user hasn't asked any questions." />
                    ) : (
                      <ul className="space-y-2">
                        {d.conversations.map((c, i) => (
                          <motion.li key={c.conversation_id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i, 10) * 0.03 }}>
                            <button
                              onClick={() => setCid(c.conversation_id)}
                              className="group flex w-full items-center gap-3 rounded-2xl border border-slate-200/80 bg-white/60 p-3 text-left transition hover:-translate-y-0.5 hover:border-indigo-500/30 hover:shadow-lg hover:shadow-indigo-500/5 dark:border-white/[0.07] dark:bg-white/[0.02]"
                            >
                              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500/15 to-cyan-500/15 text-indigo-500 dark:text-indigo-300">
                                <MessageSquareText className="h-5 w-5" />
                              </div>
                              <div className="min-w-0 flex-1">
                                <div className="truncate text-sm font-medium text-slate-900 dark:text-white">{c.title}</div>
                                <div className="muted mt-0.5 text-xs">
                                  {c.message_count} messages · {timeAgo(c.updated_at)}
                                </div>
                              </div>
                              <ChevronRight className="h-4 w-4 shrink-0 text-slate-400 transition-transform group-hover:translate-x-0.5 group-hover:text-indigo-500" />
                            </button>
                          </motion.li>
                        ))}
                      </ul>
                    ))}
                  {d && tab === "documents" &&
                    (d.documents.length === 0 ? (
                      <EmptyState icon={<FileText />} title="No documents" description="This user hasn't uploaded anything." />
                    ) : (
                      <>
                        <div className="mb-3 flex flex-wrap gap-1.5">
                          {Object.entries(d.by_domain).map(([dom, n]) => (
                            <span key={dom} className="inline-flex items-center gap-1">
                              <DomainBadge domain={dom} />
                              <span className="muted text-xs tabular-nums">{n}</span>
                            </span>
                          ))}
                        </div>
                        <ul className="space-y-2">
                          {d.documents.map((doc, i) => (
                            <motion.li
                              key={doc.doc_id}
                              initial={{ opacity: 0, y: 6 }}
                              animate={{ opacity: 1, y: 0 }}
                              transition={{ delay: Math.min(i, 10) * 0.03 }}
                              className="flex items-center gap-3 rounded-2xl border border-slate-200/80 bg-white/60 p-3 dark:border-white/[0.07] dark:bg-white/[0.02]"
                            >
                              <FileIcon ext={doc.file_type} />
                              <div className="min-w-0 flex-1">
                                <div className="truncate text-sm font-medium text-slate-900 dark:text-white" title={doc.filename}>
                                  {doc.filename}
                                </div>
                                <div className="muted mt-0.5 text-xs">
                                  {formatBytes(doc.file_size)} · {doc.page_count} pages · {doc.chunk_count} passages · {timeAgo(doc.uploaded_at)}
                                </div>
                              </div>
                              <DomainBadge domain={doc.domain} />
                            </motion.li>
                          ))}
                        </ul>
                      </>
                    ))}
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Drawer>
  );
}
