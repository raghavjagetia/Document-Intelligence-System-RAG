import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Binary,
  Combine,
  FileSearch,
  Layers,
  LogOut,
  Moon,
  Quote,
  ScanText,
  Settings as SettingsIcon,
  ShieldCheck,
  Sparkles,
  Sun,
  Upload,
  UserCircle2,
  Wand2,
} from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { useTheme } from "../hooks/useTheme";
import { api } from "../lib/api";
import { cn, formatDate, initials } from "../lib/utils";
import { Badge, Button, Card, CardBody, CardHeader, PageHeader, Segmented } from "../components/ui";
import { SystemStatusCard } from "../components/SystemStatusCard";

const PIPELINE = [
  { icon: Upload, title: "1. Upload", text: "Add PDFs, Office files, web pages, spreadsheets or images. Duplicates are spotted and new versions are tracked." },
  { icon: ScanText, title: "2. Read", text: "The text, tables and page numbers are read out of each file; scanned pages are read with text recognition (OCR)." },
  { icon: Layers, title: "3. Split into passages", text: "Each document is split at its headings, lists and table rows, so every passage knows its section and page (structure-aware chunking)." },
  { icon: Binary, title: "4. Index by meaning and words", text: "Passages are stored for meaning-based search (embeddings in FAISS) and for exact-word search (BM25)." },
  { icon: Combine, title: "5. Search both ways", text: "A question is searched by meaning and by exact words, and the two result lists are combined (hybrid search with RRF)." },
  { icon: FileSearch, title: "6. Double-check the best matches", text: "A second AI model re-reads the top passages and puts the most relevant first (cross-encoder re-ranking)." },
  { icon: Wand2, title: "7. Write the answer", text: "The answer is written only from those passages; if they do not contain it, DocuMind says so instead of guessing." },
  { icon: Quote, title: "8. Show the sources", text: "Every fact is cited [1], and each answer is checked against its sources and given a confidence score." },
];

