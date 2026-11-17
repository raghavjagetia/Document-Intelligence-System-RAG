import { useState, type ReactNode } from "react";
import { Check, Copy } from "lucide-react";
import { toast } from "sonner";
import { friendlyMethod } from "../../lib/labels";
import { cn } from "../../lib/utils";

/** Copy text to the clipboard and confirm with a toast. Returns true on success. */
export async function copyText(text: string, label = "Copied to clipboard"): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    toast.success(label, { description: text.length > 80 ? `${text.slice(0, 80)}…` : text });
    return true;
  } catch {
    toast.error("Couldn't access the clipboard");
    return false;
  }
}

/** Small icon button that copies `text` and briefly flips to a check mark. */
export function CopyIconButton({ text, label = "Copy value", className }: { text: string; label?: string; className?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={async () => {
        if (await copyText(text)) {
          setDone(true);
          setTimeout(() => setDone(false), 1400);
        }
      }}
      className={cn(
        "flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/40 dark:hover:bg-white/[0.07] dark:hover:text-slate-200",
        className,
      )}
    >
      {done ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  );
}

/** Uppercase eyebrow label with an icon, used for section titles inside cards. */
export function SectionTitle({ icon, children, aside, className }: { icon?: ReactNode; children: ReactNode; aside?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex items-center justify-between gap-3", className)}>
      <div className="flex min-w-0 items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400 [&>svg]:h-3.5 [&>svg]:w-3.5 [&>svg]:shrink-0 [&>svg]:text-indigo-500 dark:[&>svg]:text-indigo-400">
        {icon}
        <span className="truncate">{children}</span>
      </div>
      {aside}
    </div>
  );
}

/** Compact "method" pill that truncates long extractor descriptions. */
export function MethodPill({ method }: { method: string }) {
  return (
    <span
      title={`Technical detail: ${method}`}
      className="inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-full bg-violet-500/10 px-2.5 py-1 text-[11px] font-medium text-violet-600 ring-1 ring-inset ring-violet-500/25 dark:text-violet-300 sm:max-w-[280px]"
    >
      <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-violet-500" />
      <span className="truncate">{friendlyMethod(method)}</span>
    </span>
  );
}
