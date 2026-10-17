# Blood Bridge: IBM LinuxONE & Db2 Migration Guide
**IBM Z Datathon 2026 · AI Secured Track (Innovation without Exposure)**  
**Target:** IBM LinuxONE Community Cloud / Enterprise s390x Instance  

---

## 1. Overview & Hackathon Strategy

According to PRD Section 11 (**IBM Z Integration**), the delivery strategy has two levels:
- **Level 1 (Local Development & Fallback)**: Backend runs locally on PostgreSQL 16 via Docker Compose.
- **Level 2 (Mandatory Live Demo Target)**: Database runs on the organizers' **IBM LinuxONE** instance using IBM Db2 LUW.

The Blood Bridge schema and SQLAlchemy models are engineered to switch between PostgreSQL and Db2 **without changing a single line of backend code**.

---

## 2. LinuxONE Prerequisites & Driver Setup

To connect a Python/FastAPI backend or administrative client to Db2 on IBM LinuxONE:

### Step 1: Install IBM Db2 Python Drivers
```bash
pip install ibm_db ibm_db_sa
```
*(On Windows or Linux x86_64, `ibm_db` automatically downloads the pre-compiled `clidriver` library).*

### Step 2: Environment Configuration
In your `.env` file, switch `ACTIVE_DATABASE` to `db2`:

```env
# Switch database target
ACTIVE_DATABASE=db2

# IBM LinuxONE Db2 Connection Parameters
DB2_HOST=linuxone.demos.ibm.com      # Or IP provided by hackathon mentors
DB2_PORT=50000                       # Standard Db2 port (or 50001 for SSL)
DB2_DATABASE=BLDPRD                  # Db2 database name
DB2_USER=db2inst1                    # Instance username
DB2_PASSWORD=YourLinuxOnePassword    # Provided credentials
DB2_SECURITY=SSL                     # Enable if using SSL port

# SQLAlchemy URI for IBM Db2
DATABASE_URL_DB2=ibm_db_sa://db2inst1:YourLinuxOnePassword@linuxone.demos.ibm.com:50000/BLDPRD
```

---

## 3. Applying the Schema to IBM LinuxONE Db2

You have two simple options to create the database schema on LinuxONE:

### Option A: Using the Db2 Command Line on LinuxONE SSH
If you have SSH access to the LinuxONE s390x terminal:
1. Copy `sql/02_schema_ibm_db2.sql` to your LinuxONE instance:
   ```bash
   scp sql/02_schema_ibm_db2.sql db2inst1@linuxone-ip:/home/db2inst1/
   ```
2. Log in and execute the script via Db2 Command Line Processor:
   ```bash
   db2 connect to BLDPRD user db2inst1 using YourPassword
   db2 -tvf 02_schema_ibm_db2.sql
   ```

### Option B: Automated Initialization via SQLAlchemy
Run the automated schema creator from your laptop or backend container:
```bash
python -c "from models.db_models import init_db; import os; from dotenv import load_dotenv; load_dotenv(); init_db(os.getenv('DATABASE_URL_DB2'))"
```

---

## 4. Cross-Platform Schema Design Differences

| Feature | Local PostgreSQL | IBM LinuxONE Db2 | Portability Strategy |
| :--- | :--- | :--- | :--- |
| **UUIDs** | Native `UUID` | No native `UUID` | Standardized on `VARCHAR(36)` across both systems. |
| **Auto-Increment** | `SERIAL` / `BIGSERIAL` | `GENERATED ALWAYS AS IDENTITY` | Standardized on ANSI `BIGINT GENERATED ALWAYS AS IDENTITY`. |
| **Enums** | `CREATE TYPE ... AS ENUM` | Not supported | Standardized on ANSI SQL `VARCHAR(n) CHECK (col IN (...))`. |
| **Network IP** | `INET` | Not supported | Standardized on `VARCHAR(45)` text storage. |
| **Timestamps** | `TIMESTAMP WITH TIME ZONE` | `TIMESTAMP` | ISO 8601 UTC strings stored consistently. |
| **Booleans** | Native `BOOLEAN` | `BOOLEAN` or `SMALLINT` | Compatible with `BOOLEAN` (Db2 11.5+) and `SMALLINT (0, 1)`. |

---

## 5. Row-Level Locking & Concurrency on Db2

PRD Section 8.5 mandates that two hospitals must never hold the same blood unit:
- **PostgreSQL Locking Syntax**:
  ```sql
  SELECT id, units_available, units_reserved 
  FROM blood_inventory 
  WHERE id = ? 
  FOR UPDATE;
  ```
- **IBM Db2 Locking Syntax**:
  ```sql
  SELECT id, units_available, units_reserved 
  FROM blood_inventory 
  WHERE id = ? 
  FOR READ ONLY WITH RS USE AND KEEP EXCLUSIVE LOCKS;
  ```

In SQLAlchemy 2.0, this is abstracted automatically when calling `.with_for_update()`:
```python
inventory_row = db.query(BloodInventory)\
    .filter(BloodInventory.id == inv_id)\
    .with_for_update()\
    .one()
```
SQLAlchemy's `ibm_db_sa` dialect translates `.with_for_update()` to the appropriate Db2 locking clause automatically!

---

## 6. The IBM Z / LinuxONE Pitch Touchpoint (For Judges)

When presenting to the IBM judges, highlight these key architectural pillars:
1. **IBM Z Pervasive Encryption**: At rest, Db2 tablespaces on LinuxONE leverage hardware-accelerated **CPACF** (CP Assist for Cryptographic Functions), guaranteeing zero performance penalty for full encryption.
2. **IBM Secure Execution for Linux (Confidential Computing)**: Blood Bridge's matching engine and audit log verification are designed to run inside a protected KVM guest using IBM Secure Execution. Memory is encrypted at the hypervisor level, ensuring even host administrators cannot inspect or tamper with in-flight matching computations.
3. **Enterprise Audit Immutability**: The combination of Db2 append-only table constraints with SHA-256 hash chaining aligns with strict banking and healthcare regulatory mandates (HIPAA, DISHA, DPDP).
