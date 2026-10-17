# Data Dictionary

**Project:** Blood Bridge | IBM Z Datathon 2026 (AI Secured track)
**Database:** PostgreSQL (production design: Db2 on IBM Z)

> ⚠️ **SIMULATED FOR DEMONSTRATION PURPOSES.** All records are synthetic. No real patient, donor, or payment data exists in this system.

---

## 1. Overview

The database has 10 tables plus one in-code lookup (blood-group compatibility).

| Table | Purpose | Approx. rows (demo) |
|---|---|---|
| `users` | Accounts and roles for access control | Demo accounts for each role |
| `blood_banks` | Directory of participating blood banks | 15-25 |
| `hospitals` | Directory of requesting hospitals | 8-12 |
| `blood_inventory` | Stock metadata per blood bank (no donor identity) | 100-150 |
| `blood_requests` | Pseudonymous emergency requests | 30-50 historical, 5-10 live demo |
| `matching_results` | Ranked matches produced by the engine | Generated per request |
| `alerts` | Notifications to users | Generated per request |
| `audit_logs` | Immutable trail of all actions | Grows with every action |
| `location_distances` | Precomputed distance / travel time matrix | 225-625 |
| `system_config` | Matching parameters and feature toggles | One row per setting |

---

## 2. Table Definitions

### 2.1 `users`

| Field | Type | Required | Constraints / Notes |
|---|---|---|---|
| `user_id` | SERIAL | Yes | Primary key |
| `username` | VARCHAR(255) | Yes | Unique |
| `email` | VARCHAR(255) | Yes | Unique |
| `password_hash` | VARCHAR(512) | Yes | bcrypt or Argon2 hash, never plain text |
| `role` | enum | Yes | `hospital_user`, `bloodbank_user`, `admin`, `auditor` |
| `affiliated_org_id` | VARCHAR(50) | No | `hospital_id` or `blood_bank_id` |
| `created_at` | TIMESTAMP | Auto | Default current time |
| `last_login` | TIMESTAMP | No | |
| `is_active` | BOOLEAN | Auto | Default true |

Index: `affiliated_org_id`

### 2.2 `blood_banks`

| Field | Type | Required | Constraints / Notes |
|---|---|---|---|
| `blood_bank_id` | VARCHAR(50) | Yes | Primary key, e.g. `BB_001` |
| `bank_name` | VARCHAR(255) | Yes | |
| `city` | VARCHAR(100) | Yes | Keep city spelling consistent |
| `latitude` | DECIMAL(10,8) | Yes | Range -90 to 90 |
| `longitude` | DECIMAL(11,8) | Yes | Range -180 to 180 |
| `phone` | VARCHAR(20) | No | Synthetic number |
| `manager_user_id` | INTEGER | No | FK to `users.user_id` |
| `registration_date` | DATE | No | |
| `is_active` | BOOLEAN | Auto | Default true |
| `capacity_units` | INTEGER | No | Approximate storage capacity |
| `created_at`, `updated_at` | TIMESTAMP | Auto | |

Index: `city`

### 2.3 `hospitals`

| Field | Type | Required | Constraints / Notes |
|---|---|---|---|
| `hospital_id` | VARCHAR(50) | Yes | Primary key, e.g. `H_001` |
| `hospital_name` | VARCHAR(255) | Yes | |
| `city` | VARCHAR(100) | Yes | |
| `latitude` | DECIMAL(10,8) | Yes | Range -90 to 90 |
| `longitude` | DECIMAL(11,8) | Yes | Range -180 to 180 |
| `phone` | VARCHAR(20) | No | Synthetic number |
| `manager_user_id` | INTEGER | No | FK to `users.user_id` |
| `registration_date` | DATE | No | |
| `is_active` | BOOLEAN | Auto | Default true |
| `emergency_dept_capacity` | VARCHAR(50) | No | `small`, `medium`, `large` |
| `created_at`, `updated_at` | TIMESTAMP | Auto | |

Index: `city`

### 2.4 `blood_inventory`

| Field | Type | Required | Constraints / Notes |
|---|---|---|---|
| `inventory_id` | SERIAL | Yes | Primary key |
| `blood_bank_id` | VARCHAR(50) | Yes | FK to `blood_banks` |
| `blood_group` | VARCHAR(5) | Yes | `A+`, `A-`, `B+`, `B-`, `AB+`, `AB-`, `O+`, `O-` |
| `component_type` | VARCHAR(50) | Yes | Whole Blood, RBC, Plasma, Platelets |
| `units_available` | INTEGER | Yes | `>= 0` |
| `units_reserved` | INTEGER | Yes | Default 0, `>= 0` |
| `collection_date` | DATE | Yes | |
| `expiry_date` | DATE | Yes | Must be after `collection_date` |
| `storage_location_code` | VARCHAR(50) | No | Internal rack code, non-sensitive |
| `last_updated` | TIMESTAMP | Auto | |

