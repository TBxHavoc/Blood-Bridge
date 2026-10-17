# Matching Algorithm

**Project:** Blood Bridge | IBM Z Datathon 2026 (AI Secured track)

> ⚠️ **SIMULATED FOR DEMONSTRATION PURPOSES.** All data is synthetic. Matches are recommendations only; humans make the final decisions.

---

## 1. Approach: Rule-Based Scoring Instead of Machine Learning

Blood Bridge uses a **transparent rule-based scoring model** plus constraint-based optimization, not a trained ML model.

| Reason | Detail |
|---|---|
| **No training data** | A model would need historical request and match outcomes, which are not readily available |
| **Time** | Preparing data, training, and validating a model would take 4-6 hours of a 24-hour hackathon |
| **Explainability** | The track is "AI Secured: Innovation without Exposure"; a rule-based model is more transparent than a black box |
| **Fairness** | A model trained on historical data could learn existing bias (for example, favoring wealthy hospitals). Rule-based matching explicitly prevents this |

**Where the "AI" is:** the engine solves a constraint satisfaction problem (filtering inventory against compatibility, quantity, expiry, and distance constraints) and performs multi-objective optimization (balancing urgency, distance, expiry, and fairness) in real time.

---

## 2. Inputs the Engine Sees

Only these fields reach the matching engine:

- Blood group
- Quantity
- Component type
- Location (for distance)
- Clinician-supplied urgency level (1-5)
- Timestamps (for fairness and audit)

Patient name, medical record number, diagnosis, transfusion history, donor ID, and donor contact details never enter the engine.

---

## 3. Four-Phase Pipeline

```
Request + inventory snapshot
        │
        ▼
Phase 1: Eligibility filter ──► no eligible units ──► COMPLETE shortage alert
        │
        ▼
Phase 2: Priority scoring (0-100)
        │
        ▼
Phase 3: Ranking + explanations
        │
        ▼
Phase 4: Shortage check (best score < 50 ──► PARTIAL shortage alert)
        │
        ▼
Ranked matches, best match, optional shortage alert
```

### Phase 1: Eligibility Filtering (deterministic)

A unit is eligible only if **all** checks pass:

1. **Blood group compatibility:** the donor group is compatible with the recipient's group (table in section 4)
2. **Component type:** matches the requested component, if one was specified
3. **Quantity:** `units_available - units_reserved >= quantity_units`
4. **Not expired:** `expiry_date` is not before today
5. **In stock:** the unit is marked available

The output is a list of eligible units, which may be empty.

### Phase 2: Transparent Priority Scoring (0-100)

Each eligible unit gets a score from five factors:

| # | Factor | Max points | Formula |
|---|---|---|---|
| 1 | Urgency | 30 | `(urgency_level / 5) * 30` |
| 2 | Distance / ETA | 25 | `0` if distance > 300 km, else `(1 - distance_km / 300) * 25` |
| 3 | Expiry risk | 20 | Expires in ≤ 3 days: 20; ≤ 7 days: 15; otherwise: 5; expired: 0 |
| 4 | Quantity match | 15 | `(min(units_available, quantity_requested) / quantity_requested) * 15` |
| 5 | Request time (fair queue) | 10 | `(request_age_minutes / 60) * 10`, capped at 10 after 60 minutes |
| | **Total** | **100** | |

Notes on the factors:
- **Urgency** comes from the clinician and is never changed or diagnosed by the system.
- **Distance:** 300 km is treated as the maximum useful distance, beyond which blood may be too slow to help.
- **Expiry:** units expiring soon are used first to reduce waste.
- **Request time:** earlier requests get a slight priority boost; after 60 minutes all old requests are treated equally.

**Score interpretation**

| Score | Meaning |
|---|---|
| 85-100 | Excellent match (urgent, close, sufficient, not expiring) |
| 70-84 | Good match (urgent or close) |
| 50-69 | Acceptable match (meets requirements, may be distant or less urgent) |
| below 50 | Poor match (use only if there is no better option) |

### Phase 3: Ranking and Recommendation

- Eligible units are sorted by priority score, highest first.
- Each ranked unit is returned with: `inventory_id`, `blood_bank_id`, `blood_group`, `units_available`, `expiry_date`, `priority_score`, `distance_km`, `estimated_eta_minutes`, and a human-readable **explanation**.

### Phase 4: Shortage Detection and Alerts

| Situation | Shortage type | Message / recommendation |
|---|---|---|
| No eligible units | `COMPLETE` | No blood of the requested type is available in the network; manual search of external sources or donor mobilization is required |
| Best score below 50 | `PARTIAL` | Limited options; the best match is far away or scores low; consider alternative locations or consult clinicians |
| Otherwise | none | No shortage |

