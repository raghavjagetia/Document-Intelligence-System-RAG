import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { cn } from "../../lib/utils";

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
  tone = "neutral",
}: {
  icon: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
  tone?: "neutral" | "error";
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn("flex flex-col items-center justify-center px-6 py-12 text-center", className)}
    >
      <div
        className={cn(
          "relative mb-4 flex h-14 w-14 items-center justify-center rounded-2xl ring-1 [&>svg]:h-6 [&>svg]:w-6",
          tone === "error"
            ? "bg-rose-500/10 text-rose-500 ring-rose-500/20"
            : "bg-gradient-to-br from-indigo-500/15 via-violet-500/10 to-cyan-500/15 text-indigo-500 ring-indigo-500/20 dark:text-indigo-300",
        )}
      >
        {icon}
      </div>
      <h3 className="text-sm font-semibold text-slate-900 dark:text-white">{title}</h3>
      {description && <p className="muted mt-1 max-w-sm text-sm">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </motion.div>
  );
}
