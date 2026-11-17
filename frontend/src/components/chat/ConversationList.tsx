import { useMemo, useState, type KeyboardEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { toast } from "sonner";
import { Check, MessageSquare, Pencil, Plus, Search, Trash2, UserRound, X } from "lucide-react";
import { useAuth } from "../../hooks/useAuth";
import { api, errorMessage } from "../../lib/api";
import { qk, useConversations } from "../../hooks/queries";
import { cn, timeAgo } from "../../lib/utils";
import type { Conversation } from "../../types";
import { Button, ConfirmDialog, ErrorState, Input, Skeleton } from "../ui";

function bucket(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "Older";
  const now = new Date();
  const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const t = d.getTime();
  if (t >= startToday) return "Today";
  if (t >= startToday - 86400000) return "Yesterday";
  if (t >= startToday - 7 * 86400000) return "Previous 7 days";
  return "Older";
}

function Row({
  c,
  active,
  onSelect,
  onDelete,
  owner,
}: {
  c: Conversation;
  active: boolean;
  /** set when the conversation belongs to another user (administrator view) */
  owner?: string;
  onSelect: () => void;
  onDelete: () => void;
}) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(c.title);
  const rename = useMutation({
    mutationFn: (t: string) => api.renameConversation(c.conversation_id, t),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.conversations });
      qc.invalidateQueries({ queryKey: qk.conversation(c.conversation_id) });
    },
    onError: (e) => toast.error("Rename failed", { description: errorMessage(e) }),
  });
  const save = () => {
    const t = title.trim();
    setEditing(false);
    if (t && t !== c.title) rename.mutate(t);
    else setTitle(c.title);
  };
  const onKey = (e: KeyboardEvent) => {
    if (e.key === "Enter") save();
    if (e.key === "Escape") {
      setTitle(c.title);
      setEditing(false);
    }
  };

  if (editing)
    return (
      <div className="flex items-center gap-1 rounded-xl bg-slate-100 px-2 py-1.5 dark:bg-white/[0.06]">
        <input
          autoFocus
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={onKey}
          onBlur={save}
          aria-label="Conversation title"
          className="min-w-0 flex-1 bg-transparent text-sm text-slate-900 focus:outline-none dark:text-white"
        />
        <button onMouseDown={(e) => e.preventDefault()} onClick={save} className="rounded p-1 text-emerald-600 hover:bg-emerald-500/10" aria-label="Save title">
          <Check className="h-3.5 w-3.5" />
        </button>
        <button
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => {
            setTitle(c.title);
            setEditing(false);
          }}
          className="rounded p-1 text-slate-400 hover:bg-slate-500/10"
          aria-label="Cancel rename"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    );

  return (
    <div
      className={cn(
        "group relative flex items-center rounded-xl transition-colors",
        active ? "bg-indigo-500/10 ring-1 ring-inset ring-indigo-500/20" : "hover:bg-slate-100 dark:hover:bg-white/[0.04]",
      )}
    >
      <button onClick={onSelect} onDoubleClick={() => setEditing(true)} className="min-w-0 flex-1 px-3 py-2 text-left" aria-current={active ? "page" : undefined}>
        <div className={cn("truncate text-sm", active ? "font-medium text-slate-900 dark:text-white" : "text-slate-700 dark:text-slate-300")}>
          {rename.isPending ? title : c.title || "Untitled chat"}
        </div>
        <div className="flex items-center gap-1 text-[11px] text-slate-400">
          {owner && (
            <span className="inline-flex min-w-0 items-center gap-0.5 font-medium text-violet-600 dark:text-violet-300">
              <UserRound className="h-3 w-3 shrink-0" />
              <span className="truncate">{owner}</span> ·
            </span>
          )}
          <span className="shrink-0">
            {c.message_count} msg · {timeAgo(c.updated_at)}
          </span>
        </div>
      </button>
      <div className="flex shrink-0 gap-0.5 pr-1.5 opacity-100 transition-opacity lg:opacity-0 lg:group-focus-within:opacity-100 lg:group-hover:opacity-100">
        <button onClick={() => setEditing(true)} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-500/10 hover:text-slate-700 dark:hover:text-slate-200" aria-label={`Rename ${c.title}`}>
          <Pencil className="h-3.5 w-3.5" />
        </button>
        <button onClick={onDelete} className="rounded-lg p-1.5 text-slate-400 hover:bg-rose-500/10 hover:text-rose-500" aria-label={`Delete ${c.title}`}>
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

export function ConversationList({
  activeId,
  onSelect,
  onNew,
  onDeleted,
}: {
  activeId?: string;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDeleted: (id: string) => void;
}) {
  const qc = useQueryClient();
  const q = useConversations();
  const { user } = useAuth();
  const [search, setSearch] = useState("");
  const [toDelete, setToDelete] = useState<Conversation | null>(null);

  const del = useMutation({
    mutationFn: (id: string) => api.deleteConversation(id),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: qk.conversations });
      qc.removeQueries({ queryKey: qk.conversation(id) });
      toast.success("Conversation deleted");
      setToDelete(null);
      onDeleted(id);
    },
    onError: (e) => toast.error("Delete failed", { description: errorMessage(e) }),
  });

  const groups = useMemo(() => {
    const n = search.trim().toLowerCase();
    const list = [...(q.data?.conversations ?? [])]
      .filter((c) => !n || `${c.title} ${c.owner ?? ""}`.toLowerCase().includes(n))
      .sort((a, b) => b.updated_at.localeCompare(a.updated_at));
    const out: { label: string; items: Conversation[] }[] = [];
    for (const c of list) {
      const b = bucket(c.updated_at);
      const g = out.find((x) => x.label === b);
      if (g) g.items.push(c);
      else out.push({ label: b, items: [c] });
    }
    return out;
  }, [q.data, search]);

  return (
    <div className="flex h-full flex-col">
      <div className="space-y-2 p-3">
        <Button variant="gradient" className="w-full" onClick={onNew} leftIcon={<Plus className="h-4 w-4" />}>
          New chat
        </Button>
        <Input icon={<Search />} placeholder="Search chats" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Search conversations" className="h-9" />
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        {q.isLoading &&
          Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="px-3 py-2">
              <Skeleton className="h-3.5 w-4/5" />
              <Skeleton className="mt-1.5 h-2.5 w-1/3" />
            </div>
          ))}
        {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} className="py-6" />}
        {q.data && groups.length === 0 && (
          <div className="flex flex-col items-center px-4 py-10 text-center">
            <MessageSquare className="h-5 w-5 text-slate-400" />
            <p className="muted mt-2 text-xs">{search ? "No chats match." : "No conversations yet."}</p>
          </div>
        )}
        {groups.map((g) => (
          <div key={g.label} className="mb-2">
            <div className="px-3 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400">{g.label}</div>
            <AnimatePresence initial={false}>
              {g.items.map((c) => (
                <motion.div key={c.conversation_id} layout initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, height: 0 }}>
                  <Row
                    c={c}
                    owner={c.user_id && c.user_id !== user?.user_id ? c.owner : undefined}
                    active={c.conversation_id === activeId}
                    onSelect={() => onSelect(c.conversation_id)}
                    onDelete={() => setToDelete(c)}
                  />
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        ))}
      </div>
      <ConfirmDialog
        open={!!toDelete}
        onClose={() => setToDelete(null)}
        onConfirm={() => toDelete && del.mutate(toDelete.conversation_id)}
        loading={del.isPending}
        title="Delete conversation?"
        description={`“${toDelete?.title ?? ""}” and its messages will be permanently deleted.`}
      />
    </div>
  );
}
