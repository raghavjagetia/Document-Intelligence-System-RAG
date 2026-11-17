import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toast } from "sonner";
import {
  ChevronDown,
  Download,
  GitBranch,
  Hash,
  Info,
  Layers,
  MessageSquareText,
  Search,
  Sparkles,
  Trash2,
} from "lucide-react";
import { api, downloadDocumentFile, errorMessage } from "../../lib/api";
import { qk } from "../../hooks/queries";
import { cn, formatBytes, formatDate } from "../../lib/utils";
import type { Chunk, ElementType } from "../../types";
import { Badge, Button, ConfirmDialog, DomainBadge, Drawer, EmptyState, ErrorState, Input, Skeleton, SkeletonText, Tabs } from "../ui";
import { FileIcon } from "../Brand";

const ELEMENT_TONE: Record<ElementType, "indigo" | "violet" | "cyan" | "amber" | "green" | "neutral"> = {
  heading: "violet",
  paragraph: "neutral",
  list: "cyan",
  table: "amber",
  slide: "green",
  text: "indigo",
};

function ChunkRow({ chunk }: { chunk: Chunk }) {
  const [open, setOpen] = useState(false);
  const preview = chunk.content.replace(/\s+/g, " ").slice(0, 160);
  return (
    <li className="rounded-xl border border-slate-200 bg-white/50 transition-colors hover:border-indigo-500/30 dark:border-white/[0.07] dark:bg-white/[0.02]">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-start gap-3 px-3.5 py-3 text-left"
      >
        <span className="mt-0.5 font-mono text-[11px] tabular-nums text-slate-400">#{chunk.chunk_index}</span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge tone={ELEMENT_TONE[chunk.element_type] ?? "neutral"}>{chunk.element_type}</Badge>
            <Badge>p. {chunk.page_number}</Badge>
            {chunk.section && (
              <span className="truncate text-xs font-medium text-slate-700 dark:text-slate-200" title={chunk.section}>
                {chunk.section}
              </span>
            )}
          </div>
          {!open && <p className="muted mt-1.5 line-clamp-2 text-xs">{preview}</p>}
        </div>
        <ChevronDown className={cn("mt-0.5 h-4 w-4 shrink-0 text-slate-400 transition-transform", open && "rotate-180")} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
            <div className="border-t border-slate-200 px-3.5 py-3 dark:border-white/[0.07]">
              {chunk.element_type === "table" ? (
                <div className="markdown text-xs">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{chunk.content}</ReactMarkdown>
                </div>
              ) : (
                <p className="whitespace-pre-wrap text-xs leading-relaxed text-slate-700 dark:text-slate-300">{chunk.content}</p>
              )}
              <div className="mt-3 flex gap-3 text-[11px] text-slate-400">
                <span>{chunk.char_count} chars</span>
                <span>{chunk.token_count} tokens</span>
                <span className="truncate font-mono">{chunk.chunk_id}</span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </li>
  );
}

type TabKey = "overview" | "chunks" | "versions";

