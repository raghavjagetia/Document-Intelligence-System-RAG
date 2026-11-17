import type { HTMLAttributes } from "react";
import { cn, capitalize, DOMAIN_STYLES } from "../../lib/utils";

type Tone = "neutral" | "indigo" | "green" | "amber" | "red" | "cyan" | "violet";

const tones: Record<Tone, string> = {
  neutral: "bg-slate-500/10 text-slate-600 ring-slate-500/20 dark:text-slate-300",
  indigo: "bg-indigo-500/10 text-indigo-600 ring-indigo-500/20 dark:text-indigo-300",
  green: "bg-emerald-500/10 text-emerald-600 ring-emerald-500/25 dark:text-emerald-400",
  amber: "bg-amber-500/10 text-amber-700 ring-amber-500/25 dark:text-amber-400",
  red: "bg-rose-500/10 text-rose-600 ring-rose-500/25 dark:text-rose-400",
  cyan: "bg-cyan-500/10 text-cyan-700 ring-cyan-500/25 dark:text-cyan-300",
  violet: "bg-violet-500/10 text-violet-600 ring-violet-500/25 dark:text-violet-300",
};

export function Badge({ tone = "neutral", className, ...rest }: HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset",
        tones[tone],
        className,
      )}
      {...rest}
    />
  );
}

export function DomainBadge({ domain, className }: { domain: string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset",
        DOMAIN_STYLES[domain] ?? DOMAIN_STYLES.general,
        className,
      )}
    >
      {capitalize(domain)}
    </span>
  );
}
