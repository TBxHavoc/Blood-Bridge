# Blood Bridge
### IBM Z Datathon 2026 · AI Secured Track (Innovation without Exposure)

Privacy-first AI coordination layer that matches emergency blood requests from
hospitals to blood-bank inventory. It never receives patient or donor identity.
Matching is rule-based, explainable and fully audited.

> IBM Z Datathon 2026 · AI Secured track · 24-hour MVP · **all data is synthetic**
> (`SIMULATED FOR DEMONSTRATION PURPOSES`).

---

## Repository layout

```
.
├── docker-compose.yml   Full stack: PostgreSQL + API + web frontend
├── backend/     FastAPI application + ML pipeline (see backend/README.md)
│   ├── app/         Application package (routers, services, matching, seed)
│   ├── datasets/    Synthetic CSV snapshots
│   ├── models/      Trained ML model bundle (depletion_model.pkl)
│   ├── notebooks/   EDA + model-training notebook
│   ├── docs/        ML_DEPLETION_MODEL.md
│   ├── scripts/     train / predict / evaluate / metrics
│   └── tests/       Unit + integration tests
└── database/    SQL schema, ORM models and design docs (see database/README.md)
    ├── sql/         PostgreSQL + Db2 DDL, seed data, views
    ├── models/      Dual-compatible SQLAlchemy 2.0 ORM models
    ├── scripts/     Schema / privacy / audit verification
    └── docs/        Data dictionary, ERD, LinuxONE migration guide
```

`backend/` is the single application. `database/` holds only database assets —
the SQL schema, ORM models, verification scripts and documentation.

---

## Quickstart

The whole stack — PostgreSQL, the API and the web frontend — comes up from the
one `docker-compose.yml` at the repo root:

```powershell
Copy-Item .env.example .env      # then fill in the blanks
docker compose up -d --build
docker compose run --rm seed     # optional: load the synthetic demo dataset
```

- Web app: http://localhost:8080
- API docs (Swagger): http://localhost:8001/docs
- Health: http://localhost:8001/api/v1/health

Ports and credentials all come from `.env` (`WEB_PORT`, `API_PORT`, `DB_PORT`,
`ADMIN_*`, `SEED_PASSWORD`). The web container serves the SPA and proxies `/api`
to the API service, so the browser only ever talks to a single origin.

The seed job resets every table before loading the dataset and then re-creates
the bootstrap admin, so it is safe to run in either order and safe to re-run.
Log in as `ADMIN_USERNAME` / `ADMIN_PASSWORD`; the synthetic demo accounts
(`hospital_h_001`, `bank_bb_001`, ...) all share `SEED_PASSWORD`.

The same file runs on a Linux / IBM LinuxONE host — only `.env` changes — and
`DATABASE_URL` is the single switch between PostgreSQL and Db2 on IBM Z, with no
code changes and no rebuild.

### Running the pieces locally instead

```powershell
# 1. Start PostgreSQL only
docker compose up -d db

# 2. Run the API from source
cd backend
uv venv --python 3.11 .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

When the API runs from source it creates the schema and the bootstrap admin at
startup; `database/sql/*.sql` is only used by the standalone stack in
`database/` and by the Db2 migration path.

---

See [`backend/README.md`](backend/README.md) and [`database/README.md`](database/README.md)
for details.
