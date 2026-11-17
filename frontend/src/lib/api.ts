import type {
  AdminOverview,
  AdminUserDetail,
  Analytics,
  AuthResponse,
  CompareResponse,
  Conversation,
  DocumentDetail,
  DocumentList,
  Document,
  EntitiesResponse,
  EvalReport,
  EvalStatus,
  ExtractDocType,
  ExtractResponse,
  Health,
  Message,
  SourceView,
  QueryRequest,
  QueryResponse,
  Statistics,
  StreamMeta,
  SummaryResponse,
  SystemStatus,
  UploadResult,
  User,
} from "../types";

const BASE = "/api";
const TOKEN_KEY = "documind-token";
export const UNAUTHORIZED_EVENT = "documind:unauthorized";

// ---------------------------------------------------------------- token
export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}
export function setToken(token: string) {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* ignore */
  }
}
export function clearToken() {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

// ---------------------------------------------------------------- errors
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

function extractDetail(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const d = (body as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d) && d.length && typeof d[0] === "object" && d[0] && "msg" in d[0]) {
      return String((d[0] as { msg: unknown }).msg);
    }
  }
  return fallback;
}

const AUTH_PUBLIC = ["/auth/login", "/auth/register"];

function handleUnauthorized(path: string) {
  if (AUTH_PUBLIC.includes(path)) return;
  clearToken();
  window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
}

function authHeaders(extra?: HeadersInit): Headers {
  const h = new Headers(extra);
  const t = getToken();
  if (t) h.set("Authorization", `Bearer ${t}`);
  return h;
}

async function parseError(res: Response): Promise<ApiError> {
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    /* not json */
  }
  const fallback =
    res.status === 0
      ? "Network error"
      : res.status >= 500
        ? `Server error (${res.status})`
        : res.status === 404
          ? "Not found"
          : `Request failed (${res.status})`;
  return new ApiError(res.status, extractDetail(body, fallback));
}

/** Small fetch wrapper: JSON in/out, bearer token, 401 handling. */
export async function request<T>(
  path: string,
  init: { method?: string; body?: unknown; signal?: AbortSignal } = {},
): Promise<T> {
  const headers = authHeaders();
  let body: BodyInit | undefined;
  if (init.body !== undefined) {
    if (init.body instanceof FormData) body = init.body;
    else {
      headers.set("Content-Type", "application/json");
      body = JSON.stringify(init.body);
    }
  }
  let res: Response;
  try {
    res = await fetch(BASE + path, { method: init.method ?? "GET", headers, body, signal: init.signal });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(0, "Cannot reach the DocuMind server. Is the backend running?");
  }
  if (res.status === 401) {
    handleUnauthorized(path);
    throw await parseError(res);
  }
  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  if (!text) return undefined as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new ApiError(res.status, "Unexpected response from server");
  }
}

function qs(params: Record<string, string | undefined | null>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v) sp.set(k, v);
  const s = sp.toString();
  return s ? `?${s}` : "";
}

// ---------------------------------------------------------------- upload with progress
export function uploadDocuments(
  files: File[],
  domain: string,
  onProgress?: (fraction: number) => void,
): { promise: Promise<UploadResult>; abort: () => void } {
  const xhr = new XMLHttpRequest();
  const promise = new Promise<UploadResult>((resolve, reject) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    fd.append("domain", domain);
    xhr.open("POST", `${BASE}/documents/upload`);
    const t = getToken();
    if (t) xhr.setRequestHeader("Authorization", `Bearer ${t}`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total);
    };
    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        /* ignore */
      }
      if (xhr.status === 401) {
        handleUnauthorized("/documents/upload");
        reject(new ApiError(401, extractDetail(body, "Session expired")));
      } else if (xhr.status >= 200 && xhr.status < 300 && body) {
        resolve(body as UploadResult);
      } else {
        reject(new ApiError(xhr.status, extractDetail(body, `Upload failed (${xhr.status})`)));
      }
    };
    xhr.onerror = () => reject(new ApiError(0, "Network error during upload"));
    xhr.onabort = () => reject(new ApiError(0, "Upload cancelled"));
    xhr.send(fd);
  });
  return { promise, abort: () => xhr.abort() };
}

