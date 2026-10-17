-- =============================================================================
-- Blood Bridge - IBM Z / LinuxONE Db2 Schema
-- Track: IBM Z Datathon 2026 - AI Secured Track (Innovation without Exposure)
-- Complies with: PRD v1.0 Section 11 (IBM Z Integration) & SRS v1.0
-- Dialect: IBM Db2 LUW (Linux on IBM Z / s390x)
-- =============================================================================

-- Note for Db2 Command Line Processor:
-- db2 -tvf 02_schema_ibm_db2.sql

-- -----------------------------------------------------------------------------
-- 1. SYSTEM CONFIGURATION TABLE
-- -----------------------------------------------------------------------------
CREATE TABLE system_config (
    config_key VARCHAR(50) NOT NULL PRIMARY KEY,
    config_value VARCHAR(255) NOT NULL,
    description CLOB(10K),
    data_type VARCHAR(20) DEFAULT 'string' NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT TIMESTAMP NOT NULL,
    CONSTRAINT chk_cfg_dtype CHECK (data_type IN ('string', 'integer', 'float', 'boolean', 'json'))
);

-- -----------------------------------------------------------------------------
-- 2. HOSPITALS TABLE
-- Staged disclosure (NFR-P7): Hidden until match is confirmed.
-- -----------------------------------------------------------------------------
CREATE TABLE hospitals (
    id VARCHAR(36) NOT NULL PRIMARY KEY,
    hospital_code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(150) NOT NULL,
    address CLOB(10K) NOT NULL,
    latitude DECIMAL(9, 6) NOT NULL,
    longitude DECIMAL(9, 6) NOT NULL,
    delivery_point VARCHAR(255) NOT NULL,
    contact_phone VARCHAR(30) NOT NULL,
    contact_email VARCHAR(100) NOT NULL,
    is_active SMALLINT DEFAULT 1 NOT NULL, -- 1=True, 0=False for universal Db2 driver support
    created_at TIMESTAMP DEFAULT CURRENT TIMESTAMP NOT NULL,
    CONSTRAINT chk_hosp_active CHECK (is_active IN (0, 1))
);

-- -----------------------------------------------------------------------------
-- 3. BLOOD BANKS TABLE
-- -----------------------------------------------------------------------------
CREATE TABLE blood_banks (
    id VARCHAR(36) NOT NULL PRIMARY KEY,
    bank_code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(150) NOT NULL,
    address CLOB(10K) NOT NULL,
    latitude DECIMAL(9, 6) NOT NULL,
    longitude DECIMAL(9, 6) NOT NULL,
    contact_phone VARCHAR(30) NOT NULL,
    contact_email VARCHAR(100) NOT NULL,
    is_active SMALLINT DEFAULT 1 NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT TIMESTAMP NOT NULL,
    CONSTRAINT chk_bb_active CHECK (is_active IN (0, 1))
);

-- -----------------------------------------------------------------------------
-- 4. USERS & RBAC TABLE
-- -----------------------------------------------------------------------------
CREATE TABLE users (
    id VARCHAR(36) NOT NULL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL,
    affiliated_org_type VARCHAR(20) DEFAULT 'none' NOT NULL,
    affiliated_org_id VARCHAR(36) DEFAULT NULL,
    is_active SMALLINT DEFAULT 1 NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT TIMESTAMP NOT NULL,
    CONSTRAINT chk_usr_role CHECK (role IN ('hospital_user', 'bloodbank_user', 'admin', 'auditor')),
    CONSTRAINT chk_usr_org_type CHECK (affiliated_org_type IN ('hospital', 'blood_bank', 'none')),
    CONSTRAINT chk_usr_active CHECK (is_active IN (0, 1))
);

-- -----------------------------------------------------------------------------
-- 5. BLOOD INVENTORY TABLE
-- Zero donor information stored (FR-21, NFR-P1).
-- -----------------------------------------------------------------------------
CREATE TABLE blood_inventory (
    id VARCHAR(36) NOT NULL PRIMARY KEY,
    inventory_code VARCHAR(30) NOT NULL UNIQUE,
    blood_bank_id VARCHAR(36) NOT NULL,
    blood_group VARCHAR(5) NOT NULL,
    component_type VARCHAR(20) NOT NULL,
    units_available INTEGER NOT NULL,
    units_reserved INTEGER DEFAULT 0 NOT NULL,
    collection_date DATE NOT NULL,
    expiry_date DATE NOT NULL,
    is_available SMALLINT DEFAULT 1 NOT NULL,
    last_updated_at TIMESTAMP DEFAULT CURRENT TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT TIMESTAMP NOT NULL,
    CONSTRAINT fk_inv_bb FOREIGN KEY (blood_bank_id) REFERENCES blood_banks(id) ON DELETE CASCADE,
    CONSTRAINT chk_inv_bg CHECK (blood_group IN ('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-')),
    CONSTRAINT chk_inv_comp CHECK (component_type IN ('Whole Blood', 'RBC')),
    CONSTRAINT chk_inv_avail CHECK (units_available >= 0),
    CONSTRAINT chk_inv_res CHECK (units_reserved >= 0),
    CONSTRAINT chk_inv_res_le_avail CHECK (units_reserved <= units_available),
    CONSTRAINT chk_inv_exp CHECK (expiry_date > collection_date),
    CONSTRAINT chk_inv_is_avail CHECK (is_available IN (0, 1))
);

