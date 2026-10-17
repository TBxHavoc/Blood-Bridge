/** Adapters that turn backend forecasting/inventory payloads into the shapes
 *  the UI components expect (the design's `STOCK` / `BANKS` sample structures). */

import { BLOOD_GROUPS, daysUntil, hoursToRunOut } from "./blood";
import type { BloodGroup, Depletion, InventoryItem, UsageStat } from "./types";

export interface StockItem {
  type: BloodGroup;
  units: number;
  perDay: number;
  hours: number;
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
  unitsByType: Partial<Record<BloodGroup, number>>;
  total: number;
}

/** Collapse depletion rows into one entry per blood bank (for "Find supplies"). */
export function buildBankSupply(depletion: Depletion[]): BankSupply[] {
  const map = new Map<string, BankSupply>();
  for (const row of depletion) {
    let bank = map.get(row.blood_bank_id);
    if (!bank) {
      bank = {
        id: row.blood_bank_id,
        code: row.blood_bank_code,
        name: row.blood_bank_name,
        unitsByType: {},
        total: 0,
      };
      map.set(row.blood_bank_id, bank);
    }
    bank.unitsByType[row.blood_group] =
      (bank.unitsByType[row.blood_group] ?? 0) + row.units_unreserved;
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
  const lowTypes = stock.filter((item) => item.hours < 72).length;
  return { totalUnits, weeklyUsage, lowTypes, expiringUnits };
}