export function DocumentDrawer({ docId, onClose }: { docId: string | null; onClose: () => void }) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [tab, setTab] = useState<TabKey>("overview");
  const [chunkSearch, setChunkSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<ElementType | "all">("all");
  const [confirm, setConfirm] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const detail = useQuery({ queryKey: qk.document(docId ?? ""), queryFn: () => api.document(docId!), enabled: !!docId });
  const versions = useQuery({ queryKey: qk.versions(docId ?? ""), queryFn: () => api.versions(docId!), enabled: !!docId });

  const del = useMutation({
    mutationFn: () => api.deleteDocument(docId!),
    onSuccess: () => {
      toast.success("Document deleted", { description: detail.data?.document.filename });
      qc.invalidateQueries({ queryKey: ["documents"] });
      qc.invalidateQueries({ queryKey: qk.stats });
      setConfirm(false);
      onClose();
    },
    onError: (e) => toast.error("Delete failed", { description: errorMessage(e) }),
  });

  const doc = detail.data?.document;
  const chunks = useMemo(() => detail.data?.chunks ?? [], [detail.data]);
  const types = useMemo(() => Array.from(new Set(chunks.map((c) => c.element_type))), [chunks]);
  const filtered = useMemo(() => {
    const n = chunkSearch.trim().toLowerCase();
    return chunks.filter(
      (c) =>
        (typeFilter === "all" || c.element_type === typeFilter) &&
        (!n || c.content.toLowerCase().includes(n) || c.section.toLowerCase().includes(n)),
    );
  }, [chunks, chunkSearch, typeFilter]);

  const onDownload = async () => {
    if (!doc) return;
    setDownloading(true);
    try {
      await downloadDocumentFile(doc.doc_id, doc.filename);
    } catch (e) {
      toast.error("Download failed", { description: errorMessage(e) });
    } finally {
      setDownloading(false);
    }
  };

  const handleClose = () => {
    setTab("overview");
    setChunkSearch("");
    setTypeFilter("all");
    onClose();
  };

  return (
    <>
      <Drawer
        open={!!docId}
        onClose={handleClose}
        title={doc ? doc.filename : detail.isLoading ? "Loading…" : "Document"}
        subtitle={doc && <span className="font-mono">{doc.doc_id}</span>}
      >
        {detail.isLoading && (
          <div className="space-y-4 p-5">
            <div className="flex items-center gap-3">
              <Skeleton className="h-14 w-14 rounded-xl" />
              <SkeletonText lines={2} className="flex-1" />
            </div>
            <Skeleton className="h-24 w-full" />
            <SkeletonText lines={5} />
          </div>
        )}
        {detail.isError && <ErrorState error={detail.error} onRetry={() => detail.refetch()} />}
        {doc && (
          <div className="p-5">
            <div className="flex items-center gap-4">
              <FileIcon ext={doc.file_type} size="lg" />
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-1.5">
                  <DomainBadge domain={doc.domain} />
                  <Badge tone="violet">v{doc.version}</Badge>
                  <Badge tone={doc.status === "indexed" ? "green" : "red"}>{doc.status}</Badge>
                </div>
                <div className="muted mt-1.5 text-xs">Uploaded {formatDate(doc.uploaded_at, true)}</div>
              </div>
            </div>

            <div className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-3">
              <Button
                variant="gradient"
                size="sm"
                className="col-span-2 sm:col-span-1"
                leftIcon={<MessageSquareText className="h-3.5 w-3.5" />}
                onClick={() => navigate(`/chat?new=1&doc=${encodeURIComponent(doc.doc_id)}`)}
              >
                Chat with doc
              </Button>
              <Button variant="outline" size="sm" leftIcon={<Sparkles className="h-3.5 w-3.5" />} onClick={() => navigate(`/insights?doc=${encodeURIComponent(doc.doc_id)}`)}>
                Analyze
              </Button>
              <Button variant="outline" size="sm" leftIcon={<Download className="h-3.5 w-3.5" />} onClick={onDownload} loading={downloading}>
                Download
              </Button>
            </div>

            <Tabs
              className="mt-6"
              value={tab}
              onChange={setTab}
              items={[
                { value: "overview", label: "Overview", icon: <Info /> },
                { value: "chunks", label: `Chunks (${chunks.length})`, icon: <Layers /> },
                { value: "versions", label: "Versions", icon: <GitBranch /> },
              ]}
            />

            <div className="pt-5">
              {tab === "overview" && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-5">
                  <dl className="grid grid-cols-2 gap-2">
                    {[
                      ["Format", doc.file_type.replace(".", "").toUpperCase()],
                      ["Size", formatBytes(doc.file_size)],
                      ["Pages", doc.page_count],
                      ["Chunks", doc.chunk_count],
                      ["Tables", doc.tables_count],
                      ["OCR pages", doc.ocr_pages],
                      ["Version", `v${doc.version}`],
                      ["Parent", doc.parent_doc_id ? doc.parent_doc_id.slice(0, 12) + "…" : "—"],
                    ].map(([k, v]) => (
                      <div key={String(k)} className="rounded-xl border border-slate-200 bg-white/50 px-3 py-2.5 dark:border-white/[0.07] dark:bg-white/[0.02]">
                        <dt className="text-[11px] text-slate-500 dark:text-slate-400">{k}</dt>
                        <dd className="mt-0.5 truncate text-sm font-medium tabular-nums text-slate-900 dark:text-white">{v}</dd>
                      </div>
                    ))}
                  </dl>
                  <div className="rounded-xl border border-rose-500/20 bg-rose-500/[0.04] p-4">
                    <div className="text-sm font-medium text-slate-900 dark:text-white">Danger zone</div>
                    <p className="muted mt-0.5 text-xs">Removes the document and everything DocuMind uses to search it. This cannot be undone.</p>
                    <Button variant="danger" size="sm" className="mt-3" leftIcon={<Trash2 className="h-3.5 w-3.5" />} onClick={() => setConfirm(true)}>
                      Delete document
                    </Button>
                  </div>
                </motion.div>
              )}

              {tab === "chunks" && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                  <div className="mb-3 space-y-2">
                    <Input icon={<Search />} placeholder="Search passages…" value={chunkSearch} onChange={(e) => setChunkSearch(e.target.value)} aria-label="Search passages" />
                    <div className="flex flex-wrap gap-1.5">
                      {(["all", ...types] as (ElementType | "all")[]).map((t) => (
                        <button
                          key={t}
                          onClick={() => setTypeFilter(t)}
                          aria-pressed={typeFilter === t}
                          className={cn(
                            "rounded-full px-2.5 py-0.5 text-[11px] font-medium ring-1 ring-inset transition",
                            typeFilter === t
                              ? "bg-indigo-500 text-white ring-indigo-500"
                              : "text-slate-500 ring-slate-200 hover:ring-slate-300 dark:ring-white/10",
                          )}
                        >
                          {t}
                        </button>
                      ))}
                    </div>
                  </div>
                  {filtered.length === 0 ? (
                    <EmptyState icon={<Hash />} title="No passages match" className="py-8" />
                  ) : (
                    <ul className="space-y-2">
                      {filtered.slice(0, 200).map((c) => (
                        <ChunkRow key={c.chunk_id} chunk={c} />
                      ))}
                      {filtered.length > 200 && <li className="muted py-2 text-center text-xs">Showing first 200 of {filtered.length} — refine your search.</li>}
                    </ul>
                  )}
                </motion.div>
              )}

              {tab === "versions" && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                  {versions.isLoading && <SkeletonText lines={4} />}
                  {versions.isError && <ErrorState error={versions.error} onRetry={() => versions.refetch()} />}
                  {versions.data && versions.data.versions.length === 0 && <EmptyState icon={<GitBranch />} title="No version history" className="py-8" />}
                  {versions.data && versions.data.versions.length > 0 && (
                    <ol className="relative ml-2 border-l border-slate-200 dark:border-white/10">
                      {versions.data.versions.map((v) => {
                        const current = v.doc_id === doc.doc_id;
                        return (
                          <li key={v.doc_id} className="mb-4 ml-5">
                            <span
                              className={cn(
                                "absolute -left-[7px] mt-1.5 h-3.5 w-3.5 rounded-full border-2 border-white dark:border-[#11111a]",
                                current ? "bg-brand-gradient" : "bg-slate-300 dark:bg-slate-600",
                              )}
                            />
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="text-sm font-semibold text-slate-900 dark:text-white">Version {v.version}</span>
                              {current && <Badge tone="indigo">current</Badge>}
                            </div>
                            <div className="muted mt-0.5 text-xs">
                              {formatDate(v.uploaded_at, true)} · {formatBytes(v.file_size)} · {v.chunk_count} passages
                            </div>
                            {!current && (
                              <div className="mt-1.5 flex gap-3">
                                <button
                                  className="text-xs font-medium text-indigo-600 hover:underline dark:text-indigo-400"
                                  onClick={() => navigate(`/documents?doc=${encodeURIComponent(v.doc_id)}`)}
                                >
                                  Open
                                </button>
                                <button
                                  className="text-xs font-medium text-indigo-600 hover:underline dark:text-indigo-400"
                                  onClick={() => navigate(`/insights?tab=compare&a=${encodeURIComponent(v.doc_id)}&b=${encodeURIComponent(doc.doc_id)}`)}
                                >
                                  Compare with current
                                </button>
                              </div>
                            )}
                          </li>
                        );
                      })}
                    </ol>
                  )}
                </motion.div>
              )}
            </div>
          </div>
        )}
      </Drawer>
      <ConfirmDialog
        open={confirm}
        onClose={() => setConfirm(false)}
        onConfirm={() => del.mutate()}
        loading={del.isPending}
        title="Delete this document?"
        description={`“${doc?.filename ?? ""}” and all of its chunks will be permanently removed. This cannot be undone.`}
      />
    </>
  );
}