function PipelineDiagram() {
  return (
    <ol className="relative grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {PIPELINE.map((s, i) => (
        <motion.li
          key={s.title}
          initial={{ opacity: 0, y: 14 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-40px" }}
          transition={{ delay: i * 0.08, duration: 0.45 }}
          className="group relative"
        >
          <div className="glass relative h-full overflow-hidden rounded-2xl p-4 transition-all group-hover:-translate-y-0.5 group-hover:border-indigo-500/30">
            <motion.div
              className="bg-brand-gradient absolute inset-x-0 top-0 h-0.5 origin-left"
              initial={{ scaleX: 0 }}
              whileInView={{ scaleX: 1 }}
              viewport={{ once: true }}
              transition={{ delay: 0.3 + i * 0.08, duration: 0.5 }}
            />
            <div className="flex items-center gap-3">
              <div className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500/15 via-violet-500/10 to-cyan-500/15 text-indigo-500 ring-1 ring-indigo-500/20 dark:text-indigo-300">
                <s.icon className="h-4 w-4" />
              </div>
              <div>
                <div className="font-mono text-[10px] text-slate-400">STEP {String(i + 1).padStart(2, "0")}</div>
                <div className="text-sm font-semibold text-slate-900 dark:text-white">{s.title}</div>
              </div>
            </div>
            <p className="muted mt-2.5 text-xs leading-relaxed">{s.text}</p>
          </div>
          {i < PIPELINE.length - 1 && (
            <motion.span
              aria-hidden
              className="absolute -bottom-3 left-1/2 z-10 h-3 w-px bg-gradient-to-b from-indigo-500 to-cyan-500 sm:hidden"
              initial={{ scaleY: 0 }}
              whileInView={{ scaleY: 1 }}
              viewport={{ once: true }}
            />
          )}
        </motion.li>
      ))}
    </ol>
  );
}

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const { theme, setTheme } = useTheme();
  const navigate = useNavigate();
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, staleTime: 60_000 });

  return (
    <div className="space-y-6">
      <PageHeader icon={<SettingsIcon />} title="Settings" description="Your account, appearance and system information." />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader icon={<UserCircle2 className="h-4 w-4" />} title="Account" />
          <CardBody>
            {user && (
              <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
                <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 via-violet-500 to-cyan-500 text-xl font-semibold text-white shadow-lg shadow-indigo-500/30">
                  {initials(user.username)}
                </div>
                <dl className="grid flex-1 grid-cols-1 gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
                  {[
                    ["Username", user.username],
                    ["Email", user.email],
                    ["Role", <Badge key="r" tone={user.role === "admin" ? "violet" : "indigo"}>{user.role}</Badge>],
                    ["Member since", formatDate(user.created_at)],
                  ].map(([k, v]) => (
                    <div key={String(k)}>
                      <dt className="text-xs text-slate-500 dark:text-slate-400">{k}</dt>
                      <dd className="mt-0.5 truncate font-medium text-slate-900 dark:text-white">{v}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            )}
            <div className="mt-6 flex flex-wrap gap-2 border-t border-slate-200 pt-5 dark:border-white/10">
              <Button
                variant="outline"
                leftIcon={<LogOut className="h-4 w-4" />}
                onClick={async () => {
                  await logout();
                  navigate("/login");
                }}
              >
                Log out
              </Button>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader icon={theme === "dark" ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />} title="Appearance" description="Saved on this device" />
          <CardBody className="space-y-4">
            <Segmented
              ariaLabel="Theme"
              value={theme}
              onChange={setTheme}
              items={[
                { value: "dark", label: "Dark", icon: <Moon /> },
                { value: "light", label: "Light", icon: <Sun /> },
              ]}
            />
            <div className="grid grid-cols-2 gap-2">
              {(["dark", "light"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setTheme(t)}
                  aria-label={`Use ${t} theme`}
                  className={cn(
                    "overflow-hidden rounded-xl border-2 transition",
                    theme === t ? "border-indigo-500" : "border-transparent hover:border-slate-300 dark:hover:border-white/20",
                  )}
                >
                  <div className={cn("space-y-1.5 p-2.5", t === "dark" ? "bg-[#0b0b12]" : "bg-slate-100")}>
                    <div className={cn("h-2 w-2/3 rounded", t === "dark" ? "bg-white/20" : "bg-slate-300")} />
                    <div className="bg-brand-gradient h-2 w-1/2 rounded" />
                    <div className={cn("h-6 rounded", t === "dark" ? "bg-white/[0.06]" : "bg-white")} />
                  </div>
                </button>
              ))}
            </div>
            <div className="flex items-center justify-between rounded-xl bg-slate-100 px-3 py-2 text-xs dark:bg-white/[0.04]">
              <span className="text-slate-500">API server</span>
              {health.data ? (
                <Badge tone="green">
                  <ShieldCheck className="h-3 w-3" /> {health.data.status} · v{health.data.version}
                </Badge>
              ) : health.isError ? (
                <Badge tone="red">unreachable</Badge>
              ) : (
                <Badge>checking…</Badge>
              )}
            </div>
          </CardBody>
        </Card>
      </div>

      <SystemStatusCard showFormats />

      <Card>
        <CardHeader icon={<Sparkles className="h-4 w-4" />} title="About DocuMind" description="Ask questions about your documents and get answers you can verify" />
        <CardBody>
          <p className="mb-5 max-w-3xl text-sm leading-relaxed text-slate-600 dark:text-slate-300">
            DocuMind combines dense semantic search with sparse keyword retrieval, fuses them with Reciprocal Rank Fusion, reranks
            with a cross-encoder and generates answers that are strictly grounded in your documents — with inline citations, a
            grounding check and calibrated confidence. Here is the end-to-end pipeline:
          </p>
          <PipelineDiagram />
        </CardBody>
      </Card>
    </div>
  );
}
