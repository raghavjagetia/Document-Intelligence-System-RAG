import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Coins,
  Banknote,
  Briefcase,
  Building2,
  CalendarCheck,
  CalendarClock,
  CalendarDays,
  CalendarX,
  CircleSlash,
  FileSearch,
  Fingerprint,
  GraduationCap,
  Hash,
  Hourglass,
  Landmark,
  Mail,
  MapPin,
  Percent,
  Phone,
  Receipt,
  ScrollText,
  Sparkles,
  Timer,
  UserRound,
  Users,
  Wallet,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { api } from "../../lib/api";
import { cn } from "../../lib/utils";
import type { ExtractDocType } from "../../types";
import { Badge, Card, EmptyState, ErrorState, Segmented, Skeleton } from "../ui";
import { CopyIconButton } from "./shared";

function humanize(k: string) {
  return k
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .replace(/\b(Id|Po)\b/g, (w) => w.toUpperCase());
}

/** First matching rule wins; keys are matched case-insensitively against the field name. */
const FIELD_ICONS: [RegExp, LucideIcon][] = [
  [/part(y|ies)/, Users],
  [/vendor|supplier|company|employer|organi[sz]ation/, Building2],
  [/customer|client|bill_?to/, UserRound],
  [/^name$|candidate|full_?name/, UserRound],
  [/effective|start/, CalendarCheck],
  [/end_?date|expir/, CalendarX],
  [/due/, CalendarClock],
  [/date/, CalendarDays],
  [/tax|gst|vat/, Percent],
  [/total|amount|subtotal/, Banknote],
  [/value|fee|price|salary|cost/, Coins],
  [/payment/, Wallet],
  [/notice/, Timer],
  [/termination/, CircleSlash],
  [/term|duration|period/, Hourglass],
  [/governing|law|jurisdiction/, Landmark],
  [/invoice/, Receipt],
  [/_id$|number|^id$|po_|reference/, Fingerprint],
  [/email/, Mail],
  [/phone|mobile/, Phone],
  [/address|location/, MapPin],
  [/skill/, Wrench],
  [/education|degree/, GraduationCap],
  [/experience|role|title|position/, Briefcase],
  [/count|qty|quantity/, Hash],
];

function iconFor(key: string): LucideIcon {
  const k = key.toLowerCase();
  return FIELD_ICONS.find(([re]) => re.test(k))?.[1] ?? ScrollText;
}

const isMissing = (v: string | string[] | null) => v === null || (Array.isArray(v) && v.length === 0) || (typeof v === "string" && !v.trim());

function CompletenessRing({ found, total }: { found: number; total: number }) {
  const r = 18;
  const c = 2 * Math.PI * r;
  const pct = total ? found / total : 0;
  return (
    <div className="flex items-center gap-2.5">
      <div className="relative h-11 w-11">
        <svg viewBox="0 0 44 44" className="h-full w-full -rotate-90" aria-hidden>
          <defs>
            <linearGradient id="completeness" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#6366f1" />
              <stop offset="55%" stopColor="#8b5cf6" />
              <stop offset="100%" stopColor="#06b6d4" />
            </linearGradient>
          </defs>
          <circle cx="22" cy="22" r={r} fill="none" strokeWidth="4" className="stroke-slate-200 dark:stroke-white/[0.08]" />
          <motion.circle
            cx="22"
            cy="22"
            r={r}
            fill="none"
            stroke="url(#completeness)"
            strokeWidth="4"
            strokeLinecap="round"
            strokeDasharray={c}
            initial={{ strokeDashoffset: c }}
            animate={{ strokeDashoffset: c - pct * c }}
            transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-[10px] font-semibold tabular-nums text-slate-700 dark:text-slate-200">
          {Math.round(pct * 100)}%
        </span>
      </div>
      <div className="leading-tight">
        <div className="text-sm font-semibold tabular-nums text-slate-900 dark:text-white">
          {found}/{total}
        </div>
        <div className="muted text-[11px]">fields found</div>
      </div>
    </div>
  );
}

