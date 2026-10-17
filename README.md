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

```powershell
# 1. Start PostgreSQL (auto-loads schema + synthetic seed data)
cd database
docker compose up -d

# 2. Run the API locally
cd ..\backend
uv venv --python 3.11 .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

- API docs (Swagger): http://localhost:8000/docs
- Health: http://localhost:8000/api/v1/health

`DATABASE_URL` is the single switch between PostgreSQL and Db2 on IBM LinuxONE —
no code changes required.

---

See [`backend/README.md`](backend/README.md) and [`database/README.md`](database/README.md)
for details.
