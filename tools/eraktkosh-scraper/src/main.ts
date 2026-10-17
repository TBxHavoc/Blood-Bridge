#!/usr/bin/env node
/**
 * eRaktKosh snapshot generator.
 *
 * Crawls the PUBLIC aggregate stock endpoints of the eRaktKosh portal using Crawlee's
 * HttpCrawler and writes an offline snapshot. It is a deliberately manual, offline
 * tool: it is NOT wired into the running Blood Bridge API, and it must not be
 * scheduled as a background job against a government system.
 *
 * Read README.md before running this, including the "Permission and etiquette"
 * section. Aggressive crawling of a public health service is not acceptable.
 */

import { resolve } from 'node:path';

import { HttpCrawler, log } from 'crawlee';

import { writeOutputs } from './export.js';
import {
  ALL_KNOWN_COMPONENTS,
  DEFAULT_COMPONENTS,
  KNOWN_STATE_CODES,
  type CrawlableComponent,
} from './mapping.js';
import {
  type StateEntry,
  escapeControlCharsInStrings,
  extractDataRows,
  parseStateList,
  parseStockRow,
} from './parse.js';
import { stateListUrl, stockUrl } from './requests.js';
import type { BankComponentStock, Snapshot } from './types.js';

const LABEL = {
  STATE_LIST: 'STATE_LIST',
  STOCK: 'STOCK',
} as const;

const DISCLAIMER =
  'Snapshot of PUBLIC aggregate blood-stock figures published by the eRaktKosh portal. ' +
  'Not patient or donor data. Counts are indicative and may be stale; the portal itself ' +
  'advises calling the blood bank to confirm. This snapshot is not a real-time feed.';

/**
 * eRaktKosh serves its JSON payloads with `Content-Type: application/octet-stream`,
 * NOT `application/json`. Crawlee's `json` accessor only produces a value for the
 * exact `application/json` type, so it returns null here and we decode the body
 * ourselves. (`application/octet-stream` is permitted via `additionalMimeTypes`.)
 */
function readJson(json: unknown, body: string | Buffer): unknown {
  if (json !== null && json !== undefined) return json;
  const text = typeof body === 'string' ? body : body.toString('utf8');
  try {
    return JSON.parse(text) as unknown;
  } catch {
    // The portal sometimes emits raw newlines/tabs inside string values.
    return JSON.parse(escapeControlCharsInStrings(text)) as unknown;
  }
}

interface CliOptions {
  states: number[];
  allStates: boolean;
  districtCode: number | undefined;
  components: CrawlableComponent[];
  outDir: string;
  maxRequestsPerMinute: number;
  includeUnavailable: boolean;
}

function usage(): string {
  return `
eRaktKosh snapshot generator (Crawlee)

Usage:
  npm start -- --states 21,27 [options]
  npm start -- --all-states [options]

Selecting scope (required):
  --states <codes>        Comma-separated eRaktKosh state codes (e.g. 21,27,29)
  --all-states            Crawl every state the portal lists
  --district <code>       Restrict to one district (valid with a single --state)
  --components <codes>    Component codes to crawl (default: 11,12 = Whole Blood, RBC)

Output:
  --out <dir>             Output directory (default: ./output)
  --include-unavailable   Keep banks whose stock cell says "Not Available"
                          (default: only banks with reported stock are written)

Politeness:
  --rpm <n>               Max requests per minute (default: 20)

Information:
  --list-states           Print known state codes and exit
  --list-components       Print eRaktKosh component codes and exit
  --help                  Show this message
`.trim();
}

