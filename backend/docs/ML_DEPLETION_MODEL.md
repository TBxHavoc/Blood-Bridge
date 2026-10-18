# Blood Bridge: Machine Learning Supply Depletion & Demand Forecasting Engine
**IBM Z Datathon 2026 · AI Secured Track (Innovation without Exposure)**  
**Module:** Inventory Analytics & Predictive Depletion Forecasting  

---

## 1. Executive Summary & Clinical Context

In emergency blood supply management, stockouts cause immediate clinical jeopardy, while excess ordering leads to biological wastage due to expiry.

Blood Bridge's **ML Supply Depletion & Usage Forecasting Engine** solves this by:
1. **Calculating Empirical Usage**: Determining exact average daily usage (`units/day`) and weekly usage (`units/week`) per blood group (`O+`, `O-`, `A+`, `A-`, `B+`, `B-`, `AB+`, `AB-`) and component (`Whole Blood`, `RBC`).
2. **Predicting Supply Depletion & Stockout Timelines**: Forecasting the exact timestamp when a blood bank will run out of a given blood group, factoring in **both demand consumption velocity and upcoming batch expiry attrition**.
3. **Triage & Proactive Risk Categorization**: Classifying supply lines into actionable risk tiers (`CRITICAL < 24h`, `HIGH < 72h`, `MODERATE < 7d`, `STABLE > 7d`).
4. **Preserving Strict Zero-Exposure Privacy (`NFR-P1`)**: All forecasting algorithms operate strictly on aggregated unit quantities, blood groups, and timestamps. Zero patient or donor identifiers are ever ingested.

---

## 2. Mathematical & Algorithmic Formulation

### 2.1 Empirical Usage Calculation
For each unique `(blood_group, component_type)` pair:
- Given historical requests $\mathcal{R} = \{(q_1, t_1), (q_2, t_2), \dots, (q_n, t_n)\}$ (excluding cancelled requests):
- Observation time window:
  $$\Delta t_{\text{days}} = \max\left(1.0, \frac{\max(t_i) - \min(t_i)}{86400}\right)$$
- **Average Daily Usage**:
  $$\bar{U}_{\text{day}} = \frac{\sum_{i=1}^n q_i}{\Delta t_{\text{days}}} \quad [\text{units / day}]$$
- **Weekly Usage**:
  $$U_{\text{week}} = \bar{U}_{\text{day}} \times 7 \quad [\text{units / week}]$$
- **Hourly Burn Velocity**:
  $$\lambda = \frac{\bar{U}_{\text{day}}}{24} \quad [\text{units / hour}]$$

### 2.2 Expiry-Aware Depletion Simulation
Traditional inventory models assume inventory only decreases through usage. In healthcare, blood units expire. The Blood Bridge model integrates **discrete-event expiration attrition**:

For each blood bank $B$, blood group $g$, and component $c$:
- Let $S_0 = \max(0, \text{units\_available} - \text{units\_reserved})$ be current unreserved inventory.
- Let $\mathcal{E} = \{e_1, e_2, \dots, e_k\}$ be the expiration dates of on-hand batches.
- We simulate inventory state $S(h)$ forward hour by hour ($h = 1, 2, \dots, H_{\max}$):
  $$S(h) = S_0 - (\lambda \cdot h) - \sum_{j \in \mathcal{E}, e_j \le (t_0 + h)} \text{expired\_units}_j$$
- The time-to-depletion $h^*$ is the smallest hour where $S(h^*) \le 0$:
  $$T_{\text{depletion}} = t_0 + \Delta t(h^*)$$

### 2.3 Stockout Risk Categorization

| Risk Category | Criteria | Recommended Automated Action |
| :--- | :--- | :--- |
| **`IMMEDIATE_EMPTY`** | 0 unreserved units currently | Trigger immediate regional cross-bank match / shortage alert |
| **`CRITICAL`** | Supply runs out in $\le 24$ hours ($< 1$ day) | Alert network logistics and issue high-priority transfer request |
| **`HIGH`** | Supply runs out in $24 - 72$ hours ($1 - 3$ days) | Flag for replenishment in next scheduled distribution run |
| **`MODERATE`** | Supply runs out in $3 - 7$ days | Normal operational monitoring |
| **`STABLE`** | Supply exceeds $7$ days | Adequate supply buffer |
| **`EXPIRES_BEFORE_USE`**| Units will reach expiry before projected consumption | Recommend FIFO transfer to high-volume trauma hospital |

---

## 3. Running the Prediction Model (CLI)

You can run the model directly from the command line on your laptop or LinuxONE terminal:

```bash
# Run against the synthetic datasets
python backend/scripts/predict_depletion.py
```

### Sample Output:
```
========================================================================================
 BLOOD BRIDGE: MACHINE LEARNING SUPPLY DEPLETION & DEMAND FORECASTING
 IBM Z Datathon 2026 · AI Secured Track (Innovation without Exposure)
========================================================================================

[-] 1. HISTORICAL CONSUMPTION ANALYSIS (Usage per Day & Weekly):
----------------------------------------------------------------------------------------
Blood Group  Component      Total Reqs   Units Used   Avg Units/Day    Weekly Usage  
----------------------------------------------------------------------------------------
A+           RBC            8            38           19.0 u/day       133.0 u/wk    
A+           WHOLE_BLOOD    4            17           8.5 u/day        59.5 u/wk     
AB+          RBC            2            7            3.5 u/day        24.5 u/wk     
B+           RBC            5            28           14.0 u/day       98.0 u/wk     
B+           WHOLE_BLOOD    3            7            3.5 u/day        24.5 u/wk     
O+           RBC            9            30           15.0 u/day       105.0 u/wk    
O+           WHOLE_BLOOD    7            24           12.0 u/day       84.0 u/wk     
----------------------------------------------------------------------------------------

[-] 2. PREDICTED TIME TO DEPLETION & STOCKOUT RISK FORECAST:
---------------------------------------------------------------------------------------------------------
Bank Code  Blood  Component    Stock    Daily Burn   Runout Time        Days Left    Risk Tier      Cause
---------------------------------------------------------------------------------------------------------
BB_001     B-     WHOLE_BLOOD  6 u      0.1 u/d      2026-10-19 12:00   1.7 days     !  HIGH        BATCH_EXPIRATION
BB_002     O+     RBC          28 u     1.5 u/d      2026-11-05 12:00   18.7 days       STABLE      DEMAND_CONSUMPTION
BB_003     O+     WHOLE_BLOOD  26 u     1.2 u/d      2026-11-07 12:00   21.7 days       STABLE      DEMAND_CONSUMPTION
---------------------------------------------------------------------------------------------------------
```

