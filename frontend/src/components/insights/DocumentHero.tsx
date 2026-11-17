import { useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Clock, Download, FileStack, HardDrive, Layers, MessageSquareText, Table2, UserRound } from "lucide-react";
import { toast } from "sonner";
import { api, downloadDocumentFile, errorMessage } from "../../lib/api";
import { qk } from "../../hooks/queries";
import { formatBytes, formatDate, timeAgo } from "../../lib/utils";
import { Badge, Button, Card, DomainBadge, Skeleton } from "../ui";
import { FileIcon } from "../Brand";

function Stat({ icon, label, value, title }: { icon: ReactNode; label: string; value: ReactNode; title?: string }) {
  return (
    <div
      title={title}
      className="flex min-w-0 items-center gap-2 rounded-xl border border-slate-200/80 bg-white/60 px-2.5 py-1.5 dark:border-white/[0.06] dark:bg-white/[0.03] [&>svg]:h-3.5 [&>svg]:w-3.5 [&>svg]:shrink-0 [&>svg]:text-slate-400"
    >
      {icon}
      <div className="min-w-0 leading-tight">
        <div className="truncate text-[13px] font-semibold tabular-nums text-slate-900 dark:text-white">{value}</div>
        <div className="truncate text-[10px] font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</div>
      </div>
    </div>
  );
}

export function DocumentHero({ docId }: { docId: string }) {
  const navigate = useNavigate();
  const q = useQuery({ queryKey: qk.document(docId), queryFn: () => api.document(docId) });
  const [downloading, setDownloading] = useState(false);
  const doc = q.data?.document;

  if (q.isLoading)
    return (
      <Card className="mb-5 flex items-center gap-4 p-4 sm:p-5">
        <Skeleton className="h-14 w-14 rounded-xl" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-4 w-56 max-w-full" />
          <Skeleton className="h-3 w-80 max-w-full" />
        </div>
      </Card>
    );
  // The hero is a nice-to-have: if metadata fails to load, the tabs still work.
  if (!doc) return null;

  const onDownload = async () => {
    setDownloading(true);
    try {
      await downloadDocumentFile(doc.doc_id, doc.filename);
    } catch (e) {
      toast.error("Download failed", { description: errorMessage(e) });
    } finally {
      setDownloading(false);
    }
  };

  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
      <Card className="relative mb-5 overflow-hidden p-4 sm:p-5">
        <div aria-hidden className="pointer-events-none absolute -right-16 -top-20 h-48 w-48 rounded-full bg-gradient-to-br from-indigo-500/20 via-violet-500/15 to-cyan-500/10 blur-3xl" />
        <div aria-hidden className="bg-brand-gradient absolute inset-x-0 top-0 h-px opacity-60" />
        <div className="relative flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 items-start gap-3.5 sm:items-center">
            <FileIcon ext={doc.file_type} size="lg" className="ring-1 ring-inset ring-black/5 dark:ring-white/10" />
            <div className="min-w-0">
              <h2 className="truncate text-base font-semibold tracking-tight text-slate-900 dark:text-white sm:text-lg" title={doc.filename}>
                {doc.filename}
              </h2>
              <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                <DomainBadge domain={doc.domain} />
                {doc.version > 1 && <Badge tone="violet">v{doc.version}</Badge>}
                <Badge tone="neutral" className="font-mono uppercase">{doc.file_type.replace(".", "")}</Badge>
                {doc.ocr_pages > 0 && <Badge tone="amber">OCR · {doc.ocr_pages}p</Badge>}
              </div>
            </div>
          </div>
          <div className="flex shrink-0 gap-2">
            <Button
              variant="gradient"
              size="sm"
              className="flex-1 sm:flex-none"
              leftIcon={<MessageSquareText className="h-3.5 w-3.5" />}
              onClick={() => navigate(`/chat?new=1&doc=${encodeURIComponent(doc.doc_id)}`)}
            >
              Ask in chat
            </Button>
            <Button variant="outline" size="sm" className="flex-1 sm:flex-none" leftIcon={<Download className="h-3.5 w-3.5" />} onClick={onDownload} loading={downloading}>
              Download
            </Button>
          </div>
        </div>
        <div className="relative mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:flex lg:flex-wrap">
          <Stat icon={<FileStack />} label="Pages" value={doc.page_count || "—"} />
          <Stat icon={<Layers />} label="Passages" value={doc.chunk_count} />
          <Stat icon={<Table2 />} label="Tables" value={doc.tables_count} />
          <Stat icon={<HardDrive />} label="Size" value={formatBytes(doc.file_size)} />
          <Stat icon={<Clock />} label="Uploaded" value={timeAgo(doc.uploaded_at)} title={formatDate(doc.uploaded_at, true)} />
          {doc.owner && <Stat icon={<UserRound />} label="Owner" value={doc.owner} />}
        </div>
      </Card>
    </motion.div>
  );
}
