/**
 * Parsers for the eRaktKosh `GETNEARBYSTOCKDETAILS` JSON payload.
 *
 * Payload shape (verified 2026-10-18):
 *
 *   { "data": [ [ "1",
 *                 "Name<br/>Address, , District, District, State<br/>Phone: ...,Fax: ..., Email: ...",
 *                 "Govt.",
 *                 "<p class='text-success'>Available, O+Ve:27, A+Ve:14</p>",
 *                 "2026-10-17 22:19:43",
 *                 "Blood Bank" ], ... ] }
 *
 * Every row has exactly 6 columns. Inactive/de-listed banks appear with an
 * all-dashes name block ("-<br/>-<br/>-") and are skipped.
 */

import { toBloodGroup } from './mapping.js';
import type { BankComponentStock, ComponentCell, ComponentType } from './types.js';

/** Availability cell classes the portal uses. */
const CELL_SUCCESS = 'text-success';
const CELL_DANGER = 'text-danger';

/** Matches `O+Ve:27`, `AB-Ve : 3`, etc. */
const GROUP_COUNT_RE = /([A-Za-z]{1,3}[+-]Ve)\s*:\s*(\d+)/g;

/**
 * Escape raw control characters that appear INSIDE JSON string literals.
 *
 * The portal intermittently emits unescaped newlines/tabs inside bank names and
 * addresses, which is invalid JSON: `JSON.parse` fails with "Bad control character
 * in string literal". Whitespace BETWEEN tokens is legal, so this walks the text
 * tracking string state rather than blanket-replacing control characters.
 */
export function escapeControlCharsInStrings(text: string): string {
  let out = '';
  let inString = false;
  let escaped = false;

  for (const char of text) {
    if (inString) {
      if (escaped) {
        out += char;
        escaped = false;
        continue;
      }
      if (char === '\\') {
        out += char;
        escaped = true;
        continue;
      }
      if (char === '"') {
        out += char;
        inString = false;
        continue;
      }
      const code = char.charCodeAt(0);
      if (code < 0x20) {
        out +=
          code === 0x0a
            ? '\\n'
            : code === 0x0d
              ? '\\r'
              : code === 0x09
                ? '\\t'
                : `\\u${code.toString(16).padStart(4, '0')}`;
        continue;
      }
      out += char;
      continue;
    }
    if (char === '"') inString = true;
    out += char;
  }

  return out;
}

/** Remove HTML tags and collapse whitespace/entities. */
export function stripTags(input: string): string {
  return input
    .replace(/<br\s*\/?>/gi, ' ')
    .replace(/<[^>]*>/g, '')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/\s+/g, ' ')
    .trim();
}

export interface ContactBlock {
  name: string;
  addressLine: string;
  city: string | null;
  district: string | null;
  state: string | null;
  phone: string | null;
  fax: string | null;
  email: string | null;
  /** True when the portal returned the all-dashes placeholder. */
  isPlaceholder: boolean;
}

const EMPTY = new Set(['', '-', 'N/A', 'NA', '--']);

function tidy(value: string | undefined): string | null {
  if (value === undefined) return null;
  const trimmed = value.replace(/\s+/g, ' ').trim();
  return EMPTY.has(trimmed) ? null : trimmed;
}

/**
 * Parse column 1 of a stock row.
 *
 * The address segment is comma-separated and ends `..., City, District, State`.
 * City is frequently blank, which shows up as a doubled comma.
 */
export function parseContactBlock(raw: string): ContactBlock {
  const segments = raw.split(/<br\s*\/?>/i).map((part) => stripTags(part));
  const name = segments[0] ?? '';
  const addressLine = segments[1] ?? '';
  const contact = segments.slice(2).join(' ');

  const parts = addressLine
    .split(',')
    .map((part) => part.trim())
    .filter((part, index, all) => part !== '' || index === all.length - 1);

  const state = parts.length >= 1 ? tidy(parts[parts.length - 1]) : null;
  const district = parts.length >= 2 ? tidy(parts[parts.length - 2]) : null;
  const city = parts.length >= 3 ? tidy(parts[parts.length - 3]) : null;

  return {
    name,
    addressLine,
    city,
    district,
    state,
    phone: tidy(/Phone\s*:\s*([^,]*)/i.exec(contact)?.[1]),
    fax: tidy(/Fax\s*:\s*([^,]*)/i.exec(contact)?.[1]),
    email: tidy(/Email\s*:\s*([^,]*)/i.exec(contact)?.[1]),
    isPlaceholder: EMPTY.has(name.trim()),
  };
}

