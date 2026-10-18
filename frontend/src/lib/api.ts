/** Thin fetch client for the Blood Bridge API.
 *
 *  Every backend response is wrapped in the shared envelope
 *  `{ success, data, meta }` / `{ success:false, error:{code,message,details} }`
 *  (backend/app/core/envelope.py). This client unwraps `data` and turns any
 *  failure into an `ApiError` so callers only deal with domain types.
 *
 *  Requests go to a same-origin `/api/v1` prefix; in dev Vite proxies `/api`
 *  to the FastAPI backend (see vite.config.ts), so there is no CORS hop.
 */

import type {
  Alert,
  BloodRequest,
  Depletion,
  EraktkoshSummary,
  EraktkoshSupply,
  ForecastSummary,
  InventoryCreate,
  InventoryItem,
  Reservation,
  TokenResponse,
  UsageStat,
  User,
} from "./types";

const BASE =
  (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "") ||
  "/api/v1";

export class ApiError extends Error {
  code: string;
  status: number;
  details?: unknown;

  constructor(message: string, code: string, status: number, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

interface Envelope<T> {
  success?: boolean;
  data?: T;
  error?: { code?: string; message?: string; details?: unknown };
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  token?: string | null;
  signal?: AbortSignal;
}

export async function apiFetch<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  if (opts.token) headers.Authorization = `Bearer ${opts.token}`;

  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      method: opts.method ?? "GET",
      headers,
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
      signal: opts.signal,
    });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError(
      "Cannot reach the Blood Bridge API. Is the backend running?",
      "NETWORK_ERROR",
      0,
    );
  }

  const text = await res.text();
  let payload: Envelope<T> | null = null;
  if (text) {
    try {
      payload = JSON.parse(text) as Envelope<T>;
    } catch {
      payload = null;
    }
  }

  if (!res.ok || (payload && payload.success === false)) {
    const error = payload?.error;
    throw new ApiError(
      error?.message || `Request failed (HTTP ${res.status}).`,
      error?.code || "HTTP_ERROR",
      res.status,
      error?.details,
    );
  }

  if (payload && typeof payload === "object" && "data" in payload) {
    return payload.data as T;
  }
  return payload as unknown as T;
}

function qs(params?: Record<string, string | number | boolean | undefined>): string {
  if (!params) return "";
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const s = search.toString();
  return s ? `?${s}` : "";
}

export const api = {
  /* ---- auth ---- */
  login: (username: string, password: string) =>
    apiFetch<TokenResponse>("/auth/login", {
      method: "POST",
      body: { username, password },
    }),
  me: (token: string) => apiFetch<User>("/auth/me", { token }),
  logout: (token: string) =>
    apiFetch<{ status: string }>("/auth/logout", { method: "POST", token }),

  /* ---- system ---- */
  health: () => apiFetch<{ status: string; version: string; time: string }>("/health"),

  /* ---- forecasting ---- */
  summary: (token: string) =>
    apiFetch<ForecastSummary>("/forecasting/summary", { token }),
  usage: (token: string) => apiFetch<UsageStat[]>("/forecasting/usage", { token }),
  depletion: (
    token: string,
    params?: { blood_group?: string; component_type?: string; blood_bank_id?: string; risk_tier?: string },
  ) => apiFetch<Depletion[]>(`/forecasting/depletion${qs(params)}`, { token }),

  /* ---- inventory (bloodbank_user / admin) ---- */
  inventory: (
    token: string,
    params?: { blood_group?: string; component_type?: string; only_available?: boolean },
  ) => apiFetch<InventoryItem[]>(`/inventory${qs(params)}`, { token }),
  createInventory: (token: string, body: InventoryCreate) =>
    apiFetch<InventoryItem>("/inventory", { method: "POST", token, body }),

  /* ---- requests (hospital_user / admin) ---- */
  requests: (token: string, params?: { status?: string }) =>
    apiFetch<BloodRequest[]>(`/requests${qs(params)}`, { token }),
  createRequest: (
    token: string,
    body: {
      blood_group: string;
      component_type: string;
      quantity_units: number;
      urgency: number;
      required_by_timestamp?: string | null;
    },
  ) => apiFetch<BloodRequest>("/requests", { method: "POST", token, body }),
  cancelRequest: (token: string, id: string) =>
    apiFetch<BloodRequest>(`/requests/${id}/cancel`, { method: "POST", token }),
  matchQueue: (token: string, limit = 50) =>
    apiFetch<BloodRequest[]>(`/match/queue${qs({ limit })}`, { token }),

  /* ---- alerts ---- */
  alerts: (token: string, params?: { is_read?: boolean; limit?: number }) =>
    apiFetch<Alert[]>(`/alerts${qs(params)}`, { token }),
  readAlert: (token: string, id: string) =>
    apiFetch<Alert>(`/alerts/${id}`, { method: "PATCH", token, body: { is_read: true } }),

  /* ---- reservations ---- */
  reservations: (token: string) =>
    apiFetch<Reservation[]>("/reservations", { token }),

  /* ---- eRaktKosh live stock (public, no token required) ---- */
  eraktkoshSummary: () =>
    apiFetch<EraktkoshSummary>("/eraktkosh/summary"),
  eraktkoshSupply: () =>
    apiFetch<EraktkoshSupply[]>("/eraktkosh/supply"),
};
