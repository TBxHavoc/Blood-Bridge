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

## Open questions

<!-- Anything a future agent needs a human decision on. -->
