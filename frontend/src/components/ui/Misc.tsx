import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { cn } from "../../lib/utils";
import { Button } from "./Button";
import { EmptyState } from "./EmptyState";

export function Progress({ value, className, barClassName }: { value: number; className?: string; barClassName?: string }) {
  const v = Math.max(0, Math.min(100, value));
  return (
    <div
      role="progressbar"
      aria-valuenow={Math.round(v)}
      aria-valuemin={0}
      aria-valuemax={100}
      className={cn("h-1.5 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-white/[0.07]", className)}
    >
      <motion.div
        className={cn("bg-brand-gradient h-full rounded-full", barClassName)}
        initial={{ width: 0 }}
        animate={{ width: `${v}%` }}
        transition={{ type: "spring", stiffness: 120, damping: 24 }}
      />
    </div>
  );
}

export function Kbd({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <kbd
      className={cn(
        "inline-flex h-5 min-w-[20px] items-center justify-center rounded-md border border-slate-200 bg-white px-1.5 font-mono text-[10px] font-medium text-slate-500 dark:border-white/10 dark:bg-white/5 dark:text-slate-400",
        className,
      )}
    >
      {children}
    </kbd>
  );
}

export function PageHeader({
  title,
  description,
  actions,
  icon,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="flex items-start gap-3">
        {icon && (
          <div className="hidden h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500/20 via-violet-500/15 to-cyan-500/20 text-indigo-500 ring-1 ring-indigo-500/20 dark:text-indigo-300 sm:flex [&>svg]:h-5 [&>svg]:w-5">
            {icon}
          </div>
        )}
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-white">{title}</h1>
          {description && <p className="muted mt-1 text-sm">{description}</p>}
        </div>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry, className }: { error: unknown; onRetry?: () => void; className?: string }) {
  const msg = error instanceof Error ? error.message : "Something went wrong";
  return (
    <EmptyState
      tone="error"
      className={className}
      icon={<AlertTriangle />}
      title="Couldn't load this"
      description={msg}
      action={
        onRetry && (
          <Button variant="outline" size="sm" onClick={onRetry} leftIcon={<RefreshCw className="h-3.5 w-3.5" />}>
            Retry
          </Button>
        )
      }
    />
  );
}

/** Coloured chip used for filters / tags. */
export function Chip({
  active,
  onClick,
  children,
  className,
}: {
  active?: boolean;
  onClick?: () => void;
  children: ReactNode;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset transition-all",
        active
          ? "bg-indigo-500 text-white ring-indigo-500 shadow-md shadow-indigo-500/20"
          : "bg-white/60 text-slate-600 ring-slate-200 hover:ring-slate-300 dark:bg-white/[0.03] dark:text-slate-300 dark:ring-white/10 dark:hover:ring-white/20",
        className,
      )}
    >
      {children}
    </button>
  );
}
