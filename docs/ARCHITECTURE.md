# Architecture

**Project:** Blood Bridge | IBM Z Datathon 2026 (AI Secured track)

> ⚠️ **SIMULATED FOR DEMONSTRATION PURPOSES.** All data is synthetic.

---

## 1. Overview

Blood Bridge is a secure AI coordination layer between hospitals and blood banks. It is **not** a replacement for government systems such as eRaktKosh. It accepts minimal-information blood requests, matches them against blood-bank inventory metadata, ranks the matches transparently, and logs every decision. Humans make the final transfusion and transport decisions.

**Design goals**
- **Speed:** automated matching in seconds instead of 30 minutes to hours of manual coordination
- **Privacy:** patient and donor identity never enter the system
- **Fairness:** money, hospital influence, and ability to pay are never factors
- **Transparency:** every match carries a human-readable explanation and an audit trail
- **Simplicity:** an MVP built in 24 hours, with rule-based AI instead of a black-box model

---

## 2. System Architecture

```
┌───────────────────────────────────────┐
│    Frontend (React + Tailwind)        │
│ - Hospital request form               │
│ - Dashboards (matches, inventory)     │
│ - Alerts / notifications              │
└─────────────┬─────────────────────────┘
              │ HTTPS / REST API
┌─────────────▼──────────────────────────────────┐
│ Backend (FastAPI or Flask + SQLAlchemy)        │
│ - Authentication (JWT)                         │
│ - Request validation                           │
│ - API endpoints (/requests, /match, ...)       │
│ - Access-control middleware (RBAC)             │
│ - Audit logging                                │
└─────────────┬──────────────────────────────────┘
              │
    ┌─────────┴──────────┐
    │                    │
┌───▼──────────────────┐ │
│ Matching Engine      │ │
│ (Python class)       │ │
│ - Eligibility filter │ │
│ - Scoring            │ │
│ - Ranking            │ │
│ - Shortage detection │ │
└──────────────────────┘ │
                  ┌──────▼──────────┐
                  │ PostgreSQL      │
                  │ (Docker)        │
                  │ users, hospitals│
                  │ blood_banks,    │
                  │ inventory,      │
                  │ requests,       │
                  │ matches, alerts,│
                  │ audit_logs      │
                  └─────────────────┘
```

---

## 3. Components

### 3.1 Frontend
- React.js single-page app built with Vite, styled with Tailwind CSS
- Talks to the backend only through the versioned REST API (`/api/v1/...`) over HTTPS
- Role-based screens: Login, Hospital Dashboard, Request Details and Matching Results, Blood-Bank Dashboard, Admin Dashboard, Audit and Compliance
- Hospital and blood-bank names are shown as codes (`Hospital_001`, `BB_001`) and no patient information appears anywhere
- Design notes: professional blue/green palette, WCAG 2.1 AA accessibility, mobile-responsive layout (important in emergencies), optional dark mode

### 3.2 Backend API
- FastAPI or Flask with SQLAlchemy
- **JWT authentication** and **role-based authorization middleware** on every endpoint
- Input validation (for example, blood group must be one of the 8 allowed values, urgency 1-5)
- Generates the pseudonymous `request_id`
- Writes an audit log entry for every sensitive action
- Security measures: CORS restrictions, rate limiting, versioned endpoints, standard response format

### 3.3 Matching Engine
- Pure Python class (`BloodMatchingEngine`), with no heavy ML libraries
- Four phases: eligibility filtering, priority scoring, ranking with explanation, and shortage detection
- Scoring weights are configurable through `system_config`
- Full detail in [MATCHING_ALGORITHM.md](MATCHING_ALGORITHM.md)

### 3.4 Database
- PostgreSQL in Docker for the MVP; Db2 on IBM Z is the production design
- 10 tables: users, blood_banks, hospitals, blood_inventory, blood_requests, matching_results, alerts, audit_logs, location_distances, system_config
- Full detail in [DATA_DICTIONARY.md](DATA_DICTIONARY.md)

