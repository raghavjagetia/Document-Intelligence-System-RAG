import { useMemo, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { toast } from "sonner";
import { ArrowRight, AtSign, Eye, EyeOff, Layers, Lock, LogIn, Quote, ScanSearch, ShieldCheck, Sparkles, User, UserPlus } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { errorMessage } from "../lib/api";
import { cn } from "../lib/utils";
import { Logo } from "../components/Brand";
import { Button, Input, Label } from "../components/ui";

const FEATURES = [
  { icon: Layers, title: "Finds the right page", text: "Searches by meaning and by exact words, then double-checks the best matches." },
  { icon: Quote, title: "Answers you can verify", text: "Every claim links back to the exact page and section it came from." },
  { icon: ScanSearch, title: "Any document, any layout", text: "PDF, Office, HTML, spreadsheets and scanned images via OCR." },
];

function strength(pw: string): { score: number; label: string; color: string } {
  let s = 0;
  if (pw.length >= 8) s++;
  if (pw.length >= 10) s++;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) s++;
  if (/\d/.test(pw)) s++;
  if (/[^A-Za-z0-9]/.test(pw)) s++;
  const score = Math.min(4, s);
  const map = [
    { label: "Too weak", color: "bg-rose-500" },
    { label: "Weak", color: "bg-rose-500" },
    { label: "Fair", color: "bg-amber-500" },
    { label: "Good", color: "bg-emerald-500" },
    { label: "Strong", color: "bg-emerald-500" },
  ];
  return { score, ...map[score] };
}

