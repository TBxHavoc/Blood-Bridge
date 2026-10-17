# Limitations

**Project:** Blood Bridge | IBM Z Datathon 2026 (AI Secured track)

> ⚠️ **SIMULATED FOR DEMONSTRATION PURPOSES.** This document states plainly what the MVP does not do.

---

## 1. Data

- **Synthetic data only.** No real patient, donor, hospital, or blood-bank data is used, and the system does not reflect live blood availability anywhere.
- **Results reflect the demo dataset.** Synthetic data cannot capture real demand patterns, so measured performance applies to the demo scale (15-25 blood banks, 8-12 hospitals, 100-150 inventory records).
- **No integration with real systems.** There is no connection to eRaktKosh or hospital systems; real integration would need permission and data-sharing agreements.
- **Distances are approximate.** Straight-line (Haversine) distances ignore roads and traffic, so ETAs are estimates.

## 2. Matching

- **Recommendation only.** Matches are suggestions; humans make the final transport and transfusion decisions.
- **Rule-based, not learned.** There is no trained ML model, demand forecasting, or learning from outcomes.
- **Urgency comes from clinicians.** Blood Bridge does not verify or diagnose; it trusts the urgency supplied. Urgency is read-only after submission, and attempted escalations are logged.
- **Single-record matching.** Eligibility requires enough stock in a record to cover the full quantity; splitting one request across several banks is not part of the MVP.
- **Transport logistics are not modeled.** Physical transport is arranged externally by the blood bank.
- **Fixed scoring weights.** Weights (30/25/20/15/10) are design choices adjustable by administrators, not tuned on real outcomes.

## 3. Security and Privacy

- **Not production-hardened.** The demo uses a self-signed certificate; production would need a CA-signed one.
- **Not implemented:** federated learning, differential privacy, homomorphic encryption, secure multi-party computation, and confidential computing.
- **Secure Execution is a design only.** It requires specialized hardware and is documented, not built (see [IBM_Z_INTEGRATION.md](IBM_Z_INTEGRATION.md)).
- **Real-world compliance is not claimed.** No formal certification or legal review has been done.

## 4. IBM Z

- The MVP runs on PostgreSQL. Db2 on IBM Z is the production design.
- Level 2 (a test Db2 instance on LinuxONE) depends on access and time, and is documented as future work if it is not completed.
- Performance has not been compared against a production IBM Z deployment.

## 5. Scale and Operations

- Built and tested for demo scale; load testing at 100+ concurrent requests, load balancing, database replication, and disaster recovery are outside the MVP.
- Kubernetes deployment is not included.
- Notifications are in-app alerts; email notifications are optional.

## 6. Scope Exclusions (Deliberate)

- No medical diagnosis engine
- No autonomous clinical decision-making
- No public patient database and no donor identity database
- No payment or billing system (it could bias matching toward wealthy hospitals)
- No complex deep-learning models
- No public API without authentication
- No bypassing the matching process for particular hospitals; all requests compete fairly

## 7. User Interface

- Mobile app, real-time GPS tracking, and multi-language support (Hindi and regional languages) are not included in the MVP.

See [FUTURE_IMPROVEMENTS.md](FUTURE_IMPROVEMENTS.md) for how these could be addressed.