---

## 4. Blood-Group Compatibility

Embedded as a lookup dictionary in the engine (`compatibility_rules.py`), not a database table.

| Recipient | Compatible donor groups |
|---|---|
| A+ | A+, A-, O+, O- |
| A- | A-, O- |
| B+ | B+, B-, O+, O- |
| B- | B-, O- |
| AB+ | All eight groups (universal recipient) |
| AB- | AB-, A-, B-, O- |
| O+ | O+, O- |
| O- | O- (universal donor) |

---

## 5. Worked Example

**Request:** `REQ_2026_10_06_001`, blood group O+, 4 units, urgency 4. **Candidate unit:** INV_001 at BB_001, 4 units available, 8.2 km away (ETA 25 min), expiring in 39 days. Assume the request has waited 60 minutes or more.

| Factor | Calculation | Points |
|---|---|---|
| Urgency | (4 / 5) × 30 | 24.00 |
| Distance | (1 − 8.2 / 300) × 25 | 24.32 |
| Expiry | 39 days is more than 7 | 5.00 |
| Quantity | (4 / 4) × 15 | 15.00 |
| Request time | 60+ minutes | 10.00 |
| **Total** | | **78.32** |

Explanation shown to the user: *"Rank 1: Urgency 4/5 + nearby blood bank (8.2 km, 25 min ETA) + sufficient inventory (4 units) + 39 days until expiry = 78.3/100"*

---

## 6. Tie-Breaking and Fairness

**Scenario:** two requests with the same urgency, both needing O+, with limited O+ units.

1. The request with the **earlier `request_timestamp`** is served first (first come, first served).
2. If the timestamps are identical (extremely rare), the lower `request_id` wins.

**Transparency:** the result must state the reasoning, for example: *"REQ_001 received at 14:23:00 (earlier than REQ_002 at 14:24:00). Both have urgency 4 and the same blood type. REQ_001 assigned the first available unit. REQ_002 queued for the next available."*

**What never affects priority:** money, hospital size or influence, and ability to pay. The anti-bias target is a correlation of 0.05 or less between hospital affluence and match time.

---

## 7. Implementation

```
backend/matching_engine/
├── __init__.py
├── eligibility_filter.py    # Phase 1
├── priority_scoring.py      # Phase 2
├── ranking.py               # Phase 3
├── shortage_detection.py    # Phase 4
├── compatibility_rules.py   # Blood-group compatibility table
├── utils.py                 # Distance calculation, explanation generation
└── config.py                # Configurable weights and thresholds
```

**Main entry point:** `BloodMatchingEngine.match_request(request, inventory_snapshot)`

1. Run Phase 1. If nothing is eligible, return no matches plus a `COMPLETE` shortage alert.
2. Otherwise run Phases 2 and 3 to rank the units.
3. Run Phase 4 to check for a `PARTIAL` shortage.

**Return value**

```
{
  request_id,
  matches: [{rank, inventory_id, score, explanation}, ...],
  shortage_alert: None or {type, message},
  best_match: {...} or None,
  matching_timestamp
}
```

**Configurable weights:** the engine reads weights such as `urgency_weight` (default 30) and `distance_weight` (default 25) from `system_config`, so administrators can adjust them without code changes.

---

## 8. Optional Extensions

- **Predicted shortage:** if several urgent requests are pending and O- inventory is limited, flag a predicted shortage and alert blood-bank staff.
- **Predicted time-to-match:** a simple linear regression on historical request-to-match times.
- **Learning from feedback (future, not MVP):** learn from match outcomes to improve scoring weights.

---

## 9. Evaluation Targets

| Metric | Target |
|---|---|
| Matching success rate | ≥ 85% |
| Matching latency | < 2 seconds |
| Average distance to matched bank | < 50 km |
| Expired-unit avoidance | 99.5% |
| Shortage detection accuracy | 100% |
| Queue fairness (same urgency) | Earlier request matched within 1 minute of a later one |
| Anti-bias score | Correlation ≤ 0.05 |
| Eligibility query time | < 100 ms with 10,000 inventory records |

Measured results are recorded in [TESTING.md](TESTING.md).

---

## 10. Behavior Notes

- For a single request, the urgency and request-time points are the same for every candidate unit, so the **order of units** is decided by distance, expiry risk, and quantity match. Urgency and request age mainly set the overall score level, which feeds the shortage check and the queue.
- Because Phase 1 requires enough stock to cover the full quantity, the quantity-match factor is full for every eligible unit. Splitting a request across several banks is not part of the MVP.
- Distance uses straight-line (Haversine) estimates, so real road travel times may differ.