/** Minimal comma-list / duplicate-aware argv parser. */
function parseArgs(argv: string[]): CliOptions | 'help' | 'list-states' | 'list-components' {
  const states: number[] = [];
  let allStates = false;
  let districtCode: number | undefined;
  let componentCodes: number[] | undefined;
  let outDir = './output';
  let maxRequestsPerMinute = 20;
  let includeUnavailable = false;

  const need = (flag: string, index: number): string => {
    const value = argv[index + 1];
    if (value === undefined || value.startsWith('--')) {
      throw new Error(`${flag} requires a value`);
    }
    return value;
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    switch (arg) {
      case '--help':
      case '-h':
        return 'help';
      case '--list-states':
        return 'list-states';
      case '--list-components':
        return 'list-components';
      case '--all-states':
        allStates = true;
        break;
      case '--include-unavailable':
        includeUnavailable = true;
        break;
      case '--states':
        for (const part of need(arg, i).split(',')) {
          const code = Number.parseInt(part.trim(), 10);
          if (Number.isNaN(code)) throw new Error(`--states: "${part}" is not a number`);
          states.push(code);
        }
        i += 1;
        break;
      case '--district': {
        const code = Number.parseInt(need(arg, i), 10);
        if (Number.isNaN(code)) throw new Error('--district must be a number');
        districtCode = code;
        i += 1;
        break;
      }
      case '--components':
        componentCodes = need(arg, i)
          .split(',')
          .map((part) => Number.parseInt(part.trim(), 10));
        if (componentCodes.some((code) => Number.isNaN(code))) {
          throw new Error('--components: every value must be a number');
        }
        i += 1;
        break;
      case '--out':
        outDir = need(arg, i);
        i += 1;
        break;
      case '--rpm': {
        const value = Number.parseInt(need(arg, i), 10);
        if (Number.isNaN(value) || value <= 0) throw new Error('--rpm must be a positive number');
        maxRequestsPerMinute = value;
        i += 1;
        break;
      }
      default:
        throw new Error(`unknown argument: ${arg}`);
    }
  }

  if (!allStates && states.length === 0) {
    throw new Error('choose scope with --states <codes> or --all-states');
  }
  if (districtCode !== undefined && (allStates || states.length !== 1)) {
    throw new Error('--district requires exactly one --states code');
  }

  let components: CrawlableComponent[] = DEFAULT_COMPONENTS.slice();
  if (componentCodes) {
    components = componentCodes.map((code) => {
      const match = DEFAULT_COMPONENTS.find((entry) => entry.code === code);
      const known = ALL_KNOWN_COMPONENTS.find((entry) => entry.code === code);
      if (!match) {
        throw new Error(
          `--components: code ${code} (${known?.label ?? 'unknown'}) is not mapped to a ` +
            `Blood Bridge component. Supported: ${DEFAULT_COMPONENTS.map((c) => c.code).join(', ')}`,
        );
      }
      return match;
    });
  }

  return { states, allStates, districtCode, components, outDir, maxRequestsPerMinute, includeUnavailable };
}

