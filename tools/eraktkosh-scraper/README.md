# eRaktKosh snapshot generator

An **offline** tool that uses [Crawlee](https://crawlee.dev/)'s `HttpCrawler` to read the
**public aggregate blood-stock figures** published by the [eRaktKosh](https://eraktkosh.mohfw.gov.in/)
portal (India's national blood-bank directory, run by C-DAC under the Ministry of Health
and Family Welfare).

It writes a timestamped snapshot to disk. It does **not** run inside the Blood Bridge
backend, does **not** talk to the database, and is **not** a live feed.

---

## ⚠️ Read this first: permission and etiquette

`docs/DATA_SOURCES.md` states that live data from government systems is not used without
explicit permission. **This tool is the deliberate exception, and running it is a
decision the team must own.** Before you run it against the real portal, make sure:

1. **You have permission**, or a clear internal decision that this is acceptable. For an
   IBM Z Datathon entry, the safest route is still the sanctioned one: eRaktKosh is a
   registered HSPA on the **ABDM/UHI** network, which publishes an official Blood Bank
   Discovery API (`nic2008:86906`, `BloodStock`) with a public sandbox.
2. **You stay polite.** The defaults are deliberately conservative: `maxConcurrency: 1`
   and 20 requests per minute. A full India crawl is ~72 requests (36 states x 2
   components), which takes a few minutes. Do not raise this to "finish faster".
3. **You keep the disclaimer.** Everything written by this tool carries a provenance
   block saying the numbers are indicative, may be stale, and are not a real-time feed.
   eRaktKosh itself tells users to phone the blood bank to confirm.
4. **You do not schedule it.** This is a manual, run-on-demand tool. Do not wire it to a
   cron job, a CI pipeline, or a running service against a public health system.

This tool reads **only** what is already public and aggregate: blood bank names, contact
details, locations, and per-blood-group unit counts. It never touches patient records,
donor records, or transaction histories, and it cannot — those require authentication the
tool does not implement.

---

## What eRaktKosh publishes — and what Blood Bridge needs

This is the important gap. Do **not** assume the snapshot can be loaded straight into the
seeder.

| Blood Bridge needs (`blood_inventory`) | eRaktKosh publishes? |
|---|---|
| `blood_group` | ✅ yes (`A+Ve` → `A+`) |
| `component_type` | ✅ partly — only Whole Blood (11) and Packed RBC (12) map to the project's `WHOLE_BLOOD` / `RBC` |
| `units_available` | ✅ yes, per blood group |
| `units_reserved` | ❌ no |
| `collection_date` | ❌ no |
| `expiry_date` | ❌ no — the portal reports a single aggregate cell, not per-unit bags |
| `storage_location_code` | ❌ no |

| Blood Bridge needs (`blood_banks`) | eRaktKosh publishes? |
|---|---|
| `name`, `city`, `phone` | ✅ yes (parsed from an HTML blob) |
| `latitude`, `longitude` | ❌ no — only a text address; geocoding would need another service |
| `capacity_units` | ❌ no |
| `is_active` | ⚠️ inferred — de-listed banks appear as `-<br/>-<br/>-` and are dropped |

**Consequence:** this tool deliberately fabricates nothing. There is no `--make-up-expiry`
flag. If the project wants to seed `blood_inventory` from real counts, the missing columns
are a decision for the team to make openly and document, not something to invent silently
inside a scraper. Right now the snapshot is an **analysis and realism input**, not a seeder
input.

For the **synthetic demo dataset**, the existing generator
(`backend/app/seed/generate.py`) remains the source of truth, and every synthetic dataset
stays labelled "SIMULATED FOR DEMONSTRATION PURPOSES".

---

## Requirements

- Node.js >= 20 (verified on Node 24)
- Network access to `eraktkosh.mohfw.gov.in`

```bash
npm install
```

## Usage

```bash
# One state (Odisha = 21), both components
npm start -- --states 21

# Several states
npm start -- --states 21,27,29

# Every state the portal lists (≈72 requests, a few minutes at the default rate)
npm start -- --all-states

# One district of one state
npm start -- --states 21 --district 378

# Keep banks whose cell says "Not Available" (default: only stock-bearing banks)
npm start -- --states 21 --include-unavailable

# Info
npm start -- --list-states
npm start -- --list-components
npm start -- --help
```

Full component list: the portal also offers FFP (13), platelets (14/20/23),
cryoprecipitate (17) and plasma (18/19/21). Those are intentionally **not** crawled by
default because Blood Bridge models only `WHOLE_BLOOD` and `RBC`. Passing
`--components 13` is rejected with an explanatory error.

## Output

Written to `./output/` (git-ignored):

- **`eraktkosh_snapshot.json`** — full fidelity: every record plus a `provenance` block
  (generation time, disclaimer, source, components, states, counts).
- **`eraktkosh_blood_stock.csv`** — flat long format, one row per
  (bank, component, blood group), plus `availability_text`, `last_updated`, `source_url`
  and `fetched_at` so every number can be traced back to a specific response.

## How it works

```
GETSTATELIST ──► for each state × component:
                 GETNEARBYSTOCKDETAILS?stateCode&districtCode=-1&bloodGroup=all&bloodComponent=NN
                 ──► parse 6-column rows ──► dedupe ──► write snapshot
```

Three things were verified against the live portal and are load-bearing:

1. **`Content-Type` is `application/octet-stream`, not `application/json`.** Crawlee skips
   unlisted MIME types, so `additionalMimeTypes` is set and the body is decoded manually —
   Crawlee's `json` accessor only works for the exact `application/json` type.
2. **The payload is intermittently invalid JSON.** Bank names/addresses sometimes contain
   raw newlines, which makes `JSON.parse` throw "Bad control character in string literal".
   `escapeControlCharsInStrings` walks the text and escapes control characters only inside
   string literals.
3. **`bloodComponent=-1` returns an empty result.** A concrete component code is required,
   and the district endpoint uses `selectedStateCode`, not `stateCode`.

Unrecognised blood-group labels are reported as warnings rather than dropped silently, so
portal drift is visible instead of quietly corrupting the snapshot.

## Layout

```
src/
  main.ts      CLI + Crawlee HttpCrawler + provenance
  requests.ts  URL builders for the portal's hmode endpoints
  parse.ts     row/cell parsers, tolerant JSON handling
  mapping.ts   eRaktKosh code ↔ Blood Bridge value mappings
  export.ts    JSON + CSV writers
  types.ts     domain types
```
