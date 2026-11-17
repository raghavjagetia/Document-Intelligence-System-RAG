import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowDownUp, FileSearch, FileText, LayoutGrid, Layers, List, Search, Upload, UserRound, X } from "lucide-react";
import { useDocuments } from "../hooks/queries";
import { useAuth } from "../hooks/useAuth";
import { useDebounce } from "../hooks/misc";
import { capitalize, cn, formatBytes, formatDate, formatStyle, timeAgo } from "../lib/utils";
import { DOMAINS, type Document } from "../types";
import { Badge, Button, Card, Chip, DomainBadge, EmptyState, ErrorState, Input, PageHeader, Segmented, Select, Skeleton } from "../components/ui";
import { FileIcon } from "../components/Brand";
import { UploadZone } from "../components/documents/UploadZone";
import { DocumentDrawer } from "../components/documents/DocumentDrawer";

type SortKey = "newest" | "oldest" | "name" | "size" | "chunks";
type View = "grid" | "table";
const VIEW_KEY = "documind-docs-view";

function sortDocs(docs: Document[], key: SortKey) {
  const d = [...docs];
  switch (key) {
    case "newest":
      return d.sort((a, b) => b.uploaded_at.localeCompare(a.uploaded_at));
    case "oldest":
      return d.sort((a, b) => a.uploaded_at.localeCompare(b.uploaded_at));
    case "name":
      return d.sort((a, b) => a.filename.localeCompare(b.filename));
    case "size":
      return d.sort((a, b) => b.file_size - a.file_size);
    case "chunks":
      return d.sort((a, b) => b.chunk_count - a.chunk_count);
  }
}

function DocCard({ d, onOpen, index, showOwner }: { d: Document; onOpen: () => void; index: number; showOwner: boolean }) {
  return (
    <motion.button
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.96 }}
      transition={{ delay: Math.min(index, 12) * 0.03 }}
      whileHover={{ y: -3 }}
      onClick={onOpen}
      className="glass group flex flex-col rounded-2xl p-4 text-left transition-shadow hover:border-indigo-500/30 hover:shadow-xl hover:shadow-indigo-500/[0.06]"
      aria-label={`Open ${d.filename}`}
    >
      <div className="flex items-start justify-between gap-2">
        <FileIcon ext={d.file_type} />
        <div className="flex items-center gap-1">
          {d.version > 1 && <Badge tone="violet">v{d.version}</Badge>}
          {d.status === "failed" && <Badge tone="red">failed</Badge>}
          <DomainBadge domain={d.domain} />
        </div>
      </div>
      <div className="mt-4 line-clamp-2 min-h-[2.5rem] text-sm font-medium text-slate-900 group-hover:text-indigo-600 dark:text-white dark:group-hover:text-indigo-300" title={d.filename}>
        {d.filename}
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 border-t border-slate-200/80 pt-3 text-[11px] dark:border-white/[0.06]">
        <div>
          <div className="text-slate-400">Pages</div>
          <div className="font-medium tabular-nums text-slate-700 dark:text-slate-200">{d.page_count}</div>
        </div>
        <div>
          <div className="text-slate-400">Passages</div>
          <div className="font-medium tabular-nums text-slate-700 dark:text-slate-200">{d.chunk_count}</div>
        </div>
        <div>
          <div className="text-slate-400">Size</div>
          <div className="font-medium tabular-nums text-slate-700 dark:text-slate-200">{formatBytes(d.file_size)}</div>
        </div>
      </div>
      <div className="mt-3 flex items-center justify-between gap-2 text-[11px] text-slate-400">
        <span>{timeAgo(d.uploaded_at)}</span>
        {showOwner && d.owner && (
          <span className="inline-flex min-w-0 items-center gap-1 text-slate-500 dark:text-slate-400">
            <UserRound className="h-3 w-3 shrink-0" />
            <span className="truncate">{d.owner}</span>
          </span>
        )}
      </div>
    </motion.button>
  );
}

