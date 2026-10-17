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
- `frontend/` — static HTML prototypes (`demo.html`, `demo overview.html`,
  `hospital-home.html`, `design.md`). Merged from `origin/frontend`.

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

**In progress:**
-

**Known gaps / deliberately deferred:**
- `database/requirements*.txt` are still the old app-flavoured list (fastapi, uvicorn,
  httpx); DB scripts only need sqlalchemy + a driver. Left unchanged to avoid
  breaking anything — trim later if desired.
- Dependencies not installed in this environment, so `backend/` pytest suite was not
  executed. Verified only `py_compile` + stdlib script run + path resolution.

## Open questions

<!-- Anything a future agent needs a human decision on. -->