-- -----------------------------------------------------------------------------
-- 6. BLOOD REQUESTS TABLE
-- Pseudonymous request code, no patient identifiers (FR-08, NFR-P1, NFR-P2).
-- -----------------------------------------------------------------------------
CREATE TABLE blood_requests (
    id VARCHAR(36) NOT NULL PRIMARY KEY,
    request_code VARCHAR(30) NOT NULL UNIQUE,
    hospital_id VARCHAR(36) NOT NULL,
    blood_group VARCHAR(5) NOT NULL,
    component_type VARCHAR(20) NOT NULL,
    quantity INTEGER NOT NULL,
    clinician_urgency INTEGER NOT NULL,
    status VARCHAR(20) DEFAULT 'OPEN' NOT NULL,
    priority_score DECIMAL(5, 2) DEFAULT NULL,
    required_by TIMESTAMP NOT NULL,
    request_timestamp TIMESTAMP DEFAULT CURRENT TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT TIMESTAMP NOT NULL,
    CONSTRAINT fk_req_hosp FOREIGN KEY (hospital_id) REFERENCES hospitals(id) ON DELETE RESTRICT,
    CONSTRAINT chk_req_bg CHECK (blood_group IN ('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-')),
    CONSTRAINT chk_req_comp CHECK (component_type IN ('Whole Blood', 'RBC')),
    CONSTRAINT chk_req_qty CHECK (quantity > 0),
    CONSTRAINT chk_req_urg CHECK (clinician_urgency BETWEEN 1 AND 5),
    CONSTRAINT chk_req_status CHECK (status IN ('OPEN', 'HELD', 'CONFIRMED', 'CANCELLED', 'EXPIRED', 'FULFILLED'))
);

-- -----------------------------------------------------------------------------
-- 7. RESERVATIONS TABLE
-- Prevents double allocation across hospitals (PRD 8.4, 8.5).
-- -----------------------------------------------------------------------------
CREATE TABLE reservations (
    id VARCHAR(36) NOT NULL PRIMARY KEY,
    reservation_code VARCHAR(30) NOT NULL UNIQUE,
    request_id VARCHAR(36) NOT NULL,
    inventory_id VARCHAR(36) NOT NULL,
    quantity INTEGER NOT NULL,
    status VARCHAR(20) DEFAULT 'ACTIVE' NOT NULL,
    placed_at TIMESTAMP DEFAULT CURRENT TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    released_at TIMESTAMP DEFAULT NULL,
    confirmed_at TIMESTAMP DEFAULT NULL,
    CONSTRAINT fk_res_req FOREIGN KEY (request_id) REFERENCES blood_requests(id) ON DELETE CASCADE,
    CONSTRAINT fk_res_inv FOREIGN KEY (inventory_id) REFERENCES blood_inventory(id) ON DELETE RESTRICT,
    CONSTRAINT chk_res_qty CHECK (quantity > 0),
    CONSTRAINT chk_res_status CHECK (status IN ('ACTIVE', 'CONFIRMED', 'RELEASED', 'EXPIRED'))
);

-- -----------------------------------------------------------------------------
-- 8. MATCHING RESULTS TABLE
-- -----------------------------------------------------------------------------
CREATE TABLE matching_results (
    id VARCHAR(36) NOT NULL PRIMARY KEY,
    request_id VARCHAR(36) NOT NULL,
    inventory_id VARCHAR(36) NOT NULL,
    rank INTEGER NOT NULL,
    match_score DECIMAL(5, 2) NOT NULL,
    eta_minutes INTEGER NOT NULL,
    distance_km DECIMAL(6, 2) NOT NULL,
    score_breakdown CLOB(10K) NOT NULL,
    explanation CLOB(10K) NOT NULL,
    algorithm_version VARCHAR(20) DEFAULT 'v1.0' NOT NULL,
    weights_used CLOB(10K) NOT NULL,
    is_active SMALLINT DEFAULT 1 NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT TIMESTAMP NOT NULL,
    CONSTRAINT fk_mr_req FOREIGN KEY (request_id) REFERENCES blood_requests(id) ON DELETE CASCADE,
    CONSTRAINT fk_mr_inv FOREIGN KEY (inventory_id) REFERENCES blood_inventory(id) ON DELETE RESTRICT,
    CONSTRAINT chk_mr_rank CHECK (rank >= 1),
    CONSTRAINT chk_mr_score CHECK (match_score BETWEEN 0.00 AND 100.00),
    CONSTRAINT chk_mr_eta CHECK (eta_minutes >= 0),
    CONSTRAINT chk_mr_dist CHECK (distance_km >= 0),
    CONSTRAINT chk_mr_active CHECK (is_active IN (0, 1))
);

