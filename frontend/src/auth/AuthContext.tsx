import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api } from "../lib/api";
import type { User } from "../lib/types";

const STORAGE_KEY = "bb.session";

interface Stored {
  token: string;
  user: User;
}

interface AuthValue {
  token: string | null;
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthValue | null>(null);

function readStored(): Stored | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<Stored>;
    if (parsed && typeof parsed.token === "string" && parsed.user) {
      return { token: parsed.token, user: parsed.user as User };
    }
  } catch {
    /* ignore malformed storage */
  }
  return null;
}

function writeStored(value: Stored | null): void {
  if (value) localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
  else localStorage.removeItem(STORAGE_KEY);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Stored | null>(() => readStored());
  const [loading, setLoading] = useState<boolean>(() => readStored() !== null);

  // Validate a restored token once on boot; drop it if the backend rejects it.
  useEffect(() => {
    const current = readStored();
    if (!current) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    api
      .me(current.token)
      .then((user) => {
        if (cancelled) return;
        const next = { token: current.token, user };
        writeStored(next);
        setSession(next);
      })
      .catch(() => {
        if (cancelled) return;
        writeStored(null);
        setSession(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await api.login(username, password);
    const next = { token: res.access_token, user: res.user };
    writeStored(next);
    setSession(next);
  }, []);

  const logout = useCallback(async () => {
    const current = readStored();
    if (current) {
      try {
        await api.logout(current.token);
      } catch {
        /* best effort — the token is revoked where possible, then discarded */
      }
    }
    writeStored(null);
    setSession(null);
  }, []);

  const value = useMemo<AuthValue>(
    () => ({
      token: session?.token ?? null,
      user: session?.user ?? null,
      loading,
      login,
      logout,
    }),
    [session, loading, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
