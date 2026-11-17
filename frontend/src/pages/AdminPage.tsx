import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Activity,
  ChevronLeft,
  ChevronRight,
  Database,
  Eye,
  FileText,
  HardDrive,
  KeyRound,
  LogOut,
  MessageSquareText,
  Search,
  ShieldCheck,
  ShieldOff,
  Trash2,
  UserCheck,
  UserCog,
  UserPlus,
  UserX,
  Users,
} from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { UserActivityDrawer } from "../components/admin/UserActivityDrawer";
import { qk, useAdminOverview } from "../hooks/queries";
import { api, errorMessage } from "../lib/api";
import { cn, fmtPct, fmtSeconds, formatBytes, formatStyle, timeAgo } from "../lib/utils";
import type { AdminUserRow } from "../types";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  ConfirmDialog,
  Dialog,
  DomainBadge,
  EmptyState,
  ErrorState,
  Input,
  Label,
  PageHeader,
  Select,
  Skeleton,
  Tabs,
  Tooltip,
} from "../components/ui";

const PAGE_SIZE = 10;

function Kpi({ label, value, icon, delay }: { label: string; value: ReactNode; icon: ReactNode; delay: number }) {
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay }}>
      <Card className="flex items-center gap-3 p-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500/15 via-violet-500/10 to-cyan-500/15 text-indigo-500 ring-1 ring-indigo-500/20 dark:text-indigo-300">
          {icon}
        </div>
        <div className="min-w-0">
          <div className="muted text-xs">{label}</div>
          <div className="truncate text-xl font-semibold text-slate-900 dark:text-white">{value}</div>
        </div>
      </Card>
    </motion.div>
  );
}

function IconAction({
  label,
  onClick,
  children,
  danger,
  disabled,
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
  danger?: boolean;
  disabled?: boolean;
}) {
  return (
    <Tooltip label={label} width={180}>
      <button
        type="button"
        onClick={onClick}
        disabled={disabled}
        aria-label={label}
        className={cn(
          "rounded-lg p-1.5 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 disabled:pointer-events-none disabled:opacity-30 dark:text-slate-400 dark:hover:bg-white/[0.06] dark:hover:text-white [&>svg]:h-4 [&>svg]:w-4",
          danger && "hover:bg-rose-500/10 hover:text-rose-600 dark:hover:bg-rose-500/10 dark:hover:text-rose-400",
        )}
      >
        {children}
      </button>
    </Tooltip>
  );
}