---

## 4. FastAPI REST Endpoints

The model is mounted under the `/api/v1/forecasting/` prefix:

### 1. `GET /api/v1/forecasting/usage`
Returns the computed daily and weekly consumption rates across all blood types.

```json
{
  "success": true,
  "data": [
    {
      "blood_group": "O+",
      "component_type": "RBC",
      "total_requests": 9,
      "total_units_consumed": 30,
      "observation_days": 2.0,
      "avg_usage_per_day": 15.0,
      "weekly_usage": 105.0,
      "hourly_burn_rate": 0.625,
      "peak_24h_demand": 18,
      "recent_trend": "RISING"
    }
  ]
}
```

### 2. `GET /api/v1/forecasting/depletion`
Returns time-to-depletion and stockout risks for each blood bank.  
**Query Parameters**:
- `blood_group` (e.g. `O+`)
- `component_type` (e.g. `RBC`)
- `blood_bank_id` (e.g. `BB_001`)
- `risk_tier` (e.g. `CRITICAL`, `HIGH`, `MODERATE`, `STABLE`)

```json
{
  "success": true,
  "data": [
    {
      "blood_bank_id": "b0010000-0000-0000-0000-000000000001",
      "blood_bank_code": "BB_001",
      "blood_bank_name": "Red Cross Regional Blood Center",
      "blood_group": "O+",
      "component_type": "RBC",
      "units_available": 18,
      "units_reserved": 0,
      "units_unreserved": 18,
      "avg_usage_per_day": 1.5,
      "weekly_usage": 10.5,
      "hours_until_depletion": 72.0,
      "days_until_depletion": 3.0,
      "predicted_depletion_timestamp": "2026-10-20T12:00:00",
      "stockout_risk": "HIGH",
      "confidence_interval_hours": [65.5, 78.5],
      "earliest_batch_expiry": "2026-10-20",
      "depletion_cause": "BATCH_EXPIRATION"
    }
  ]
}
```

### 3. `GET /api/v1/forecasting/summary`
Returns an executive summary dashboard showing total inventory lines monitored, count of critical/high-risk stockouts, and top 10 most imminent stockouts.

---

## 5. Trained Machine Learning Artifact Integration (`depletion_model.pkl`)

The production forecasting engine directly integrates the trained model artifact bundle located at:
`backend/models/depletion_model.pkl`.

### Model Architecture:
- **Continuous Runout Regressor**: `LightGBM` Gradient Boosted Decision Tree (`LGBMRegressor`) predicting continuous hours until stockout.
- **Stockout Urgency Classifier**: `Random Forest Classifier` (`RandomForestClassifier`) predicting urgency risk tiers (`IMMEDIATE_EMPTY`, `CRITICAL < 24h`, `HIGH 1-3d`, `MODERATE 3-7d`, `STABLE > 7d`).
- **Feature Vector**:
  - `feat_bg`: Categorical LabelEncoded Blood Group (`O+`, `O-`, `A+`, etc.)
  - `feat_ct`: Categorical LabelEncoded Component Type (`RBC`, `WHOLE_BLOOD`)
  - `feat_city`: Categorical LabelEncoded Geographic City
  - `total_unreserved`: Available minus reserved units
  - `total_available`: Total on-hand units
  - `total_reserved`: Clinical reserved hold
  - `days_to_expiry`: Days until earliest batch expiration
  - `bank_daily_burn`: Apportioned regional consumption rate
  - `capacity_units`: Facility storage capacity
  - `avg_urgency`: Regional request clinical urgency score
- **Biological Expiration Bounding**: Predictions are physically constrained by $H_{\max} = \text{days\_to\_expiry} \times 24$ hours.
- **Resilient Fallback**: If `scikit-learn` or `lightgbm` are omitted in a lightweight container, the service automatically falls back to deterministic discrete-event simulation without downtime.

---

## 6. Running the Integration Tests

To test and verify the trained model bundle end-to-end:

```bash
# Run comprehensive multi-scenario verification test
python backend/scripts/test_trained_model.py

# Or specify a custom model path
python backend/scripts/test_trained_model.py --model "backend/models/depletion_model.pkl"

# Run backend pytest suite
pytest backend/tests/test_model_bundle.py backend/tests/test_p9_forecasting.py
```

---

## 7. IBM LinuxONE & Zero-Exposure Fit

1. **In-Process Micro-Execution**: Operates without external heavy ML runtimes or GPU drivers, ensuring instant compilation and flawless execution on **IBM LinuxONE (s390x)**.
2. **Secure Execution Ready**: Can execute inside an IBM Secure Execution confidential KVM guest, guaranteeing that forecasting logic and regional hospital demand patterns remain encrypted in memory.
3. **No External Network Leaks**: All inferences are deterministic, self-contained, and audited.

