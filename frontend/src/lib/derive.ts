/** Adapters that turn backend forecasting/inventory payloads into the shapes
 *  the UI components expect (the design's `STOCK` / `BANKS` sample structures). */

import { BLOOD_GROUPS, daysUntil, hoursToRunOut } from "./blood";
import type {
  BloodGroup,
  Depletion,
  EraktkoshSummary,
  EraktkoshSupply,
  InventoryItem,
  UsageStat,
} from "./types";

export interface StockItem {
  type: BloodGroup;
  units: number;
  perDay: number;
  hours: number | null;
  reserved: number;
  expiring: { units: number; days: number } | null;
}

export type PerDayByGroup = Partial<Record<BloodGroup, number>>;

/** Network consumption rate per blood group (summed over components). */
export function usagePerDayByGroup(usage: UsageStat[]): PerDayByGroup {
  const out: PerDayByGroup = {};
  for (const row of usage) {
    out[row.blood_group] = (out[row.blood_group] ?? 0) + row.avg_usage_per_day;
  }
  return out;
}

const EXPIRY_WINDOW_DAYS = 7;

/** Build one stock item per blood group for the gauge / inventory table.
 *
 *  `units` come from the depletion rows (unreserved = allocatable), scoped to a
 *  single bank for `bloodbank_user`s; the burn rate is the network consumption
 *  rate from `forecasting/usage` (the only consumption data the API exposes).
 */
export function buildStock(
  depletion: Depletion[],
  usage: UsageStat[],
  opts: { bankId?: string } = {},
): StockItem[] {
  const scope = opts.bankId
    ? depletion.filter((row) => row.blood_bank_id === opts.bankId)
    : depletion;
  const perDayByGroup = usagePerDayByGroup(usage);

  return BLOOD_GROUPS.map((group) => {
    const rows = scope.filter((row) => row.blood_group === group);
    const units = rows.reduce((sum, row) => sum + row.units_unreserved, 0);
    const reserved = rows.reduce((sum, row) => sum + row.units_reserved, 0);
    const perDay =
      perDayByGroup[group] ?? rows.reduce((sum, row) => sum + row.avg_usage_per_day, 0);
    const hours = hoursToRunOut(units, perDay);

    let expiringUnits = 0;
    let minDays = Infinity;
    for (const row of rows) {
      if (!row.earliest_batch_expiry) continue;
      const days = daysUntil(row.earliest_batch_expiry);
      if (days >= 0 && days <= EXPIRY_WINDOW_DAYS) {
        expiringUnits += row.units_unreserved;
        minDays = Math.min(minDays, days);
      }
    }

    return {
      type: group,
      units,
      perDay,
      hours,
      reserved,
      expiring:
        expiringUnits > 0 && Number.isFinite(minDays)
          ? { units: expiringUnits, days: minDays }
          : null,
    };
  });
}

export interface BankSupply {
  id: string;
  code: string;
  name: string;
  address: string;
  unitsByType: Partial<Record<BloodGroup, number>>;
  total: number;
}

/** Collapse depletion rows into one entry per blood bank (for "Find supplies"). */
export function buildBankSupply(depletion: Depletion[]): BankSupply[] {
  const map = new Map<string, BankSupply>();
  for (const row of depletion) {
    let bank = map.get(row.blood_bank_id) ?? {
      id: row.blood_bank_id,
      code: row.blood_bank_code,
      name: row.blood_bank_name,
      address: "",
      unitsByType: {},
      total: 0,
    };
    map.set(row.blood_bank_id, bank);
    const units = (bank.unitsByType[row.blood_group] ?? 0) + row.units_unreserved;
    bank.unitsByType[row.blood_group] = units;
    bank.total += row.units_unreserved;
  }
  return [...map.values()].sort((a, b) => a.name.localeCompare(b.name));
}

export interface InventorySummary {
  totalUnits: number;
  weeklyUsage: number;
  lowTypes: number;
  expiringUnits: number;
}

