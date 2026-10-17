# Testing

**Project:** Blood Bridge | IBM Z Datathon 2026 (AI Secured track)

> ⚠️ **SIMULATED FOR DEMONSTRATION PURPOSES.** All tests run on synthetic data.

**How to use this document:** the test cases and targets below come from the project plan. Record each outcome in the **Result** column as you run it (✅ pass, ❌ fail, with notes), and fill the measured value in the metrics table. Tests run with `pytest` from the `backend/` folder (target: 50-70% coverage; test files `test_api_requests.py`, `test_matching_engine.py`, `test_security.py`, `test_audit_logs.py`, `integration/test_end_to_end.py`).

---

## 1. Functional Test Cases

| # | Scenario | Setup | Expected | Pass criteria | Result |
|---|---|---|---|---|---|
| 1 | **Normal request and matching:** 4 units O+, urgency 3, no expiry constraints | Blood bank has 10 units O+, 30 days to expiry | Match found, clear explanation | Status becomes `MATCHED`, `best_match` returned, score ≥ 70 | ☐ |
| 2 | **Urgent request:** critical patient (urgency 5) needs AB+, required in 30 minutes | AB+ available 20 km away (ETA 22 min) | Match found despite longer transport | Match found; urgency component carries the largest weight | ☐ |
| 3 | **Competing requests:** REQ_001 at 14:23 and REQ_002 at 14:24, both O+, urgency 3 | Only 4 units O+ available | REQ_001 gets Rank 1 (earlier timestamp); REQ_002 queued behind it | Earlier request wins; both users notified | ☐ |
| 4 | **Insufficient quantity:** request 10 units, only 6 available | 6 units available | Match found with a partial note ("6/10 units available") | Request still matches with a quantity-mismatch note in the explanation | ☐ |
| 5 | **Complete shortage:** request B-, none available | No B- in the network | No match; shortage alert generated | Response has `shortage_alert`, status `UNFULFILLED`, alert sent to hospital | ☐ |
| 6 | **Expired units not matched:** request O+; unit INV_001 expires today | INV_001 expires today | INV_001 filtered out | Only non-expired units matched | ☐ |
| 7 | **Distance penalties:** two O+ units | Unit A 5 km, Unit B 400 km, both expire in 45 days | Unit A ranked higher | Unit A rank 1, Unit B rank 2 | ☐ |
| 8 | **Expiry-risk prioritization:** two O+ units at the same distance | Unit A expires in 2 days, Unit B in 60 days | Unit A ranked higher (waste prevention) | Unit A rank 1 (expiry score 20) | ☐ |

Note for case 4: the matching engine's Phase 1 as designed requires enough stock for the full quantity ([MATCHING_ALGORITHM.md](MATCHING_ALGORITHM.md)). Agree with the backend owner whether partial matches are supported before running this case, and record the decision in the Result column.

---

## 2. Security and Privacy Test Cases

| # | Scenario | Setup | Expected | Pass criteria | Result |
|---|---|---|---|---|---|
| S1 | **Unauthorized request access:** Hospital A user opens Hospital B's request | User A calls `GET /api/v1/requests/REQ_B_001` | 403 Forbidden, "You do not have access to other hospitals' requests" | Status 403; request not returned | ☐ |
| S2 | **Patient identity exposure:** query returns request data | Any request endpoint | No patient name, ID, or medical history | Response contains only `request_id`, blood group, quantity, urgency, status, timestamps (no `patient_id`, `patient_name`, `diagnosis`) | ☐ |
| S3 | **Unauthorized inventory access:** Hospital A user lists inventory | `GET /api/v1/inventory` without an ID, trying to see Hospital B's data | Only the user's own organization's data is returned (filtered by `affiliated_org_id`) | Another organization's inventory is not visible | ☐ |
| S4 | **Priority manipulation:** user changes urgency from 2 to 5 | `PATCH /api/v1/requests/REQ_001 { urgency_level: 5 }` | Rejected (urgency is read-only after submission), or allowed but logged | 400 Bad Request, or an audit log entry shows the attempted escalation | ☐ |
| S5 | **Audit log tampering:** admin tries to delete or modify an audit record | `DELETE /api/v1/audit/logs/123`, or `UPDATE audit_logs SET action_type = ...` | Database trigger or application logic blocks the change | Operation fails; logs remain immutable | ☐ |
| S6 | **SQL injection:** request with `blood_group = "O+' OR '1'='1"` | `POST /api/v1/requests` | Input validation rejects it; parameterized queries | 400 Bad Request; no SQL error; database unaffected | ☐ |

