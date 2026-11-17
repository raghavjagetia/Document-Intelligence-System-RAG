import { useMemo, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Activity,
  ArrowUpRight,
  BarChart3,
  Boxes,
  FileText,
  FlaskConical,
  Gauge,
  MessageSquarePlus,
  MessagesSquare,
  PieChart as PieIcon,
  ShieldCheck,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  Timer,
  TrendingUp,
  Trophy,
  Upload,
  Users,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useAuth } from "../hooks/useAuth";
import { useAnalytics, useStatistics } from "../hooks/queries";
import { useCountUp } from "../hooks/misc";
import { capitalize, cn, formatBytes, formatDate, formatStyle, greeting, timeAgo, toPct } from "../lib/utils";
import { Card, CardHeader, DomainBadge, EmptyState, ErrorState, Skeleton } from "../components/ui";
import { FileIcon } from "../components/Brand";
import { SystemStatusCard } from "../components/SystemStatusCard";
import { EvaluationSummaryCard } from "../components/evaluation/AdvancedEvaluation";
import { ChartTooltip, Legend, useChartTheme } from "../components/charts";

function Kpi({
  label,
  value,
  format,
  icon,
  accent,
  loading,
  index,
}: {
  label: string;
  value: number | undefined;
  format: (n: number) => string;
  icon: ReactNode;
  accent: string;
  loading: boolean;
  index: number;
}) {
  const n = useCountUp(value ?? 0);
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.4 }}
      whileHover={{ y: -3 }}
      className="glass group relative overflow-hidden rounded-2xl p-4"
    >
      <div className={cn("absolute -right-8 -top-8 h-24 w-24 rounded-full opacity-20 blur-2xl transition-opacity group-hover:opacity-40", accent)} />
      <div className="relative flex items-center justify-between">
        <span className="text-xs font-medium text-slate-500 dark:text-slate-400">{label}</span>
        <span className="text-slate-400 [&>svg]:h-4 [&>svg]:w-4">{icon}</span>
      </div>
      <div className="relative mt-3 text-2xl font-semibold tabular-nums tracking-tight text-slate-900 dark:text-white">
        {loading ? <Skeleton className="h-7 w-16" /> : value === undefined ? "—" : format(n)}
      </div>
    </motion.div>
  );
}

function ChartCard({
  title,
  description,
  icon,
  children,
  className,
  loading,
  empty,
  error,
  onRetry,
  legend,
}: {
  title: string;
  description?: string;
  icon: ReactNode;
  children: ReactNode;
  className?: string;
  loading?: boolean;
  empty?: boolean;
  error?: unknown;
  onRetry?: () => void;
  legend?: ReactNode;
}) {
  return (
    <Card className={cn("flex flex-col", className)}>
      <CardHeader icon={icon} title={title} description={description} />
      {legend && <div className="px-5 pt-3">{legend}</div>}
      <div className="min-h-[220px] flex-1 p-3 pt-4">
        {loading ? (
          <Skeleton className="h-full min-h-[200px] w-full rounded-xl" />
        ) : error ? (
          <ErrorState error={error} onRetry={onRetry} className="py-6" />
        ) : empty ? (
          <EmptyState icon={<BarChart3 />} title="No data yet" description="Ask a few questions and upload documents to populate this chart." className="py-8" />
        ) : (
          children
        )}
      </div>
    </Card>
  );
}

const shortDate = (d: unknown) => {
  const dt = new Date(String(d));
  return Number.isNaN(dt.getTime()) ? String(d) : dt.toLocaleDateString(undefined, { month: "short", day: "numeric" });
};