Rules:
- `units_available >= units_reserved` (database check)
- A unit is usable only if `units_available > units_reserved` and the current time is before `expiry_date`. The plan calls this the computed `is_available` flag; it is derived, not stored in the DDL.
- Standard blood group format only (`A+`, never "A Positive").
- No donor identifiers, ever.

Indexes: `blood_group`, `expiry_date`, `blood_bank_id`

### 2.5 `blood_requests`

| Field | Type | Required | Constraints / Notes |
|---|---|---|---|
| `request_id` | VARCHAR(50) | Yes | Primary key, pseudonymous, e.g. `REQ_2026_10_06_001`; contains no patient info |
| `hospital_id` | VARCHAR(50) | Yes | FK to `hospitals` |
| `blood_group` | VARCHAR(5) | Yes | Same 8 values as inventory |
| `component_type` | VARCHAR(50) | Yes | |
| `quantity_units` | INTEGER | Yes | `> 0` |
| `clinician_urgency_level` | INTEGER | Yes | 1 to 5 (see scale below), set by authorized clinician, never by the AI |
| `request_timestamp` | TIMESTAMP | Yes | When submitted |
| `required_by_timestamp` | TIMESTAMP | No | Must be `>= request_timestamp` if present |
| `status` | VARCHAR(50) | Yes | Default `PENDING`; see statuses below |
| `created_by_user_id` | INTEGER | Yes | FK to `users` |
| `created_at`, `updated_at` | TIMESTAMP | Auto | |

**Urgency scale:**

| Level | Meaning |
|---|---|
| 1 | Routine |
| 2 | Moderately urgent |
| 3 | Urgent |
| 4 | Critical |
| 5 | Life-threatening |

**Status values:** `PENDING`, `MATCHED`, `FULFILLED`, `UNFULFILLED`, `CANCELLED`

**Privacy:** no patient name, ID, medical record number, or history is stored here.

Indexes: `hospital_id`, `status`, `blood_group`, `request_timestamp`

### 2.6 `matching_results`

| Field | Type | Required | Constraints / Notes |
|---|---|---|---|
| `match_id` | SERIAL | Yes | Primary key |
| `request_id` | VARCHAR(50) | Yes | FK to `blood_requests` |
| `inventory_id` | INTEGER | Yes | FK to `blood_inventory` |
| `match_timestamp` | TIMESTAMP | Auto | |
| `priority_score` | DECIMAL(10,4) | Yes | Computed by the matching engine |
| `ranking` | INTEGER | No | 1 = best choice |
| `distance_km` | DECIMAL(10,2) | No | |
| `estimated_eta_minutes` | INTEGER | No | |
| `eligibility_reason` | TEXT | No | Human-readable explanation |
| `is_active` | BOOLEAN | Auto | False if the unit is used elsewhere |
| `created_by_system` | VARCHAR(50) | No | Algorithm version |

Indexes: `request_id`, `match_timestamp`

### 2.7 `alerts`

| Field | Type | Required | Constraints / Notes |
|---|---|---|---|
| `alert_id` | SERIAL | Yes | Primary key |
| `request_id` | VARCHAR(50) | Yes | FK to `blood_requests` |
| `alert_type` | VARCHAR(50) | Yes | `MATCH_FOUND`, `SHORTAGE_DETECTED`, `MATCH_EXPIRED`, etc. |
| `message` | TEXT | Yes | |
| `recipient_user_id` | INTEGER | No | FK to `users` |
| `is_read` | BOOLEAN | Auto | Default false |
| `created_at`, `read_at` | TIMESTAMP | Auto / No | |

Indexes: `request_id`, `recipient_user_id`

### 2.8 `audit_logs`

| Field | Type | Required | Constraints / Notes |
|---|---|---|---|
| `log_id` | SERIAL | Yes | Primary key |
| `action_type` | VARCHAR(50) | Yes | `CREATE_REQUEST`, `UPDATE_INVENTORY`, `MATCH_GENERATED`, `ALERT_SENT`, `USER_LOGIN`, etc. |
| `user_id` | INTEGER | No | FK to `users` |
| `resource_type` | VARCHAR(50) | No | `blood_request`, `inventory`, `matching_result`, `user`, etc. |
| `resource_id` | VARCHAR(255) | No | ID of the affected record |
| `old_value` | TEXT | No | JSON of previous state |
| `new_value` | TEXT | No | JSON of new state |
| `reason_notes` | TEXT | No | |
| `ip_address` | INET | No | |
| `created_at` | TIMESTAMP | Auto | Not null |