/** Stat-strip figures for the Inventory page. */
export function inventorySummary(
  stock: StockItem[],
  items: InventoryItem[],
): InventorySummary {
  const totalUnits = items.reduce((sum, item) => sum + item.units_available, 0);
  const expiringUnits = items.reduce((sum, item) => {
    const days = daysUntil(item.expiry_date);
    return days >= 0 && days <= EXPIRY_WINDOW_DAYS ? sum + item.units_available : sum;
  }, 0);
  const weeklyUsage = stock.reduce((sum, item) => sum + item.perDay * 7, 0);
  const lowTypes = stock.filter((item) => item.hours != null && item.hours < 72).length;
  return { totalUnits, weeklyUsage, lowTypes, expiringUnits };
}

/** eRaktKosh `all_groups` key (e.g. `A+Ve`) -> BloodGroup. */
const ALL_GROUPS_TO_BLOOD_GROUP: Record<string, BloodGroup> = {
  "A+Ve": "A+",
  "A-Ve": "A-",
  "B+Ve": "B+",
  "B-Ve": "B-",
  "O+Ve": "O+",
  "O-Ve": "O-",
  "AB+Ve": "AB+",
  "AB-Ve": "AB-",
};

function slug(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

/** One stock item per blood group from the live eRaktKosh summary. Scraped data
 *  is a point-in-time snapshot, so there is no consumption rate or expiry:
 *  `perDay` is 0 and `hours` is null (rendered as "—" by the UI). */
export function buildStockFromErakthosh(
  summary: EraktkoshSummary,
): StockItem[] {
  return BLOOD_GROUPS.map((group) => {
    const g = summary.blood_groups[group];
    const units = g?.total_units ?? 0;
    return {
      type: group,
      units,
      perDay: 0,
      hours: null,
      reserved: 0,
      expiring: null,
    };
  });
}

/** Collapse the scraped per-bank records (one entry per bank, deduplicated by
 *  name, each carrying its full `all_groups` breakdown) into BankSupply rows. */
export function buildBankSupplyFromErakthosh(
  supply: EraktkoshSupply[],
): BankSupply[] {
  const out: BankSupply[] = [];
  for (const rec of supply) {
    const unitsByType: Partial<Record<BloodGroup, number>> = {};
    let total = 0;
    for (const [key, value] of Object.entries(rec.all_groups)) {
      const group = ALL_GROUPS_TO_BLOOD_GROUP[key];
      if (!group) continue;
      const units = Number(value) || 0;
      unitsByType[group] = units;
      total += units;
    }
    out.push({
      id: slug(rec.name),
      code: "",
      name: rec.name,
      address: rec.address,
      unitsByType,
      total,
    });
  }
  return out.sort((a, b) => b.total - a.total || a.name.localeCompare(b.name));
}

/** One stock item per blood group from a blood bank's own DB inventory
 *  (InventoryItem rows). Scraped data has no consumption rate, so `perDay` is 0
 *  and `hours` is null (rendered as "—" by the UI). */
export function buildStockFromInventory(items: InventoryItem[]): StockItem[] {
  return BLOOD_GROUPS.map((group) => {
    const rows = items.filter((i) => i.blood_group === group && i.is_available);
    const units = rows.reduce((sum, row) => sum + row.units_available, 0);
    const reserved = rows.reduce((sum, row) => sum + row.units_reserved, 0);
    let expiringUnits = 0;
    let minDays = Infinity;
    for (const row of rows) {
      const days = daysUntil(row.expiry_date);
      if (days >= 0 && days <= 7) {
        expiringUnits += row.units_available;
        minDays = Math.min(minDays, days);
      }
    }
    return {
      type: group,
      units,
      perDay: 0,
      hours: null,
      reserved,
      expiring:
        expiringUnits > 0 && Number.isFinite(minDays)
          ? { units: expiringUnits, days: minDays }
          : null,
    };
  });
}