### 3.5 Security Layer
- RBAC with four roles, authentication, data masking and tokenization
- HTTPS/TLS 1.2+ in transit; bcrypt-hashed passwords and column-level encryption (pgcrypto) for email and phone at rest
- Immutable audit logs
- Optional in production: IBM Z Secure Execution
- Full detail in [PRIVACY_SECURITY.md](PRIVACY_SECURITY.md)

---

## 4. End-to-End Flow: Request to Match

1. **Hospital user submits a request.** The clinician fills in blood group, component, quantity, urgency (1-5), and an optional required-by time. The frontend sends `POST /api/v1/requests` with the JWT.
2. **Backend authenticates and validates.** Middleware verifies the token, confirms the user is a `hospital_user` affiliated with the submitted `hospital_id`, validates the input, generates a pseudonymous `request_id` (e.g. `REQ_2026_10_06_001`), and inserts the request with status `PENDING`.
3. **Audit logging.** A `CREATE_REQUEST` entry is written with the user, resource, new values, and IP address.
4. **Matching engine runs** (automatically or on demand):
   - Query inventory that is available, unexpired, and in a compatible blood group
   - **Phase 1:** eligibility filter
   - **Phase 2:** priority scoring
   - **Phase 3:** ranking with explanations
   - **Phase 4:** shortage detection
5. **Results stored.** One `matching_results` row per ranked unit; request status becomes `MATCHED` if a best match exists; match generation is logged.
6. **Alerts generated.** The hospital user gets "Match found" with distance and ETA, and the blood-bank user is told their unit was matched. If no compatible blood exists, a shortage alert is created.
7. **Hospital user receives the alert** (polling or WebSocket) and opens the ranked results.
8. **Hospital confirms and the blood bank fulfils.** On "Confirm Match for Rank 1": the request becomes `FULFILLED`, inventory is reserved, and the other ranked options are deactivated. The blood bank arranges physical transport. Blood Bridge does not handle logistics.
9. **Audit trail.** Every step (`CREATE_REQUEST`, `MATCH_GENERATED`, status update) is logged so an auditor can verify fairness and privacy.

---

## 5. Data Isolation for Privacy

```
┌─────────────────────────────────────────────┐
│ Hospital system (external)                  │
│ - Patient ID, name, diagnosis, local EMR    │
└──────────────────────┬──────────────────────┘
                       │ Hospital's backend strips all identifying info:
                       │ { blood_group: "O+", quantity: 4, urgency: 4 }
                       ▼
┌─────────────────────────────────────────────┐
│ Blood Bridge (this system)                  │
│ - request_id: REQ_2026_10_06_001            │
│ - hospital_id: H_001 (de-identified)        │
│ - blood group, quantity, urgency            │
│ - NO patient name, ID, diagnosis, history   │
└──────────────────────┬──────────────────────┘
                       │ Match found: INV_001 from BB_001
                       ▼
┌─────────────────────────────────────────────┐
│ Hospital's local fulfilment system          │
│ - Maps request_id back to the patient       │
│ - Clinician verifies the unit               │
│ - Executes the transfusion locally          │
└─────────────────────────────────────────────┘
```

Even if Blood Bridge is breached, an attacker sees only blood types, locations, and urgency levels, with no names or identifiers.

The matching engine itself only ever sees: blood type, quantity, location, urgency level, and timestamps.

---

## 6. API Overview