export default function DashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const stats = useStatistics();
  const analytics = useAnalytics();
  const ct = useChartTheme();
  const s = stats.data;
  const a = analytics.data;
  const isAdmin = user?.role === "admin";
  const fb = a?.feedback;
  const STYLE_NAMES: Record<string, string> = { quick: "Quick answer", detailed: "Detailed answer", quote: "Exact quote" };
  const feedbackData = (fb?.by_style ?? []).map((r) => ({
    name: STYLE_NAMES[r.style] ?? capitalize(r.style),
    Helpful: r.helpful,
    "Not helpful": r.not_helpful,
  }));

  const domainData = useMemo(
    () => Object.entries(s?.by_domain ?? {}).filter(([, v]) => v > 0).map(([k, v]) => ({ name: capitalize(k), value: v })),
    [s],
  );
  const formatData = useMemo(
    () =>
      Object.entries(s?.by_format ?? {})
        .map(([k, v]) => ({ name: formatStyle(k).label, value: v }))
        .sort((x, y) => y.value - x.value),
    [s],
  );
  const confHistory = useMemo(
    () =>
      (a?.confidence_history ?? []).map((p) => ({
        t: p.timestamp,
        Confidence: +toPct(p.confidence).toFixed(1),
        "Backed by sources": +toPct(p.grounding).toFixed(1),
      })),
    [a],
  );
  const topDocs = a?.top_documents ?? [];
  const maxCites = Math.max(1, ...topDocs.map((d) => d.citations));

  const kpis = [
    { label: "Documents", value: s?.total_documents, format: (n: number) => Math.round(n).toLocaleString(), icon: <FileText />, accent: "bg-indigo-500" },
    isAdmin
      ? { label: "Users", value: s?.total_users ?? undefined, format: (n: number) => Math.round(n).toLocaleString(), icon: <Users />, accent: "bg-violet-500" }
      : { label: "Searchable passages", value: s?.total_chunks, format: (n: number) => Math.round(n).toLocaleString(), icon: <Boxes />, accent: "bg-violet-500" },
    { label: "Questions asked", value: s?.total_questions, format: (n: number) => Math.round(n).toLocaleString(), icon: <MessagesSquare />, accent: "bg-cyan-500" },
    { label: "Avg confidence", value: s ? toPct(s.avg_confidence) : undefined, format: (n: number) => `${n.toFixed(1)}%`, icon: <Gauge />, accent: "bg-emerald-500" },
    { label: "Backed by sources", value: s ? toPct(s.grounded_rate) : undefined, format: (n: number) => `${n.toFixed(1)}%`, icon: <ShieldCheck />, accent: "bg-sky-500" },
    { label: "Avg answer time", value: s?.avg_latency, format: (n: number) => `${n.toFixed(2)}s`, icon: <Timer />, accent: "bg-amber-500" },
  ];

  const quick = [
    isAdmin
      ? { label: "Manage users", desc: "Roles, suspensions, passwords", icon: ShieldCheck, to: "/admin" }
      : { label: "Upload documents", desc: "PDF, Office, images & more", icon: Upload, to: "/documents?upload=1" },
    { label: "Ask a question", desc: "Answers with exact sources", icon: MessageSquarePlus, to: "/chat?new=1" },
    { label: "Generate insights", desc: "Summaries, key facts, compare", icon: Sparkles, to: "/insights" },
    { label: "Run benchmark", desc: "See how accurate it is", icon: FlaskConical, to: "/evaluation" },
  ];

  return (
    <div className="space-y-6">
      {/* Greeting */}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <motion.h1
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-white sm:text-3xl"
          >
            {greeting()}, <span className="text-gradient">{user?.username ?? "there"}</span>
          </motion.h1>
          <p className="muted mt-1 flex flex-wrap items-center gap-2 text-sm">
            {isAdmin ? (
              <>
                <span className="inline-flex items-center gap-1 rounded-full bg-violet-500/10 px-2 py-0.5 text-xs font-medium text-violet-600 ring-1 ring-violet-500/25 dark:text-violet-300">
                  <ShieldCheck className="h-3.5 w-3.5" /> Administrator
                </span>
                System-wide view across {s?.total_users ?? "all"} users and every document in DocuMind.
              </>
            ) : (
              "Here’s what’s happening across your document knowledge base."
            )}
          </p>
        </div>
        <button
          onClick={() => navigate(isAdmin ? "/admin" : "/chat?new=1")}
          className="group inline-flex items-center gap-2 self-start rounded-xl bg-gradient-to-r from-indigo-500 via-violet-500 to-cyan-500 px-4 py-2.5 text-sm font-medium text-white shadow-lg shadow-indigo-500/25 transition hover:shadow-indigo-500/40 sm:self-auto"
        >
          {isAdmin ? <ShieldCheck className="h-4 w-4" /> : <MessageSquarePlus className="h-4 w-4" />}
          {isAdmin ? "Admin panel" : "New chat"}
          <ArrowUpRight className="h-4 w-4 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
        </button>
      </div>

      {stats.isError && (
        <Card>
          <ErrorState error={stats.error} onRetry={() => stats.refetch()} className="py-6" />
        </Card>
      )}

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {kpis.map((k, i) => (
          <Kpi key={k.label} {...k} loading={stats.isLoading} index={i} />
        ))}
      </div>

      {/* Charts row 1 */}
      <div className="grid gap-4 lg:grid-cols-3">
        <ChartCard
          className="lg:col-span-2"
          title="Queries per day"
          description={isAdmin ? "Questions asked by all users" : "Questions asked across all conversations"}
          icon={<Activity className="h-4 w-4" />}
          loading={analytics.isLoading}
          error={analytics.error}
          onRetry={() => analytics.refetch()}
          empty={!a?.queries_per_day.length}
        >
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={a?.queries_per_day ?? []} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
              <defs>
                <linearGradient id="qpd" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={ct.accent} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={ct.accent} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid vertical={false} stroke={ct.grid} />
              <XAxis dataKey="date" tickFormatter={shortDate} {...ct.axisProps} minTickGap={24} />
              <YAxis allowDecimals={false} {...ct.axisProps} />
              <RTooltip
                cursor={{ stroke: ct.axis, strokeDasharray: "3 3" }}
                content={<ChartTooltip labelFormatter={shortDate} />}
              />
              <Area type="monotone" dataKey="count" name="Queries" stroke={ct.accent} strokeWidth={2} fill="url(#qpd)" activeDot={{ r: 4 }} />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="Documents by domain"
          icon={<PieIcon className="h-4 w-4" />}
          loading={stats.isLoading}
          empty={!domainData.length}
          legend={domainData.length > 0 && <Legend items={domainData.map((d, i) => ({ label: `${d.name} (${d.value})`, color: ct.series[i % 8] }))} />}
        >
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={domainData}
                dataKey="value"
                nameKey="name"
                innerRadius="58%"
                outerRadius="85%"
                paddingAngle={2}
                stroke="none"
                animationDuration={800}
              >
                {domainData.map((_, i) => (
                  <Cell key={i} fill={ct.series[i % 8]} />
                ))}
              </Pie>
              <RTooltip content={<ChartTooltip />} />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      {/* Charts row 2 */}
      <div className="grid gap-4 lg:grid-cols-3">
        <ChartCard
          className="lg:col-span-2"
          title="Answer confidence and source backing over time"
          description="Per-answer scores (%)"
          icon={<TrendingUp className="h-4 w-4" />}
          loading={analytics.isLoading}
          error={analytics.error}
          onRetry={() => analytics.refetch()}
          empty={!confHistory.length}
          legend={
            <Legend
              items={[
                { label: "Confidence", color: ct.series[0] },
                { label: "Backed by sources", color: ct.series[1] },
              ]}
            />
          }
        >
          <ResponsiveContainer width="100%" height={230}>
            <LineChart data={confHistory} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke={ct.grid} />
              <XAxis dataKey="t" tickFormatter={shortDate} {...ct.axisProps} minTickGap={32} />
              <YAxis domain={[0, 100]} {...ct.axisProps} />
              <RTooltip
                cursor={{ stroke: ct.axis, strokeDasharray: "3 3" }}
                content={<ChartTooltip labelFormatter={(l) => formatDate(String(l), true)} formatter={(v) => `${v.toFixed(1)}%`} />}
              />
              <Line type="monotone" dataKey="Confidence" stroke={ct.series[0]} strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
              <Line type="monotone" dataKey="Backed by sources" stroke={ct.series[1]} strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Documents by format" icon={<BarChart3 className="h-4 w-4" />} loading={stats.isLoading} empty={!formatData.length}>
          <ResponsiveContainer width="100%" height={230}>
            <BarChart data={formatData} margin={{ top: 8, right: 8, left: -22, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke={ct.grid} />
              <XAxis dataKey="name" {...ct.axisProps} interval={0} tick={{ ...ct.axisProps.tick, fontSize: 10 }} />
              <YAxis allowDecimals={false} {...ct.axisProps} />
              <RTooltip cursor={{ fill: ct.cursor }} content={<ChartTooltip />} />
              <Bar dataKey="value" name="Documents" fill={ct.accent} radius={[4, 4, 0, 0]} maxBarSize={36} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      {/* Benchmark vs standard approaches (error bars, main failure cause, other languages) */}
      <EvaluationSummaryCard />

      {/* Answer feedback (thumbs up / down) */}
      <ChartCard
        title="Answer feedback"
        description={isAdmin ? "Thumbs up / down from all users, per answer style" : "Your thumbs up / down, per answer style"}
        icon={<ThumbsUp className="h-4 w-4" />}
        loading={analytics.isLoading}
        error={analytics.error}
        onRetry={() => analytics.refetch()}
        empty={!fb?.rated}
        legend={
          fb?.rated ? (
            <Legend
              items={[
                { label: "Helpful", color: "#10b981" },
                { label: "Not helpful", color: "#f43f5e" },
              ]}
            />
          ) : undefined
        }
      >
        <div className="grid items-center gap-6 sm:grid-cols-[200px_1fr]">
          <div className="text-center sm:text-left">
            <div className="text-4xl font-semibold tabular-nums text-slate-900 dark:text-white">
              {fb?.satisfaction != null ? `${Math.round(fb.satisfaction * 100)}%` : "–"}
            </div>
            <div className="muted mt-1 text-sm">of rated answers were helpful</div>
            <div className="mt-3 flex justify-center gap-4 text-sm sm:justify-start">
              <span className="inline-flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400">
                <ThumbsUp className="h-3.5 w-3.5" /> {fb?.helpful ?? 0}
              </span>
              <span className="inline-flex items-center gap-1.5 text-rose-600 dark:text-rose-400">
                <ThumbsDown className="h-3.5 w-3.5" /> {fb?.not_helpful ?? 0}
              </span>
            </div>
            <div className="muted mt-2 text-xs">
              {fb ? `${fb.rated} of ${fb.answers} answers rated` : ""}
            </div>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={feedbackData} margin={{ top: 8, right: 8, left: -22, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke={ct.grid} />
              <XAxis dataKey="name" {...ct.axisProps} interval={0} />
              <YAxis allowDecimals={false} {...ct.axisProps} />
              <RTooltip cursor={{ fill: ct.cursor }} content={<ChartTooltip />} />
              <Bar dataKey="Helpful" fill="#10b981" radius={[4, 4, 0, 0]} maxBarSize={40} />
              <Bar dataKey="Not helpful" fill="#f43f5e" radius={[4, 4, 0, 0]} maxBarSize={40} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </ChartCard>

      {/* Row 3 */}
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="flex flex-col">
          <CardHeader icon={<Trophy className="h-4 w-4" />} title="Most cited documents" description="By citations in answers" />
          <div className="flex-1 p-5 pt-4">
            {analytics.isLoading ? (
              <div className="space-y-4">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-6 w-full" />
                ))}
              </div>
            ) : topDocs.length === 0 ? (
              <EmptyState icon={<Trophy />} title="No citations yet" description="Cited documents will appear here." className="py-6" />
            ) : (
              <ul className="space-y-3.5">
                {topDocs.slice(0, 6).map((d, i) => (
                  <li key={d.filename + i}>
                    <div className="mb-1 flex items-center justify-between gap-3 text-sm">
                      <span className="truncate text-slate-700 dark:text-slate-200" title={d.filename}>
                        {d.filename}
                      </span>
                      <span className="font-mono text-xs tabular-nums text-slate-500">{d.citations}</span>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-slate-200 dark:bg-white/[0.06]">
                      <motion.div
                        className="bg-brand-gradient h-full rounded-full"
                        initial={{ width: 0 }}
                        animate={{ width: `${(d.citations / maxCites) * 100}%` }}
                        transition={{ delay: 0.1 + i * 0.06, duration: 0.6 }}
                      />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Card>

        <SystemStatusCard />

        <Card className="flex flex-col">
          <CardHeader
            icon={<FileText className="h-4 w-4" />}
            title={isAdmin ? "Latest uploads (all users)" : "Recent documents"}
            action={
              <Link to={isAdmin ? "/admin" : "/documents"} className="text-xs font-medium text-indigo-600 hover:underline dark:text-indigo-400">
                View all
              </Link>
            }
          />
          <div className="flex-1 p-3">
            {stats.isLoading ? (
              Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="flex items-center gap-3 p-2">
                  <Skeleton className="h-10 w-10 rounded-xl" />
                  <div className="flex-1 space-y-1.5">
                    <Skeleton className="h-3 w-3/4" />
                    <Skeleton className="h-2.5 w-1/2" />
                  </div>
                </div>
              ))
            ) : !s?.recent_documents.length ? (
              <EmptyState
                icon={<Upload />}
                title="No documents yet"
                description="Upload your first document to get started."
                className="py-6"
                action={
                  <Link to="/documents?upload=1" className="text-sm font-medium text-indigo-600 hover:underline dark:text-indigo-400">
                    Upload now
                  </Link>
                }
              />
            ) : (
              <ul>
                {s.recent_documents.slice(0, 5).map((d, i) => (
                  <motion.li key={d.doc_id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
                    <Link
                      to={isAdmin ? "/admin" : `/documents?doc=${encodeURIComponent(d.doc_id)}`}
                      className="flex items-center gap-3 rounded-xl p-2 transition-colors hover:bg-slate-100/70 dark:hover:bg-white/[0.04]"
                    >
                      <FileIcon ext={d.file_type} />
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-medium text-slate-900 dark:text-white">{d.filename}</div>
                        <div className="muted text-xs">
                          {d.owner ? `${d.owner} · ` : ""}
                          {formatBytes(d.file_size)} · {d.chunk_count} passages · {timeAgo(d.uploaded_at)}
                        </div>
                      </div>
                      <DomainBadge domain={d.domain} />
                    </Link>
                  </motion.li>
                ))}
              </ul>
            )}
          </div>
        </Card>
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {quick.map((q, i) => (
          <motion.div key={q.label} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 + i * 0.05 }}>
            <Link
              to={q.to}
              className="glass group flex items-center gap-3 rounded-2xl p-4 transition-all hover:-translate-y-0.5 hover:border-indigo-500/30 hover:shadow-lg hover:shadow-indigo-500/5"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500/15 to-cyan-500/15 text-indigo-500 dark:text-indigo-300">
                <q.icon className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium text-slate-900 dark:text-white">{q.label}</div>
                <div className="muted truncate text-xs">{q.desc}</div>
              </div>
              <ArrowUpRight className="h-4 w-4 text-slate-400 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-indigo-500" />
            </Link>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
