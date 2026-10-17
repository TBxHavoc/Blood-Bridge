# Ethical Considerations

**Project:** Blood Bridge | IBM Z Datathon 2026 (AI Secured track)

> ⚠️ **SIMULATED FOR DEMONSTRATION PURPOSES.** All data is synthetic.

Blood allocation is a life-or-death domain, so ethics is a design requirement rather than an add-on. This document covers bias and fairness, privacy ethics, transparency, accountability, and honesty.

---

## 1. Fairness

**The risk:** without a structured system, priority can depend on a hospital's influence, ability to pay, or whoever calls first.

**Our safeguards**
- **Only medical and logistical factors affect priority:** clinician-supplied urgency, blood compatibility, availability and expiry risk, distance, and request time. Money, hospital size, influence, and ability to pay are never inputs.
- **No payment module.** Introducing payment could bias matching toward wealthy hospitals, so it is explicitly excluded.
- **Timestamp tie-breaking.** For equal urgency and blood type, the earlier request is served first; if timestamps are identical, the lower request ID wins. The reasoning is shown in the result.
- **No special lanes.** Urgent requests are never hardcoded to bypass matching; all requests compete under the same rules.
- **Measured fairness.** The anti-bias target is a Pearson correlation of 0.05 or less between hospital affluence and match time, and the queue-fairness target is that earlier requests are matched within 1 minute of later ones with the same urgency (see [TESTING.md](TESTING.md)).
- **Auditor access.** `GET /audit/matching-fairness` reports average match time by urgency, the correlation with hospital size, and the count of requests prioritized by money or influence (expected: 0).

## 2. Why Rule-Based Instead of a Learned Model

A model trained on historical data could learn existing bias, such as favoring wealthy or well-connected hospitals. A transparent rule-based score avoids this and can be inspected by anyone. It also requires no historical outcome data, which does not exist for this project.

## 3. Human Responsibility

- **Recommendations, not decisions.** Humans make the final transport and transfusion decisions.
- **No diagnosis.** Blood Bridge does not judge patient condition. Urgency is supplied by clinicians, and a machine-learning urgency predictor is explicitly out of scope.
- **Manipulation resistance.** Urgency is read-only after submission; any escalation attempt is logged for the auditor.
- **Honesty about shortages.** When no compatible blood exists, the system says so and recommends external mobilization instead of forcing a poor match.

## 4. Privacy Ethics

- **Patients:** identity never enters the system. Requests carry a pseudonymous ID, and the hospital maps it back to the patient locally. Even a breach would expose only blood types, locations, and urgency levels.
- **Donors:** no donor name, contact, or health data is stored; blood banks share inventory metadata only, so donors are protected.
- **Data minimization:** the matching engine sees only blood type, quantity, location, urgency, and timestamps.
- **Separation of duties:** administrators manage users but cannot see patient data, donor data, or operational requests and inventory, which prevents them from favoring particular organizations. Auditors can verify fairness without seeing identities.
- **Hospitals and banks cannot spy on each other:** each sees only its own requests or inventory.

See [PRIVACY_SECURITY.md](PRIVACY_SECURITY.md).

## 5. Transparency and Accountability

- **Explainable matches:** every ranked match includes a human-readable explanation of why it was recommended.
- **Immutable audit trail:** every sensitive action is logged, and logs cannot be edited or deleted.
- **Open scoring:** weights and the formula are documented in [MATCHING_ALGORITHM.md](MATCHING_ALGORITHM.md) and are configurable by administrators.

## 6. Honesty About the Data and the System

- All data is synthetic and clearly labeled "SIMULATED FOR DEMONSTRATION PURPOSES"; it is never presented as real.
- Reported metrics are measured on the demo dataset only, and the limits of the MVP are stated in [LIMITATIONS.md](LIMITATIONS.md).
- IBM Z capabilities that are designed but not built are described as design.
- Code review checks that no real personal information appears in any dataset.

## 7. Equity and Access Considerations

- **Rare blood groups:** shortages of groups such as AB- are reported openly, so the system does not hide the people hardest to match.
- **Geography:** distance affects priority because time matters in emergencies, which can disadvantage remote hospitals; the shortage and partial-match alerts make this visible instead of silent.
- **Mobile-friendly design and accessibility (WCAG 2.1 AA)** support users in emergency and low-resource settings.

## 8. Scope Boundaries (What We Will Not Build)

Medical diagnosis, autonomous clinical decisions, a patient or donor identity database, a payment system, and an unauthenticated public API.

## 9. Future Ethical Work

- Bias detection and explainability (XAI) tooling beyond the MVP's fairness report
- Privacy-preserving techniques such as federated learning and differential privacy
- Review with clinicians, blood-bank staff, and regulators before any real deployment
