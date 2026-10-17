# Future Improvements

**Project:** Blood Bridge | IBM Z Datathon 2026 (AI Secured track)

This roadmap follows the project plan's priority tiers. Items marked "Should have" were targeted for the hackathon if time allowed; the rest are beyond the 24-hour MVP.

---

## 1. Should-Have Items If Not Finished During the Hackathon

- Comprehensive API documentation (OpenAPI/Swagger)
- Admin dashboard: view the queue and configure matching weights
- Auditor dashboard: audit logs and fairness reports
- Alerts and notifications (when a match is found, when a shortage is detected)
- Request queue visualization to show fairness and transparency
- Demo fallback mode with pre-recorded or seeded matches
- Unit tests with at least 50% coverage for the matching engine and API
- Performance optimization (database indexes and query tuning)
- Responsive, mobile-friendly frontend
- Data masking in audit logs
- Test Db2 instance on IBM LinuxONE (if access is available)

## 2. IBM Z Roadmap

| Step | Description |
|---|---|
| Db2 on IBM Z | Move the core database for high availability, disaster recovery, transparent field-level encryption, and built-in auditing |
| Secure Execution | Run the matching engine in a hardware-protected area so even administrators cannot see inputs or outputs, with cryptographic proof that matching was fair |
| Hybrid cloud | Use IBM Z as the central hub connecting hospitals and blood banks without exposing data to the public cloud or to each other |
| OpenShift on IBM Z | Container orchestration for production |

See [IBM_Z_INTEGRATION.md](IBM_Z_INTEGRATION.md).

## 3. Privacy and Security

| Technique | Benefit |
|---|---|
| Federated learning | Hospitals and blood banks train local models without sharing raw data |
| Confidential computing (Secure Execution) | Protect data while it is processed |
| Differential privacy | Safe sharing of aggregate statistics |
| Homomorphic encryption | Compute on encrypted data (needs performance work) |
| Secure multi-party computation | Cross-organization matching without a trusted party |
| Multi-factor authentication | Stronger sign-in (SMS or authenticator app) |

## 4. AI and Matching

- Advanced ML for predictive matching and demand forecasting
- Predicted time-to-match (for example, a simple linear regression on historical times)
- Predicted shortages when many urgent requests are pending and inventory is low
- Learning from match outcomes to improve scoring weights, with fairness checks so historical bias is not learned
- Matching across several blood banks for large requests

**Not to build:** machine learning that predicts urgency or diagnoses patient condition, which violates scope. Urgency stays with clinicians.

## 5. Integration

- Integration with the real eRaktKosh API, if permission is obtained
- Real distances and travel times via a mapping API instead of straight-line estimates
- Real-time GPS tracking for blood transport
- Email notifications

## 6. Product

- Mobile app (iOS and Android)
- Multi-language support (Hindi and regional languages)

## 7. Scale and Operations

- Production-grade deployment: load balancing, database replication, disaster recovery
- Load testing with 100+ concurrent requests
- Kubernetes deployment (manifests are optional in `deploy/kubernetes/`)
- Partnership with eRaktKosh for national-scale deployment

## 8. Governance

- Pilot with real stakeholders (clinicians, blood banks, regulators) before real use
- Data-sharing agreements and a formal privacy and compliance review
- Bias detection and explainability (XAI) tooling beyond the current fairness report

## 9. Explicitly Not Planned

- A payment or billing module (it would bias matching toward wealthy hospitals)
- A medical diagnosis engine
- Autonomous clinical decision-making
- A patient or donor identity database
