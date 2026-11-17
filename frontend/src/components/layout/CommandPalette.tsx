import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { CornerDownLeft, FileText, MessageSquarePlus, Moon, Search, Sun, Upload } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { qk } from "../../hooks/queries";
import { useTheme } from "../../hooks/useTheme";
import { cn } from "../../lib/utils";
import { navFor } from "./nav";
import { useAuth } from "../../hooks/useAuth";
import { Kbd } from "../ui";

interface Cmd {
  id: string;
  group: "Pages" | "Actions" | "Documents" | "Conversations";
  label: string;
  hint?: string;
  icon: ReactNode;
  run: () => void;
}

export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { theme, toggle } = useTheme();
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const docs = useQuery({ queryKey: qk.documents(), queryFn: () => api.documents(), enabled: open });
  const convs = useQuery({ queryKey: qk.conversations, queryFn: api.conversations, enabled: open });

  useEffect(() => {
    if (open) {
      setQ("");
      setActive(0);
      setTimeout(() => inputRef.current?.focus(), 20);
    }
  }, [open]);

  const go = (path: string) => {
    navigate(path);
    onClose();
  };

  const commands = useMemo<Cmd[]>(() => {
    const list: Cmd[] = [
      ...navFor(user?.role).map((n) => ({
        id: `nav-${n.to}`,
        group: "Pages" as const,
        label: n.label,
        hint: n.description,
        icon: <n.icon className="h-4 w-4" />,
        run: () => go(n.to),
      })),
      {
        id: "new-chat",
        group: "Actions",
        label: "Start new chat",
        icon: <MessageSquarePlus className="h-4 w-4" />,
        run: () => go("/chat?new=1"),
      },
      {
        id: "upload",
        group: "Actions",
        label: "Upload documents",
        icon: <Upload className="h-4 w-4" />,
        run: () => go("/documents?upload=1"),
      },
      {
        id: "theme",
        group: "Actions",
        label: theme === "dark" ? "Switch to light mode" : "Switch to dark mode",
        icon: theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />,
        run: () => {
          toggle();
          onClose();
        },
      },
      ...(docs.data?.documents ?? []).map((d) => ({
        id: `doc-${d.doc_id}`,
        group: "Documents" as const,
        label: d.filename,
        hint: `${d.domain} · ${d.chunk_count} passages`,
        icon: <FileText className="h-4 w-4" />,
        run: () => go(`/documents?doc=${encodeURIComponent(d.doc_id)}`),
      })),
      ...(convs.data?.conversations ?? []).slice(0, 20).map((c) => ({
        id: `conv-${c.conversation_id}`,
        group: "Conversations" as const,
        label: c.title || "Untitled chat",
        hint: `${c.message_count} messages`,
        icon: <MessageSquarePlus className="h-4 w-4" />,
        run: () => go(`/chat/${encodeURIComponent(c.conversation_id)}`),
      })),
    ];
    const needle = q.trim().toLowerCase();
    if (!needle) return list.slice(0, 40);
    return list.filter((c) => c.label.toLowerCase().includes(needle) || c.hint?.toLowerCase().includes(needle));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, docs.data, convs.data, theme, user?.role]);

  useEffect(() => setActive(0), [q]);
  useEffect(() => {
    listRef.current?.querySelector<HTMLElement>(`[data-idx="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(commands.length - 1, a + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(0, a - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      commands[active]?.run();
    } else if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    }
  };

  let lastGroup = "";
  return createPortal(
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[95] flex items-start justify-center px-4 pt-[12vh]">
          <motion.div
            className="absolute inset-0 bg-slate-950/50 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label="Command palette"
            className="glass-strong relative w-full max-w-xl overflow-hidden rounded-2xl"
            initial={{ opacity: 0, scale: 0.96, y: -8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -8 }}
            transition={{ type: "spring", stiffness: 420, damping: 32 }}
          >
            <div className="flex items-center gap-3 border-b border-slate-200 px-4 dark:border-white/10">
              <Search className="h-4 w-4 text-slate-400" aria-hidden />
              <input
                ref={inputRef}
                value={q}
                onChange={(e) => setQ(e.target.value)}
                onKeyDown={onKey}
                placeholder="Search pages, documents, conversations…"
                aria-label="Search commands"
                role="combobox"
                aria-expanded="true"
                aria-controls="cmdk-list"
                aria-activedescendant={commands[active] ? `cmdk-${commands[active].id}` : undefined}
                className="h-14 flex-1 bg-transparent text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none dark:text-white"
                style={{ boxShadow: "none" }}
              />
              <Kbd>Esc</Kbd>
            </div>
            <div ref={listRef} id="cmdk-list" role="listbox" className="max-h-[50vh] overflow-y-auto p-2">
              {commands.length === 0 && <div className="muted px-3 py-10 text-center text-sm">No results for “{q}”</div>}
              {commands.map((c, i) => {
                const header = c.group !== lastGroup ? c.group : null;
                lastGroup = c.group;
                return (
                  <div key={c.id}>
                    {header && (
                      <div className="px-3 pb-1 pt-3 text-[10px] font-semibold uppercase tracking-wider text-slate-400">{header}</div>
                    )}
                    <button
                      id={`cmdk-${c.id}`}
                      data-idx={i}
                      role="option"
                      aria-selected={i === active}
                      tabIndex={-1}
                      onMouseMove={() => setActive(i)}
                      onClick={c.run}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition-colors",
                        i === active ? "bg-indigo-500/10 text-slate-900 dark:text-white" : "text-slate-600 dark:text-slate-300",
                      )}
                    >
                      <span className={cn("text-slate-400", i === active && "text-indigo-500")}>{c.icon}</span>
                      <span className="min-w-0 flex-1 truncate">{c.label}</span>
                      {c.hint && <span className="hidden max-w-[45%] truncate text-xs text-slate-400 sm:block">{c.hint}</span>}
                      {i === active && <CornerDownLeft className="h-3.5 w-3.5 text-slate-400" aria-hidden />}
                    </button>
                  </div>
                );
              })}
            </div>
            <div className="flex items-center gap-4 border-t border-slate-200 px-4 py-2 text-[11px] text-slate-400 dark:border-white/10">
              <span className="flex items-center gap-1">
                <Kbd>↑</Kbd>
                <Kbd>↓</Kbd> navigate
              </span>
              <span className="flex items-center gap-1">
                <Kbd>↵</Kbd> select
              </span>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
