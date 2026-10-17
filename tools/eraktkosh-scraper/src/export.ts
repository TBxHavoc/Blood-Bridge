/**
 * Output writers.
 *
 * Two artefacts are produced side by side:
 *
 *   - eraktkosh_snapshot.json : full fidelity, including provenance and raw text
 *   - eraktkosh_blood_stock.csv : flat long format, one row per (bank, component, group)
 *
 * Nothing is fabricated. The portal does not publish per-unit collection/expiry
 * dates, coordinates or reserved counts, so none are invented here.
 */

import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

import { BLOOD_GROUPS } from './mapping.js';
import type { BankComponentStock, Snapshot } from './types.js';

const CSV_COLUMNS = [
  'source_key',
  'bank_name',
  'category',
  'entity_type',
  'address',
  'city',
  'district',
  'state',
  'state_code',
  'district_code',
  'phone',
  'fax',
  'email',
  'component',
  'component_code',
  'blood_group',
  'units',
  'available',
  'availability_text',
  'last_updated',
  'source_url',
  'fetched_at',
] as const;

/** RFC 4180-ish escaping: quote when the value contains , " or a newline. */
function csvCell(value: unknown): string {
  if (value === null || value === undefined) return '';
  const text = String(value);
  if (/[",\r\n]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

function csvRow(values: readonly unknown[]): string {
  return values.map(csvCell).join(',');
}

/**
 * Flatten records to one row per blood group.
 *
 * A bank that is available but has no reported units for a group simply omits that
 * group. A bank with no stock at all (text-danger) still gets one row with an empty
 * blood_group and empty units, so the bank is not silently lost.
 */
export function toLongRows(records: BankComponentStock[]): unknown[][] {
  const rows: unknown[][] = [];

  for (const record of records) {
    const base = [
      record.sourceKey,
      record.name,
      record.category,
      record.entityType,
      record.addressLine,
      record.city,
      record.district,
      record.state,
      record.stateCode,
      record.districtCode,
      record.phone,
      record.fax,
      record.email,
      record.component,
      record.componentCode,
    ];

    const byGroup = new Map(record.cells.map((cell) => [cell.bloodGroup, cell.units]));
    const reported = BLOOD_GROUPS.filter((group) => byGroup.has(group));

    if (reported.length === 0) {
      rows.push([...base, '', '', String(record.available), record.availabilityText, record.lastUpdated, record.sourceUrl, record.fetchedAt]);
      continue;
    }

    for (const group of reported) {
      rows.push([
        ...base,
        group,
        byGroup.get(group) ?? 0,
        String(record.available),
        record.availabilityText,
        record.lastUpdated,
        record.sourceUrl,
        record.fetchedAt,
      ]);
    }
  }

  return rows;
}

export function toCsv(records: BankComponentStock[]): string {
  const lines = [csvRow(CSV_COLUMNS), ...toLongRows(records).map(csvRow)];
  return `${lines.join('\n')}\n`;
}

export interface WrittenOutputs {
  snapshotPath: string;
  csvPath: string;
  recordCount: number;
  bankCount: number;
}

export async function writeOutputs(outDir: string, snapshot: Snapshot): Promise<WrittenOutputs> {
  await mkdir(outDir, { recursive: true });

  const snapshotPath = join(outDir, 'eraktkosh_snapshot.json');
  const csvPath = join(outDir, 'eraktkosh_blood_stock.csv');

  await writeFile(snapshotPath, `${JSON.stringify(snapshot, null, 2)}\n`, 'utf8');
  await writeFile(csvPath, toCsv(snapshot.records), 'utf8');

  return {
    snapshotPath,
    csvPath,
    recordCount: snapshot.records.length,
    bankCount: snapshot.provenance.bankCount,
  };
}
