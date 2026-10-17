/**
 * Mappings between eRaktKosh codes/labels and Blood Bridge domain values.
 *
 * Verified against the live portal on 2026-10-18:
 *   - component dropdown on stockAvailability.cnt
 *   - availability cells rendered as `A+Ve`, `AB-Ve`, ...
 *
 * eRaktKosh is a third party: these codes can change without notice. Everything
 * unmapped is reported rather than silently dropped, so drift is visible.
 */

import type { BloodGroup, ComponentType } from './types.js';

export const ERAKTKOSH_ORIGIN = 'https://eraktkosh.mohfw.gov.in';
export const ERAKTKOSH_ENDPOINT = `${ERAKTKOSH_ORIGIN}/BLDAHIMS/bloodbank/nearbyBB.cnt`;

/** `hmode` values used by the portal's own AJAX calls. */
export const HMODE = {
  STATE_LIST: 'GETSTATELIST',
  DISTRICT_LIST: 'GETDISTRICTLIST',
  NEARBY_STOCK: 'GETNEARBYSTOCKDETAILS',
} as const;

export interface CrawlableComponent {
  /** eRaktKosh numeric component code. */
  code: number;
  /** Portal's human label (for provenance). */
  label: string;
  /** Mapped Blood Bridge component type. */
  component: ComponentType;
}

/**
 * Only the components Blood Bridge actually models are crawled by default.
 *
 * The portal also offers FFP (13), platelets (14, 20, 23), cryoprecipitate (17),
 * plasma (18, 19, 21) and SAGM cells (28). Those are intentionally out of scope:
 * the project's COMPONENT_TYPES is ("WHOLE_BLOOD", "RBC") only.
 */
export const DEFAULT_COMPONENTS: readonly CrawlableComponent[] = [
  { code: 11, label: 'Whole Blood', component: 'WHOLE_BLOOD' },
  { code: 12, label: 'Packed Red Blood Cells', component: 'RBC' },
] as const;

/** Every component code the portal advertises, for `--list-components`. */
export const ALL_KNOWN_COMPONENTS: readonly { code: number; label: string }[] = [
  { code: 11, label: 'Whole Blood' },
  { code: 12, label: 'Packed Red Blood Cells' },
  { code: 13, label: 'Fresh Frozen Plasma' },
  { code: 14, label: 'Single Donor Platelet' },
  { code: 16, label: 'Platelet Rich Plasma' },
  { code: 17, label: 'Cryoprecipitate' },
  { code: 18, label: 'Single Donor Plasma' },
  { code: 19, label: 'Plasma' },
  { code: 20, label: 'Platelet Concentrate' },
  { code: 21, label: 'Cryo Poor Plasma' },
  { code: 23, label: 'Random Donor Platelets' },
  { code: 28, label: 'Sagm Packed Red Blood Cells' },
] as const;

/** Blood Bridge canonical blood groups, in a stable order for CSV columns. */
export const BLOOD_GROUPS: readonly BloodGroup[] = [
  'A+',
  'A-',
  'B+',
  'B-',
  'AB+',
  'AB-',
  'O+',
  'O-',
] as const;

/**
 * Convert an eRaktKosh group label (`A+Ve`, `AB-Ve`, ...) to a Blood Bridge group.
 * Returns null for anything unrecognised so callers can log drift.
 */
export function toBloodGroup(label: string): BloodGroup | null {
  // Order matters: AB must be tried before A and B.
  const match = /^(AB|A|B|O)([+-])Ve$/.exec(label.trim());
  if (!match) return null;
  return `${match[1]}${match[2]}` as BloodGroup;
}

/** Numeric eRaktKosh state codes seen on the portal, for `--list-states` help text. */
export const KNOWN_STATE_CODES: Readonly<Record<number, string>> = {
  35: 'Andaman and Nicobar Islands',
  28: 'Andhra Pradesh',
  12: 'Arunachal Pradesh',
  18: 'Assam',
  10: 'Bihar',
  94: 'Chandigarh',
  22: 'Chhattisgarh',
  25: 'Dadra And Nagar Haveli And Daman And Diu',
  97: 'Delhi',
  30: 'Goa',
  24: 'Gujarat',
  96: 'Haryana',
  92: 'Himachal Pradesh',
  91: 'Jammu and Kashmir',
  20: 'Jharkhand',
  29: 'Karnataka',
  32: 'Kerala',
  37: 'Ladakh',
  31: 'Lakshadweep',
  23: 'Madhya Pradesh',
  27: 'Maharashtra',
  14: 'Manipur',
  17: 'Meghalaya',
  15: 'Mizoram',
  13: 'Nagaland',
  21: 'Odisha',
  34: 'Puducherry',
  3: 'Punjab',
  8: 'Rajasthan',
  11: 'Sikkim',
  33: 'Tamil Nadu',
  36: 'Telangana',
  38: 'Tripura',
  9: 'Uttar Pradesh',
  5: 'Uttarakhand',
  19: 'West Bengal',
};
