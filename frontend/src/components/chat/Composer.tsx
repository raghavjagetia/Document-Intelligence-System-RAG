import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { ArrowUp, Square } from "lucide-react";
import { capitalize, cn } from "../../lib/utils";
import type { AnswerStyle, Document, QueryDomain } from "../../types";
import { DOMAINS } from "../../types";
import { Select } from "../ui";

/** How the answer is written. Every style searches the same way (meaning + exact words, AI re-ranked)
 * and only uses the documents; they differ in length and form. */
export const ANSWER_STYLES: { value: AnswerStyle; label: string; hint: string }[] = [
  {
    value: "quick",
    label: "Quick answer",
    hint: "Quick answer: the answer in one or two sentences, with sources.",
  },
  {
    value: "detailed",
    label: "Detailed answer",
    hint: "Detailed answer: the answer plus conditions, limits, exceptions and differences between documents, as bullet points.",
  },
  {
    value: "quote",
    label: "Exact quote",
    hint: "Exact quote: the relevant sentences copied word-for-word from your documents, with document and page.",
  },
];

export type Scope = { kind: "domain"; domain: QueryDomain } | { kind: "doc"; docId: string };

export function encodeScope(s: Scope) {
  return s.kind === "domain" ? `domain:${s.domain}` : `doc:${s.docId}`;
}
export function decodeScope(v: string): Scope {
  if (v.startsWith("doc:")) return { kind: "doc", docId: v.slice(4) };
  return { kind: "domain", domain: (v.slice(7) || "all") as QueryDomain };
}

export function Composer({
  onSend,
  onStop,
  streaming,
  scope,
  onScopeChange,
  answerStyle,
  onAnswerStyleChange,
  documents,
  autoFocus,
}: {
  onSend: (text: string) => void;
  onStop: () => void;
  streaming: boolean;
  scope: Scope;
  onScopeChange: (s: Scope) => void;
  answerStyle: AnswerStyle;
  onAnswerStyleChange: (s: AnswerStyle) => void;
  documents: Document[];
  autoFocus?: boolean;
}) {
  const [text, setText] = useState("");
  const ta = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ta.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = Math.min(200, el.scrollHeight) + "px";
  }, [text]);

  useEffect(() => {
    if (autoFocus) ta.current?.focus();
  }, [autoFocus]);

  const submit = () => {
    const t = text.trim();
    if (!t || streaming) return;
    onSend(t);
    setText("");
  };

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  const scopeDocMissing = scope.kind === "doc" && !documents.some((d) => d.doc_id === scope.docId);

  return (
    <div className="glass-strong rounded-2xl p-2 shadow-2xl shadow-indigo-500/[0.06] transition focus-within:border-indigo-500/40 focus-within:ring-4 focus-within:ring-indigo-500/10">
      <label htmlFor="composer" className="sr-only">
        Ask a question
      </label>
      <textarea
        id="composer"
        ref={ta}
        rows={1}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKey}
        placeholder="Ask anything about your documents, in any language…"
        className="block max-h-[200px] w-full resize-none bg-transparent px-3 py-2.5 text-[0.95rem] text-slate-900 placeholder:text-slate-400 focus:outline-none dark:text-white"
        style={{ boxShadow: "none" }}
      />
      <div className="flex flex-wrap items-center gap-2 px-1 pt-1">
        <div className="w-full min-w-0 sm:w-56">
          <Select
            value={encodeScope(scope)}
            onChange={(e) => onScopeChange(decodeScope(e.target.value))}
            aria-label="Search scope"
            className="h-8 rounded-lg text-xs"
          >
            <optgroup label="Domain">
              <option value="domain:all">All documents</option>
              {DOMAINS.map((d) => (
                <option key={d} value={`domain:${d}`}>
                  {capitalize(d)} domain
                </option>
              ))}
            </optgroup>
            {(documents.length > 0 || scopeDocMissing) && (
              <optgroup label="Specific document">
                {scopeDocMissing && scope.kind === "doc" && <option value={`doc:${scope.docId}`}>Selected document</option>}
                {documents.map((d) => (
                  <option key={d.doc_id} value={`doc:${d.doc_id}`}>
                    {d.filename}
                  </option>
                ))}
              </optgroup>
            )}
          </Select>
        </div>
        <div className="w-full min-w-0 sm:w-44">
          <Select
            value={answerStyle}
            onChange={(e) => onAnswerStyleChange(e.target.value as AnswerStyle)}
            aria-label="Answer style"
            title={ANSWER_STYLES.find((a) => a.value === answerStyle)?.hint}
            className="h-8 rounded-lg text-xs"
          >
            {ANSWER_STYLES.map((a) => (
              <option key={a.value} value={a.value}>
                {a.label}
              </option>
            ))}
          </Select>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <span className="hidden text-[11px] text-slate-400 xl:inline">
            <b className="font-medium">Enter</b> to send · <b className="font-medium">Shift+Enter</b> new line
          </span>
          {streaming ? (
            <button
              onClick={onStop}
              className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-900 text-white transition hover:scale-105 dark:bg-white dark:text-slate-900"
              aria-label="Stop generating"
            >
              <Square className="h-3.5 w-3.5 fill-current" />
            </button>
          ) : (
            <button
              onClick={submit}
              disabled={!text.trim()}
              className={cn(
                "flex h-9 w-9 items-center justify-center rounded-xl text-white transition",
                text.trim()
                  ? "bg-gradient-to-br from-indigo-500 via-violet-500 to-cyan-500 shadow-lg shadow-indigo-500/30 hover:scale-105"
                  : "cursor-not-allowed bg-slate-300 dark:bg-white/10",
              )}
              aria-label="Send message"
            >
              <ArrowUp className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
      <p className="px-2 pb-0.5 pt-1.5 text-[11px] leading-snug text-slate-400" aria-live="polite">
        {ANSWER_STYLES.find((a) => a.value === answerStyle)?.hint}
      </p>
    </div>
  );
}
