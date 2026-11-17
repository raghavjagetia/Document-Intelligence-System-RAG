import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { toast } from "sonner";
import { ArrowDown, Eye, FileText, Lightbulb, MessagesSquare, PanelLeft, Plus, Sparkles, X } from "lucide-react";
import { api, ApiError, errorMessage, streamQuery, StreamUnavailableError } from "../lib/api";
import { qk, useDocuments } from "../hooks/queries";
import { useAuth } from "../hooks/useAuth";
import { capitalize, cn } from "../lib/utils";
import { DOMAINS, type Message, type QueryDomain, type QueryRequest, type AnswerStyle } from "../types";
import { ConversationList } from "../components/chat/ConversationList";
import { AssistantMessage, UserBubble, type UIMessage } from "../components/chat/MessageView";
import { Composer, type Scope } from "../components/chat/Composer";
import { Drawer, ErrorState, Skeleton } from "../components/ui";

const STYLE_KEY = "documind-answer-style";

function blankMessage(role: "user" | "assistant", content: string, conversationId: string): UIMessage {
  return {
    message_id: `tmp-${role}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    conversation_id: conversationId,
    role,
    content,
    rewritten_query: null,
    citations: [],
    grounded: false,
    grounding_score: 0,
    confidence_score: 0,
    latency_seconds: 0,
    model_name: null,
    generation_mode: null,
    abstained: false,
    timestamp: new Date().toISOString(),
  };
}

export default function ChatPage() {
  const { conversationId } = useParams();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { user } = useAuth();

  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [scope, setScope] = useState<Scope>(() => {
    const doc = params.get("doc");
    return doc ? { kind: "doc", docId: doc } : { kind: "domain", domain: "all" };
  });
  const [style, setStyle] = useState<AnswerStyle>(() => {
    try {
      const v = localStorage.getItem(STYLE_KEY);
      if (v === "quick" || v === "detailed" || v === "quote") return v;
    } catch {
      /* ignore */
    }
    return "quick";
  });
  const [listOpen, setListOpen] = useState(false);
  const [atBottom, setAtBottom] = useState(true);

  const abortRef = useRef<AbortController | null>(null);
  /** conversation ids created by the in-flight stream – don't clobber local state with a fetch. */
  const streamingConvRef = useRef<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickRef = useRef(true);

  const docs = useDocuments();
  const documents = useMemo(() => docs.data?.documents ?? [], [docs.data]);
  const conv = useQuery({
    queryKey: qk.conversation(conversationId ?? ""),
    queryFn: () => api.conversation(conversationId!),
    enabled: !!conversationId,
  });
  const convData = conv.data?.conversation;
  /** username of another user whose conversation an administrator is viewing (read-only) */
  const readOnlyOwner =
    conversationId && convData?.user_id && convData.user_id !== user?.user_id ? convData.owner ?? "another user" : null;
  const suggestionDomain = scope.kind === "domain" && scope.domain !== "all" ? scope.domain : "";
  const suggestions = useQuery({
    queryKey: qk.suggestions(suggestionDomain),
    queryFn: () => api.suggestions(suggestionDomain || undefined),
    staleTime: 5 * 60_000,
  });

  useEffect(() => {
    try {
      localStorage.setItem(STYLE_KEY, style);
    } catch {
      /* ignore */
    }
  }, [style]);

  // ?new=1 → fresh chat; ?doc= → scope to doc
  useEffect(() => {
    const isNew = params.get("new") === "1";
    const doc = params.get("doc");
    if (!isNew && !doc) return;
    if (doc) setScope({ kind: "doc", docId: doc });
    if (isNew) {
      abortRef.current?.abort();
      setMessages([]);
      if (conversationId) navigate(`/chat${doc ? `?doc=${encodeURIComponent(doc)}` : ""}`, { replace: true });
    }
    const next = new URLSearchParams(params);
    next.delete("new");
    next.delete("doc");
    setParams(next, { replace: true });
  }, [params, setParams, navigate, conversationId]);

  // Sync messages from server when switching conversations.
  useEffect(() => {
    if (!conversationId) {
      if (!streamingConvRef.current) setMessages([]);
      return;
    }
    if (streamingConvRef.current === conversationId) return;
    if (conv.data && conv.data.conversation.conversation_id === conversationId) {
      setMessages(conv.data.messages);
      const d = conv.data.conversation.domain;
      if (d && (d === "all" || (DOMAINS as string[]).includes(d))) {
        setScope((s) => (s.kind === "doc" ? s : { kind: "domain", domain: d as QueryDomain }));
      }
    }
  }, [conversationId, conv.data]);

  // Abort stream on unmount.
  useEffect(() => () => abortRef.current?.abort(), []);

  // Auto-scroll
  useEffect(() => {
    const el = scrollRef.current;
    if (el && stickRef.current) el.scrollTo({ top: el.scrollHeight, behavior: streaming ? "auto" : "smooth" });
  }, [messages, streaming]);

  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const near = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    stickRef.current = near;
    setAtBottom(near);
  };
  const scrollToBottom = () => {
    stickRef.current = true;
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  };

  const patchMsg = (id: string, p: Partial<UIMessage> | ((m: UIMessage) => Partial<UIMessage>)) =>
    setMessages((ms) => ms.map((m) => (m.message_id === id ? { ...m, ...(typeof p === "function" ? p(m) : p) } : m)));

  const send = useCallback(
    async (question: string) => {
      if (streaming) return;
      stickRef.current = true;
      const convId = conversationId ?? "";
      const userTmp = blankMessage("user", question, convId);
      const asstTmp: UIMessage = { ...blankMessage("assistant", "", convId), streaming: true };
      let userId = userTmp.message_id;
      let asstId = asstTmp.message_id;
      setMessages((ms) => [...ms, userTmp, asstTmp]);
      setStreaming(true);

      const ctrl = new AbortController();
      abortRef.current = ctrl;
      const req: QueryRequest = {
        question,
        retrieval_mode: "hybrid",
        answer_style: style,
        ...(conversationId ? { conversation_id: conversationId } : {}),
        ...(scope.kind === "doc" ? { doc_id: scope.docId, domain: "all" } : { domain: scope.domain }),
      };

      let newConv: string | null = null;
      const adoptConversation = (cid: string) => {
        if (!conversationId && cid && !newConv) {
          newConv = cid;
          streamingConvRef.current = cid;
          navigate(`/chat/${encodeURIComponent(cid)}`, { replace: true });
        }
      };
      const finalize = (final: Message) => {
        const realId = final.message_id || asstId;
        patchMsg(asstId, { ...final, streaming: false });
        asstId = realId;
      };

      try {
        try {
          await streamQuery(
            req,
            {
              onMeta: (meta) => {
                adoptConversation(meta.conversation_id);
                if (meta.user_message) {
                  patchMsg(userId, meta.user_message);
                  userId = meta.user_message.message_id || userId;
                }
                patchMsg(asstId, { citations: meta.citations ?? [], rewritten_query: meta.rewritten_query, conversation_id: meta.conversation_id });
              },
              onToken: (t) => patchMsg(asstId, (m) => ({ content: m.content + t })),
              onDone: (final) => finalize(final),
              onError: (detail) => patchMsg(asstId, { streaming: false, error: detail }),
            },
            ctrl.signal,
          );
        } catch (e) {
          if (!(e instanceof StreamUnavailableError)) throw e;
          // Fallback to non-streaming endpoint.
          const r = await api.query(req, ctrl.signal);
          adoptConversation(r.conversation_id);
          patchMsg(userId, r.user_message);
          finalize(r.assistant_message);
        }
      } catch (e) {
        if ((e as Error).name === "AbortError") {
          patchMsg(asstId, { streaming: false, stopped: true });
        } else {
          const msg = errorMessage(e);
          patchMsg(asstId, { streaming: false, error: msg });
          if (!(e instanceof ApiError && e.status === 401)) toast.error("Couldn't get an answer", { description: msg });
        }
      } finally {
        setMessages((ms) => ms.map((m) => (m.streaming ? { ...m, streaming: false } : m)));
        setStreaming(false);
        abortRef.current = null;
        const cid = newConv ?? conversationId;
        qc.invalidateQueries({ queryKey: qk.conversations });
        qc.invalidateQueries({ queryKey: qk.stats });
        qc.invalidateQueries({ queryKey: qk.analytics });
        if (cid) {
          // Mark cache stale without overwriting local messages that include error/stopped state.
          qc.invalidateQueries({ queryKey: qk.conversation(cid), refetchType: "none" });
        }
        streamingConvRef.current = null;
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [streaming, conversationId, style, scope, navigate, qc],
  );

  const stop = () => abortRef.current?.abort();

  const newChat = () => {
    abortRef.current?.abort();
    setMessages([]);
    setListOpen(false);
    navigate("/chat");
  };

  const selectConv = (id: string) => {
    setListOpen(false);
    if (id !== conversationId) {
      abortRef.current?.abort();
      navigate(`/chat/${encodeURIComponent(id)}`);
    }
  };

  const onDeleted = (id: string) => {
    if (id === conversationId) newChat();
  };

  // Map each assistant message to the preceding user question (for rewrite + regenerate).
  const questionFor = useMemo(() => {
    const map = new Map<string, string>();
    let last = "";
    for (const m of messages) {
      if (m.role === "user") last = m.content;
      else map.set(m.message_id, last);
    }
    return map;
  }, [messages]);

  const lastAssistantId = [...messages].reverse().find((m) => m.role === "assistant")?.message_id;
  const scopedDoc = scope.kind === "doc" ? documents.find((d) => d.doc_id === scope.docId) : undefined;
  const loadingConv = !!conversationId && conv.isLoading && messages.length === 0;
  const showEmpty = !conversationId && messages.length === 0;

  const list = <ConversationList activeId={conversationId} onSelect={selectConv} onNew={newChat} onDeleted={onDeleted} />;

  return (
    <div className="flex h-full">
      <aside className="hidden w-72 shrink-0 border-r border-slate-200/80 bg-white/40 backdrop-blur-xl dark:border-white/[0.06] dark:bg-white/[0.01] md:block">
        {list}
      </aside>
      <Drawer open={listOpen} onClose={() => setListOpen(false)} side="left" title="Conversations">
        {list}
      </Drawer>

      <section className="relative flex min-w-0 flex-1 flex-col">
        {/* Header */}
        <div className="flex h-12 shrink-0 items-center gap-2 border-b border-slate-200/60 px-3 dark:border-white/[0.05] sm:px-5">
          <button onClick={() => setListOpen(true)} className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-500/10 md:hidden" aria-label="Show conversations">
            <PanelLeft className="h-4 w-4" />
          </button>
          <MessagesSquare className="hidden h-4 w-4 text-slate-400 sm:block" />
          <h1 className="min-w-0 flex-1 truncate text-sm font-medium text-slate-800 dark:text-slate-100">
            {conversationId ? conv.data?.conversation.title ?? (conv.isLoading ? "Loading…" : "Conversation") : "New chat"}
          </h1>
          {readOnlyOwner && (
            <span className="flex shrink-0 items-center gap-1 rounded-full bg-violet-500/10 px-2 py-0.5 text-[11px] font-medium text-violet-600 ring-1 ring-inset ring-violet-500/20 dark:text-violet-300">
              <Eye className="h-3 w-3" /> {readOnlyOwner}’s chat · read-only
            </span>
          )}
          {scope.kind === "doc" && (
            <span className="flex max-w-[50%] items-center gap-1 rounded-full bg-indigo-500/10 py-0.5 pl-2 pr-1 text-[11px] font-medium text-indigo-600 ring-1 ring-inset ring-indigo-500/20 dark:text-indigo-300">
              <FileText className="h-3 w-3 shrink-0" />
              <span className="truncate">{scopedDoc?.filename ?? "Selected document"}</span>
              <button onClick={() => setScope({ kind: "domain", domain: "all" })} className="rounded-full p-0.5 hover:bg-indigo-500/20" aria-label="Clear document scope">
                <X className="h-3 w-3" />
              </button>
            </span>
          )}
        </div>

        {/* Messages */}
        <div ref={scrollRef} onScroll={onScroll} className="min-h-0 flex-1 overflow-y-auto" aria-live="polite">
          <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6">
            {loadingConv && (
              <div className="space-y-6">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="space-y-3">
                    <div className="flex justify-end">
                      <Skeleton className="h-10 w-2/3 rounded-2xl" />
                    </div>
                    <div className="flex gap-3">
                      <Skeleton className="h-8 w-8 rounded-full" />
                      <Skeleton className="h-24 flex-1 rounded-2xl" />
                    </div>
                  </div>
                ))}
              </div>
            )}
            {conversationId && conv.isError && messages.length === 0 && <ErrorState error={conv.error} onRetry={() => conv.refetch()} />}

            {showEmpty && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col items-center pt-6 text-center sm:pt-14">
                <div className="relative mb-5">
                  <div className="absolute inset-0 animate-pulse rounded-3xl bg-gradient-to-br from-indigo-500 via-violet-500 to-cyan-500 opacity-40 blur-xl" />
                  <div className="relative flex h-16 w-16 items-center justify-center rounded-3xl bg-gradient-to-br from-indigo-500 via-violet-500 to-cyan-500 text-white shadow-xl">
                    <Sparkles className="h-7 w-7" />
                  </div>
                </div>
                <h2 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-white">What would you like to know?</h2>
                <p className="muted mt-2 max-w-md text-sm">
                  {scopedDoc
                    ? `Questions will be answered from “${scopedDoc.filename}”.`
                    : scope.kind === "domain" && scope.domain !== "all"
                      ? `Searching the ${capitalize(scope.domain)} domain.`
                      : "Answers come only from your documents, with the exact source shown for every fact."}
                </p>
                <div className="mt-8 grid w-full gap-2.5 sm:grid-cols-2">
                  {suggestions.isLoading &&
                    Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-16 rounded-2xl" />)}
                  {suggestions.data?.questions.slice(0, 6).map((q, i) => (
                    <motion.button
                      key={q}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.1 + i * 0.05 }}
                      whileHover={{ y: -2 }}
                      onClick={() => send(q)}
                      className="glass group flex items-start gap-3 rounded-2xl p-3.5 text-left text-sm text-slate-700 transition-colors hover:border-indigo-500/30 dark:text-slate-200"
                    >
                      <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-amber-500 transition-transform group-hover:scale-110" />
                      <span className="line-clamp-2">{q}</span>
                    </motion.button>
                  ))}
                </div>
                {suggestions.data && suggestions.data.questions.length === 0 && (
                  <p className="muted text-xs">Upload documents to get suggested questions.</p>
                )}
              </motion.div>
            )}

            <div className="space-y-7">
              {messages.map((m) =>
                m.role === "user" ? (
                  <UserBubble key={m.message_id} m={m} username={user?.username ?? "You"} />
                ) : (
                  <AssistantMessage
                    key={m.message_id}
                    m={m}
                    question={questionFor.get(m.message_id)}
                    canRegenerate={!streaming && m.message_id === lastAssistantId}
                    canRate={!readOnlyOwner}
                    onRegenerate={() => {
                      const q = questionFor.get(m.message_id);
                      if (q) send(q);
                    }}
                  />
                ),
              )}
            </div>
          </div>
        </div>

        <AnimatePresence>
          {!atBottom && messages.length > 0 && (
            <motion.button
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 8 }}
              onClick={scrollToBottom}
              className="glass-strong absolute bottom-36 left-1/2 z-10 flex h-8 w-8 -translate-x-1/2 items-center justify-center rounded-full"
              aria-label="Scroll to latest"
            >
              <ArrowDown className="h-4 w-4" />
            </motion.button>
          )}
        </AnimatePresence>

        {/* Composer */}
        <div className={cn("shrink-0 px-3 pb-3 pt-2 sm:px-6 sm:pb-5")}>
          <div className="mx-auto w-full max-w-3xl">
            {readOnlyOwner ? (
              <div className="glass flex flex-col items-center justify-between gap-3 rounded-2xl px-4 py-3 text-sm sm:flex-row">
                <span className="muted">
                  You are viewing <span className="font-medium text-slate-800 dark:text-slate-100">{readOnlyOwner}</span>’s conversation as an administrator.
                </span>
                <button
                  onClick={() => navigate("/chat?new=1")}
                  className="inline-flex shrink-0 items-center gap-1.5 rounded-xl bg-indigo-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-600"
                >
                  <Plus className="h-3.5 w-3.5" /> Start your own chat
                </button>
              </div>
            ) : (
            <Composer
              onSend={send}
              onStop={stop}
              streaming={streaming}
              scope={scope}
              onScopeChange={setScope}
              answerStyle={style}
              onAnswerStyleChange={setStyle}
              documents={documents}
              autoFocus
            />
            )}
            <p className="mt-2 text-center text-[11px] text-slate-400">
              DocuMind answers only from your documents and flags low-evidence answers. Verify important facts using the cited sources.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
