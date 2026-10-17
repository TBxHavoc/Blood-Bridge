# Data Sources

**Project:** Blood Bridge | IBM Z Datathon 2026 (AI Secured track)

> ⚠️ **SIMULATED FOR DEMONSTRATION PURPOSES.** The demo dataset is entirely synthetic: no real patient, donor, or hospital data, and the system does not reflect live blood availability anywhere. The single real input is an offline snapshot of eRaktKosh's public aggregate stock figures (§2.1 and §2.3), which is not loaded into the demo dataset.

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
| eRaktKosh aggregate stock (offline snapshot) | Public aggregate figures read by `tools/eraktkosh-scraper` | Yes — public aggregate counts only, and not loaded into the demo dataset |

**Why synthetic:** real hospital request data and live blood-bank feeds are not available to this project, and real patient or donor data would contradict the project's privacy goals. The eRaktKosh snapshot (§2.1) is public and aggregate, and is used for realism and analysis rather than as the demo dataset.

---

## 2. Public Sources Used for Reference

These inform how realistic the synthetic data is. They are used for validation and realistic data generation, **not as training data**.

### 2.1 eRaktKosh (India's national blood bank database)
- **What is public:** aggregate blood-stock levels by blood group and location, and the registered blood-bank directory.
- **What is restricted:** real-time donor records, patient records, and transaction histories. None of these are accessed, and the tooling below has no ability to access them.
- **Access approach:** an **offline** snapshot tool (`tools/eraktkosh-scraper`, built on Crawlee) reads only the public aggregate stock figures and writes a timestamped snapshot. It is run by hand, is not part of the running system, is not scheduled, and is not a live feed.
- **Fallback:** a synthetic dataset that mimics the eRaktKosh structure. The snapshot tool is not required to run the demo.

### 2.2 Research datasets and reports
- Academic papers on blood-bank inventory management, blood shortage patterns, and geographical demand
- Red Cross / Red Crescent public reports
- WHO blood-safety and availability reports

### 2.3 Change of position on eRaktKosh access

Earlier revisions of this document stated flatly that live data "is not scraped without
explicit permission", and listed scraped government data under "Data We Deliberately Do
Not Use". That no longer describes the project, so the statement has been replaced rather
than left in place inaccurately.

What changed, and the limits that now apply:

- The project uses an **offline snapshot** of **public aggregate** figures only: blood-bank
  names, locations, contact details, and per-blood-group unit counts. It reads nothing that
  requires authentication, and it cannot reach donor or patient records.
- The tool is **manual and unscheduled** — not wired into the backend, the database, or CI.
  It is conservative by default (one concurrent request, 20 requests per minute); a
  nationwide run is on the order of 72 requests.
- Every artefact it writes carries provenance and a disclaimer that the figures are
  indicative, may be stale, and must be confirmed by phone. eRaktKosh's own pages say the
  same, so the project does not present the numbers as authoritative or real-time.
- The snapshot is an **analysis and realism input**. The synthetic demo dataset and its
  generator are unchanged, and every synthetic dataset remains labelled
  "SIMULATED FOR DEMONSTRATION PURPOSES".
- The snapshot **does not** contain everything the seeder needs (no expiry dates,
  coordinates, reserved counts or capacity), because the portal does not publish those.
  Nothing is fabricated to fill the gap.
- The sanctioned integration route remains the **ABDM/UHI Blood Bank Discovery API**
  (`nic2008:86906`, `BloodStock`), on which eRaktKosh is a registered HSPA. Any move from a
  manual snapshot to a live or deployed integration should go through that route.

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
- Live or scraped data from government systems, other than the offline public-aggregate snapshot described in §2.1 and §2.3

Request IDs such as `REQ_2026_10_06_001` are pseudonymous and carry no patient information. Code review checks that no personal information appears in any dataset.

---

## 5. Labeling

Every synthetic dataset is marked "SIMULATED FOR DEMONSTRATION PURPOSES" in the documentation and in the UI. The project never claims synthetic data is real or live.

---

## 6. Limitations

- Synthetic data cannot capture real demand patterns, so performance numbers reflect the demo dataset only.
- A live integration with a real system such as eRaktKosh remains future work. What exists today is an offline snapshot of public aggregate figures (§2.1), which is not a live feed and is not used by the running demo.
