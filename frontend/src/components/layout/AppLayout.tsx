import { useCallback, useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronsLeft, ChevronsRight, LogOut, Menu, Moon, Search, Sun, User as UserIcon, X } from "lucide-react";
import { useAuth } from "../../hooks/useAuth";
import { useTheme } from "../../hooks/useTheme";
import { useDismiss, useMediaQuery } from "../../hooks/misc";
import { cn, initials } from "../../lib/utils";
import { Logo } from "../Brand";
import { Button, Kbd, Tooltip } from "../ui";
import { navFor } from "./nav";
import { CommandPalette } from "./CommandPalette";

const COLLAPSE_KEY = "documind-sidebar-collapsed";

function SidebarNav({ collapsed, onNavigate }: { collapsed: boolean; onNavigate?: () => void }) {
  const { user } = useAuth();
  return (
    <nav aria-label="Main" className="flex flex-col gap-1">
      {navFor(user?.role).map((item) => {
        const link = (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                collapsed && "justify-center px-0",
                isActive
                  ? "text-slate-900 dark:text-white"
                  : "text-slate-500 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-white/[0.04] dark:hover:text-white",
              )
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <motion.span
                    layoutId={onNavigate ? "nav-active-mobile" : "nav-active"}
                    className="absolute inset-0 rounded-xl bg-gradient-to-r from-indigo-500/15 via-violet-500/10 to-transparent ring-1 ring-inset ring-indigo-500/20"
                    transition={{ type: "spring", stiffness: 450, damping: 38 }}
                  />
                )}
                <item.icon
                  className={cn("relative h-[18px] w-[18px] shrink-0 transition-transform group-hover:scale-110", isActive && "text-indigo-500 dark:text-indigo-400")}
                  aria-hidden
                />
                {!collapsed && <span className="relative">{item.label}</span>}
                {collapsed && <span className="sr-only">{item.label}</span>}
              </>
            )}
          </NavLink>
        );
        return collapsed ? (
          <Tooltip key={item.to} label={item.label} width={120}>
            <div className="w-full">{link}</div>
          </Tooltip>
        ) : (
          link
        );
      })}
    </nav>
  );
}