---

## 3. Realistic Scenarios

### Scenario A: Multi-city shortage
Mumbai hospitals request 30 units of AB-. Mumbai blood banks have 0; Pune banks (150 km away) have 5; Delhi banks (1,400 km away) have 15.
- **Expected:** Mumbai requests matched to Pune (slow but possible); a critical shortage alert for the Delhi units (too distant for an acute emergency); the auditor report shows equitable distribution.
- **Result:** ☐

### Scenario B: Rush hour
Five hospitals submit O+ requests within the same minute at 15:00. The network has 8 units of O+.
- **Expected:** all 5 requests matched, ranked fairly by timestamp; 3 get Rank 1 (certain match) and 2 get Rank 2 (wait or source elsewhere); no prioritization by hospital size or influence; fair queuing visible in the logs.
- **Result:** ☐

### Scenario C: Rare blood group (AB-)
A hospital requests 2 units of AB-. The network has only 1 unit (300 km away, expires in 5 days).
- **Expected:** that unit matched as Rank 1; shortage alert "Only 1/2 units available. External source mobilization recommended."; the audit log shows an exhaustive search of all blood banks.
- **Result:** ☐

---

## 4. Metrics and Evaluation

Record the measured value for each metric.

### 4.1 Functional

| # | Metric | Definition / measurement | Target | Baseline (manual) | Measured |
|---|---|---|---|---|---|
| 1 | Request matching success rate | Requests with at least one eligible match ÷ total requests (`status != 'UNFULFILLED'` ÷ total) | ≥ 85% | about 60% | |
| 2 | Matching latency | `AVG(matching_timestamp - request_timestamp)` over matched requests | < 2 seconds | 30-60 minutes | |
| 3 | Average distance | `AVG(distance_km)` over matched units | < 50 km | Higher (random calling) | |
| 4 | Expired-unit avoidance | Units delivered not expired ÷ total units matched | 99.5% | 95% | |
| 5 | Shortage detection accuracy | Correctly identified shortages ÷ true shortages | 100% | Varies | |

### 4.2 Privacy

| # | Metric | Measurement | Target | Baseline | Measured |
|---|---|---|---|---|---|
| 6 | Patient identity exposure prevention | Manual audit of schema and sample records | 100% (zero patient names, IDs, diagnoses in any table) | 0% | |
| 7 | Access control enforcement | Attempt 10 different unauthorized accesses; verify all are blocked | 100% | 0% | |
| 8 | Audit log completeness | Generate 50 requests; verify every `CREATE_REQUEST` is logged | 100% | Inconsistent | |

### 4.3 Fairness

| # | Metric | Measurement | Target | Baseline | Measured |
|---|---|---|---|---|---|
| 9 | Request queue fairness | For all pairs with the same urgency, the earlier request is matched within 1 minute of the later one | Difference ≤ 1 minute | No guarantee | |
| 10 | Anti-bias score | Tag hospitals as affluent or poor; compute the Pearson correlation between wealth and match time | ≤ 0.05 | Often positive | |

### 4.4 System

| # | Metric | Measurement | Target | Baseline | Measured |
|---|---|---|---|---|---|
| 11 | API response time (p99) | Load test with 1,000 concurrent requests | < 500 ms | Single instance may exceed 1 s under load | |
| 12 | Database query performance | Benchmark the eligibility query over synthetic data (10,000 inventory records) | < 100 ms | Non-indexed queries may exceed 1 s | |

---

## 5. Test Summary

| Area | Total | Passed | Failed |
|---|---|---|---|
| Functional (1-8) | 8 | | |
| Security and privacy (S1-S6) | 6 | | |
| Realistic scenarios (A-C) | 3 | | |

Code coverage: ______ (target 50-70%)
