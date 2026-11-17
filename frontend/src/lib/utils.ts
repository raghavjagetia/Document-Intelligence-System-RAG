import clsx, { type ClassValue } from "clsx";

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
  const v = bytes / Math.pow(1024, i);
  return `${v.toFixed(v >= 10 || i === 0 ? 0 : 1)} ${units[i]}`;
}

function parseDate(iso: string): Date | null {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatDate(iso: string, withTime = false): string {
  const d = parseDate(iso);
  if (!d) return "—";
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  });
}

export function timeAgo(iso: string): string {
  const d = parseDate(iso);
  if (!d) return "—";
  const s = Math.round((Date.now() - d.getTime()) / 1000);
  if (s < 45) return "just now";
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  const days = Math.round(h / 24);
  if (days < 7) return `${days}d ago`;
  return formatDate(iso);
}

/**
 * The API does not pin whether some scores (confidence, grounding, rates) are 0..1 or 0..100.
 * Normalise to a 0..100 percentage: values in [0,1] are treated as fractions.
 */
export function toPct(v: number | null | undefined): number {
  if (v === null || v === undefined || !Number.isFinite(v)) return 0;
  return Math.abs(v) <= 1 ? v * 100 : v;
}

export function fmtPct(v: number | null | undefined, digits = 0): string {
  return `${toPct(v).toFixed(digits)}%`;
}

export function fmtSeconds(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  if (v < 1) return `${Math.round(v * 1000)} ms`;
  return `${v.toFixed(2)} s`;
}

export function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

export function initials(name: string): string {
  const parts = name.trim().split(/[\s._-]+/).filter(Boolean);
  if (!parts.length) return "?";
  return (parts[0][0] + (parts[1]?.[0] ?? "")).toUpperCase();
}

export function capitalize(s: string): string {
  if (!s) return s;
  if (s.toLowerCase() === "hr") return "HR";
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export const FORMAT_STYLES: Record<string, { label: string; className: string; color: string }> = {
  ".pdf": { label: "PDF", className: "bg-rose-500/15 text-rose-500 dark:text-rose-400", color: "#f43f5e" },
  ".docx": { label: "DOCX", className: "bg-blue-500/15 text-blue-600 dark:text-blue-400", color: "#3b82f6" },
  ".txt": { label: "TXT", className: "bg-slate-500/15 text-slate-600 dark:text-slate-300", color: "#64748b" },
  ".md": { label: "MD", className: "bg-zinc-500/15 text-zinc-600 dark:text-zinc-300", color: "#71717a" },
  ".html": { label: "HTML", className: "bg-orange-500/15 text-orange-600 dark:text-orange-400", color: "#f97316" },
  ".csv": { label: "CSV", className: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400", color: "#10b981" },
  ".xlsx": { label: "XLSX", className: "bg-green-500/15 text-green-600 dark:text-green-400", color: "#22c55e" },
  ".pptx": { label: "PPTX", className: "bg-amber-500/15 text-amber-600 dark:text-amber-400", color: "#f59e0b" },
  ".png": { label: "PNG", className: "bg-fuchsia-500/15 text-fuchsia-600 dark:text-fuchsia-400", color: "#d946ef" },
  ".jpg": { label: "JPG", className: "bg-purple-500/15 text-purple-600 dark:text-purple-400", color: "#a855f7" },
  ".jpeg": { label: "JPEG", className: "bg-purple-500/15 text-purple-600 dark:text-purple-400", color: "#a855f7" },
};

export function formatStyle(ext: string) {
  const key = ext.startsWith(".") ? ext.toLowerCase() : `.${ext.toLowerCase()}`;
  return (
    FORMAT_STYLES[key] ?? {
      label: key.replace(".", "").toUpperCase() || "FILE",
      className: "bg-indigo-500/15 text-indigo-600 dark:text-indigo-400",
      color: "#6366f1",
    }
  );
}

export const DOMAIN_STYLES: Record<string, string> = {
  general: "bg-slate-500/10 text-slate-600 ring-slate-500/20 dark:text-slate-300",
  hr: "bg-sky-500/10 text-sky-600 ring-sky-500/20 dark:text-sky-300",
  legal: "bg-violet-500/10 text-violet-600 ring-violet-500/20 dark:text-violet-300",
  healthcare: "bg-emerald-500/10 text-emerald-600 ring-emerald-500/20 dark:text-emerald-300",
  finance: "bg-amber-500/10 text-amber-700 ring-amber-500/20 dark:text-amber-300",
};


export const ACCEPTED_EXTENSIONS = [
  ".pdf", ".docx", ".txt", ".md", ".html", ".csv", ".xlsx", ".pptx", ".png", ".jpg", ".jpeg",
];

export function fileExt(name: string): string {
  const i = name.lastIndexOf(".");
  return i === -1 ? "" : name.slice(i).toLowerCase();
}
