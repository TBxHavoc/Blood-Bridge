# Demo Script

**Project:** Blood Bridge | IBM Z Datathon 2026 (AI Secured track)
**Length:** 5-10 minutes

> ⚠️ **SIMULATED FOR DEMONSTRATION PURPOSES.** Say this at the start: all data is synthetic.

---

## Storyline

A hospital in Mumbai faces a blood shortage while several hospitals request blood at the same time. Blood Bridge prioritizes fairly and quickly, and protects privacy throughout.

**Flow:** problem → solution → transparent matching → privacy controls → audit → IBM Z → metrics → shortage handling.

---

## Before You Start (Pre-Demo Checklist)

- [ ] Seeded demo data loaded (about 20 blood banks, 10 hospitals)
- [ ] One demo account ready per role: hospital user, blood-bank user, admin, auditor
- [ ] Fallback demo mode ready (see section "If Something Breaks")
- [ ] Backup demo video recorded
- [ ] Architecture diagram, including the IBM Z component, ready on screen
- [ ] A second hospital account ready for the access-control moment
- [ ] Time limit noted for each section; script practiced

---

## Step-by-Step

### 1. Setup (1 min)
- **Show:** the frontend dashboard, database schema and architecture diagram. Display a map of India with 20 blood banks and 10 hospitals marked.
- **Say:** *"Blood Bridge is a privacy-focused AI coordination system. We'll show a real emergency scenario."*

### 2. Scenario: Multiple Simultaneous Requests (1 min)
Three hospital users submit requests at the same time, all for O+:

| Hospital | Case | Urgency |
|---|---|---|
| A | Critical patient, required in 30 minutes | 5 |
| B | Routine | 2 |
| C | Urgent, required in 1 hour | 4 |

- **Say:** *"Three hospitals request O+ at the same time. How does Blood Bridge prioritize fairly?"*

### 3. Matching in Action (1.5 min)
Show the matching engine results live (or pre-recorded if live is risky).

Expected pattern (read the real scores off the screen):

| Hospital | Expected outcome | Explanation to point out |
|---|---|---|
| A | Rank 1 match from a nearby blood bank (about 8 km, ETA about 20 min) | Critical urgency + nearby + sufficient inventory |
| B | Match from a distant blood bank (about 200 km, ETA about 3 hours), lowest score | Routine, lower urgency, distant source |
| C | Rank 1 match from a different blood bank (about 15 km, ETA about 25 min) | Urgent + close + adequate inventory |

- **Say:** *"Notice: Hospital A gets priority because it's critical, NOT because it's wealthy or influential. Matching is transparent and fair."*

### 4. Privacy Preservation (1 min)
- **Show:** the matching request, for example `{ request_id: "REQ_001", blood_group: "O+", urgency: 5 }`.
- **Point out:** no patient name, ID, diagnosis, or personal details.
- **Show:** the patient's real ID (for example `PID_12345`) lives in the hospital's own EMR, not in Blood Bridge.
- **Show also:** the matched unit is a unit ID (`INV_001` from `BB_001`), never a donor ID.
- **Show:** the access-control check, where a user from another hospital tries to open this request and gets `403 Forbidden`.
- **Show:** the user email field is encrypted in the database.
- **Say:** *"Patient identity is completely separate from the matching system. Even if Blood Bridge is compromised, the patient's identity is safe."*

### 5. Audit and Transparency (1 min)
- **Show:** the audit log table, for example "User U_042 created request REQ_001, Timestamp 14:23:00".
- **Point out:** the user ID is masked, and no email, phone, or real names are visible.
- **Show:** the fairness report, for example "3 requests, matched in order of urgency. No bias detected. 0 requests prioritized by money/influence."
- **Say:** *"Every action is logged immutably. Auditors can verify that matching was fair and that privacy was respected."*

