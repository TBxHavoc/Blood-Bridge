# Blood Bridge

> Privacy-focused AI coordination platform for emergency blood supply.
> IBM Z Datathon 2026 | Track: AI Secured: Innovation without Exposure

**⚠️ SIMULATED FOR DEMONSTRATION PURPOSES: all data in this project is synthetic.**

**Core value:** rapid, fair, secure blood-supply matching without exposing patient or donor identity.

---

## 1. The Problem

During emergencies that need a blood transfusion, hospitals face four challenges:
- **Speed bottleneck:** manual coordination between blood banks and hospitals takes 30 minutes to several hours. Staff phone multiple locations, check compatibility by hand, and negotiate transport.
- **Information privacy paradox:** finding compatible blood quickly means sharing blood type, location, urgency, and quantity, which is sensitive healthcare data. Donor privacy must also be protected.
- **Equity and fairness:** without a structured system, priority can depend on a hospital's influence, ability to pay, or whoever calls first. Government systems like eRaktKosh aim to prevent this, but coordination remains manual and opaque.
- **Inventory visibility gap:** blood banks cannot see each other's inventory, so a request can go unfilled in one city while compatible blood expires in a neighboring city 50 km away.

## 2. Our Solution

Blood Bridge is a secure AI coordination layer (not a replacement for government systems) that:
- Accepts **minimal-information requests**: blood type, quantity, clinician-provided urgency, hospital location, timestamp, and component type only. Patient identity never enters the matching system.
- Matches against **inventory metadata only** (available units, blood type, quantity, expiry, location), with no donor identity.
- Ranks matches **transparently** with rule-based scoring: (1) medical eligibility, (2) clinician-provided urgency, (3) availability and expiry risk, (4) distance and transport time, (5) request timestamp as the fairness tie-breaker. Money, hospital influence, and ability to pay are never factors.
- Prevents identity exposure with pseudonymous request IDs and role-based access.
- Generates **audit trails** so every matching decision can be explained and validated.
- **Alerts** stakeholders when a match is found or a shortage exists. Humans make the final transport and transfusion decisions.

## 3. Key Features (MVP)

- Hospital request submission and dashboard
- Blood-bank inventory dashboard
- Matching engine: eligibility filtering (blood group, quantity, expiry), priority scoring (urgency, distance, expiry, fairness), ranking with explanation, and shortage detection
- Ranked match results with human-readable explanations
- Authentication (JWT) and role-based access control
- Immutable audit logging
- Alerts and notifications
- Admin and auditor dashboards
- Pseudonymous request IDs; no patient identity stored
- Fallback demo mode with seeded data

## 4. How It Works

1. A hospital user submits a request (blood group, component, quantity, urgency, required-by time).
2. The backend authenticates the user and checks their role.
3. The matching engine filters eligible inventory, scores it, and ranks the results.
4. Results are stored with an explanation for each match.
5. Alerts are generated for the hospital and the matched blood banks.
6. Humans confirm and fulfil the request.
7. Every step is written to the audit log.

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) and [MATCHING_ALGORITHM.md](docs/MATCHING_ALGORITHM.md).

## 5. Privacy & Security

- **Pseudonymization:** request IDs such as `REQ_2026_10_06_001` carry no patient information.
- **Minimal data:** the matching engine sees only blood type, quantity, location, urgency, and timestamps.
- **RBAC with four roles:**

| Role | Can do | Cannot see |
|---|---|---|
| Hospital User | Submit requests, view own requests, matches, and alerts | Other hospitals' requests, inventory details, audit logs |
| Blood-Bank User | Manage own inventory, receive match alerts | Hospital details, urgency levels, other banks' inventory |
| Administrator | Manage users, configuration, system health | Patient data, donor data, operational requests and inventory |
| Auditor | View audit logs, verify fairness, generate compliance reports | Patient or donor identities, operational data |

- **Encryption in transit:** HTTPS/TLS 1.2+.
- **Encryption at rest:** passwords hashed with bcrypt; email and phone column encryption via PostgreSQL pgcrypto.
- **Audit logs:** immutable, covering every sensitive action.
- **API security:** CORS restrictions, rate limiting, input validation, versioned endpoints (`/api/v1/...`).

Details: [PRIVACY_SECURITY.md](docs/PRIVACY_SECURITY.md)

## 6. IBM Z Integration

| Level | Scope |
|---|---|
| 1 (core) | PostgreSQL for the MVP, with Db2 on IBM Z documented as the production design |
| 2 (if time permits) | Test Db2 instance on IBM LinuxONE; key tables migrated and queried by the matching engine |
| 3 (proof of concept) | Secure Execution design for the matching engine, with pseudocode and security benefits |

Details: [IBM_Z_INTEGRATION.md](docs/IBM_Z_INTEGRATION.md)

## 7. Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React.js with Vite |
| Styling | Tailwind CSS |
| Backend | Flask or FastAPI (Python) |
| Matching engine | Pure Python, rule-based (no TensorFlow/PyTorch) |
| Database | PostgreSQL with SQLAlchemy ORM (Db2 on IBM Z in production) |
| Authentication | JWT, bcrypt |
| Encryption | cryptography library, pgcrypto |
| API docs | OpenAPI / Swagger |
| Testing | pytest |
| Deployment | Docker and Docker Compose; local Docker or IBM Cloud Lite |
| Version control | Git and GitHub |