function Pager({ page, total, onPage }: { page: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  if (total <= PAGE_SIZE) return null;
  const from = page * PAGE_SIZE + 1;
  const to = Math.min(total, (page + 1) * PAGE_SIZE);
  const nums = Array.from({ length: pages }, (_, i) => i).filter((i) => i === 0 || i === pages - 1 || Math.abs(i - page) <= 1);
  return (
    <div className="flex flex-col items-center justify-between gap-3 border-t border-slate-100 px-4 py-3 sm:flex-row dark:border-white/5">
      <span className="muted text-xs tabular-nums">
        Showing {from}–{to} of {total}
      </span>
      <div className="flex items-center gap-1">
        <Button variant="ghost" size="sm" onClick={() => onPage(page - 1)} disabled={page === 0} leftIcon={<ChevronLeft className="h-4 w-4" />}>
          Prev
        </Button>
        {nums.map((n, i) => (
          <span key={n} className="flex items-center">
            {i > 0 && n - nums[i - 1] > 1 && <span className="muted px-1 text-xs">…</span>}
            <button
              type="button"
              onClick={() => onPage(n)}
              aria-current={n === page ? "page" : undefined}
              className={cn(
                "h-8 min-w-8 rounded-lg px-2 text-xs font-medium tabular-nums transition",
                n === page
                  ? "bg-indigo-500 text-white shadow-sm shadow-indigo-500/30"
                  : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-white/[0.06]",
              )}
            >
              {n + 1}
            </button>
          </span>
        ))}
        <Button variant="ghost" size="sm" onClick={() => onPage(page + 1)} disabled={page >= pages - 1} rightIcon={<ChevronRight className="h-4 w-4" />}>
          Next
        </Button>
      </div>
    </div>
  );
}

function usePaged<T>(rows: T[], resetKey: string) {
  const [page, setPage] = useState(0);
  useEffect(() => setPage(0), [resetKey]);
  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const safe = Math.min(page, pages - 1);
  return { page: safe, setPage, slice: rows.slice(safe * PAGE_SIZE, (safe + 1) * PAGE_SIZE) };
}

const th = "px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400";
const td = "px-4 py-3 align-middle text-sm text-slate-700 dark:text-slate-200";
const tr = "border-b border-slate-100 transition-colors last:border-0 hover:bg-slate-50/70 dark:border-white/5 dark:hover:bg-white/[0.02]";

type Pending =
  | { kind: "delete-user"; user: AdminUserRow }
  | { kind: "delete-doc"; id: string; name: string }
  | { kind: "password"; user: AdminUserRow }
  | null;

export default function AdminPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const q = useAdminOverview(isAdmin);
  const qc = useQueryClient();
  const [tab, setTab] = useState("users");
  const [filter, setFilter] = useState("");
  const [pending, setPending] = useState<Pending>(null);
  const [newPassword, setNewPassword] = useState("");
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ username: "", email: "", password: "", role: "user" as "user" | "admin" });
  const [viewUser, setViewUser] = useState<AdminUserRow | null>(null);
  const [viewConv, setViewConv] = useState<string | null>(null);

  const refresh = () => {
    qc.invalidateQueries({ queryKey: qk.admin });
    qc.invalidateQueries({ queryKey: qk.stats });
    qc.invalidateQueries({ queryKey: qk.analytics });
  };
  const run = useMutation({
    mutationFn: (fn: () => Promise<unknown>) => fn(),
    onSuccess: refresh,
    onError: (e) => toast.error(errorMessage(e)),
  });
  const act = (fn: () => Promise<unknown>, ok: string) =>
    run.mutate(fn, {
      onSuccess: () => {
        toast.success(ok);
        setPending(null);
      },
    });

  const f = filter.trim().toLowerCase();
  const users = useMemo(
    () => (q.data?.users ?? []).filter((u) => !f || `${u.username} ${u.email} ${u.role}`.toLowerCase().includes(f)),
    [q.data, f],
  );
  const documents = useMemo(
    () => (q.data?.documents ?? []).filter((d) => !f || `${d.filename} ${d.owner} ${d.domain}`.toLowerCase().includes(f)),
    [q.data, f],
  );
  const recent = useMemo(
    () => (q.data?.recent_questions ?? []).filter((r) => !f || `${r.username} ${r.question}`.toLowerCase().includes(f)),
    [q.data, f],
  );
  const pu = usePaged(users, `${f}`);
  const pd = usePaged(documents, `${f}`);
  const pr = usePaged(recent, `${f}`);

  if (user && !isAdmin) return <Navigate to="/" replace />;
  const t = q.data?.totals;
  const suspended = q.data?.users.filter((u) => u.disabled).length ?? 0;

  const onCreate = (e: FormEvent) => {
    e.preventDefault();
    run.mutate(() => api.adminCreateUser(form), {
      onSuccess: () => {
        toast.success(`Created ${form.username}`);
        setCreating(false);
        setForm({ username: "", email: "", password: "", role: "user" });
      },
    });
  };

  return (
    <div className="space-y-6">
      <PageHeader
        icon={<ShieldCheck />}
        title="Administration"
        description="Manage every account, document and conversation in the system."
        actions={
          <Button variant="gradient" onClick={() => setCreating(true)} leftIcon={<UserPlus className="h-4 w-4" />}>
            Add user
          </Button>
        }
      />

      {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {q.isLoading || !t
          ? Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-[72px] rounded-2xl" />)
          : [
              { label: "Users", value: suspended ? `${t.users} · ${suspended} suspended` : t.users, icon: <Users className="h-5 w-5" /> },
              { label: "Active sessions", value: t.active_sessions, icon: <Activity className="h-5 w-5" /> },
              { label: "Documents", value: t.documents, icon: <FileText className="h-5 w-5" /> },
              { label: "Searchable passages", value: t.chunks.toLocaleString(), icon: <Database className="h-5 w-5" /> },
              { label: "Questions asked", value: t.questions, icon: <MessageSquareText className="h-5 w-5" /> },
              { label: "Storage", value: formatBytes(t.storage_bytes), icon: <HardDrive className="h-5 w-5" /> },
            ].map((k, i) => <Kpi key={k.label} {...k} delay={i * 0.04} />)}
      </div>

      <Card>
        <CardHeader
          title="Directory"
          description="Search, page through and manage users, documents and questions"
          action={
            <div className="w-48 sm:w-72">
              <Input
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder="Filter…"
                aria-label="Filter"
                icon={<Search className="h-4 w-4" />}
              />
            </div>
          }
        />
        <div className="px-5 pt-3">
          <Tabs
            value={tab}
            onChange={setTab}
            items={[
              { value: "users", label: `Users (${users.length})` },
              { value: "documents", label: `Documents (${documents.length})` },
              { value: "activity", label: `Recent questions (${recent.length})` },
            ]}
          />
        </div>

        <div className="mt-2 overflow-x-auto">
          {tab === "users" && (
            <table className="w-full min-w-[880px]">
              <thead>
                <tr className="border-b border-slate-200 dark:border-white/10">
                  <th className={th}>User</th>
                  <th className={th}>Role</th>
                  <th className={th}>Status</th>
                  <th className={cn(th, "text-right")}>Docs</th>
                  <th className={cn(th, "text-right")}>Storage</th>
                  <th className={cn(th, "text-right")}>Questions</th>
                  <th className={th}>Last active</th>
                  <th className={cn(th, "text-right")}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {pu.slice.map((u) => {
                  const self = u.user_id === user?.user_id;
                  return (
                    <tr key={u.user_id} className={cn(tr, u.disabled && "opacity-60")}>
                      <td className={td}>
                        <div className="font-medium text-slate-900 dark:text-white">
                          {u.username} {self && <span className="muted text-xs font-normal">(you)</span>}
                        </div>
                        <div className="muted text-xs">{u.email}</div>
                      </td>
                      <td className={td}>
                        <Badge tone={u.role === "admin" ? "violet" : "neutral"}>{u.role}</Badge>
                      </td>
                      <td className={td}>
                        {u.disabled ? (
                          <Badge tone="red">suspended</Badge>
                        ) : u.sessions > 0 ? (
                          <Badge tone="green">online · {u.sessions}</Badge>
                        ) : (
                          <Badge tone="neutral">active</Badge>
                        )}
                      </td>
                      <td className={cn(td, "text-right tabular-nums")}>{u.documents}</td>
                      <td className={cn(td, "text-right tabular-nums")}>{formatBytes(u.storage_bytes)}</td>
                      <td className={cn(td, "text-right tabular-nums")}>{u.questions}</td>
                      <td className={cn(td, "muted text-xs")}>{u.last_active ? timeAgo(u.last_active) : "never"}</td>
                      <td className={cn(td, "text-right")}>
                        <div className="inline-flex items-center gap-0.5">
                          <IconAction label="View activity" onClick={() => setViewUser(u)}>
                            <Eye />
                          </IconAction>
                          <IconAction
                            label={u.role === "admin" ? "Remove admin rights" : "Make administrator"}
                            disabled={self}
                            onClick={() =>
                              act(
                                () => api.adminUpdateUser(u.user_id, { role: u.role === "admin" ? "user" : "admin" }),
                                `${u.username} is now ${u.role === "admin" ? "a user" : "an administrator"}`,
                              )
                            }
                          >
                            {u.role === "admin" ? <ShieldOff /> : <UserCog />}
                          </IconAction>
                          <IconAction
                            label={u.disabled ? "Reactivate account" : "Suspend account"}
                            disabled={self}
                            onClick={() =>
                              act(
                                () => api.adminUpdateUser(u.user_id, { disabled: !u.disabled }),
                                `${u.username} ${u.disabled ? "reactivated" : "suspended"}`,
                              )
                            }
                          >
                            {u.disabled ? <UserCheck /> : <UserX />}
                          </IconAction>
                          <IconAction
                            label="Reset password"
                            onClick={() => {
                              setNewPassword("");
                              setPending({ kind: "password", user: u });
                            }}
                          >
                            <KeyRound />
                          </IconAction>
                          <IconAction
                            label="Sign out all sessions"
                            disabled={self || u.sessions === 0}
                            onClick={() => act(() => api.adminLogoutUser(u.user_id), `Signed ${u.username} out everywhere`)}
                          >
                            <LogOut />
                          </IconAction>
                          <IconAction label="Delete user" danger disabled={self} onClick={() => setPending({ kind: "delete-user", user: u })}>
                            <Trash2 />
                          </IconAction>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}

          {tab === "documents" && (
            <table className="w-full min-w-[820px]">
              <thead>
                <tr className="border-b border-slate-200 dark:border-white/10">
                  <th className={th}>Document</th>
                  <th className={th}>Owner</th>
                  <th className={th}>Domain</th>
                  <th className={cn(th, "text-right")}>Pages</th>
                  <th className={cn(th, "text-right")}>Passages</th>
                  <th className={cn(th, "text-right")}>Size</th>
                  <th className={th}>Uploaded</th>
                  <th className={cn(th, "text-right")}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {pd.slice.map((d) => {
                  const fmt = formatStyle(d.file_type);
                  return (
                    <tr key={d.doc_id} className={tr}>
                      <td className={cn(td, "max-w-[18rem]")}>
                        <div className="flex items-center gap-2">
                          <span className={cn("shrink-0 rounded-md px-1.5 py-0.5 text-[10px] font-semibold", fmt.className)}>{fmt.label}</span>
                          <span className="truncate font-medium text-slate-900 dark:text-white" title={d.filename}>
                            {d.filename}
                          </span>
                          {d.version > 1 && <Badge tone="cyan">v{d.version}</Badge>}
                          {d.ocr_pages > 0 && <Badge tone="amber">OCR</Badge>}
                        </div>
                      </td>
                      <td className={td}>{d.owner}</td>
                      <td className={td}>
                        <DomainBadge domain={d.domain} />
                      </td>
                      <td className={cn(td, "text-right tabular-nums")}>{d.page_count}</td>
                      <td className={cn(td, "text-right tabular-nums")}>{d.chunk_count}</td>
                      <td className={cn(td, "text-right tabular-nums")}>{formatBytes(d.file_size)}</td>
                      <td className={cn(td, "muted text-xs")}>{timeAgo(d.uploaded_at)}</td>
                      <td className={cn(td, "text-right")}>
                        <IconAction label="Delete document" danger onClick={() => setPending({ kind: "delete-doc", id: d.doc_id, name: d.filename })}>
                          <Trash2 />
                        </IconAction>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}

          {tab === "activity" && (
            <table className="w-full min-w-[820px]">
              <thead>
                <tr className="border-b border-slate-200 dark:border-white/10">
                  <th className={th}>When</th>
                  <th className={th}>User</th>
                  <th className={th}>Question</th>
                  <th className={cn(th, "text-right")}>Confidence</th>
                  <th className={cn(th, "text-right")}>Answer time</th>
                  <th className={cn(th, "text-right")}>Transcript</th>
                </tr>
              </thead>
              <tbody>
                {pr.slice.map((r, i) => (
                  <tr key={`${r.timestamp}-${i}`} className={tr}>
                    <td className={cn(td, "muted whitespace-nowrap text-xs")}>{timeAgo(r.timestamp)}</td>
                    <td className={td}>{r.username}</td>
                    <td className={cn(td, "max-w-md")}>
                      <div className="truncate font-medium text-slate-900 dark:text-white" title={r.question}>
                        {r.question}
                      </div>
                      <div className="muted truncate text-xs" title={r.answer}>
                        {r.answer}
                      </div>
                    </td>
                    <td className={cn(td, "text-right tabular-nums")}>
                      {r.abstained ? <Badge tone="amber">not in documents</Badge> : fmtPct(r.confidence_score)}
                    </td>
                    <td className={cn(td, "text-right tabular-nums")}>{fmtSeconds(r.latency_seconds)}</td>
                    <td className={cn(td, "text-right")}>
                      <IconAction
                        label="Open conversation"
                        onClick={() => {
                          const owner = q.data?.users.find((u) => u.username === r.username) ?? null;
                          setViewConv(r.conversation_id);
                          setViewUser(owner);
                        }}
                      >
                        <Eye />
                      </IconAction>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {q.data && ((tab === "users" && !users.length) || (tab === "documents" && !documents.length) || (tab === "activity" && !recent.length)) && (
            <EmptyState icon={<Search className="h-5 w-5" />} title="Nothing matches" description="Try a different filter." />
          )}
        </div>

        {tab === "users" && <Pager page={pu.page} total={users.length} onPage={pu.setPage} />}
        {tab === "documents" && <Pager page={pd.page} total={documents.length} onPage={pd.setPage} />}
        {tab === "activity" && <Pager page={pr.page} total={recent.length} onPage={pr.setPage} />}
      </Card>

      <UserActivityDrawer
        user={viewUser}
        initialConversation={viewConv}
        onClose={() => {
          setViewUser(null);
          setViewConv(null);
        }}
      />

      <ConfirmDialog
        open={pending?.kind === "delete-user"}
        onClose={() => setPending(null)}
        loading={run.isPending}
        title={`Delete ${pending?.kind === "delete-user" ? pending.user.username : ""}?`}
        description="The account, all of its documents, vectors and conversations will be permanently removed."
        onConfirm={() => pending?.kind === "delete-user" && act(() => api.adminDeleteUser(pending.user.user_id), `Deleted ${pending.user.username}`)}
      />
      <ConfirmDialog
        open={pending?.kind === "delete-doc"}
        onClose={() => setPending(null)}
        loading={run.isPending}
        title="Delete document?"
        description={pending?.kind === "delete-doc" ? `“${pending.name}” will be removed from its owner's library and the search index.` : ""}
        onConfirm={() => pending?.kind === "delete-doc" && act(() => api.adminDeleteDocument(pending.id), "Document deleted")}
      />
      <Dialog
        open={pending?.kind === "password"}
        onClose={() => setPending(null)}
        title={`Reset password for ${pending?.kind === "password" ? pending.user.username : ""}`}
        description="The user will be signed out of every device and must log in with the new password."
        footer={
          <>
            <Button variant="ghost" onClick={() => setPending(null)}>
              Cancel
            </Button>
            <Button
              disabled={newPassword.length < 8}
              loading={run.isPending}
              onClick={() =>
                pending?.kind === "password" &&
                act(() => api.adminUpdateUser(pending.user.user_id, { password: newPassword }), "Password updated")
              }
            >
              Set password
            </Button>
          </>
        }
      >
        <Label htmlFor="new-pw">New password</Label>
        <Input id="new-pw" type="text" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="At least 8 characters" icon={<KeyRound />} />
      </Dialog>

      <Dialog open={creating} onClose={() => setCreating(false)} title="Add user" description="Create an account. Share the password with the user securely.">
        <form onSubmit={onCreate} className="space-y-4">
          <div>
            <Label htmlFor="nu-name">Username</Label>
            <Input id="nu-name" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} placeholder="jane" />
          </div>
          <div>
            <Label htmlFor="nu-email">Email</Label>
            <Input id="nu-email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="jane@example.com" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="nu-pw">Password</Label>
              <Input id="nu-pw" type="text" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="Min 8 characters" />
            </div>
            <div>
              <Label htmlFor="nu-role">Role</Label>
              <Select id="nu-role" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as "user" | "admin" })}>
                <option value="user">User</option>
                <option value="admin">Administrator</option>
              </Select>
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="ghost" onClick={() => setCreating(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="gradient" loading={run.isPending} leftIcon={<UserPlus className="h-4 w-4" />}>
              Create user
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
