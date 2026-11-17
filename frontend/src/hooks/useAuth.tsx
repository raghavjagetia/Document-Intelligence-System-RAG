import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, ApiError, clearToken, getToken, setToken, UNAUTHORIZED_EVENT } from "../lib/api";
import type { AuthResponse, User } from "../types";

interface AuthCtx {
  user: User | null;
  /** true while validating an existing token on boot */
  loading: boolean;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<User>;
  register: (username: string, email: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(() => !!getToken());

  // Validate stored token on boot. Only a 401 from the server means the session is gone (the API client
  // clears the token then); a cancelled request (e.g. the page being refreshed) or a server that is briefly
  // unreachable must not log the user out, so those are retried and the token is kept.
  useEffect(() => {
    if (!getToken()) return;
    let cancelled = false;
    const check = (attempt: number) => {
      api
        .me()
        .then((r) => {
          if (!cancelled) {
            setUser(r.user);
            setLoading(false);
          }
        })
        .catch((e) => {
          if (cancelled) return;
          if (e instanceof ApiError && e.status === 401) {
            setUser(null);
            setLoading(false);
          } else if (attempt < 4) {
            setTimeout(() => !cancelled && check(attempt + 1), 1000 * (attempt + 1));
          } else {
            setLoading(false);
          }
        });
    };
    check(0);
    return () => {
      cancelled = true;
    };
  }, []);

  // Global 401 handler (fired by the API client).
  useEffect(() => {
    const onUnauthorized = () => {
      setUser(null);
      qc.clear();
    };
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, [qc]);

  const accept = useCallback(
    (r: AuthResponse) => {
      setToken(r.token);
      qc.clear();
      setUser(r.user);
      return r.user;
    },
    [qc],
  );

  const login = useCallback((u: string, p: string) => api.login({ username: u, password: p }).then(accept), [accept]);
  const register = useCallback(
    (u: string, e: string, p: string) => api.register({ username: u, email: e, password: p }).then(accept),
    [accept],
  );
  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      /* ignore */
    }
    clearToken();
    setUser(null);
    qc.clear();
  }, [qc]);

  return (
    <Ctx.Provider value={{ user, loading, isAuthenticated: !!user, login, register, logout }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAuth() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth must be used within AuthProvider");
  return c;
}
