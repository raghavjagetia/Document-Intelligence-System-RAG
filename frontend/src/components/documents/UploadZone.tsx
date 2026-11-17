import { useCallback, useState } from "react";
import { useDropzone, type FileRejection } from "react-dropzone";
import { AnimatePresence, motion } from "framer-motion";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { CheckCircle2, CloudUpload, Copy, Loader2, X, XCircle } from "lucide-react";
import { uploadDocuments, errorMessage } from "../../lib/api";
import { ACCEPTED_EXTENSIONS, capitalize, cn, fileExt, formatBytes } from "../../lib/utils";
import { DOMAINS, type Domain, type UploadResult } from "../../types";
import { Button, Card, Progress, Select } from "../ui";
import { FileIcon } from "../Brand";

type ItemStatus = "queued" | "uploading" | "processing" | "done" | "duplicate" | "error";

interface Item {
  id: string;
  file: File;
  progress: number;
  status: ItemStatus;
  message?: string;
}

const CONCURRENCY = 3;

export function UploadZone({ highlight = false }: { highlight?: boolean }) {
  const qc = useQueryClient();
  const [domain, setDomain] = useState<Domain>("general");
  const [items, setItems] = useState<Item[]>([]);
  const [running, setRunning] = useState(false);

  const patch = (id: string, p: Partial<Item>) => setItems((xs) => xs.map((x) => (x.id === id ? { ...x, ...p } : x)));

  const runUploads = useCallback(
    async (batch: Item[]) => {
      setRunning(true);
      const total: UploadResult = { processed: [], duplicates: [], errors: [] };
      const queue = [...batch];
      const worker = async () => {
        for (;;) {
          const it = queue.shift();
          if (!it) return;
          patch(it.id, { status: "uploading" });
          try {
            const { promise } = uploadDocuments([it.file], domain, (f) => {
              patch(it.id, { progress: f * 100, status: f >= 1 ? "processing" : "uploading" });
            });
            const r = await promise;
            total.processed.push(...r.processed);
            total.duplicates.push(...r.duplicates);
            total.errors.push(...r.errors);
            if (r.errors.length) patch(it.id, { status: "error", progress: 100, message: r.errors[0].error });
            else if (r.duplicates.length) patch(it.id, { status: "duplicate", progress: 100, message: "Already in your library" });
            else {
              const d = r.processed[0];
              patch(it.id, {
                status: "done",
                progress: 100,
                message: d ? `${d.chunk_count} passages · ${d.page_count} pages${d.version > 1 ? ` · v${d.version}` : ""}` : "Processed",
              });
            }
          } catch (e) {
            const msg = errorMessage(e);
            total.errors.push({ filename: it.file.name, error: msg });
            patch(it.id, { status: "error", progress: 100, message: msg });
          }
        }
      };
      await Promise.all(Array.from({ length: Math.min(CONCURRENCY, batch.length) }, worker));
      setRunning(false);
      qc.invalidateQueries({ queryKey: ["documents"] });
      qc.invalidateQueries({ queryKey: ["statistics"] });

      const parts = [
        `${total.processed.length} processed`,
        total.duplicates.length ? `${total.duplicates.length} duplicate${total.duplicates.length > 1 ? "s" : ""}` : null,
        total.errors.length ? `${total.errors.length} error${total.errors.length > 1 ? "s" : ""}` : null,
      ].filter(Boolean);
      const description = [
        ...total.duplicates.map((d) => `Duplicate: ${d.filename}`),
        ...total.errors.map((e) => `${e.filename}: ${e.error}`),
      ]
        .slice(0, 4)
        .join("\n");
      if (total.errors.length && !total.processed.length) toast.error(`Upload finished — ${parts.join(", ")}`, { description });
      else if (total.errors.length || total.duplicates.length) toast.warning(`Upload finished — ${parts.join(", ")}`, { description });
      else toast.success(`Upload complete — ${parts.join(", ")}`);
    },
    [domain, qc],
  );

  const onDrop = useCallback(
    (accepted: File[], rejected: FileRejection[]) => {
      if (rejected.length) {
        toast.error(`${rejected.length} file${rejected.length > 1 ? "s" : ""} not supported`, {
          description: rejected.map((r) => r.file.name).slice(0, 4).join(", "),
        });
      }
      if (!accepted.length) return;
      const batch: Item[] = accepted.map((file) => ({
        id: `${file.name}-${file.size}-${Math.random().toString(36).slice(2, 8)}`,
        file,
        progress: 0,
        status: "queued",
      }));
      setItems((xs) => [...batch, ...xs.filter((x) => x.status === "uploading" || x.status === "processing" || x.status === "queued")]);
      void runUploads(batch);
    },
    [runUploads],
  );

  const accept: Record<string, string[]> = {};
  for (const e of ACCEPTED_EXTENSIONS) (accept[mimeFor(e)] ??= []).push(e);
  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({ onDrop, accept, noClick: true, multiple: true });

  const finished = items.length > 0 && items.every((i) => ["done", "duplicate", "error"].includes(i.status));

  return (
    <Card className={cn("overflow-hidden transition-shadow", highlight && "ring-2 ring-indigo-500/40")}>
      <div
        {...getRootProps()}
        className={cn(
          "relative m-3 flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition-all",
          isDragActive
            ? "scale-[1.01] border-indigo-500 bg-indigo-500/[0.06]"
            : "border-slate-300 hover:border-indigo-400/60 dark:border-white/10 dark:hover:border-indigo-400/40",
        )}
      >
        <input {...getInputProps()} aria-label="Upload files" />
        <motion.div
          animate={isDragActive ? { y: -6, scale: 1.08 } : { y: 0, scale: 1 }}
          className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 via-violet-500 to-cyan-500 text-white shadow-lg shadow-indigo-500/30"
        >
          <CloudUpload className="h-6 w-6" />
        </motion.div>
        <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
          {isDragActive ? "Drop to upload" : "Drag & drop documents here"}
        </h3>
        <p className="muted mt-1 text-xs">{ACCEPTED_EXTENSIONS.join("  ")}</p>
        <div className="mt-5 flex flex-col items-center gap-2 sm:flex-row">
          <div className="w-44">
            <Select value={domain} onChange={(e) => setDomain(e.target.value as Domain)} aria-label="Domain for uploaded files" className="h-9">
              {DOMAINS.map((d) => (
                <option key={d} value={d}>
                  Domain: {capitalize(d)}
                </option>
              ))}
            </Select>
          </div>
          <Button variant="gradient" size="md" className="h-9" onClick={open} loading={running} leftIcon={<CloudUpload className="h-4 w-4" />}>
            Browse files
          </Button>
        </div>
      </div>

      <AnimatePresence initial={false}>
        {items.length > 0 && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}>
            <div className="flex items-center justify-between px-5 pb-1 pt-1">
              <span className="text-xs font-medium text-slate-500">
                {items.filter((i) => i.status === "done").length}/{items.length} processed
              </span>
              {finished && (
                <button onClick={() => setItems([])} className="text-xs text-slate-500 hover:text-slate-800 dark:hover:text-slate-200">
                  Clear
                </button>
              )}
            </div>
            <ul className="max-h-72 space-y-1 overflow-y-auto px-3 pb-3" aria-live="polite">
              <AnimatePresence initial={false}>
                {items.map((it) => (
                  <motion.li
                    key={it.id}
                    layout
                    initial={{ opacity: 0, y: -6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, x: 20 }}
                    className="flex items-center gap-3 rounded-xl px-2 py-2 hover:bg-slate-100/60 dark:hover:bg-white/[0.03]"
                  >
                    <FileIcon ext={fileExt(it.file.name)} size="sm" />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate text-sm text-slate-800 dark:text-slate-100">{it.file.name}</span>
                        <span className="shrink-0 text-[11px] text-slate-400">{formatBytes(it.file.size)}</span>
                      </div>
                      {it.status === "uploading" || it.status === "queued" || it.status === "processing" ? (
                        <div className="mt-1.5 flex items-center gap-2">
                          <Progress value={it.status === "processing" ? 100 : it.progress} className="h-1" />
                          <span className="w-20 shrink-0 text-right text-[11px] text-slate-400">
                            {it.status === "queued" ? "Queued" : it.status === "processing" ? "Indexing…" : `${Math.round(it.progress)}%`}
                          </span>
                        </div>
                      ) : (
                        <div
                          className={cn(
                            "mt-0.5 truncate text-[11px]",
                            it.status === "done" && "text-emerald-600 dark:text-emerald-400",
                            it.status === "duplicate" && "text-amber-600 dark:text-amber-400",
                            it.status === "error" && "text-rose-600 dark:text-rose-400",
                          )}
                          title={it.message}
                        >
                          {it.message}
                        </div>
                      )}
                    </div>
                    <span className="shrink-0">
                      {it.status === "done" && <CheckCircle2 className="h-4 w-4 text-emerald-500" aria-label="Done" />}
                      {it.status === "duplicate" && <Copy className="h-4 w-4 text-amber-500" aria-label="Duplicate" />}
                      {it.status === "error" && <XCircle className="h-4 w-4 text-rose-500" aria-label="Error" />}
                      {(it.status === "uploading" || it.status === "processing") && (
                        <Loader2 className="h-4 w-4 animate-spin text-indigo-500" aria-label="Uploading" />
                      )}
                      {it.status === "queued" && <X className="h-4 w-4 text-slate-300" aria-hidden />}
                    </span>
                  </motion.li>
                ))}
              </AnimatePresence>
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  );
}

function mimeFor(ext: string): string {
  switch (ext) {
    case ".pdf":
      return "application/pdf";
    case ".docx":
      return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
    case ".txt":
      return "text/plain";
    case ".md":
      return "text/markdown";
    case ".html":
      return "text/html";
    case ".csv":
      return "text/csv";
    case ".xlsx":
      return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
    case ".pptx":
      return "application/vnd.openxmlformats-officedocument.presentationml.presentation";
    case ".png":
      return "image/png";
    default:
      return "image/jpeg";
  }
}