export interface ParsedAvailability {
  available: boolean;
  cells: ComponentCell[];
  /** Group labels the portal emitted that we could not map. */
  unmappedGroups: string[];
  text: string;
}

/** Parse column 3 of a stock row. */
export function parseAvailabilityCell(raw: string): ParsedAvailability {
  const text = stripTags(raw);
  const isDanger = raw.includes(CELL_DANGER);

  if (isDanger || /not\s+available/i.test(text)) {
    return { available: false, cells: [], unmappedGroups: [], text };
  }

  const cells: ComponentCell[] = [];
  const unmappedGroups: string[] = [];

  for (const match of text.matchAll(GROUP_COUNT_RE)) {
    const label = match[1];
    const units = Number.parseInt(match[2] ?? '', 10);
    if (label === undefined || Number.isNaN(units)) continue;
    const group = toBloodGroup(label);
    if (group === null) {
      unmappedGroups.push(label);
      continue;
    }
    cells.push({ bloodGroup: group, units });
  }

  return { available: raw.includes(CELL_SUCCESS), cells, unmappedGroups, text };
}

export interface ParseStockRowContext {
  componentCode: number;
  component: ComponentType;
  stateCode: number;
  districtCode: number;
  sourceUrl: string;
  fetchedAt: string;
}

export interface ParseStockRowResult {
  record: BankComponentStock | null;
  /** Set when the row was deliberately skipped, for reporting. */
  skippedReason?: string;
  unmappedGroups: string[];
}

/** Parse a single 6-column `data` row into a bank record. */
export function parseStockRow(
  row: unknown[],
  rowIndex: number,
  ctx: ParseStockRowContext,
): ParseStockRowResult {
  const unmappedGroups: string[] = [];

  if (row.length < 6) {
    return { record: null, skippedReason: `expected 6 columns, got ${row.length}`, unmappedGroups };
  }

  const contactRaw = String(row[1] ?? '');
  const category = stripTags(String(row[2] ?? ''));
  const availabilityRaw = String(row[3] ?? '');
  const lastUpdatedRaw = stripTags(String(row[4] ?? ''));
  const entityType = stripTags(String(row[5] ?? ''));

  const contact = parseContactBlock(contactRaw);
  if (contact.isPlaceholder || contact.name === '') {
    return { record: null, skippedReason: 'placeholder/inactive bank row', unmappedGroups };
  }

  const availability = parseAvailabilityCell(availabilityRaw);
  unmappedGroups.push(...availability.unmappedGroups);

  const record: BankComponentStock = {
    sourceKey: `${ctx.componentCode}:${ctx.stateCode}:${ctx.districtCode}:${rowIndex}`,
    name: contact.name,
    category,
    entityType,
    addressLine: contact.addressLine,
    city: contact.city,
    district: contact.district,
    state: contact.state,
    phone: contact.phone,
    fax: contact.fax,
    email: contact.email,
    stateCode: ctx.stateCode,
    districtCode: ctx.districtCode,
    component: ctx.component,
    componentCode: ctx.componentCode,
    available: availability.available,
    availabilityText: availability.text,
    cells: availability.cells,
    lastUpdated: lastUpdatedRaw !== '' ? lastUpdatedRaw : null,
    sourceUrl: ctx.sourceUrl,
    fetchedAt: ctx.fetchedAt,
  };

  return { record, unmappedGroups };
}

/** Extract the `data` array from a stock payload, tolerating junk. */
export function extractDataRows(payload: unknown): unknown[][] {
  if (payload === null || typeof payload !== 'object') return [];
  const data = (payload as { data?: unknown }).data;
  if (!Array.isArray(data)) return [];
  return data.filter((row): row is unknown[] => Array.isArray(row));
}

export interface StateEntry {
  code: number;
  name: string;
}

/** Parse the GETSTATELIST payload, which is a bare array. */
export function parseStateList(payload: unknown): StateEntry[] {
  if (!Array.isArray(payload)) return [];
  const states: StateEntry[] = [];
  for (const entry of payload) {
    if (entry === null || typeof entry !== 'object') continue;
    const { value, label } = entry as { value?: unknown; label?: unknown };
    const code = Number.parseInt(String(value ?? ''), 10);
    if (Number.isNaN(code) || typeof label !== 'string') continue;
    states.push({ code, name: label });
  }
  return states;
}
