# Data Sources

**Project:** Blood Bridge | IBM Z Datathon 2026 (AI Secured track)

> ⚠️ **SIMULATED FOR DEMONSTRATION PURPOSES.** All data used in this project is synthetic. Nothing here is real patient, donor, or hospital data, and the system does not reflect live blood availability anywhere.

---

## 1. Summary

| Dataset | Source type | Real data used? |
|---|---|---|
| Blood banks | Synthetic, mimicking the structure of public blood-bank directories | No |
| Hospitals | Synthetic | No |
| Blood inventory | Synthetic | No |
| Blood requests | Synthetic | No |
| Distance / travel-time matrix | Calculated from coordinates | No |
| Blood-group compatibility | Standard medical knowledge, embedded as a lookup in the matching engine | N/A |
| Users and credentials | Synthetic demo accounts | No |

**Why synthetic:** real hospital request data and live blood-bank APIs are not available or permitted, and real patient or donor data would contradict the project's privacy goals.

---

## 2. Public Sources Used for Reference

These inform how realistic the synthetic data is. They are used for validation and realistic data generation, **not as training data**.

### 2.1 eRaktKosh (India's national blood bank database)
- **What is public:** aggregate blood-stock levels by blood group and location, and the registered blood-bank directory.
- **What is restricted:** real-time donor records, patient records, and transaction histories. None of these are accessed.
- **Access approach:** use only publicly available aggregate snapshots (blood-bank names, locations, published stock levels), or a historical data dump if permitted by the organizers.
- **No scraping:** live data is not scraped without explicit permission.
- **Fallback:** a synthetic dataset that mimics the eRaktKosh structure.

### 2.2 Research datasets and reports
- Academic papers on blood-bank inventory management, blood shortage patterns, and geographical demand
- Red Cross / Red Crescent public reports
- WHO blood-safety and availability reports

---

## 3. Synthetic Data Generation

| Item | Detail |
|---|---|
| Generator | Python seed script, `datasets/seed_data.py` |
| Output | JSON or CSV files imported into the database during setup |
| Source files | `blood_banks.csv`, `hospitals.csv`, `blood_inventory.csv`, `blood_requests.csv`, `location_distances.csv` |

### 3.1 Dataset sizes

| Dataset | Records |
|---|---|
| Blood banks | 15-25 (covers a realistic multi-city region) |
| Hospitals | 8-12 |
| Inventory records | 100-150 |
| Historical requests | 30-50 (testing and baseline comparison) |
| Live demo requests | 5-10 (run during the presentation) |
| Distance matrix entries | 225-625 |

The sizes are large enough to show matching complexity but small enough to load, process, and debug within minutes.

### 3.2 Realism choices

- **Blood groups:** weighted realistically, with O+ the most common and AB- the rarest.
- **Locations:** realistic cities such as Mumbai, Delhi, Bangalore and Chennai. Some hospitals are in the same city as a blood bank and some are distant.
- **Inventory:** realistic quantities and expiry dates, about 5 records per blood bank.
- **Requests:** realistic urgency and blood-type distribution, timestamps spanning the demo period, some simultaneous and some sequential.
- **Test scenarios:** rush hour, rare blood types, and shortages.

### 3.3 Distances

- **Method:** precomputed matrix using the Haversine formula on latitude and longitude (straight-line distance). A mapping API such as Google Maps Distance Matrix, or mock data labeled "estimated", is used if time permits.
- **Limitation:** straight-line distance ignores roads and traffic, so travel times are approximations.

### 3.4 Cleaning and validation rules

- Blood groups in `A+` format only (not "A Positive")
- ISO 8601 timestamps
- Urgency as integer 1 to 5
- Positive quantities, and `units_available >= units_reserved`
- Valid coordinate ranges (latitude -90 to 90, longitude -180 to 180) and consistent city names
- Only the five allowed request status values
- No duplicate inventory or request IDs
- Mandatory fields: `blood_group`, `hospital_id`, `clinician_urgency_level`

See [DATA_DICTIONARY.md](DATA_DICTIONARY.md) for field-level details.

---

## 4. Data We Deliberately Do Not Use

- Real patient names, IDs, medical records, or identifiers
- Real donor names, contact details, or identifiers
- Payment or billing information (also excluded because it could bias matching toward wealthier hospitals)
- Live or scraped data from government systems without explicit permission

Request IDs such as `REQ_2026_10_06_001` are pseudonymous and carry no patient information. Code review checks that no personal information appears in any dataset.

---

## 5. Labeling

Every synthetic dataset is marked "SIMULATED FOR DEMONSTRATION PURPOSES" in the documentation and in the UI. The project never claims synthetic data is real or live.

---

## 6. Limitations

- Synthetic data cannot capture real demand patterns, so performance numbers reflect the demo dataset only.
- Integration with a real system such as eRaktKosh (if permission is obtained) is future work.