export default function DocumentsPage() {
  const [params, setParams] = useSearchParams();
  const [search, setSearch] = useState("");
  const debounced = useDebounce(search, 300);
  const [domain, setDomain] = useState<string>("");
  const [format, setFormat] = useState<string>("");
  const [sort, setSort] = useState<SortKey>("newest");
  const [owner, setOwner] = useState<string>("");
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [view, setView] = useState<View>(() => {
    try {
      return (localStorage.getItem(VIEW_KEY) as View) || "grid";
    } catch {
      return "grid";
    }
  });
  const [showUpload, setShowUpload] = useState(params.get("upload") === "1");
  const uploadRef = useRef<HTMLDivElement>(null);

  const q = useDocuments(domain || undefined, debounced.trim() || undefined);
  const openDoc = params.get("doc");

  useEffect(() => {
    try {
      localStorage.setItem(VIEW_KEY, view);
    } catch {
      /* ignore */
    }
  }, [view]);

  useEffect(() => {
    if (params.get("upload") === "1") {
      setShowUpload(true);
      setTimeout(() => uploadRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 100);
      const next = new URLSearchParams(params);
      next.delete("upload");
      setParams(next, { replace: true });
    }
  }, [params, setParams]);

  const docs = useMemo(() => q.data?.documents ?? [], [q.data]);
  const formats = useMemo(() => Array.from(new Set(docs.map((d) => d.file_type.toLowerCase()))).sort(), [docs]);
  const owners = useMemo(() => Array.from(new Set(docs.map((d) => d.owner ?? ""))).filter(Boolean).sort(), [docs]);
  const visible = useMemo(
    () =>
      sortDocs(
        docs.filter((d) => (!format || d.file_type.toLowerCase() === format) && (!owner || d.owner === owner)),
        sort,
      ),
    [docs, format, owner, sort],
  );

  const setOpenDoc = (id: string | null) => {
    const next = new URLSearchParams(params);
    if (id) next.set("doc", id);
    else next.delete("doc");
    setParams(next, { replace: !id });
  };

  const filtersActive = !!(search || domain || format || owner);

  return (
    <div>
      <PageHeader
        icon={<FileText />}
        title="Documents"
        description={
          isAdmin
            ? `Every document in the system, across ${owners.length} user${owners.length === 1 ? "" : "s"}. Uploads go to your own account.`
            : "Upload, organise and explore the documents that power your answers."
        }
        actions={
          <Button
            variant={showUpload ? "outline" : "gradient"}
            leftIcon={showUpload ? <X className="h-4 w-4" /> : <Upload className="h-4 w-4" />}
            onClick={() => setShowUpload((s) => !s)}
          >
            {showUpload ? "Hide upload" : "Upload"}
          </Button>
        }
      />

      <AnimatePresence initial={false}>
        {showUpload && (
          <motion.div
            ref={uploadRef}
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="mb-6 overflow-hidden"
          >
            <UploadZone />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Toolbar */}
      <div className="mb-4 flex flex-col gap-3">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <div className="flex-1">
            <Input
              icon={<Search />}
              placeholder="Search documents by name or content…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search documents"
            />
          </div>
          <div className="flex flex-wrap gap-2">
            {isAdmin && (
              <div className="w-40">
                <Select value={owner} onChange={(e) => setOwner(e.target.value)} aria-label="Filter by owner">
                  <option value="">All users</option>
                  {owners.map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </Select>
              </div>
            )}
            <div className="w-36">
              <Select value={format} onChange={(e) => setFormat(e.target.value)} aria-label="Filter by format">
                <option value="">All formats</option>
                {formats.map((f) => (
                  <option key={f} value={f}>
                    {formatStyle(f).label}
                  </option>
                ))}
              </Select>
            </div>
            <div className="w-36">
              <Select value={sort} onChange={(e) => setSort(e.target.value as SortKey)} aria-label="Sort documents">
                <option value="newest">Newest</option>
                <option value="oldest">Oldest</option>
                <option value="name">Name A–Z</option>
                <option value="size">Largest</option>
                <option value="chunks">Most passages</option>
              </Select>
            </div>
            <Segmented
              ariaLabel="View mode"
              value={view}
              onChange={setView}
              items={[
                { value: "grid", label: <span className="sr-only">Grid</span>, icon: <LayoutGrid /> },
                { value: "table", label: <span className="sr-only">Table</span>, icon: <List /> },
              ]}
            />
          </div>
        </div>
        <div className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1 [scrollbar-width:none]">
          <Chip active={!domain} onClick={() => setDomain("")}>
            All domains
          </Chip>
          {DOMAINS.map((d) => (
            <Chip key={d} active={domain === d} onClick={() => setDomain(domain === d ? "" : d)}>
              {capitalize(d)}
            </Chip>
          ))}
        </div>
      </div>

      <div className="mb-3 flex items-center justify-between text-xs text-slate-500">
        <span>
          {q.isLoading ? "Loading…" : `${visible.length} document${visible.length === 1 ? "" : "s"}`}
          {q.data && q.data.total !== visible.length && ` of ${q.data.total}`}
        </span>
        {filtersActive && (
          <button
            className="font-medium text-indigo-600 hover:underline dark:text-indigo-400"
            onClick={() => {
              setSearch("");
              setDomain("");
              setFormat("");
              setOwner("");
            }}
          >
            Clear filters
          </button>
        )}
      </div>

      {q.isLoading ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Card key={i} className="p-4">
              <Skeleton className="h-10 w-10 rounded-xl" />
              <Skeleton className="mt-4 h-4 w-3/4" />
              <Skeleton className="mt-2 h-4 w-1/2" />
              <Skeleton className="mt-5 h-8 w-full" />
            </Card>
          ))}
        </div>
      ) : q.isError ? (
        <Card>
          <ErrorState error={q.error} onRetry={() => q.refetch()} />
        </Card>
      ) : visible.length === 0 ? (
        <Card>
          {filtersActive ? (
            <EmptyState icon={<FileSearch />} title="No documents match your filters" description="Try a different search term or domain." />
          ) : (
            <EmptyState
              icon={<Upload />}
              title="Your library is empty"
              description="Upload PDFs, Word files, spreadsheets, slides or images to start asking questions."
              action={
                <Button variant="gradient" leftIcon={<Upload className="h-4 w-4" />} onClick={() => setShowUpload(true)}>
                  Upload documents
                </Button>
              }
            />
          )}
        </Card>
      ) : view === "grid" ? (
        <motion.div layout className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          <AnimatePresence mode="popLayout">
            {visible.map((d, i) => (
              <DocCard key={d.doc_id} d={d} index={i} showOwner={isAdmin} onOpen={() => setOpenDoc(d.doc_id)} />
            ))}
          </AnimatePresence>
        </motion.div>
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs font-medium text-slate-500 dark:border-white/[0.07]">
                  <th className="px-4 py-3">Name</th>
                  {isAdmin && <th className="px-3 py-3">Owner</th>}
                  <th className="px-3 py-3">Domain</th>
                  <th className="px-3 py-3 text-right">Pages</th>
                  <th className="px-3 py-3 text-right">
                    <span className="inline-flex items-center gap-1">
                      <Layers className="h-3 w-3" /> Chunks
                    </span>
                  </th>
                  <th className="px-3 py-3 text-right">Size</th>
                  <th className="px-3 py-3">Version</th>
                  <th className="px-4 py-3">
                    <span className="inline-flex items-center gap-1">
                      <ArrowDownUp className="h-3 w-3" /> Uploaded
                    </span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {visible.map((d, i) => (
                  <motion.tr
                    key={d.doc_id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: Math.min(i, 15) * 0.02 }}
                    onClick={() => setOpenDoc(d.doc_id)}
                    onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), setOpenDoc(d.doc_id))}
                    tabIndex={0}
                    className="cursor-pointer border-b border-slate-100 transition-colors last:border-0 hover:bg-indigo-500/[0.04] dark:border-white/[0.04]"
                  >
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-3">
                        <FileIcon ext={d.file_type} size="sm" />
                        <span className="max-w-[280px] truncate font-medium text-slate-900 dark:text-white" title={d.filename}>
                          {d.filename}
                        </span>
                      </div>
                    </td>
                    {isAdmin && <td className="px-3 py-2.5 text-slate-600 dark:text-slate-300">{d.owner}</td>}
                    <td className="px-3 py-2.5">
                      <DomainBadge domain={d.domain} />
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-slate-600 dark:text-slate-300">{d.page_count}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-slate-600 dark:text-slate-300">{d.chunk_count}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-slate-600 dark:text-slate-300">{formatBytes(d.file_size)}</td>
                    <td className="px-3 py-2.5">
                      <Badge tone={d.version > 1 ? "violet" : "neutral"}>v{d.version}</Badge>
                    </td>
                    <td className={cn("px-4 py-2.5 text-slate-500")}>{formatDate(d.uploaded_at)}</td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <DocumentDrawer docId={openDoc} onClose={() => setOpenDoc(null)} />
    </div>
  );
}
