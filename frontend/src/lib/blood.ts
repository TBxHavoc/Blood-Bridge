/** Business/derivation logic — ported from design.md §6.2 so the box gauge,
 *  the table chips and the alerts always agree (single-sourced). */

import type { BloodGroup, ComponentType, RequestStatus, StockoutRisk } from "./types";

export const BLOOD_GROUPS: BloodGroup[] = [
  "A+",
  "A-",
  "B+",
  "B-",
  "O+",
  "O-",
  "AB+",
  "AB-",
];

export const COMPONENT_TYPES: ComponentType[] = ["RBC", "WHOLE_BLOOD"];

export const COMPONENT_LABELS: Record<ComponentType, string> = {
  RBC: "Red blood cells",
  WHOLE_BLOOD: "Whole blood",
};

export const URGENCY_LABELS: Record<number, string> = {
  1: "Routine",
  2: "Moderately urgent",
  3: "Urgent",
  4: "Critical",
  5: "Life-threatening",
};

export type StatusClass = "crit" | "low" | "warn" | "good";

export function hoursToRunOut(units: number, perDay: number): number {
  if (perDay <= 0) return units > 0 ? Infinity : 0;
  return (units / perDay) * 24;
}

export function status(hours: number): [StatusClass, string] {
  if (hours < 24) return ["crit", "Critical"];
  if (hours < 72) return ["low", "Low"];
  if (hours < 168) return ["warn", "Watch"];
  return ["good", "Good"];
}

export function duration(hours: number): string {
  if (!Number.isFinite(hours)) return "—";
  const total = Math.round(hours);
  if (total < 24) return `${total} hrs`;
  return `${Math.floor(total / 24)}d ${total % 24}h`;
}

export function levelPct(hours: number): number {
  if (!Number.isFinite(hours)) return 100;
  return Math.min(hours / 240, 1) * 100;
}

/** Availability of a stock count. `specific` = a specific blood type was asked for. */
export function availabilityOf(units: number, specific: boolean): [StatusClass, string] {
  const [high, mid] = specific ? [40, 15] : [250, 100];
  if (units >= high) return ["good", "High"];
  if (units >= mid) return ["warn", "Medium"];
  return ["low", "Limited"];
}

const RISK_CLASS: Record<StockoutRisk, StatusClass> = {
  IMMEDIATE_EMPTY: "crit",
  CRITICAL: "crit",
  HIGH: "low",
  MODERATE: "warn",
  EXPIRES_BEFORE_USE: "warn",
  STABLE: "good",
};

const RISK_LABEL: Record<StockoutRisk, string> = {
  IMMEDIATE_EMPTY: "Empty",
  CRITICAL: "Critical",
  HIGH: "High risk",
  MODERATE: "Watch",
  EXPIRES_BEFORE_USE: "Expiring",
  STABLE: "Good",
};

export function riskClass(risk: StockoutRisk): StatusClass {
  return RISK_CLASS[risk] ?? "good";
}

export function riskLabel(risk: StockoutRisk): string {
  return RISK_LABEL[risk] ?? "Good";
}

export function componentLabel(component: ComponentType): string {
  return COMPONENT_LABELS[component] ?? component;
}

export function urgencyLabel(urgency: number): string {
  return URGENCY_LABELS[urgency] ?? `Level ${urgency}`;
}

export function requestStatusClass(statusValue: RequestStatus): StatusClass {
  switch (statusValue) {
    case "FULFILLED":
      return "good";
    case "CONFIRMED":
      return "good";
    case "OPEN":
      return "warn";
    case "HELD":
      return "low";
    case "EXPIRED":
      return "crit";
    case "CANCELLED":
      return "crit";
    default:
      return "warn";
  }
}

/** "o-", "O negative", "ab pos" … become a blood type filter; anything else
 *  searches bank names. Ported from the prototype's parseQuery(). */
export function parseQuery(text: string): { type: BloodGroup | ""; q: string } {
  const t = text.trim().replace(/[\u2212\u2013]/g, "-").toLowerCase();
  const m = t.match(/^(ab|a|b|o)\s*(\+|-|pos(?:itive)?|neg(?:ative)?)$/);
  if (m) {
    const sign = m[2] === "+" || m[2][0] === "p" ? "+" : "-";
    const type = `${m[1].toUpperCase()}${sign}` as BloodGroup;
    return { type, q: "" };
  }
  return { type: "", q: t };
}

/** Typo-tolerant match of a free-text query against a bank name. */
export function editDistance(a: string, b: string): number {
  const m = a.length;
  const n = b.length;
  if (!m) return n;
  if (!n) return m;
  let prev = Array.from({ length: n + 1 }, (_, i) => i);
  for (let i = 1; i <= m; i++) {
    const cur = [i];
    for (let j = 1; j <= n; j++) {
      cur[j] = Math.min(
        prev[j] + 1,
        cur[j - 1] + 1,
        prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1),
      );
    }
    prev = cur;
  }
  return prev[n];
}

export function nameScore(name: string, query: string): number {
  const n = name.toLowerCase();
  const q = query.toLowerCase().trim();
  if (!q) return 0;
  if (n.includes(q)) return 100;
  const nTokens = n.match(/[a-z]+/g) || [];
  const qTokens = q.match(/[a-z]+/g) || [];
  if (!qTokens.length) return 0;
  const matched = qTokens.filter((qt) =>
    nTokens.some(
      (nt) =>
        nt === qt ||
        (qt.length >= 3 && nt.includes(qt)) ||
        (nt.length >= 3 && qt.includes(nt)) ||
        (qt.length >= 4 && editDistance(nt, qt) <= 1),
    ),
  ).length;
  return matched ? Math.round((matched / qTokens.length) * 60) : 0;
}

/** Human-friendly relative time for feeds (created_at / request_timestamp). */
/** The API stores and returns naive UTC (no offset, e.g. `2026-10-17T20:04:44.020416`).
 *  `new Date()` would read that as *local* time, so pin it to UTC; date-only
 *  strings (`2026-10-19`) are already UTC per spec and are left alone. */
function parseApiDate(iso: string): Date {
  const cleaned = iso.trim();
  if (!cleaned) return new Date(NaN);
  if (/^\d{4}-\d{2}-\d{2}$/.test(cleaned)) return new Date(cleaned);
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(cleaned);
  const trimmed = cleaned.replace(/(\.\d{3})\d+/, "$1");
  return new Date(hasZone ? trimmed : `${trimmed}Z`);
}

export function relativeTime(iso: string): string {
  const then = parseApiDate(iso).getTime();
  if (Number.isNaN(then)) return "";
  const mins = Math.max(0, Math.round((Date.now() - then) / 60000));
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days}d ago`;
  return parseApiDate(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/** Whole days from today until an ISO date (negative if already past). */
export function daysUntil(iso: string): number {
  const target = new Date(iso);
  if (Number.isNaN(target.getTime())) return Infinity;
  const today = new Date();
  const a = Date.UTC(target.getFullYear(), target.getMonth(), target.getDate());
  const b = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.round((a - b) / 86400000);
}
