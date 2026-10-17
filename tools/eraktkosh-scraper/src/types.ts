/**
 * Domain types for the eRaktKosh snapshot tool.
 *
 * These mirror what the eRaktKosh portal actually PUBLISHES. They deliberately do
 * not pretend to be the Blood Bridge database schema, because the portal does not
 * publish everything that schema requires (see README -> "What eRaktKosh does not
 * publish").
 */

/** Blood Bridge canonical blood groups (backend/app/constants.py -> BLOOD_GROUPS). */
export type BloodGroup = 'A+' | 'A-' | 'B+' | 'B-' | 'AB+' | 'AB-' | 'O+' | 'O-';

/** Blood Bridge component types this project supports (backend/app/constants.py). */
export type ComponentType = 'WHOLE_BLOOD' | 'RBC';

/** One blood group count inside a bank's availability cell. */
export interface ComponentCell {
  bloodGroup: BloodGroup;
  units: number;
}

/**
 * One bank, for one component, as returned by GETNEARBYSTOCKDETAILS.
 *
 * Note the granularity: the portal reports a single aggregate availability cell per
 * (bank, component), listing units per blood group. It does not expose per-unit
 * collection or expiry dates.
 */
export interface BankComponentStock {
  /** Deterministic key derived from the source URL and row position. */
  sourceKey: string;
  name: string;
  /** Portal's own category label, e.g. "Govt." or "Charitable/Vol". */
  category: string;
  /** Portal's entity type label, e.g. "Blood Bank". */
  entityType: string;
  addressLine: string;
  city: string | null;
  district: string | null;
  state: string | null;
  phone: string | null;
  fax: string | null;
  email: string | null;
  /** eRaktKosh numeric state code used in the request. */
  stateCode: number;
  /** eRaktKosh numeric district code used in the request (-1 means "all districts"). */
  districtCode: number;
  component: ComponentType;
  /** eRaktKosh component code used in the request (11, 12, ...). */
  componentCode: number;
  /** True when the portal cell was `text-success`. */
  available: boolean;
  /** Raw human-readable availability text, kept for auditability. */
  availabilityText: string;
  cells: ComponentCell[];
  /** Portal's "Last Updated" value, exactly as published (no timezone is claimed). */
  lastUpdated: string | null;
  sourceUrl: string;
  /** When this tool fetched the row, ISO 8601 UTC. */
  fetchedAt: string;
}

/** Provenance block written alongside every snapshot. */
export interface SnapshotProvenance {
  generator: string;
  generatedAt: string;
  disclaimer: string;
  source: string;
  components: Array<{ code: number; label: string; component: ComponentType }>;
  statesRequested: Array<{ code: number; name: string }>;
  /** Aggregate counts so a reviewer can sanity-check the run. */
  rowCount: number;
  bankCount: number;
}

export interface Snapshot {
  provenance: SnapshotProvenance;
  records: BankComponentStock[];
}