**Immutable:** no UPDATE or DELETE allowed. This is enforced at the application layer.

Indexes: `user_id`, `action_type`, `(resource_type, resource_id)`, `created_at`

### 2.9 `location_distances`

| Field | Type | Required | Constraints / Notes |
|---|---|---|---|
| `origin_location_id` | VARCHAR(50) | Yes | Part of primary key |
| `destination_location_id` | VARCHAR(50) | Yes | Part of primary key |
| `origin_type` | VARCHAR(20) | Yes | `hospital` or `blood_bank` |
| `destination_type` | VARCHAR(20) | Yes | `hospital` or `blood_bank` |
| `distance_km` | DECIMAL(10,2) | Yes | Straight-line (Haversine) or estimated |
| `estimated_travel_time_minutes` | INTEGER | Yes | |
| `last_updated` | TIMESTAMP | Auto | |

Index: `origin_location_id`

### 2.10 `system_config`

| Field | Type | Required | Constraints / Notes |
|---|---|---|---|
| `config_key` | VARCHAR(255) | Yes | Primary key, e.g. `max_distance_km`, `priority_weight_urgency`, `priority_weight_distance` |
| `config_value` | TEXT | Yes | |
| `data_type` | VARCHAR(50) | No | `string`, `integer`, `boolean`, `json` |
| `description` | TEXT | No | |
| `updated_at` | TIMESTAMP | Auto | |
| `updated_by_user_id` | INTEGER | No | FK to `users` |

---

## 3. Blood-Group Compatibility Lookup

Stored as a dictionary inside the matching engine, not as a database table.

| Recipient | Compatible donor groups |
|---|---|
| A+ | A+, A-, O+, O- |
| A- | A-, O- |
| B+ | B+, B-, O+, O- |
| B- | B-, O- |
| AB+ | All eight groups |
| AB- | AB-, A-, B-, O- |
| O+ | O+, O- |
| O- | O- |

---

## 4. Relationships

| From | To | Type | Meaning |
|---|---|---|---|
| `users` | `blood_banks` / `hospitals` | many-to-one | Users are affiliated with one organization |
| `blood_requests` | `hospitals` | many-to-one | Each request comes from one hospital |
| `blood_requests` | `users` | many-to-one | Created by one authorized clinician |
| `blood_inventory` | `blood_banks` | many-to-one | Each record belongs to one bank |
| `matching_results` | `blood_requests` | many-to-one | One request has several ranked candidates |
| `matching_results` | `blood_inventory` | many-to-one | Candidate unit |
| `alerts` | `blood_requests` | many-to-one | Several alerts per request |
| `alerts` | `users` | many-to-one | Alert recipient |
| `audit_logs` | `users` | many-to-one | Who performed the action |

---

## 5. Data Quality Rules

1. **Blood groups:** always `[ABO][Rh]` format, e.g. `O+`.
2. **Timestamps:** ISO 8601, e.g. `2026-10-06T14:23:00Z`.
3. **Urgency:** integer 1 to 5 only.
4. **Quantities:** positive integers; `units_available >= units_reserved`.
5. **Coordinates:** latitude -90 to 90, longitude -180 to 180.
6. **Status values:** only the five allowed enums.
7. **No duplicates:** unique inventory IDs and request IDs.
8. **Mandatory fields:** `blood_group`, `hospital_id`, `clinician_urgency_level`. Optional: `required_by_timestamp` and similar.

---

## 6. Synthetic Data Generation

- **Generator:** a Python seed script (`datasets/seed_data.py`) that generates blood banks, hospitals, inventory, requests, and the distance matrix.
- **Output:** JSON or CSV files imported into the database during setup.
- **Blood groups:** weighted realistically (O+ most common, AB- rarest).
- **Locations:** realistic cities such as Mumbai, Delhi, Bangalore and Chennai; some hospitals share a city with a blood bank and some are distant.
- **Inventory:** realistic quantities and expiry dates, about 5 records per blood bank.
- **Requests:** realistic urgency and blood-type distribution, timestamps across the demo period, some simultaneous and some sequential.
- **Distances:** Haversine straight-line formula on latitude/longitude (simple method); a mapping API or mock data labeled "estimated" if time permits.

See [DATA_SOURCES.md](DATA_SOURCES.md) for the full data strategy.

---

## 7. Data Never Stored

- Real patient names, IDs, medical records, or identifiers
- Real donor names, contact details, or identifiers
- Payment or billing information
- Anything that could identify an individual

---
