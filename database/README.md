# Blood Bridge — Backend & Database
### IBM Z Datathon 2026 · AI Secured Track (Innovation without Exposure)

Privacy-first AI coordination layer that matches emergency blood requests from
hospitals to blood-bank inventory. It never receives patient or donor identity.
Matching is rule-based, explainable and fully audited.

> IBM Z Datathon 2026 · AI Secured track · 24-hour MVP · **all data is synthetic**
> (`SIMULATED FOR DEMONSTRATION PURPOSES`).

---

## ⚡ Stack & Architecture

- **FastAPI** + **SQLAlchemy 2.0** + **PostgreSQL 16** (Docker), matching engine as a
  plain in-process Python module (no queues/workers).
- `DATABASE_URL` is the single switch between PostgreSQL (local fallback) and Db2 on IBM LinuxONE (live demo) — no application code changes required (see `.env.example`).
- Python 3.11+.

---

## 🚀 Quickstart (Local Development)

### 1. Start the Full Stack (PostgreSQL + API + pgAdmin)
```powershell
docker compose up -d
```
- **PostgreSQL 16**: Port `5432` (`bloodbridge` db, auto-initialized with schema, seed data, and views)
- **FastAPI API**: http://localhost:8000 (Swagger docs: http://localhost:8000/docs)
- **pgAdmin 4**: http://localhost:5050 (Login: `admin@bloodbridge.sim` / `Admin2026!`)

### 2. Or Run API Locally with Python
```powershell
# Start database only
docker compose up -d db

# Create venv + install dependencies
uv venv --python 3.11 .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt

# Configure environment
Copy-Item .env.example .env

# Run FastAPI backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

---

## 🔐 Seeded Demo Accounts (for Presentation)

All users share the demo password: **`Demo2026!`**

| Username | Role | Organization Affiliation | Purpose in Demo |
| :--- | :--- | :--- | :--- |
| `dr_sharma_apex` | `hospital_user` | Apex Trauma Hospital (`HOSP_001`) | Submit emergency requests, view ranked matches |
| `dr_patel_citygen` | `hospital_user` | City General Hospital (`HOSP_002`) | Competing request fairness scenario |
| `mgr_redcross` | `bloodbank_user` | Red Cross Blood Center (`BB_001`) | Manage stock, view match alerts & anonymous demand |
| `mgr_rotary` | `bloodbank_user` | Rotary LifeBank (`BB_002`) | Review active reservations & fulfillment |
| `auditor_compliance` | `auditor` | System-wide Compliance | Inspect immutable audit logs & fairness reports |
| `admin_sys` | `admin` | Platform Operator | System configuration, health, weights tuning |

---

## 📁 Repository Layout

```
├── app/
│   ├── main.py                     # FastAPI app factory
│   ├── config.py                   # Settings (env-driven, switchable DATABASE_URL)
│   ├── database.py                 # Engine, session, declarative Base
│   ├── core/                       # Response envelope, errors, security, audit, masking
│   ├── api/                        # Routers (system, auth, requests, inventory, matching)
├── sql/
│   ├── 01_schema_postgresql.sql    # Complete ANSI PostgreSQL DDL with indexes & triggers
│   ├── 02_schema_ibm_db2.sql       # IBM LinuxONE Db2 DDL (100% dialect-adapted)
│   ├── 03_seed_data.sql            # Synthetic demo dataset (10 hospitals, 16 banks, 120+ units)
│   └── 04_queries_and_views.sql    # Views for expiry alerts, anonymous demand, & fairness queue
├── models/
│   ├── __init__.py                 # Models package export
│   └── db_models.py                # Dual-compatible SQLAlchemy 2.0 ORM models
├── scripts/
│   ├── verify_db.py                # Schema validation & Zero-Patient privacy compliance checker
│   ├── test_hold_transaction.py    # Row locking (SELECT FOR UPDATE) concurrency test
│   └── audit_chain_verifier.py     # Cryptographic SHA-256 audit log tamper-detection
├── docs/
│   ├── DATABASE_DESIGN.md          # Full Data Dictionary, ERD, and State Machine specs
│   └── LINUXONE_MIGRATION_GUIDE.md # Instructions for attaching to IBM LinuxONE & Db2
├── tests/                          # Unit + integration tests
├── docker-compose.yml              # Local PostgreSQL 16 + FastAPI + pgAdmin
├── pyproject.toml / requirements.txt
└── .env.example                    # Dual-target template (PostgreSQL <-> LinuxONE Db2)
```

---

## 🛡️ Privacy Invariants (Verified)

- **Zero Patient Identifiers**: No patient names, MRNs, Aadhaar, room numbers, or diagnoses (`FR-08`, `NFR-P1`).
- **Zero Donor Identifiers**: Inventory tables contain only blood group, component, units, and dates (`FR-21`, `NFR-P1`).
- **Pseudonymous Request IDs**: Cryptographically random request codes (`REQ_98A2F1`), never sequential (`NFR-P2`).
- **Staged Disclosure**: Hospital name and delivery dock hidden from blood banks until hold confirmation (`NFR-P7`).
- **Immutable Audit Logs**: Append-only enforcement via database trigger and SHA-256 hash chaining (`NFR-P5`, `FR-20`).
- **Universal Portability**: Zero vendor lock-in. 100% ANSI types (`VARCHAR(36)` UUIDs, standard `CHECK` constraints, text IPs) for immediate attachment to IBM LinuxONE.

---

## 🧪 Database & Compliance Tests

```bash
# 1. Verify schema tables, synthetic data counts, and Zero-Patient privacy compliance:
python scripts/verify_db.py

# 2. Test transactional holds, row-level locking, and double-allocation prevention:
python scripts/test_hold_transaction.py

# 3. Verify cryptographic SHA-256 hash chain of the audit trail:
python scripts/audit_chain_verifier.py
```

---

## 🚀 IBM LinuxONE (Db2) Deployment

See [LINUXONE_MIGRATION_GUIDE.md](docs/LINUXONE_MIGRATION_GUIDE.md) for full instructions on attaching to the organizers' IBM LinuxONE instance and presenting IBM Secure Execution to the hackathon judges.