// ---------------------------------------------------------------- file download
export async function downloadDocumentFile(docId: string, filename: string) {
  const res = await fetch(`${BASE}/documents/${encodeURIComponent(docId)}/file`, { headers: authHeaders() });
  if (res.status === 401) {
    handleUnauthorized(`/documents/${docId}/file`);
    throw await parseError(res);
  }
  if (!res.ok) throw await parseError(res);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

// ---------------------------------------------------------------- streaming query (SSE over fetch)
export interface StreamHandlers {
  onMeta?: (meta: StreamMeta) => void;
  onToken?: (text: string) => void;
  onDone?: (msg: Message) => void;
  onError?: (detail: string) => void;
}

/**
 * POST /api/query/stream and parse Server-Sent Events from the response body.
 * Resolves once the stream ends. Throws `StreamUnavailableError` if the stream could not be
 * opened at all (caller may then fall back to POST /api/query).
 */
export class StreamUnavailableError extends Error {}

export async function streamQuery(req: QueryRequest, handlers: StreamHandlers, signal?: AbortSignal) {
  const headers = authHeaders({ "Content-Type": "application/json", Accept: "text/event-stream" });
  let res: Response;
  try {
    res = await fetch(`${BASE}/query/stream`, { method: "POST", headers, body: JSON.stringify(req), signal });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new StreamUnavailableError("network");
  }
  if (res.status === 401) {
    handleUnauthorized("/query/stream");
    throw await parseError(res);
  }
  if (!res.ok || !res.body) {
    if (res.status >= 400 && res.status < 500 && res.status !== 404 && res.status !== 405) throw await parseError(res);
    throw new StreamUnavailableError(`status ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let gotDone = false;

  const dispatch = (event: string, data: string) => {
    let payload: unknown;
    try {
      payload = JSON.parse(data);
    } catch {
      payload = data;
    }
    switch (event) {
      case "meta":
        handlers.onMeta?.(payload as StreamMeta);
        break;
      case "token": {
        const p = payload as { text?: string } | string;
        handlers.onToken?.(typeof p === "string" ? p : (p.text ?? ""));
        break;
      }
      case "done":
        gotDone = true;
        handlers.onDone?.((payload as { assistant_message: Message }).assistant_message);
        break;
      case "error": {
        const p = payload as { detail?: string } | string;
        handlers.onError?.(typeof p === "string" ? p : (p.detail ?? "Generation failed"));
        gotDone = true;
        break;
      }
    }
  };

  const processBlock = (block: string) => {
    let event = "message";
    const dataLines: string[] = [];
    for (const raw of block.split("\n")) {
      const line = raw.replace(/\r$/, "");
      if (!line || line.startsWith(":")) continue;
      const idx = line.indexOf(":");
      const field = idx === -1 ? line : line.slice(0, idx);
      let value = idx === -1 ? "" : line.slice(idx + 1);
      if (value.startsWith(" ")) value = value.slice(1);
      if (field === "event") event = value;
      else if (field === "data") dataLines.push(value);
    }
    if (dataLines.length) dispatch(event, dataLines.join("\n"));
  };

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      processBlock(buffer.slice(0, sep));
      buffer = buffer.slice(sep + 2);
    }
  }
  if (buffer.trim()) processBlock(buffer);
  if (!gotDone) handlers.onError?.("Stream ended unexpectedly");
}

// ---------------------------------------------------------------- endpoints
export const api = {
  // auth
  register: (b: { username: string; email: string; password: string }) =>
    request<AuthResponse>("/auth/register", { method: "POST", body: b }),
  login: (b: { username: string; password: string }) =>
    request<AuthResponse>("/auth/login", { method: "POST", body: b }),
  logout: () => request<{ ok: true }>("/auth/logout", { method: "POST" }),
  me: () => request<{ user: User }>("/auth/me"),

  // system
  health: () => request<Health>("/health"),
  systemStatus: () => request<SystemStatus>("/system/status"),
  statistics: () => request<Statistics>("/statistics"),
  analytics: () => request<Analytics>("/analytics"),
  adminOverview: () => request<AdminOverview>("/admin/overview"),
  adminCreateUser: (body: { username: string; email: string; password: string; role: "user" | "admin" }) =>
    request<User>("/admin/users", { method: "POST", body }),
  adminUpdateUser: (id: string, body: { role?: "user" | "admin"; disabled?: boolean; password?: string }) =>
    request<User>(`/admin/users/${encodeURIComponent(id)}`, { method: "PATCH", body }),
  adminLogoutUser: (id: string) =>
    request<{ ok: true; sessions_revoked: number }>(`/admin/users/${encodeURIComponent(id)}/logout`, { method: "POST" }),
  adminDeleteUser: (id: string) => request<{ ok: true }>(`/admin/users/${encodeURIComponent(id)}`, { method: "DELETE" }),
  adminDeleteDocument: (id: string) => request<{ ok: true }>(`/admin/documents/${encodeURIComponent(id)}`, { method: "DELETE" }),
  adminUserDetail: (id: string) => request<AdminUserDetail>(`/admin/users/${encodeURIComponent(id)}`),
  adminUserConversations: (id: string) =>
    request<{ conversations: Conversation[] }>(`/admin/users/${encodeURIComponent(id)}/conversations`),
  adminConversation: (cid: string) =>
    request<{ conversation: Conversation & { username: string }; messages: Message[] }>(
      `/admin/conversations/${encodeURIComponent(cid)}`,
    ),

  // documents
  documents: (p: { domain?: string; search?: string } = {}) =>
    request<DocumentList>(`/documents${qs({ domain: p.domain, search: p.search })}`),
  document: (id: string) => request<DocumentDetail>(`/documents/${encodeURIComponent(id)}`),
  versions: (id: string) => request<{ versions: Document[] }>(`/documents/${encodeURIComponent(id)}/versions`),
  deleteDocument: (id: string) => request<{ ok: true }>(`/documents/${encodeURIComponent(id)}`, { method: "DELETE" }),
  summarize: (id: string, summary_type: "short" | "detailed", refresh = false) =>
    request<SummaryResponse>(`/documents/${encodeURIComponent(id)}/summarize`, { method: "POST", body: { summary_type, refresh } }),
  entities: (id: string) => request<EntitiesResponse>(`/documents/${encodeURIComponent(id)}/entities`, { method: "POST" }),
  extract: (id: string, document_type: ExtractDocType) =>
    request<ExtractResponse>(`/documents/${encodeURIComponent(id)}/extract`, { method: "POST", body: { document_type } }),
  compare: (doc_id_a: string, doc_id_b: string) =>
    request<CompareResponse>("/documents/compare", { method: "POST", body: { doc_id_a, doc_id_b } }),
  sourceView: (docId: string, body: { chunk_id?: string; page_number?: number; focus?: string }) =>
    request<SourceView>(`/documents/${encodeURIComponent(docId)}/source-view`, { method: "POST", body }),

  // chat
  conversations: () => request<{ conversations: Conversation[] }>("/conversations"),
  createConversation: (b: { title?: string; domain?: string } = {}) =>
    request<Conversation>("/conversations", { method: "POST", body: b }),
  conversation: (id: string) =>
    request<{ conversation: Conversation; messages: Message[] }>(`/conversations/${encodeURIComponent(id)}`),
  renameConversation: (id: string, title: string) =>
    request<Conversation>(`/conversations/${encodeURIComponent(id)}`, { method: "PATCH", body: { title } }),
  deleteConversation: (id: string) =>
    request<{ ok: true }>(`/conversations/${encodeURIComponent(id)}`, { method: "DELETE" }),
  suggestions: (domain?: string) => request<{ questions: string[] }>(`/suggestions${qs({ domain })}`),
  query: (b: QueryRequest, signal?: AbortSignal) => request<QueryResponse>("/query", { method: "POST", body: b, signal }),
  feedback: (messageId: string, rating: 1 | -1 | 0) =>
    request<{ message: Message }>(`/messages/${encodeURIComponent(messageId)}/feedback`, { method: "POST", body: { rating } }),

  // evaluation
  evalDataset: () => request<unknown>("/evaluation/dataset"),
  evalRun: () => request<{ status: "running" }>("/evaluation/run", { method: "POST" }),
  evalStatus: () => request<EvalStatus>("/evaluation/status"),
  evalResults: () => request<{ latest: EvalReport | null }>("/evaluation/results"),
  evalAdvanced: () => request<{ report: unknown }>("/evaluation/advanced"),
};

export function errorMessage(e: unknown): string {
  if (e instanceof Error) return e.message;
  return String(e);
}
