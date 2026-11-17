import { forwardRef, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "../../lib/utils";

const base =
  "w-full rounded-xl border border-slate-200 bg-white/70 px-3.5 text-sm text-slate-900 placeholder:text-slate-400 transition focus:border-indigo-500/60 focus:outline-none focus:ring-4 focus:ring-indigo-500/15 disabled:opacity-60 dark:border-white/10 dark:bg-white/[0.03] dark:text-slate-100 dark:placeholder:text-slate-500";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  icon?: ReactNode;
  rightSlot?: ReactNode;
  invalid?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { icon, rightSlot, invalid, className, ...rest },
  ref,
) {
  return (
    <div className="relative">
      {icon && (
        <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 [&>svg]:h-4 [&>svg]:w-4">
          {icon}
        </span>
      )}
      <input
        ref={ref}
        className={cn(
          base,
          "h-10",
          icon && "pl-9",
          rightSlot && "pr-10",
          invalid && "border-rose-500/60 focus:border-rose-500/60 focus:ring-rose-500/15",
          className,
        )}
        aria-invalid={invalid || undefined}
        {...rest}
      />
      {rightSlot && <span className="absolute right-2 top-1/2 -translate-y-1/2">{rightSlot}</span>}
    </div>
  );
});

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Select(
  { className, children, ...rest },
  ref,
) {
  return (
    <div className="relative">
      <select ref={ref} className={cn(base, "h-10 cursor-pointer appearance-none pr-9", className)} {...rest}>
        {children}
      </select>
      <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
    </div>
  );
});

export function Label({ htmlFor, children, className }: { htmlFor?: string; children: ReactNode; className?: string }) {
  return (
    <label htmlFor={htmlFor} className={cn("mb-1.5 block text-xs font-medium text-slate-600 dark:text-slate-300", className)}>
      {children}
    </label>
  );
}
