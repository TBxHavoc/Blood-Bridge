/**
 * URL builders for the eRaktKosh portal's internal AJAX endpoints.
 *
 * These are the same `hmode` calls the portal's own pages make; they return JSON.
 * Parameter shapes verified against stockAvailability.cnt on 2026-10-18.
 */

import { ERAKTKOSH_ENDPOINT, HMODE } from './mapping.js';

/** All states, as `[{ value: "21", label: "Odisha" }, ...]`. */
export function stateListUrl(): string {
  const url = new URL(ERAKTKOSH_ENDPOINT);
  url.searchParams.set('hmode', HMODE.STATE_LIST);
  url.searchParams.set('lang', '0');
  return url.toString();
}

/**
 * Districts within a state.
 *
 * Note the parameter is `selectedStateCode`, NOT `stateCode` — using the latter
 * silently returns `{"records": []}`.
 */
export function districtListUrl(stateCode: number): string {
  const url = new URL(ERAKTKOSH_ENDPOINT);
  url.searchParams.set('hmode', HMODE.DISTRICT_LIST);
  url.searchParams.set('selectedStateCode', String(stateCode));
  url.searchParams.set('lang', '0');
  return url.toString();
}

/**
 * Aggregate stock for one (state, district, component) combination.
 *
 * `districtCode: -1` means "every district in the state". `bloodGroup: all` returns
 * every group in a single cell rather than one request per group.
 *
 * `bloodComponent` MUST be a concrete code: `-1` (which the portal's own hidden
 * input defaults to) returns an empty `{"data": []}`.
 */
export function stockUrl(options: {
  stateCode: number;
  districtCode?: number;
  componentCode: number;
}): string {
  const { stateCode, districtCode = -1, componentCode } = options;
  const url = new URL(ERAKTKOSH_ENDPOINT);
  url.searchParams.set('hmode', HMODE.NEARBY_STOCK);
  url.searchParams.set('stateCode', String(stateCode));
  url.searchParams.set('districtCode', String(districtCode));
  url.searchParams.set('bloodGroup', 'all');
  url.searchParams.set('bloodComponent', String(componentCode));
  url.searchParams.set('lang', '0');
  return url.toString();
}