function UserMenu() {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const btn = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useDismiss(open, close, [btn, menu]);
  if (!user) return null;
  return (
    <div className="relative">
      <button
        ref={btn}
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Account menu"
        className="flex items-center gap-2 rounded-full p-0.5 pr-0.5 transition hover:ring-4 hover:ring-indigo-500/10 sm:pr-3"
      >
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 via-violet-500 to-cyan-500 text-xs font-semibold text-white">
          {initials(user.username)}
        </span>
        <span className="hidden max-w-[120px] truncate text-sm font-medium text-slate-700 dark:text-slate-200 sm:block">{user.username}</span>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            ref={menu}
            role="menu"
            initial={{ opacity: 0, y: -6, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.97 }}
            transition={{ duration: 0.14 }}
            className="glass-strong absolute right-0 top-12 z-50 w-60 origin-top-right rounded-2xl p-1.5"
          >
            <div className="px-3 py-2.5">
              <div className="truncate text-sm font-semibold text-slate-900 dark:text-white">{user.username}</div>
              <div className="muted truncate text-xs">{user.email}</div>
            </div>
            <div className="my-1 h-px bg-slate-200 dark:bg-white/10" />
            {[
              {
                label: "Profile & settings",
                icon: <UserIcon className="h-4 w-4" />,
                onClick: () => {
                  navigate("/settings");
                  close();
                },
              },
              {
                label: theme === "dark" ? "Light mode" : "Dark mode",
                icon: theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />,
                onClick: toggle,
              },
              {
                label: "Log out",
                icon: <LogOut className="h-4 w-4" />,
                onClick: async () => {
                  close();
                  await logout();
                  navigate("/login");
                },
                danger: true,
              },
            ].map((it) => (
              <button
                key={it.label}
                role="menuitem"
                onClick={it.onClick}
                className={cn(
                  "flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left text-sm transition-colors",
                  it.danger
                    ? "text-rose-600 hover:bg-rose-500/10 dark:text-rose-400"
                    : "text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-white/[0.06]",
                )}
              >
                {it.icon}
                {it.label}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function AppLayout() {
  const location = useLocation();
  const { theme, toggle } = useTheme();
  const isDesktop = useMediaQuery("(min-width: 1024px)");
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem(COLLAPSE_KEY) === "1";
    } catch {
      return false;
    }
  });
  const [mobileOpen, setMobileOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    try {
      localStorage.setItem(COLLAPSE_KEY, collapsed ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [collapsed]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => setMobileOpen(false), [location.pathname]);
  useEffect(() => {
    if (isDesktop) setMobileOpen(false);
  }, [isDesktop]);

  const section = "/" + (location.pathname.split("/")[1] ?? "");
  const current = navFor("admin").find((n) => (n.to === "/" ? section === "/" : section === n.to));
  const isChat = section === "/chat";

  return (
    <div className="page-bg relative flex h-[100dvh] overflow-hidden">
      <a
        href="#main"
        className="sr-only z-[100] rounded-lg bg-indigo-600 px-3 py-2 text-white focus:not-sr-only focus:absolute focus:left-3 focus:top-3"
      >
        Skip to content
      </a>

      {/* Desktop sidebar */}
      <aside
        className={cn(
          "relative z-20 hidden shrink-0 flex-col border-r border-slate-200/80 bg-white/60 backdrop-blur-xl transition-[width] duration-300 dark:border-white/[0.06] dark:bg-white/[0.015] lg:flex",
          collapsed ? "w-[72px]" : "w-64",
        )}
      >
        <div className={cn("flex h-16 items-center", collapsed ? "justify-center" : "px-5")}>
          <NavLink to="/" aria-label="DocuMind home">
            <Logo collapsed={collapsed} />
          </NavLink>
        </div>
        <div className={cn("flex-1 overflow-y-auto py-2", collapsed ? "px-3" : "px-3")}>
          <SidebarNav collapsed={collapsed} />
        </div>
        <div className="p-3">
          {!collapsed && (
            <div className="mb-3 rounded-2xl border border-indigo-500/20 bg-gradient-to-br from-indigo-500/10 via-violet-500/5 to-cyan-500/10 p-3.5">
              <div className="text-xs font-semibold text-slate-800 dark:text-slate-100">Answers you can check</div>
              <p className="muted mt-1 text-[11px] leading-relaxed">
                Every answer comes from your documents and shows exactly where it was found.
              </p>
            </div>
          )}
          <Button
            variant="ghost"
            size="sm"
            className={cn("w-full", collapsed ? "justify-center px-0" : "justify-start")}
            onClick={() => setCollapsed((c) => !c)}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            leftIcon={collapsed ? <ChevronsRight className="h-4 w-4" /> : <ChevronsLeft className="h-4 w-4" />}
          >
            {!collapsed && "Collapse"}
          </Button>
        </div>
      </aside>

      {/* Mobile drawer */}
      <AnimatePresence>
        {mobileOpen && (
          <div className="fixed inset-0 z-[60] lg:hidden">
            <motion.div
              className="absolute inset-0 bg-slate-950/50 backdrop-blur-sm"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setMobileOpen(false)}
            />
            <motion.aside
              className="glass-strong absolute inset-y-0 left-0 flex w-72 flex-col rounded-none border-y-0 border-l-0"
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "spring", stiffness: 340, damping: 34 }}
              aria-label="Navigation"
            >
              <div className="flex h-16 items-center justify-between px-5">
                <Logo />
                <Button variant="ghost" size="icon-sm" onClick={() => setMobileOpen(false)} aria-label="Close navigation">
                  <X className="h-4 w-4" />
                </Button>
              </div>
              <div className="px-3 py-2">
                <SidebarNav collapsed={false} onNavigate={() => setMobileOpen(false)} />
              </div>
            </motion.aside>
          </div>
        )}
      </AnimatePresence>

      <div className="relative z-10 flex min-w-0 flex-1 flex-col">
        {/* Top bar */}
        <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center gap-3 border-b border-slate-200/80 bg-white/60 px-4 backdrop-blur-xl dark:border-white/[0.06] dark:bg-[#07070c]/60 sm:px-6">
          <Button variant="ghost" size="icon-sm" className="lg:hidden" onClick={() => setMobileOpen(true)} aria-label="Open navigation">
            <Menu className="h-5 w-5" />
          </Button>
          <div className="hidden min-w-0 items-center gap-2 text-sm md:flex">
            <span className="muted">DocuMind</span>
            <span className="text-slate-300 dark:text-slate-600">/</span>
            <span className="truncate font-medium text-slate-900 dark:text-white">{current?.label ?? "Not found"}</span>
          </div>
          <button
            onClick={() => setPaletteOpen(true)}
            className="group mx-auto flex h-9 w-full max-w-md items-center gap-2 rounded-xl border border-slate-200 bg-white/70 px-3 text-sm text-slate-400 transition hover:border-indigo-500/40 hover:shadow-md hover:shadow-indigo-500/5 dark:border-white/10 dark:bg-white/[0.03] md:mx-0 md:ml-auto"
            aria-label="Open command palette (Ctrl+K)"
          >
            <Search className="h-4 w-4" />
            <span className="flex-1 truncate text-left">Search or jump to…</span>
            <span className="hidden items-center gap-1 sm:flex">
              <Kbd>Ctrl</Kbd>
              <Kbd>K</Kbd>
            </span>
          </button>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={toggle}
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            className="hidden sm:inline-flex"
          >
            <AnimatePresence mode="wait" initial={false}>
              <motion.span
                key={theme}
                initial={{ rotate: -90, opacity: 0 }}
                animate={{ rotate: 0, opacity: 1 }}
                exit={{ rotate: 90, opacity: 0 }}
                transition={{ duration: 0.18 }}
              >
                {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              </motion.span>
            </AnimatePresence>
          </Button>
          <UserMenu />
        </header>

        <main id="main" className={cn("relative min-h-0 flex-1", isChat ? "overflow-hidden" : "overflow-y-auto")}>
          <motion.div
            key={section}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
            className={cn(isChat ? "h-full" : "mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8")}
          >
            <Outlet />
          </motion.div>
        </main>
      </div>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  );
}
