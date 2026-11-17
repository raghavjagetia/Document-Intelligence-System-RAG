import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Check, ChevronsUpDown, Search } from "lucide-react";
import { useDismiss } from "../hooks/misc";
import { cn, formatBytes } from "../lib/utils";
import type { Document } from "../types";
import { FileIcon } from "./Brand";

export function DocCombobox({
  documents,
  value,
  onChange,
  placeholder = "Select a document…",
  loading,
  exclude,
  label,
}: {
  documents: Document[];
  value: string | null;
  onChange: (id: string) => void;
  placeholder?: string;
  loading?: boolean;
  exclude?: string | null;
  label?: string;
}) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useDismiss(open, close, [root, panel]);

  // The list is portalled to <body> with fixed positioning so cards below (each its own
  // stacking context because of backdrop blur) can never paint over it.
  const [pos, setPos] = useState<{
    left: number;
    width: number;
    top?: number;
    bottom?: number;
    maxH: number;
  } | null>(null);
  const place = useCallback(() => {
    const r = root.current?.querySelector("button")?.getBoundingClientRect();
    if (!r) return;
    const below = window.innerHeight - r.bottom - 12;
    const above = r.top - 12;
    const up = below < 260 && above > below;
    const maxH = Math.max(160, Math.min(380, (up ? above : below) - 8));
    setPos(
      up
        ? {
            left: r.left,
            width: r.width,
            bottom: window.innerHeight - r.top + 6,
            maxH,
          }
        : { left: r.left, width: r.width, top: r.bottom + 6, maxH },
    );
  }, []);
  useLayoutEffect(() => {
    if (open) place();
  }, [open, place]);
  useEffect(() => {
    if (!open) return;
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [open, place]);
  useEffect(() => {
    listRef.current
      ?.querySelector<HTMLElement>(`[data-index="${active}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [active]);

  const selected = documents.find((d) => d.doc_id === value);
  /** documents from several users (administrator view): label each with its owner */
  const multiOwner = useMemo(
    () => new Set(documents.map((d) => d.owner)).size > 1,
    [documents],
  );
  const options = useMemo(() => {
    const n = q.trim().toLowerCase();
    return documents.filter(
      (d) =>
        d.doc_id !== exclude &&
        (!n ||
          `${d.filename} ${d.domain} ${d.owner ?? ""}`
            .toLowerCase()
            .includes(n)),
    );
  }, [documents, q, exclude]);

  const choose = (d: Document) => {
    onChange(d.doc_id);
    setOpen(false);
    setQ("");
  };

  const onKey = (e: KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(options.length - 1, a + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(0, a - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (options[active]) choose(options[active]);
    }
  };

  return (
    <div ref={root} className="relative">
      {label && (
        <div className="mb-1.5 text-xs font-medium text-slate-600 dark:text-slate-300">
          {label}
        </div>
      )}
      <button
        type="button"
        onClick={() => {
          setOpen((o) => !o);
          setActive(0);
          setTimeout(() => input.current?.focus(), 20);
        }}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={`${id}-list`}
        className="flex h-12 w-full items-center gap-3 rounded-xl border border-slate-200 bg-white/70 px-3 text-left text-sm transition hover:border-indigo-500/40 dark:border-white/10 dark:bg-white/[0.03]"
      >
        {selected ? (
          <>
            <FileIcon ext={selected.file_type} size="sm" />
            <span className="min-w-0 flex-1 truncate font-medium text-slate-900 dark:text-white">
              {selected.filename}
              {multiOwner && selected.owner && (
                <span className="muted font-normal"> · {selected.owner}</span>
              )}
            </span>
          </>
        ) : (
          <span className="flex-1 text-slate-400">
            {loading ? "Loading documents…" : placeholder}
          </span>
        )}
        <ChevronsUpDown className="h-4 w-4 shrink-0 text-slate-400" />
      </button>
      {createPortal(
        <AnimatePresence>
          {open && pos && (
            <motion.div
              ref={panel}
              initial={{ opacity: 0, y: pos.top !== undefined ? -4 : 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: pos.top !== undefined ? -4 : 4 }}
              transition={{ duration: 0.12 }}
              style={{
                position: "fixed",
                left: pos.left,
                width: pos.width,
                top: pos.top,
                bottom: pos.bottom,
              }}
              className="glass-strong z-[90] flex flex-col overflow-hidden rounded-xl shadow-2xl shadow-black/30"
            >
              <div className="flex items-center gap-2 border-b border-slate-200 px-3 dark:border-white/10">
                <Search className="h-4 w-4 text-slate-400" />
                <input
                  ref={input}
                  value={q}
                  onChange={(e) => {
                    setQ(e.target.value);
                    setActive(0);
                  }}
                  onKeyDown={onKey}
                  placeholder="Search documents…"
                  role="combobox"
                  aria-expanded="true"
                  aria-controls={`${id}-list`}
                  aria-activedescendant={
                    options[active]
                      ? `${id}-opt-${options[active].doc_id}`
                      : undefined
                  }
                  className="h-10 flex-1 bg-transparent text-sm focus:outline-none"
                  style={{ boxShadow: "none" }}
                />
              </div>
              <ul
                ref={listRef}
                id={`${id}-list`}
                role="listbox"
                style={{ maxHeight: pos.maxH - 44 }}
                className="overflow-y-auto p-1"
              >
                {options.length === 0 && (
                  <li className="muted px-3 py-6 text-center text-xs">
                    {documents.length
                      ? "No matches"
                      : "No documents uploaded yet"}
                  </li>
                )}
                {options.map((d, i) => (
                  <li
                    key={d.doc_id}
                    data-index={i}
                    id={`${id}-opt-${d.doc_id}`}
                    role="option"
                    aria-selected={d.doc_id === value}
                    onMouseMove={() => setActive(i)}
                    onClick={() => choose(d)}
                    className={cn(
                      "flex cursor-pointer items-center gap-3 rounded-lg px-2.5 py-2 text-sm",
                      i === active && "bg-indigo-500/10",
                    )}
                  >
                    <FileIcon ext={d.file_type} size="sm" />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-slate-900 dark:text-white">
                        {d.filename}
                      </div>
                      <div className="text-[11px] text-slate-400">
                        {multiOwner && d.owner ? `${d.owner} · ` : ""}
                        {d.domain} · {d.page_count} pages ·{" "}
                        {formatBytes(d.file_size)}
                        {d.version > 1 ? ` · v${d.version}` : ""}
                      </div>
                    </div>
                    {d.doc_id === value && (
                      <Check className="h-4 w-4 text-indigo-500" />
                    )}
                  </li>
                ))}
              </ul>
            </motion.div>
          )}
        </AnimatePresence>,
        document.body,
      )}
    </div>
  );
}