export default function AuthPage({ mode }: { mode: "login" | "register" }) {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "/";

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [busy, setBusy] = useState<"form" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const pw = useMemo(() => strength(password), [password]);
  const isRegister = mode === "register";

  const validate = (): string | null => {
    if (!username.trim()) return isRegister ? "Choose a username" : "Enter your username or email";
    if (isRegister) {
      if (!/^\S+@\S+\.\S+$/.test(email)) return "Enter a valid email address";
      if (password.length < 8) return "Password must be at least 8 characters";
      if (password !== confirm) return "Passwords do not match";
    } else if (!password) return "Enter your password";
    return null;
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const v = validate();
    if (v) {
      setError(v);
      return;
    }
    setError(null);
    setBusy("form");
    try {
      const u = isRegister ? await register(username.trim(), email.trim(), password) : await login(username.trim(), password);
      toast.success(`Welcome${isRegister ? "" : " back"}, ${u.username}!`);
      navigate(from, { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="grid min-h-[100dvh] lg:grid-cols-[1.1fr_1fr]">
      {/* Hero */}
      <div className="relative hidden overflow-hidden bg-[#06060b] lg:flex lg:flex-col lg:justify-between lg:p-12">
        <div className="absolute inset-0">
          <div className="absolute -left-24 top-10 h-[28rem] w-[28rem] animate-float rounded-full bg-indigo-600/40 blur-[110px]" />
          <div className="absolute right-0 top-1/3 h-[24rem] w-[24rem] animate-float rounded-full bg-violet-600/35 blur-[110px] [animation-delay:-5s]" />
          <div className="absolute bottom-0 left-1/3 h-[22rem] w-[22rem] animate-float rounded-full bg-cyan-500/30 blur-[110px] [animation-delay:-9s]" />
          <div
            className="absolute inset-0 opacity-[0.15]"
            style={{
              backgroundImage:
                "linear-gradient(rgba(255,255,255,.08) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.08) 1px, transparent 1px)",
              backgroundSize: "44px 44px",
              maskImage: "radial-gradient(ellipse at center, black 30%, transparent 75%)",
            }}
          />
        </div>
        <div className="relative">
          <div className="[&_div]:!text-white">
            <Logo />
          </div>
        </div>
        <div className="relative max-w-xl">
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300 backdrop-blur">
              <Sparkles className="h-3.5 w-3.5 text-cyan-300" /> AI Document Intelligence
            </div>
            <h1 className="text-4xl font-semibold leading-[1.15] tracking-tight text-white xl:text-[2.75rem]">
              Ask your documents.
              <span className="mt-1 block whitespace-nowrap bg-gradient-to-r from-indigo-300 via-violet-300 to-cyan-300 bg-[length:200%_auto] bg-clip-text text-transparent animate-gradient-x">
                Get answers you can trust.
              </span>
            </h1>
            <p className="mt-5 max-w-lg text-base leading-relaxed text-slate-400">
              DocuMind turns contracts, policies, reports and scans into a searchable knowledge base with grounded,
              citation-backed answers.
            </p>
          </motion.div>
          <ul className="mt-10 space-y-5">
            {FEATURES.map((f, i) => (
              <motion.li
                key={f.title}
                className="flex gap-4"
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.25 + i * 0.12, duration: 0.5 }}
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-indigo-200 backdrop-blur">
                  <f.icon className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-sm font-semibold text-white">{f.title}</div>
                  <div className="text-sm text-slate-400">{f.text}</div>
                </div>
              </motion.li>
            ))}
          </ul>
        </div>
        <div className="relative flex items-center gap-2 text-xs text-slate-500">
          <ShieldCheck className="h-4 w-4" /> Your documents stay private to your account.
        </div>
      </div>

      {/* Form */}
      <div className="page-bg relative flex items-center justify-center px-4 py-10 sm:px-8 lg:px-12">
        <motion.div
          className="relative z-10 w-full max-w-[26rem]"
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45 }}
        >
          <div className="mb-8 flex justify-center lg:hidden">
            <Logo />
          </div>

          <div className="glass rounded-2xl p-6 shadow-xl shadow-indigo-500/5 sm:p-8">
            <div className="text-center">
              <div className="mx-auto mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500/20 to-cyan-500/20 text-indigo-500 ring-1 ring-indigo-500/20 dark:text-indigo-300">
                {isRegister ? <UserPlus className="h-5 w-5" /> : <LogIn className="h-5 w-5" />}
              </div>
              <h2 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-white">
                {isRegister ? "Create your account" : "Welcome back"}
              </h2>
              <p className="muted mt-1.5 text-sm">
                {isRegister ? "Start building your document knowledge base." : "Sign in to continue to DocuMind."}
              </p>
            </div>

            <form onSubmit={onSubmit} className="mt-7 space-y-5" noValidate>
              <div>
                <Label htmlFor="username">{isRegister ? "Username" : "Username or email"}</Label>
                <Input
                  id="username"
                  autoComplete="username"
                  autoCapitalize="none"
                  spellCheck={false}
                  autoFocus
                  icon={<User />}
                  className="h-11"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder={isRegister ? "jane" : "jane or jane@example.com"}
                />
              </div>
              {isRegister && (
                <div>
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    autoComplete="email"
                    icon={<AtSign />}
                    className="h-11"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="jane@example.com"
                  />
                </div>
              )}
              <div>
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type={showPw ? "text" : "password"}
                  autoComplete={isRegister ? "new-password" : "current-password"}
                  icon={<Lock />}
                  className="h-11"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  rightSlot={
                    <button
                      type="button"
                      onClick={() => setShowPw((s) => !s)}
                      className="rounded-md p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                      aria-label={showPw ? "Hide password" : "Show password"}
                    >
                      {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  }
                />
                {isRegister && password && (
                  <div className="mt-2" aria-live="polite">
                    <div className="flex gap-1">
                      {[0, 1, 2, 3].map((i) => (
                        <div key={i} className="h-1 flex-1 overflow-hidden rounded-full bg-slate-200 dark:bg-white/10">
                          <motion.div
                            className={cn("h-full", pw.color)}
                            initial={false}
                            animate={{ width: i < pw.score ? "100%" : "0%" }}
                            transition={{ duration: 0.25 }}
                          />
                        </div>
                      ))}
                    </div>
                    <div className="muted mt-1 text-[11px]">Strength: {pw.label}</div>
                  </div>
                )}
              </div>
              {isRegister && (
                <div>
                  <Label htmlFor="confirm">Confirm password</Label>
                  <Input
                    id="confirm"
                    type={showPw ? "text" : "password"}
                    autoComplete="new-password"
                    icon={<Lock />}
                    className="h-11"
                    value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
                    invalid={!!confirm && confirm !== password}
                    placeholder="Repeat your password"
                  />
                </div>
              )}

              <AnimatePresence>
                {error && (
                  <motion.div
                    role="alert"
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="rounded-xl border border-rose-500/25 bg-rose-500/10 px-3 py-2 text-sm text-rose-600 dark:text-rose-400">
                      {error}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              <Button
                type="submit"
                variant="gradient"
                size="lg"
                className="w-full"
                loading={busy === "form"}
                disabled={busy !== null}
                rightIcon={<ArrowRight className="h-4 w-4" />}
              >
                {isRegister ? "Create account" : "Sign in"}
              </Button>
            </form>

          </div>

          <p className="muted mt-6 text-center text-sm">
            {isRegister ? "Already have an account? " : "New to DocuMind? "}
            <Link
              to={isRegister ? "/login" : "/register"}
              state={location.state}
              className="font-medium text-indigo-600 hover:underline dark:text-indigo-400"
            >
              {isRegister ? "Sign in" : "Create an account"}
            </Link>
          </p>
        </motion.div>
      </div>
    </div>
  );
}