All endpoints are under `/api/v1`. Details and examples are in [API_DOCUMENTATION.md](API_DOCUMENTATION.md).

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` |
| Requests | `POST /requests`, `GET /requests`, `GET /requests/:request_id`, `PATCH /requests/:request_id` |
| Matching | `POST /match`, `GET /match/queue` |
| Inventory | `GET /inventory`, `POST /inventory`, `PATCH /inventory/:inventory_id`, `GET /inventory/demand` |
| Alerts | `GET /alerts`, `PATCH /alerts/:alert_id` |
| Audit | `GET /audit/logs`, `GET /audit/matching-fairness` |
| System | `GET /health` (public), `GET /config` |

---

## 7. Roles and Access

| Role | Can do | Cannot see |
|---|---|---|
| Hospital User | Submit requests; view own requests, matches, alerts and explanations | Other hospitals' requests, inventory details, donor information, audit logs |
| Blood-Bank User | View and update own inventory; receive match alerts; view anonymized demand trends | Hospital details, patient information, urgency levels, other banks' inventory |
| Administrator | Manage users and roles; system configuration; monitor system health; view pseudonymized audit logs | Patient data, donor data, operational requests and inventory |
| Auditor | View audit logs; verify matching followed the rules; generate compliance reports | Patient or donor identities, operational requests and inventory |

---

## 8. Deployment Architecture and IBM Z

### 8.1 MVP deployment
- Docker and Docker Compose for the full stack, run locally or on IBM Cloud Lite
- PostgreSQL as the database
- Kubernetes is deliberately avoided as too complex for 24 hours

### 8.2 Production design with IBM Z

```
Frontend (Web/Mobile)          [IBM Cloud or local Docker]
        │ HTTPS/TLS
Backend API layer              [IBM Cloud, local Docker, or IBM Z Linux]
        │ Encrypted connection
   ┌────┴─────────────────────────┐
Matching Engine           Audit Log Service
(scoring, conflict        (immutable trail)
 resolution)              [PostgreSQL or Db2 on IBM Z]
        │
Core Database                  [Db2 on IBM Z or PostgreSQL]
(blood banks, hospitals, inventory, requests,
 matching results, audit logs, users, distances)

Security layer: TLS, encryption at rest, access control, audit trails,
RBAC, authentication, data masking, column-level encryption,
(optional in production) IBM Z Secure Execution
```

| IBM Z touchpoint | Value |
|---|---|
| **Db2 on IBM Z** (database tier) | High availability and disaster recovery, transparent field-level encryption, built-in audit trails, high transaction throughput |
| **Secure Execution** (security tier) | Matching engine runs in a hardware-protected area so even system administrators cannot see inputs or outputs; supports verifiable fairness |
| **Hybrid cloud** (connectivity tier) | IBM Z as the central hub for matching, audit logs, and security controls, connecting hospitals and blood banks without exposing data to the public cloud or to each other |

### 8.3 What is built vs designed
| Level | Scope |
|---|---|
| 1 (core) | PostgreSQL for the MVP; Db2 on IBM Z documented as the production design |
| 2 (if time permits) | Test Db2 instance on IBM LinuxONE; key tables migrated and queried by the matching engine |
| 3 (proof of concept) | Secure Execution design for the matching engine with pseudocode |

See [IBM_Z_INTEGRATION.md](IBM_Z_INTEGRATION.md).

---

## 9. Privacy-Preserving Techniques

**Implemented in the MVP**
1. Pseudonymization (request IDs, hospital and bank codes)
2. Role-based access control with per-table and per-row filtering
3. Encryption at rest (hashed passwords, encrypted PII fields)
4. Encryption in transit (HTTPS/TLS)
5. Immutable audit logs
6. Data masking in logs and UI
7. Authentication and authorization (username/password with session tokens)

**Designed but not implemented (future work)**
1. Federated learning
2. Confidential computing (IBM Secure Execution)
3. Differential privacy for aggregate statistics
4. Homomorphic encryption
5. Secure multi-party computation

---

## 10. Out of Scope

- Medical diagnosis: urgency is supplied by clinicians
- Autonomous clinical decision-making: matches are recommendations only
- A patient or donor database
- Payment or billing (it could bias matching toward wealthy hospitals)
- Transport logistics, which are handled externally
- Complex deep-learning models
- A public API without authentication
