import { useId, useRef, type KeyboardEvent, type ReactNode } from "react";
import { motion } from "framer-motion";
import { cn } from "../../lib/utils";

export interface TabItem<T extends string> {
  value: T;
  label: ReactNode;
  icon?: ReactNode;
  /** Hover explanation (also used as the accessible description) */
  hint?: string;
}

/** Underline-style tabs with an animated indicator + roving keyboard focus. */
export function Tabs<T extends string>({
  items,
  value,
  onChange,
  className,
}: {
  items: TabItem<T>[];
  value: T;
  onChange: (v: T) => void;
  className?: string;
}) {
  const id = useId();
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const onKey = (e: KeyboardEvent, i: number) => {
    let n = i;
    if (e.key === "ArrowRight") n = (i + 1) % items.length;
    else if (e.key === "ArrowLeft") n = (i - 1 + items.length) % items.length;
    else return;
    e.preventDefault();
    onChange(items[n].value);
    refs.current[n]?.focus();
  };
  return (
    <div role="tablist" className={cn("flex gap-1 overflow-x-auto overflow-y-hidden [scrollbar-width:none] border-b border-slate-200 dark:border-white/10", className)}>
      {items.map((it, i) => {
        const active = it.value === value;
        return (
          <button
            key={it.value}
            ref={(el) => (refs.current[i] = el)}
            role="tab"
            aria-selected={active}
            tabIndex={active ? 0 : -1}
            onKeyDown={(e) => onKey(e, i)}
            onClick={() => onChange(it.value)}
            className={cn(
              "relative flex items-center gap-2 whitespace-nowrap px-3 pb-3 pt-2 text-sm font-medium transition-colors [&>svg]:h-4 [&>svg]:w-4",
              active ? "text-slate-900 dark:text-white" : "text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200",
            )}
          >
            {it.icon}
            {it.label}
            {active && (
              <motion.span
                layoutId={`${id}-tab-indicator`}
                className="bg-brand-gradient absolute inset-x-1 -bottom-px h-0.5 rounded-full"
                transition={{ type: "spring", stiffness: 500, damping: 40 }}
              />
            )}
          </button>
        );
      })}
    </div>
  );
}

/** Pill segmented control. */
export function Segmented<T extends string>({
  items,
  value,
  onChange,
  size = "md",
  className,
  ariaLabel,
}: {
  items: TabItem<T>[];
  value: T;
  onChange: (v: T) => void;
  size?: "sm" | "md";
  className?: string;
  ariaLabel?: string;
}) {
  const id = useId();
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className={cn("inline-flex rounded-xl bg-slate-100 p-1 dark:bg-white/[0.05]", className)}
    >
      {items.map((it) => {
        const active = it.value === value;
        return (
          <button
            key={it.value}
            role="radio"
            aria-checked={active}
            title={it.hint}
            onClick={() => onChange(it.value)}
            className={cn(
              "relative flex items-center gap-1.5 rounded-lg font-medium transition-colors [&_svg]:h-3.5 [&_svg]:w-3.5",
              size === "sm" ? "px-2.5 py-1 text-xs" : "px-3 py-1.5 text-sm",
              active ? "text-slate-900 dark:text-white" : "text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200",
            )}
          >
            {active && (
              <motion.span
                layoutId={`${id}-seg`}
                className="absolute inset-0 rounded-lg bg-white shadow-sm ring-1 ring-slate-200 dark:bg-white/10 dark:ring-white/10"
                transition={{ type: "spring", stiffness: 500, damping: 38 }}
              />
            )}
            <span className="relative flex items-center gap-1.5">
              {it.icon}
              {it.label}
            </span>
          </button>
        );
      })}
    </div>
  );
}
