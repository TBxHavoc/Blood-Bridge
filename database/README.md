# Blood Bridge — Database
### IBM Z Datathon 2026 · AI Secured Track (Innovation without Exposure)

Database layer for Blood Bridge: the ANSI SQL schema, dual-compatible SQLAlchemy
ORM models, verification scripts and design documentation. The FastAPI application
lives in [`../backend/`](../backend/README.md).

> IBM Z Datathon 2026 · AI Secured track · 24-hour MVP · **all data is synthetic**
> (`SIMULATED FOR DEMONSTRATION PURPOSES`).

---

## ⚡ Stack

- **PostgreSQL 16** (Docker) for local development; **Db2 on IBM LinuxONE** for the
  live demo.
- `DATABASE_URL` is the single switch between the two — no application code changes
  required (see `.env.example`).
- Python 3.11+ for the verification scripts.

---

## 🚀 Quickstart

### 1. Start PostgreSQL (+ pgAdmin) with the schema pre-loaded
```powershell
docker compose up -d
```
- **PostgreSQL 16**: Port `5432` (`bloodbridge` db, auto-initialized with schema, seed data, and views)
- **pgAdmin 4**: http://localhost:5050 (Login: `admin@bloodbridge.sim` / `Admin2026!`)

### 2. Or apply the SQL manually
```powershell
# Against a running PostgreSQL instance, in order:
psql -f sql/01_schema_postgresql.sql
psql -f sql/03_seed_data.sql
psql -f sql/04_queries_and_views.sql
```

### 3. Run the verification suite
```powershell
python -m pip install -r requirements.txt

# Verify schema tables, synthetic data counts, and Zero-Patient privacy compliance:
python scripts/verify_db.py

# Test transactional holds, row-level locking, and double-allocation prevention:
python scripts/test_hold_transaction.py

# Verify the cryptographic SHA-256 hash chain of the audit trail:
python scripts/audit_chain_verifier.py
```

---

## 📁 Layout

```
database/
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
├── docker-compose.yml              # Local PostgreSQL 16 + pgAdmin
├── pyproject.toml / requirements.txt
└── .env.example                    # Dual-target template (PostgreSQL <-> LinuxONE Db2)
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

## 🛡️ Privacy Invariants (Verified)

- **Zero Patient Identifiers**: No patient names, MRNs, Aadhaar, room numbers, or diagnoses (`FR-08`, `NFR-P1`).
- **Zero Donor Identifiers**: Inventory tables contain only blood group, component, units, and dates (`FR-21`, `NFR-P1`).
- **Pseudonymous Request IDs**: Cryptographically random request codes (`REQ_98A2F1`), never sequential (`NFR-P2`).
- **Staged Disclosure**: Hospital name and delivery dock hidden from blood banks until hold confirmation (`NFR-P7`).
- **Immutable Audit Logs**: Append-only enforcement via database trigger and SHA-256 hash chaining (`NFR-P5`, `FR-20`).
- **Universal Portability**: Zero vendor lock-in. 100% ANSI types (`VARCHAR(36)` UUIDs, standard `CHECK` constraints, text IPs) for immediate attachment to IBM LinuxONE.

---

## 🚀 IBM LinuxONE (Db2) Deployment

See [LINUXONE_MIGRATION_GUIDE.md](docs/LINUXONE_MIGRATION_GUIDE.md) for full instructions on attaching to the organizers' IBM LinuxONE instance and presenting IBM Secure Execution to the hackathon judges.