async function main(): Promise<void> {
  let options: CliOptions | 'help' | 'list-states' | 'list-components';
  try {
    options = parseArgs(process.argv.slice(2));
  } catch (error) {
    log.error((error as Error).message);
    log.error(usage());
    process.exitCode = 1;
    return;
  }

  if (options === 'help') {
    log.info(usage());
    return;
  }

  if (options === 'list-components') {
    log.info('eRaktKosh component codes:');
    for (const component of ALL_KNOWN_COMPONENTS) {
      const mapped = DEFAULT_COMPONENTS.some((entry) => entry.code === component.code)
        ? ' [crawled by default]'
        : '';
      log.info(`  ${component.code}  ${component.label}${mapped}`);
    }
    return;
  }

  if (options === 'list-states') {
    log.info('eRaktKosh state codes (verified 2026-10-18; the portal is authoritative):');
    for (const [code, name] of Object.entries(KNOWN_STATE_CODES).sort((a, b) => Number(a[0]) - Number(b[0]))) {
      log.info(`  ${code}\t${name}`);
    }
    return;
  }

  const {
    states,
    allStates,
    districtCode,
    components,
    outDir,
    maxRequestsPerMinute,
    includeUnavailable,
  } = options;

  const records: BankComponentStock[] = [];
  const statesRequested: StateEntry[] = [];
  const unmappedGroupLabels = new Set<string>();
  let skippedRows = 0;

  log.info(
    `Crawling eRaktKosh: ${allStates ? 'all states' : `states ${states.join(', ')}`}, ` +
      `components ${components.map((c) => `${c.code} (${c.label})`).join(', ')}, ` +
      `max ${maxRequestsPerMinute} req/min`,
  );

  const crawler = new HttpCrawler({
    // Politeness: one in-flight request and a hard per-minute ceiling.
    maxConcurrency: 1,
    maxRequestsPerMinute,
    maxRequestRetries: 2,
    // A government health portal should not be hit harder than necessary; there is
    // no robots.txt on this origin (verified 404), but we honour one if it appears.
    respectRobotsTxtFile: true,
    additionalHttpErrorStatusCodes: [404],
    // eRaktKosh returns its JSON as application/octet-stream, not application/json.
    additionalMimeTypes: ['application/octet-stream'],

    async requestHandler({ request, json, body, crawler: activeCrawler }) {
      const payload = readJson(json, body);
      const userData = request.userData as Record<string, unknown>;

      if (userData.label === LABEL.STATE_LIST) {
        const all = parseStateList(payload);
        log.info(`Portal reports ${all.length} states/UTs`);

        const selected = allStates ? all : all.filter((state) => states.includes(state.code));
        const missing = states.filter((code) => !all.some((state) => state.code === code));
        if (missing.length > 0) {
          log.warning(`State codes not present in the portal list (skipped): ${missing.join(', ')}`);
        }

        const stockRequests = selected.flatMap((state) =>
          components.map((component) => ({
            url: stockUrl({ stateCode: state.code, districtCode, componentCode: component.code }),
            label: LABEL.STOCK,
            userData: {
              label: LABEL.STOCK,
              stateCode: state.code,
              stateName: state.name,
              componentCode: component.code,
              component: component.component,
              componentLabel: component.label,
            },
          })),
        );

        log.info(`Queueing ${stockRequests.length} stock requests`);
        await activeCrawler.addRequests(stockRequests);
        return;
      }

      // STOCK
      const { stateCode, stateName, componentCode, component, componentLabel } = userData as {
        stateCode: number;
        stateName: string;
        componentCode: number;
        component: BankComponentStock['component'];
        componentLabel: string;
      };
      statesRequested.push({ code: stateCode, name: stateName });

      const rows = extractDataRows(payload);
      const fetchedAt = new Date().toISOString();

      for (const [index, row] of rows.entries()) {
        const { record, skippedReason, unmappedGroups } = parseStockRow(row, index, {
          componentCode,
          component,
          stateCode,
          districtCode: districtCode ?? -1,
          sourceUrl: request.url,
          fetchedAt,
        });
        for (const label of unmappedGroups) unmappedGroupLabels.add(label);
        if (skippedReason !== undefined) {
          skippedRows += 1;
          continue;
        }
        if (record === null) continue;
        if (!includeUnavailable && !record.available) continue;
        records.push(record);
      }

      log.info(
        `${stateName} [${componentLabel}] -> ${rows.length} rows ` +
          `(${records.length} kept so far)`,
      );
    },

    async failedRequestHandler({ request }, error) {
      log.error(`Request failed permanently: ${request.url} :: ${error.message}`);
    },
  });

  await crawler.run([
    {
      url: stateListUrl(),
      label: LABEL.STATE_LIST,
      userData: { label: LABEL.STATE_LIST },
    },
  ]);

  // Stable de-duplication: the portal can repeat a bank across district boundaries.
  const unique = new Map<string, BankComponentStock>();
  for (const record of records) {
    const key = [record.name, record.componentCode, record.district ?? '', record.phone ?? ''].join('|');
    if (!unique.has(key)) unique.set(key, record);
  }
  const dedupedRecords = [...unique.values()];
  const dedupedAway = records.length - dedupedRecords.length;

  if (unmappedGroupLabels.size > 0) {
    log.warning(
      `Unmapped blood-group labels seen (check mapping.ts for drift): ` +
        [...unmappedGroupLabels].join(', '),
    );
  }
  if (skippedRows > 0) {
    log.info(`Skipped ${skippedRows} placeholder/inactive rows`);
  }
  if (dedupedAway > 0) {
    log.info(`Removed ${dedupedAway} duplicate rows`);
  }

  const bankCount = new Set(dedupedRecords.map((record) => record.name)).size;

  const snapshot: Snapshot = {
    provenance: {
      generator: 'tools/eraktkosh-scraper (Crawlee HttpCrawler)',
      generatedAt: new Date().toISOString(),
      disclaimer: DISCLAIMER,
      source: stateListUrl().replace(/hmode=[A-Z]+/, 'hmode=GET*'),
      components: components.map((component) => ({
        code: component.code,
        label: component.label,
        component: component.component,
      })),
      statesRequested: [...new Map(statesRequested.map((s) => [s.code, s])).values()],
      rowCount: dedupedRecords.length,
      bankCount,
    },
    records: dedupedRecords,
  };

  const written = await writeOutputs(resolve(outDir), snapshot);
  log.info(`Wrote ${written.recordCount} records across ${written.bankCount} banks`);
  log.info(`  ${written.snapshotPath}`);
  log.info(`  ${written.csvPath}`);
  log.warning(DISCLAIMER);
}

await main();