function FieldCard({ name, value, index }: { name: string; value: string | string[] | null; index: number }) {
  const Icon = iconFor(name);
  const missing = isMissing(value);
  const long = typeof value === "string" && value.length > 70;
  const copy = Array.isArray(value) ? value.join(", ") : (value ?? "");

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index, 14) * 0.035, duration: 0.3 }}
      className={cn("min-w-0", long && "sm:col-span-2")}
    >
      {missing ? (
        <div className="flex h-full items-center gap-3 rounded-2xl border border-dashed border-slate-300 px-4 py-3.5 dark:border-white/10">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-400 dark:bg-white/[0.04] dark:text-slate-500">
            <Icon className="h-4 w-4" />
          </span>
          <div className="min-w-0">
            <div className="truncate text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">{humanize(name)}</div>
            <div className="mt-0.5 text-xs italic text-slate-400 dark:text-slate-500">Not found in document</div>
          </div>
        </div>
      ) : (
        <div className="glass group relative flex h-full gap-3 rounded-2xl px-4 py-3.5 transition hover:border-indigo-500/30 dark:hover:border-indigo-400/25">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500/15 via-violet-500/10 to-cyan-500/15 text-indigo-600 ring-1 ring-inset ring-indigo-500/20 dark:text-indigo-300">
            <Icon className="h-4 w-4" />
          </span>
          <div className="min-w-0 flex-1 pr-6">
            <div className="truncate text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">{humanize(name)}</div>
            {Array.isArray(value) ? (
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {value.map((x, j) => (
                  <Badge key={j} tone="indigo" className="max-w-full whitespace-normal break-words px-2 py-0.5 text-left text-xs">
                    {x}
                  </Badge>
                ))}
              </div>
            ) : (
              <div className={cn("mt-1 break-words text-slate-900 dark:text-white", long ? "text-sm leading-relaxed" : "text-[15px] font-semibold")}>{value}</div>
            )}
          </div>
          <CopyIconButton text={copy} label={`Copy ${humanize(name)}`} className="absolute right-2 top-2 opacity-60 group-hover:opacity-100" />
        </div>
      )}
    </motion.div>
  );
}

export function ExtractTab({ docId }: { docId: string }) {
  const [type, setType] = useState<ExtractDocType>("auto");
  const q = useQuery({ queryKey: ["extract", docId, type], queryFn: () => api.extract(docId, type), staleTime: Infinity });
  const fields = Object.entries(q.data?.structured_data.fields ?? {});
  const found = fields.filter(([, v]) => !isMissing(v)).length;
  // found values first, misses last — keeps the useful information at the top
  const ordered = [...fields.filter(([, v]) => !isMissing(v)), ...fields.filter(([, v]) => isMissing(v))];

  return (
    <div className="space-y-4">
      <Card className="flex flex-col gap-3 p-3 sm:flex-row sm:items-center sm:justify-between sm:p-3 sm:pl-4">
        <div className="flex flex-wrap items-center gap-3">
          <Segmented
            ariaLabel="Document type"
            value={type}
            onChange={setType}
            items={[
              { value: "auto", label: "Auto", icon: <Sparkles /> },
              { value: "contract", label: "Contract" },
              { value: "invoice", label: "Invoice" },
              { value: "resume", label: "Resume" },
            ]}
          />
          {q.data && (
            <div className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
              {type === "auto" ? "Detected" : "Schema"}
              <Badge tone="indigo" className="px-2.5 py-1 text-xs capitalize">
                {q.data.structured_data.document_type}
              </Badge>
            </div>
          )}
        </div>
        {q.data && fields.length > 0 && <CompletenessRing found={found} total={fields.length} />}
      </Card>

      {q.isLoading && (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 9 }).map((_, i) => (
            <Card key={i} className="flex gap-3 px-4 py-3.5">
              <Skeleton className="h-8 w-8 rounded-xl" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-2.5 w-20" />
                <Skeleton className="h-4 w-3/4" />
              </div>
            </Card>
          ))}
        </div>
      )}
      {q.isError && (
        <Card>
          <ErrorState error={q.error} onRetry={() => q.refetch()} />
        </Card>
      )}
      {q.data && fields.length === 0 && (
        <Card>
          <EmptyState icon={<FileSearch />} title="No fields for this document type" description="Try another schema above." />
        </Card>
      )}
      {q.data && fields.length > 0 && (
        <div key={type} className="grid grid-flow-row-dense gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {ordered.map(([k, v], i) => (
            <FieldCard key={k} name={k} value={v} index={i} />
          ))}
        </div>
      )}
    </div>
  );
}
