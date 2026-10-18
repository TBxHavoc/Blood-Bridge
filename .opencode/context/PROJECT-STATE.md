# Project state

> Maintained by the agent. Read this before planning; update it after changing anything.
> Global rules: `@vault` `GLOBAL/MEMORY-RULES.md`.

## Purpose

**Blood Bridge** (IBM Z Datathon 2026, AI Secured track, 24-hour MVP). Privacy-first
AI coordination layer that matches emergency hospital blood requests to blood-bank
inventory. It never receives patient or donor identity; matching is rule-based,
explainable and audited. All data is synthetic (`SIMULATED FOR DEMONSTRATION PURPOSES`).

## Architecture

Monorepo, two top-level packages:

- `backend/` — the single FastAPI application (`app/`) **plus the whole ML pipeline**:
  `datasets/` (synthetic CSVs), `models/depletion_model.pkl`, `notebooks/`,
  `docs/ML_DEPLETION_MODEL.md`, `scripts/` (train/predict/evaluate/test/metrics),
  `tests/`. Stack: FastAPI + SQLAlchemy 2.0 + PostgreSQL.
- `database/` — **DB-only deliverable**: `sql/` (PostgreSQL + Db2 DDL, seed, views),
  `models/db_models.py` (dual-compatible ORM), `scripts/` (verify_db,
  test_hold_transaction, audit_chain_verifier), `docs/` (design + LinuxONE guide),
  `docker-compose.yml` (postgres + pgadmin). No app, no notebooks.
- `frontend/` — **Vite 5 + React 18 + TypeScript SPA** (`src/`, `package.json`,
  `vite.config.ts`, `tsconfig.json`). Ported 1:1 from `prototypes/`
  (`login page.html`, `hospital-home.html`), which are kept as the visual
  reference. Talks to `backend/` through a Vite dev proxy (`/api` →
  `http://127.0.0.1:8000`, override with `VITE_BACKEND`), so no CORS changes are
  needed. See `frontend/README.md`.

`DATABASE_URL` is the single switch between PostgreSQL and Db2 on IBM Z — no code
changes needed. Python 3.11 (`backend/`), 3.11+ (`database/` scripts).

Everything above ships as containers from the **root `docker-compose.yml`**
(`db` + `api` + `web`, plus the opt-in `seed` and `tools`/pgAdmin profiles). The
`web` container is nginx serving the built SPA and proxying `/api` → `api:8000`,
so the browser only ever sees one origin. All configuration is the git-ignored
root `.env` (template: the tracked `.env.example`); the same file targets a
Linux / IBM LinuxONE host — only the values change, never the compose file or the
images.

