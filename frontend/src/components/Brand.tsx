import { File, FileImage, FileSpreadsheet, FileText, FileType2, Presentation, FileCode2 } from "lucide-react";
import { cn, formatStyle } from "../lib/utils";

export function Logo({ collapsed = false, className }: { collapsed?: boolean; className?: string }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <div className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 via-violet-500 to-cyan-500 shadow-lg shadow-indigo-500/30">
        <svg viewBox="0 0 64 64" className="h-5 w-5" aria-hidden>
          <path d="M20 16h14a14 14 0 0 1 0 28h-6v6h-8z" fill="none" stroke="#fff" strokeWidth="6" strokeLinejoin="round" />
          <circle cx="33" cy="30" r="4.5" fill="#fff" />
        </svg>
      </div>
      {!collapsed && (
        <div className="leading-none">
          <div className="text-[15px] font-semibold tracking-tight text-slate-900 dark:text-white">DocuMind</div>
          <div className="mt-0.5 text-[10px] font-medium uppercase tracking-[0.14em] text-slate-400">Document AI</div>
        </div>
      )}
    </div>
  );
}

export function FileIcon({ ext, size = "md", className }: { ext: string; size?: "sm" | "md" | "lg"; className?: string }) {
  const s = formatStyle(ext);
  const e = ext.toLowerCase();
  const Icon =
    e === ".csv" || e === ".xlsx"
      ? FileSpreadsheet
      : e === ".png" || e === ".jpg" || e === ".jpeg"
        ? FileImage
        : e === ".pptx"
          ? Presentation
          : e === ".html" || e === ".md"
            ? FileCode2
            : e === ".pdf"
              ? FileType2
              : e === ".docx" || e === ".txt"
                ? FileText
                : File;
  const dims = size === "sm" ? "h-8 w-8 [&>svg]:h-4 [&>svg]:w-4" : size === "lg" ? "h-14 w-14 [&>svg]:h-7 [&>svg]:w-7" : "h-10 w-10 [&>svg]:h-5 [&>svg]:w-5";
  return (
    <div className={cn("flex shrink-0 items-center justify-center rounded-xl", s.className, dims, className)} aria-label={`${s.label} file`}>
      <Icon aria-hidden />
    </div>
  );
}