### 6. IBM Z Integration (30 sec)
- **Show:** the architecture diagram with the IBM Z / LinuxONE component.
- **Diagram label:** "In production, the database (Db2) and matching engine run on IBM Z for maximum security and reliability."
- **Say:** *"IBM Z provides encrypted processing and auditable computation, which is critical for a healthcare system."*
- Be clear about which parts are built and which are designed (see [IBM_Z_INTEGRATION.md](IBM_Z_INTEGRATION.md)).

### 7. Metrics and Impact (1 min)
- **Show:** the measured results from [TESTING.md](TESTING.md) against the baseline:

| Metric | Baseline (manual) | Target |
|---|---|---|
| Matching latency | 30-60 minutes | < 2 seconds |
| Match success rate | about 60% | ≥ 85% |
| Average distance | unpredictable | < 50 km |
| Fairness (bias correlation) | unknown | ≤ 0.05 |
| Privacy | low | 0 patient identifiers stored |

- **Say:** *"Blood Bridge improves speed, fairness, and privacy compared to manual coordination."*

### 8. Shortage Handling (30 sec)
- **Show:** a scenario where AB- (a rare blood type) has no match.
- **Display:** "Shortage detected: No compatible blood available nationwide. External mobilization recommended."
- **Say:** *"The system is honest about shortages, enabling proactive management."*

---

## If Something Breaks

| Problem | Fallback |
|---|---|
| Backend unresponsive or matching engine crashes | Switch the frontend to the fallback demo mode (`MockAPI` in `demo_mode.py`), which returns pre-computed matches for the demo requests |
| Frontend will not connect | Deploy a mock frontend with hardcoded data |
| Live demo crashes | Play the pre-recorded demo video |
| Demo scenario running long | Keep to the per-section time limits |
| Judges ask a question the team cannot answer | Use the prepared FAQ; the team lead is the primary spokesperson |

---

## Presentation Deck Outline (12 slides)

1. **Title:** Blood Bridge: Privacy-Focused AI Coordination for Emergency Blood Supply (IBM Z Datathon 2026, AI Secured Track)
2. **Problem:** life-or-death emergency; manual calls and 30-60 minute delays; unfair prioritization; privacy violations from sharing patient/donor data
3. **Solution overview:** automated AI matching; fair ranking (urgency, distance, expiry, fairness, not money); privacy-preserving; transparent
4. **System architecture:** Frontend → Backend API → Matching Engine + Database → Security Layer → IBM Z (production)
5. **AI matching engine:** four phases; scoring formula; transparent, rule-based, no black-box ML
6. **Privacy and security:** patient identity stays in the hospital's EMR; pseudonymous request IDs; encryption; RBAC; immutable audit logs; data masking
7. **IBM Z value:** Db2 for a high-reliability database; Secure Execution for cryptographically verified matching; built-in audit and compliance
8. **Demo highlights:** 2-3 screenshots of the actual demo run
9. **Metrics and impact:** metric / baseline / Blood Bridge table, using measured values
10. **Fairness and ethics:** money does not affect priority; donor identity protected; transparent decisions; timestamp-based tie-breaking
11. **Limitations and future work:** synthetic data; recommendations only; transport not modeled; future federated learning, advanced ML, national blood bank integration
12. **Conclusion:** privacy-first, AI-powered, fair, transparent, auditable; ready for national-scale deployment in partnership with eRaktKosh

---

## Final Checklist Before Submitting

- [ ] GitHub repo has clean, well-organized code, commented and documented
- [ ] README includes setup instructions that actually work
- [ ] Database schema DDL is provided; datasets (CSV or seed script) are included
- [ ] API endpoints are documented (OpenAPI/Swagger preferred)
- [ ] Demo works, or the demo video is recorded
- [ ] Slides are clear and tell a compelling story
- [ ] Team members can explain their parts clearly
- [ ] Metrics report is quantified and meaningful
- [ ] Privacy preservation is visibly demonstrated
- [ ] IBM Z integration is explained (even as "production architecture")
- [ ] No real patient or donor data is used or exposed
- [ ] Synthetic data is clearly labeled as such
- [ ] Git history shows all team members contributed
