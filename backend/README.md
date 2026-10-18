# Blood Bridge — Backend

Privacy-first AI coordination layer that matches emergency blood requests from
hospitals to blood-bank inventory. It never receives patient or donor identity.
Matching is rule-based, explainable and fully audited.

> IBM Z Datathon 2026 · AI Secured track · 24-hour MVP · **all data is synthetic**
> (`SIMULATED FOR DEMONSTRATION PURPOSES`).

## Stack

- **FastAPI** + **SQLAlchemy 2.0** + **PostgreSQL** (Docker), matching engine as a
  plain in-process Python module (no queues/workers).
- `DATABASE_URL` is the single switch between PostgreSQL and Db2 on IBM Z — no code
  changes required (see `.env.example`).
- Python 3.11.

## Quickstart (local)

```powershell
# 1. Start PostgreSQL (from the repo root, not backend/)
docker compose up -d db

# 2. Create venv + install deps
uv venv --python 3.11 .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt

# 3. Configure
Copy-Item .env.example .env

# 4. Run the API
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

- API docs (Swagger): http://localhost:8000/docs
- Health: http://localhost:8000/api/v1/health

To run the whole stack (PostgreSQL + API + frontend) containerised, use the
compose file at the repo root: `docker compose up -d --build` — see the
[top-level README](../README.md).

## Layout

The monorepo has two top-level folders: `backend/` (this FastAPI application and
the ML pipeline) and `database/` (SQL schema, ORM models and documentation). Run
all commands from inside `backend/`.

```
backend/
  app/               FastAPI application
    main.py          App factory
    config.py        Settings (env-driven, incl. DATABASE_URL switch)
    database.py      Engine, session, declarative Base
    core/            Response envelope, errors, security, audit, masking
    api/             Routers (system, auth, requests, inventory, matching, ...)
    matching/        Matching engine: eligibility, priority, scoring, shortage
    services/        Matching, reservations, forecasting (ML) services
    seed/            Synthetic dataset generator + loader
  datasets/          Synthetic CSV snapshots (source of truth)
  models/            depletion_model.pkl (trained ML bundle)
  notebooks/         EDA + model-training notebook
  docs/              ML_DEPLETION_MODEL.md
  scripts/           ML pipeline + operations
                     train_model.py, predict_depletion.py,
                     evaluate_model_accuracy.py, test_trained_model.py, metrics.py,
                     fetch_karnataka_hospitals.py
  tests/             Unit + integration tests
  Dockerfile         API image (also built by the root docker-compose.yml)
  requirements*.txt  Dependencies
  pyproject.toml     Ruff + pytest + coverage config
```

### ML pipeline

```powershell
# Train (writes models/depletion_model.pkl from datasets/)
python scripts/train_model.py

# Predict depletion / stockout tiers from the synthetic datasets
python scripts/predict_depletion.py

# Evaluate model accuracy and clinical-safety constraints
python scripts/evaluate_model_accuracy.py

# End-to-end model + service-layer integration test
python scripts/test_trained_model.py
```

### Reference data

```powershell
# Refresh the Karnataka district-wise hospital registries from data.gov.in
# (writes datasets/karnataka/*.csv). Needs DATAGOVIN_API_KEY -- see .env.example.
python scripts/fetch_karnataka_hospitals.py
```

## Privacy invariants

No patient or donor identifiers in any table, log or payload. Pseudonymous request
codes (`REQ_` + random suffix). Server-side role/row filtering. Append-only audit
log. Never scored on money, hospital size or influence.

## Phase status

P0 Foundations · P1 Data model · P2 Seed · P3 Auth/RBAC · P4 Core APIs ·
P5 Matching · P6 Holds · P7 Alerts/Audit · P8 Hardening · P9 IBM Z/Db2

See `.opencode/context/PROJECT-STATE.md` for the live state.