-- -----------------------------------------------------------------------------
-- 9. ALERTS TABLE
-- -----------------------------------------------------------------------------
CREATE TABLE alerts (
    id VARCHAR(36) NOT NULL PRIMARY KEY,
    recipient_role VARCHAR(20) NOT NULL,
    recipient_org_id VARCHAR(36) DEFAULT NULL,
    recipient_user_id VARCHAR(36) DEFAULT NULL,
    alert_type VARCHAR(30) NOT NULL,
    title VARCHAR(150) NOT NULL,
    message CLOB(10K) NOT NULL,
    request_id VARCHAR(36) DEFAULT NULL,
    is_read SMALLINT DEFAULT 0 NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT TIMESTAMP NOT NULL,
    CONSTRAINT fk_alt_user FOREIGN KEY (recipient_user_id) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_alt_req FOREIGN KEY (request_id) REFERENCES blood_requests(id) ON DELETE SET NULL,
    CONSTRAINT chk_alt_role CHECK (recipient_role IN ('hospital_user', 'bloodbank_user', 'admin', 'auditor')),
    CONSTRAINT chk_alt_type CHECK (alert_type IN ('MATCH_FOUND', 'SHORTAGE_DETECTED', 'MATCH_EXPIRED', 'ALLOCATED')),
    CONSTRAINT chk_alt_read CHECK (is_read IN (0, 1))
);

-- -----------------------------------------------------------------------------
-- 10. LOCATION DISTANCES TABLE
-- -----------------------------------------------------------------------------
CREATE TABLE location_distances (
    id VARCHAR(36) NOT NULL PRIMARY KEY,
    hospital_id VARCHAR(36) NOT NULL,
    blood_bank_id VARCHAR(36) NOT NULL,
    distance_km DECIMAL(6, 2) NOT NULL,
    estimated_transit_minutes INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT TIMESTAMP NOT NULL,
    CONSTRAINT fk_dist_hosp FOREIGN KEY (hospital_id) REFERENCES hospitals(id) ON DELETE CASCADE,
    CONSTRAINT fk_dist_bb FOREIGN KEY (blood_bank_id) REFERENCES blood_banks(id) ON DELETE CASCADE,
    CONSTRAINT uq_db2_hosp_bb UNIQUE (hospital_id, blood_bank_id),
    CONSTRAINT chk_dist_km CHECK (distance_km >= 0),
    CONSTRAINT chk_dist_eta CHECK (estimated_transit_minutes >= 0)
);

-- -----------------------------------------------------------------------------
-- 11. AUDIT LOGS TABLE
-- Immutable append-only audit trail on IBM Z LinuxONE (Db2)
-- -----------------------------------------------------------------------------
CREATE TABLE audit_logs (
    id VARCHAR(36) NOT NULL PRIMARY KEY,
    sequence_number BIGINT GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1) NOT NULL UNIQUE,
    user_id VARCHAR(36) DEFAULT NULL,
    username VARCHAR(50) DEFAULT NULL,
    user_role VARCHAR(20) DEFAULT NULL,
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(36) DEFAULT NULL,
    old_values CLOB(10K) DEFAULT NULL,
    new_values CLOB(10K) DEFAULT NULL,
    ip_address VARCHAR(45) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT TIMESTAMP NOT NULL,
    prev_hash VARCHAR(64) DEFAULT NULL,
    current_hash VARCHAR(64) DEFAULT NULL,
    CONSTRAINT fk_audit_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- -----------------------------------------------------------------------------
-- DB2 INDEXES
-- -----------------------------------------------------------------------------
CREATE INDEX idx_inv_lookup ON blood_inventory (blood_group, component_type, is_available, expiry_date);
CREATE INDEX idx_inv_bb ON blood_inventory (blood_bank_id);
CREATE INDEX idx_req_stat ON blood_requests (status, clinician_urgency DESC, request_timestamp ASC);
CREATE INDEX idx_req_hosp ON blood_requests (hospital_id);
CREATE INDEX idx_res_stat ON reservations (status, expires_at);
CREATE INDEX idx_mr_req_rnk ON matching_results (request_id, rank);
CREATE INDEX idx_alt_pol ON alerts (recipient_role, recipient_org_id, is_read, created_at DESC);
CREATE INDEX idx_loc_dist ON location_distances (hospital_id, blood_bank_id);
CREATE INDEX idx_aud_seq ON audit_logs (sequence_number);