## 8. Getting Started

**Prerequisites:** Docker and Docker Compose, Git. For local development without Docker: Python 3 and Node.js.

```bash
# 1. Clone
git clone <repository-url>
cd blood-bridge

# 2. Run the full stack (database, backend, frontend)
docker compose -f deploy/docker-compose.yml up --build

# 3. Seed synthetic data
python datasets/seed_data.py
```

Full instructions: [SETUP.md](docs/SETUP.md)

## 9. Project Structure

```
blood-bridge/
├── README.md
├── LICENSE
├── backend/        # API, matching engine, models, middleware, tests
├── frontend/       # React + Vite app (pages, components, hooks)
├── datasets/       # Synthetic CSVs and seed_data.py
├── deploy/         # Dockerfiles, docker-compose.yml, IBM setup guides
├── docs/           # All project documentation
├── tools/          # Offline utilities (e.g. the eRaktKosh snapshot generator)
└── .github/        # CI and deploy workflows
```

## 10. Documentation Index

| Doc | Purpose |
|---|---|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design and data flow |
| [DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md) | Tables and fields |
| [DATA_SOURCES.md](docs/DATA_SOURCES.md) | Where data comes from, synthetic data disclosure |
| [API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md) | Endpoints with examples |
| [SETUP.md](docs/SETUP.md) | Dev environment setup |
| [MATCHING_ALGORITHM.md](docs/MATCHING_ALGORITHM.md) | Algorithm and pseudocode |
| [PRIVACY_SECURITY.md](docs/PRIVACY_SECURITY.md) | Security model |
| [IBM_Z_INTEGRATION.md](docs/IBM_Z_INTEGRATION.md) | IBM Z design |
| [TESTING.md](docs/TESTING.md) | Tests and results |
| [DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) | Demo walkthrough |
| [LIMITATIONS.md](docs/LIMITATIONS.md) | What we did not build |
| [ETHICAL_CONSIDERATIONS.md](docs/ETHICAL_CONSIDERATIONS.md) | Bias, fairness, ethics |
| [FUTURE_IMPROVEMENTS.md](docs/FUTURE_IMPROVEMENTS.md) | Roadmap |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | Docker, cloud, CI/CD |

## 11. Evaluation Targets

Measured results are recorded in [TESTING.md](docs/TESTING.md).

| Metric | Target | Baseline (manual) |
|---|---|---|
| Matching success rate | ≥ 85% | ~60% |
| Matching latency | < 2 seconds | 30-60 minutes |
| Average distance to matched bank | < 50 km | Higher (random calling) |
| Expired-unit avoidance | 99.5% | 95% |
| Shortage detection accuracy | 100% | Varies |
| Patient identity exposure | 0 patient identifiers in any table | n/a |
| Unauthorized access blocked | 100% | 0% |
| Audit log completeness | 100% | Inconsistent |
| Queue fairness (same urgency) | Earlier request matched within 1 min of later | No guarantee |
| Anti-bias score (affluence vs. match time) | Correlation ≤ 0.05 | Often positive |
| API response time (p99) | < 500 ms | n/a |

## 12. Limitations & Future Work

- MVP uses synthetic data, not real data
- Matching is a recommendation only; humans execute decisions
- Transport logistics are not modeled
- Rule-based matching, not a trained ML model
- **Future:** federated learning, advanced ML, and a live integration with the national blood bank system (eRaktKosh) via the sanctioned ABDM/UHI `BloodStock` API. Today's eRaktKosh support is an offline snapshot of public aggregate figures only, not a live feed (see [DATA_SOURCES.md](docs/DATA_SOURCES.md) §2.1 and §2.3).

See [LIMITATIONS.md](docs/LIMITATIONS.md) and [FUTURE_IMPROVEMENTS.md](docs/FUTURE_IMPROVEMENTS.md).

## 13. What Blood Bridge Is Not

- Not a diagnosis engine: urgency is supplied by clinicians
- Not autonomous clinical decision-making
- Not a patient or donor database
- Not a payment or billing system (it would bias matching toward wealthy hospitals)

## 14. Team

| Name | GitHub |
|---|---|
| Nikshep Badam | [TBxHavoc](https://github.com/TBxHavoc) |
| Preetham Reddy | [preethamr421-cloud](https://github.com/preethamr421-cloud) |
| Sujay Kathi | [Sujay-Kathi](https://github.com/Sujay-Kathi) |
| Samarth R Bharadwaj | [Samarth-17-18](https://github.com/Samarth-17-18) |
| Anish N | [Dr-Diesel-23](https://github.com/Dr-Diesel-23) |

**Repository:** [add link] | **Demo video:** [add link]

## 15. Acknowledgments

Healthcare IT practices (HL7 FHIR, HIPAA privacy principles, HITRUST), WHO blood safety guidelines, Red Cross inventory management, algorithmic fairness and explainability research, privacy-preserving techniques (pseudonymization, RBAC, audit logging), and IBM Z security features.

## License

See [LICENSE](LICENSE).