The API also runs the eRaktKosh background scraper
(`app/services/eraktkosh_scraper.py`, wired into `main.py`'s lifespan): it scrapes
Bengaluru stock once shortly after startup and then every
`ERAKTKOSH_SYNC_INTERVAL_SECONDS`, writing to `/data/eraktkosh` — a `bb_scrape`
named volume, pre-created in the image because the path is hardcoded upstream.
That same volume is mounted read-only into the `web` container at
`/usr/share/nginx/html/data`, so nginx serves `/data/eraktkosh/*.json` straight
off disk: the UI's static-first fetches see each new scrape in place, with no
API round-trip and no rebuild. It needs `scrapling[fetchers]` (see
`DECISIONS.md`).

## Scope boundaries

**In scope:**
- Blood request↔inventory matching, supply-depletion ML, synthetic data generation.

**Out of scope (do not touch without asking):**
- Re-introducing a second app copy: `database/` must stay DB-only. The app lives in
  `backend/` only.
- Root-level `datasets/`, `docs/`, `notebooks/`, `scripts/` are gone by design —
  do not recreate them; ML assets belong under `backend/`.

## Invariants

- No patient/donor identity ever enters the system.
- **No credential ever lives in tracked files.** Passwords come from the
  git-ignored `backend/.env` (`SEED_PASSWORD`, `ADMIN_USERNAME`,
  `ADMIN_PASSWORD`) and are stored only as bcrypt hashes. The frontend never
  receives or embeds a credential. Before committing, grep tracked files for the
  values in `backend/.env` to confirm none leaked into code.
- All data must remain synthetic/demonstration-only.
- `DATABASE_URL` switches PostgreSQL↔Db2 without code changes.
- Single source of truth: one app (`backend/`), one model artifact
  (`backend/models/depletion_model.pkl`), one notebook, one copy of each ML script.

## Current state

**Done:**
- Repo cloned from `https://github.com/TBxHavoc/Blood-Bridge.git`, branch `dev`
  (HEAD `9ae54e6`), tracking `origin/dev`, into `D:\ibm dev branch`.
- De-duplication / pipeline rebuild: removed root stragglers (`datasets/`, `docs/`,
  `notebooks/`, `scripts/`), the stray `backend/model/` (singular), the stale
  `database/app/` tree and all duplicate ML assets. Consolidated the ML pipeline
  into `backend/`. `database/` reduced to DB-only. See `DECISIONS.md`.
- Merged `origin/frontend` into `dev` (`30ceb11`) — added `frontend/` prototypes.
  Root `.gitignore`/`README.md` preserved (frontend branch had deleted them).
- Prototypes moved to `frontend/prototypes/` (`git mv`).
- Frontend built: Vite + React 18 + TS SPA in `frontend/src` — `lib/{api,types,
  blood,derive,session}` (envelope-unwrapping client, field-accurate types),
  `auth/AuthContext` (JWT in `localStorage` key `bb.session`), `app/NavContext`
  (no router dep), `components/*`, `pages/*` (Login, Dashboard shell, Overview,
  Inventory, FindSupplies, RequestBlood, Reports, Faq). Styles ported verbatim to
  `styles/{tokens,app,login}.css`; `login.css` scoped under `.login-page`.
- Verified: `tsc --noEmit` clean, `vite build` clean (57 modules, ~195 kB JS),
  dev server serves the app, and `/api` proxy reaches the API end-to-end
  (login → role, `/inventory` 200 for `bloodbank_user`, `/forecasting/summary`,
  `/requests` + `matches`, `/inventory` 403 for `hospital_user`). Smoke-tested
  against a local SQLite `DATABASE_URL` (SQLAlchemy layer is dialect-neutral, so
  the Postgres/Db2 code path is unchanged).
- Sidebar/UI polish: profile menu (account button → dropdown with Profile dialog
  / Logout, `components/Sidebar.tsx` + `Icons.tsx`) and an ambient **bloodstream**
  canvas behind the nav (`components/Bloodstream.tsx` — RBCs/WBCs/platelets/plasma
  drifting bottom-to-top, one recycled cell pool, depth-sorted, reduced-motion
  aware). It replaced an earlier DNA-helix canvas (removed). It sits at
  `z-index: -1`, which only works because `.side` is a stacking context — see
  `DECISIONS.md` before changing it. Also, the login page de-chromed
  (`styles/login.css`): input borders flattened, and `.box`/`.notice` given
  explicit resets because the dashboard stylesheet leaks its alert-card and
  banner chrome into them — see `DECISIONS.md`.
- Karnataka reference data: three district-wise hospital registries pulled from
  data.gov.in into `backend/datasets/karnataka/` — private 1543, public district
  33, public general 137 rows — via the new stdlib-only
  `backend/scripts/fetch_karnataka_hospitals.py`. The key comes from
  `DATAGOVIN_API_KEY` (blank placeholder added to `.env.example`); nothing is
  hardcoded. Reference data only: **not** wired into the `hospitals` table, seed
  or ML contract.
- **Containerised locally** — root `docker-compose.yml`, verified running.
  `db` (postgres:16-alpine, loopback-only 5432) + `api` (non-root `appuser`,
  healthcheck on `/api/v1/health`) + `web` (nginx: SPA shell, SPA deep-link
  fallback, and `/api` reverse proxy) all report **healthy**; login through the
  proxy returns a JWT and the database holds the 11 tables plus the seeded rows.
  Opt-in profiles: `seed` (`docker compose run --rm seed`, run with `--no-csv`)
  and `tools` (pgAdmin). Retired the superseded `backend/docker-compose.yml`,
  and dropped every explicit `container_name` so a sibling copy of this repo
  (`D:\ibm hackathon`, project `ibmhackathon`) no longer collides on the global
  name `bloodbridge-db`. See `DECISIONS.md`.
- **Fixed the seed's two missing demo accounts.** `app/seed/seed.py` built the
  `_admin`/`_auditor` `User` objects and counted them, but never passed them to
  `db.add()`, so they were never inserted — 30 rows persisted while 32 were
  reported, and `_admin` returned 401. They are now added in one `db.add_all`
  plus `flush()`, and the reported `users` count is read back from the database
  rather than trusting `len(users)`, so that class of divergence cannot hide
  again. Verified in the container: 33 users (20 bank + 10 hospital + `_auditor`
  + `_admin` + the bootstrap `admin`) and all five login paths authenticate. See
  `DECISIONS.md`.
- **Pulled + containerised the eRaktKosh feature** (`bfac9ce`, `51ca05c`): a
  background scraper in the API, `GET /api/v1/eraktkosh/{summary,bangalore/{bg}}`,
  `POST /api/v1/eraktkosh/sync-now`, and a "Live Bangalore Stock" page. The API
  crashed on startup until `scrapling[fetchers]==0.5` was added to
  `backend/requirements.txt`; the scraper also needed a writable
  `/data/eraktkosh` plus a `bb_scrape` volume. Verified live: the worker fetched
  906 component records, wrote all 8 blood groups (17 files), and
  `GET /api/v1/eraktkosh/bangalore/O%2B` returns 273 records / 13708 units. See
  `DECISIONS.md`.
- **Made the scraped data actually show in the UI.** The Live page's static-first
  fetches could never reach their API fallback (the parse error on nginx's
  SPA-fallback `index.html` fired *inside* the `if (res.ok)` branch), and nothing
  served `/data/eraktkosh/*.json` at all, so the blood-group table never had live
  data. Fixed the fetch logic and mounted `bb_scrape` into the web container at
  `/usr/share/nginx/html/data`. Verified: the static endpoint returns
  `application/json`, and a forced scrape moved the served `last_updated_iso`
  `23:46:25 → 23:51:28` with no rebuild.

**In progress:**
- Nothing actively mid-edit; frontend feature-complete pending review of visuals
  in a browser (structure/CSS ported, not yet eyeballed).

**Known gaps / deliberately deferred:**
- **Signing in has no UI hint by design.** The temp admin is
  `ADMIN_USERNAME`/`ADMIN_PASSWORD` from the local git-ignored `backend/.env`,
  (re)created hashed at every startup by `app/seed/bootstrap.py`. Because `.env`
  is the source of truth, editing the password there and restarting rotates it.
- `backend/datasets/*.csv` show timestamp-only churn from a `app.seed.seed` run
  that wrote CSVs (rows get `datetime.now()`-relative timestamps, so every run
  differs). Left in the working tree, uncommitted and unmodified by us.
- `frontend` pins `vite@^5.x` on purpose — see `DECISIONS.md`; `npm install`
  fails if it drifts to `vite@8` while `@vitejs/plugin-react` stays on `4.x`.
- `database/requirements*.txt` are still the old app-flavoured list (fastapi, uvicorn,
  httpx); DB scripts only need sqlalchemy + a driver. Left unchanged to avoid
  breaking anything — trim later if desired.
- Backend still has no blood-bank directory / hospitals endpoint and no activity
  feed, and exposes `distance_km`/`eta_minutes` only inside a created request's
  `matches`. The frontend derives what it can from `/forecasting/*` and `/alerts`.
- Model artifact needs `lightgbm` to unpickle; without it `forecasting.py` logs a
  warning and uses its simulation fallback (also produces the seeded predictions).
- `backend/` pytest suite still not executed (deps only installed in a throwaway
  `.venv` for the smoke test); frontend has no test suite yet.
- `database/sql/03_seed_data.sql` hardcodes bcrypt hashes for the demo password
  `Demo2026!` (documented in `database/README.md`) and that standalone stack does
  not read `SEED_PASSWORD`. The value is therefore intentional; only the
  *example env files* were scrubbed. Regenerating those hashes is a DB-team call.
- **`POST /api/v1/eraktkosh/sync-now` has no authentication.** Unlike every other
  non-health endpoint it takes no `require_roles(...)` dependency, so anyone
  reaching the API can force an outbound scrape. It is bound to loopback and only
  proxied behind nginx, but it should still be admin-gated (or removed, since the
  background worker already syncs on a timer). Raised, not changed — upstream's
  route.
- **The new root `.gitignore` ignores `*.csv` globally** ("Scraped public data
  files (deliberately not committed)"), which silently covers
  `backend/datasets/karnataka/*.csv` �?" the reference data added earlier can no
  longer be staged without `-f`. Tracked CSVs are unaffected. Worth confirming
  that blanket rule is intended.
- **Switched Inventory, Find Supplies, and Overview off the seeded demo
  depletion/inventory data onto live eRaktKosh scraped data.**
  - Backend: added `GET /eraktkosh/supply` (aggregates all 8 group snapshots into
    per-bank supply; verified 98 Bengaluru banks).
  - Frontend: new public `eraktkoshSummary()` / `eraktkoshSupply()` api methods;
    `buildStockFromErakthosh()` / `buildBankSupplyFromErakthosh()` derive adapters
    (`StockItem.hours` is now `number | null` since scraped data has no burn-rate
    or expiry); `BloodBox` renders null-hours as units-based availability.
  - Verified: `/eraktkosh/summary` `last_updated_iso` advanced
    `23:51:28 �+' 00:13:10` via the automatic 10-min cycle; `/eraktkosh/supply`
    returns 98 banks; SPA 200; `tsc && vite build` clean.
- **Per-org inventory: blood banks see their own DB stock, not eRaktKosh.**
  - `Inventory.tsx` / `Overview.tsx` are now role-aware: `bloodbank_user` fetches
    `api.inventory()` (server-scoped to `affiliated_org_id`) + `AddStockForm`;
    `hospital_user` sees a "hospitals request, banks hold stock" message (no
    inventory table exists for hospitals); `admin`/`auditor` see live eRaktKosh.
  - Added 4 dedicated demo accounts with individual env-driven passwords
    (`DEMO_HOSPITAL_1/2_PASSWORD`, `DEMO_BANK_1/2_PASSWORD`), affiliated to 2
    hospitals + 2 blood banks; verified each blood bank logs in and sees only
    its own inventory (bank_1 ≠ bank_2). `SEED_PASSWORD` still required for seed.

## Open questions

<!-- Anything a future agent needs a human decision on. -->
