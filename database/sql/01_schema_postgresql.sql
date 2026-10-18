-- =============================================================================
-- Blood Bridge - PostgreSQL Database Schema
-- Track: IBM Z Datathon 2026 - AI Secured Track (Innovation without Exposure)
-- Architecture: Local PostgreSQL Fallback & IBM LinuxONE / Db2 Compatible
-- Complies with: PRD v1.0 & SRS v1.0
-- =============================================================================

-- Ensure strict constraints and consistent character encoding
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;

-- -----------------------------------------------------------------------------
-- CLEANUP (Drop tables in reverse dependency order for clean recreation)
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS audit_logs CASCADE;
DROP TABLE IF EXISTS alerts CASCADE;
DROP TABLE IF EXISTS matching_results CASCADE;
DROP TABLE IF EXISTS reservations CASCADE;
DROP TABLE IF EXISTS blood_requests CASCADE;
DROP TABLE IF EXISTS blood_inventory CASCADE;
DROP TABLE IF EXISTS location_distances CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS blood_banks CASCADE;
DROP TABLE IF EXISTS hospitals CASCADE;
DROP TABLE IF EXISTS system_config CASCADE;

-- -----------------------------------------------------------------------------
-- 1. SYSTEM CONFIGURATION TABLE
-- Stores algorithm weights, hold timeout, shortage thresholds.
-- PRD FR-11: "Weights and thresholds are read from system_config, not hard-coded."
-- -----------------------------------------------------------------------------
CREATE TABLE system_config (
    config_key VARCHAR(50) PRIMARY KEY,
    config_value VARCHAR(255) NOT NULL,
    description TEXT,
    data_type VARCHAR(20) DEFAULT 'string' NOT NULL CHECK (data_type IN ('string', 'integer', 'float', 'boolean', 'json')),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- -----------------------------------------------------------------------------
-- 2. HOSPITALS TABLE
-- Holds hospital operational metadata.
-- PRIVACY: Does NOT store patient data. Staged disclosure (NFR-P7) hides
-- hospital name, delivery point, and contact phone until a match is confirmed.
-- -----------------------------------------------------------------------------
CREATE TABLE hospitals (
    id VARCHAR(36) PRIMARY KEY, -- 36-char UUID string for universal Db2/Postgres compatibility
    hospital_code VARCHAR(20) NOT NULL UNIQUE, -- e.g., 'HOSP_001'
    name VARCHAR(150) NOT NULL,
    address TEXT NOT NULL,
    latitude DECIMAL(9, 6) NOT NULL,
    longitude DECIMAL(9, 6) NOT NULL,
    delivery_point VARCHAR(255) NOT NULL, -- e.g., 'Trauma Center, Dock B' (disclosed only upon confirmation)
    contact_phone VARCHAR(30) NOT NULL,
    contact_email VARCHAR(100) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- -----------------------------------------------------------------------------
-- 3. BLOOD BANKS TABLE
-- Holds blood bank inventory facility metadata.
-- -----------------------------------------------------------------------------
CREATE TABLE blood_banks (
    id VARCHAR(36) PRIMARY KEY, -- 36-char UUID string
    bank_code VARCHAR(20) NOT NULL UNIQUE, -- e.g., 'BB_001'
    name VARCHAR(150) NOT NULL,
    address TEXT NOT NULL,
    latitude DECIMAL(9, 6) NOT NULL,
    longitude DECIMAL(9, 6) NOT NULL,
    contact_phone VARCHAR(30) NOT NULL,
    contact_email VARCHAR(100) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- -----------------------------------------------------------------------------
-- 4. USERS & RBAC TABLE
-- Supports hospital_user, bloodbank_user, admin, auditor (FR-04, FR-1).
-- Uses bcrypt/Argon2 hashes. Never accepts role from client input (FR-3).
-- -----------------------------------------------------------------------------
CREATE TABLE users (
    id VARCHAR(36) PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('hospital_user', 'bloodbank_user', 'admin', 'auditor')),
    affiliated_org_type VARCHAR(20) DEFAULT 'none' NOT NULL CHECK (affiliated_org_type IN ('hospital', 'blood_bank', 'none')),
    affiliated_org_id VARCHAR(36) DEFAULT NULL, -- Points to hospitals.id or blood_banks.id
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- -----------------------------------------------------------------------------
-- 5. BLOOD INVENTORY TABLE
-- Anonymized inventory units held by blood banks.
-- STRICT PRIVACY: ZERO donor identifiers (FR-21, NFR-P1).
-- PRD Section 6.4: units_available >= units_reserved, expiry > collection.
-- -----------------------------------------------------------------------------
CREATE TABLE blood_inventory (
    id VARCHAR(36) PRIMARY KEY,
    inventory_code VARCHAR(30) NOT NULL UNIQUE, -- e.g., 'INV-202610-001'
    blood_bank_id VARCHAR(36) NOT NULL REFERENCES blood_banks(id) ON DELETE CASCADE,
    blood_group VARCHAR(5) NOT NULL CHECK (blood_group IN ('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-')),
    component_type VARCHAR(20) NOT NULL CHECK (component_type IN ('Whole Blood', 'RBC')),
    units_available INTEGER NOT NULL CHECK (units_available >= 0),
    units_reserved INTEGER DEFAULT 0 NOT NULL CHECK (units_reserved >= 0),
    collection_date DATE NOT NULL,
    expiry_date DATE NOT NULL,
    is_available BOOLEAN DEFAULT TRUE NOT NULL,
    last_updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT chk_units_reserved_le_available CHECK (units_reserved <= units_available),
    CONSTRAINT chk_expiry_gt_collection CHECK (expiry_date > collection_date)
);

-- -----------------------------------------------------------------------------
-- 6. BLOOD REQUESTS TABLE
-- Emergency blood requests submitted by hospitals.
-- STRICT PRIVACY: ZERO patient identifiers, names, diagnoses (FR-08, NFR-P1).
-- PRD NFR-P2: pseudonymous request code: REQ_ + random suffix (never sequential).
-- State machine (PRD 8.4): OPEN, HELD, CONFIRMED, CANCELLED, EXPIRED, FULFILLED.
-- -----------------------------------------------------------------------------
CREATE TABLE blood_requests (
    id VARCHAR(36) PRIMARY KEY,
    request_code VARCHAR(30) NOT NULL UNIQUE, -- Pseudonymous code e.g., 'REQ_7X9A21'
    hospital_id VARCHAR(36) NOT NULL REFERENCES hospitals(id) ON DELETE RESTRICT,
    blood_group VARCHAR(5) NOT NULL CHECK (blood_group IN ('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-')),
    component_type VARCHAR(20) NOT NULL CHECK (component_type IN ('Whole Blood', 'RBC')),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    clinician_urgency INTEGER NOT NULL CHECK (clinician_urgency BETWEEN 1 AND 5),
    status VARCHAR(20) DEFAULT 'OPEN' NOT NULL CHECK (status IN ('OPEN', 'HELD', 'CONFIRMED', 'CANCELLED', 'EXPIRED', 'FULFILLED')),
    priority_score DECIMAL(5, 2) DEFAULT NULL, -- Overall priority metric across competing requests
    required_by TIMESTAMP WITH TIME ZONE NOT NULL,
    request_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- -----------------------------------------------------------------------------
-- 7. RESERVATIONS TABLE
-- Manages transactional holds and prevents double allocation (PRD 8.2, 8.4, 8.5).
-- Default hold duration: 10 minutes (configurable via system_config).
-- States: ACTIVE, CONFIRMED, RELEASED, EXPIRED.
-- -----------------------------------------------------------------------------
CREATE TABLE reservations (
    id VARCHAR(36) PRIMARY KEY,
    reservation_code VARCHAR(30) NOT NULL UNIQUE, -- e.g., 'RES_3B9F2'
    request_id VARCHAR(36) NOT NULL REFERENCES blood_requests(id) ON DELETE CASCADE,
    inventory_id VARCHAR(36) NOT NULL REFERENCES blood_inventory(id) ON DELETE RESTRICT,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    status VARCHAR(20) DEFAULT 'ACTIVE' NOT NULL CHECK (status IN ('ACTIVE', 'CONFIRMED', 'RELEASED', 'EXPIRED')),
    placed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    released_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    confirmed_at TIMESTAMP WITH TIME ZONE DEFAULT NULL
);

-- -----------------------------------------------------------------------------
-- 8. MATCHING RESULTS TABLE
-- Stores transparent, explainable ranking of eligible inventory units per request.
-- PRD Section 7: ETA (max 50), Expiry (max 30), Freshness (max 20).
-- Human-readable explanation and algorithm version stored for full reproducibility.
-- -----------------------------------------------------------------------------
CREATE TABLE matching_results (
    id VARCHAR(36) PRIMARY KEY,
    request_id VARCHAR(36) NOT NULL REFERENCES blood_requests(id) ON DELETE CASCADE,
    inventory_id VARCHAR(36) NOT NULL REFERENCES blood_inventory(id) ON DELETE RESTRICT,
    rank INTEGER NOT NULL CHECK (rank >= 1),
    match_score DECIMAL(5, 2) NOT NULL CHECK (match_score BETWEEN 0.00 AND 100.00),
    eta_minutes INTEGER NOT NULL CHECK (eta_minutes >= 0),
    distance_km DECIMAL(6, 2) NOT NULL CHECK (distance_km >= 0),
    score_breakdown TEXT NOT NULL, -- JSON string containing factor scores for Db2/Postgres portability
    explanation TEXT NOT NULL, -- Human-readable justification (FR-13, FR-29)
    algorithm_version VARCHAR(20) DEFAULT 'v1.0' NOT NULL,
    weights_used TEXT NOT NULL, -- JSON snapshot of system_config weights applied
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- -----------------------------------------------------------------------------
-- 9. ALERTS TABLE
-- Delivers notifications with unread/read state (PRD 6.5, FR-17, FR-18).
-- Alert types: MATCH_FOUND, SHORTAGE_DETECTED, MATCH_EXPIRED, ALLOCATED.
-- -----------------------------------------------------------------------------
CREATE TABLE alerts (
    id VARCHAR(36) PRIMARY KEY,
    recipient_role VARCHAR(20) NOT NULL CHECK (recipient_role IN ('hospital_user', 'bloodbank_user', 'admin', 'auditor')),
    recipient_org_id VARCHAR(36) DEFAULT NULL, -- hospital_id or blood_bank_id
    recipient_user_id VARCHAR(36) DEFAULT NULL REFERENCES users(id) ON DELETE SET NULL,
    alert_type VARCHAR(30) NOT NULL CHECK (alert_type IN ('MATCH_FOUND', 'SHORTAGE_DETECTED', 'MATCH_EXPIRED', 'ALLOCATED')),
    title VARCHAR(150) NOT NULL,
    message TEXT NOT NULL,
    request_id VARCHAR(36) DEFAULT NULL REFERENCES blood_requests(id) ON DELETE SET NULL,
    is_read BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- -----------------------------------------------------------------------------
-- 10. LOCATION DISTANCES TABLE
-- Precomputed distance and travel ETA matrix between hospitals and blood banks.
-- Precomputed via Haversine formula (PRD Section 10).
-- -----------------------------------------------------------------------------
CREATE TABLE location_distances (
    id VARCHAR(36) PRIMARY KEY,
    hospital_id VARCHAR(36) NOT NULL REFERENCES hospitals(id) ON DELETE CASCADE,
    blood_bank_id VARCHAR(36) NOT NULL REFERENCES blood_banks(id) ON DELETE CASCADE,
    distance_km DECIMAL(6, 2) NOT NULL CHECK (distance_km >= 0),
    estimated_transit_minutes INTEGER NOT NULL CHECK (estimated_transit_minutes >= 0),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT uq_hospital_blood_bank UNIQUE (hospital_id, blood_bank_id)
);

-- -----------------------------------------------------------------------------
-- 11. DELIVERIES TABLE
-- Live delivery and transit tracking from blood bank to hospital.
-- -----------------------------------------------------------------------------
CREATE TABLE deliveries (
    id VARCHAR(36) PRIMARY KEY,
    request_id VARCHAR(36) NOT NULL REFERENCES blood_requests(id) ON DELETE CASCADE,
    blood_bank_id VARCHAR(36) NOT NULL REFERENCES blood_banks(id) ON DELETE CASCADE,
    hospital_id VARCHAR(36) NOT NULL REFERENCES hospitals(id) ON DELETE CASCADE,
    distance_km DECIMAL(6, 2) NOT NULL DEFAULT 0.0 CHECK (distance_km >= 0),
    eta_minutes INTEGER NOT NULL DEFAULT 30 CHECK (eta_minutes >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'DISPATCHED' CHECK (status IN ('DISPATCHED', 'IN_TRANSIT', 'ARRIVING', 'DELIVERED')),
    dispatched_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    delivered_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- -----------------------------------------------------------------------------
-- 12. AUDIT LOGS TABLE
-- Immutable, append-only audit trail (PRD 6.6, FR-19, FR-20, NFR-10, NFR-P5).
-- Stores who, what, resource, old/new value, IP (as text for Db2 compatibility).
-- Stretch Goal / Feature: Cryptographic hash chaining (prev_hash -> current_hash).
-- -----------------------------------------------------------------------------
CREATE TABLE audit_logs (
    id VARCHAR(36) PRIMARY KEY,
    sequence_number BIGINT GENERATED ALWAYS AS IDENTITY NOT NULL UNIQUE,
    user_id VARCHAR(36) DEFAULT NULL REFERENCES users(id) ON DELETE SET NULL,
    username VARCHAR(50) DEFAULT NULL,
    user_role VARCHAR(20) DEFAULT NULL,
    action VARCHAR(50) NOT NULL, -- e.g., 'LOGIN', 'CREATE_REQUEST', 'HOLD_RESERVATION', 'CONFIRM_HOLD', etc.
    resource_type VARCHAR(50) NOT NULL, -- e.g., 'blood_requests', 'blood_inventory', 'reservations'
    resource_id VARCHAR(36) DEFAULT NULL,
    old_values TEXT DEFAULT NULL, -- JSON string or masked text
    new_values TEXT DEFAULT NULL, -- JSON string or masked text
    ip_address VARCHAR(45) NOT NULL, -- Standard text (IPv4 / IPv6) to avoid non-portable INET
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    prev_hash VARCHAR(64) DEFAULT NULL, -- SHA-256 hash of the preceding row
    current_hash VARCHAR(64) DEFAULT NULL -- SHA-256 hash of this record including prev_hash
);

-- -----------------------------------------------------------------------------
-- IMMUTABILITY ENFORCEMENT ON AUDIT LOGS (FR-20, FR-46, NFR-P5)
-- Database-level protection against tampering or record deletion.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_enforce_audit_immutability()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'PERMISSION DENIED: audit_logs is append-only and cannot be modified or deleted.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_no_update ON audit_logs;
CREATE TRIGGER trg_audit_no_update
BEFORE UPDATE OR DELETE ON audit_logs
FOR EACH ROW
EXECUTE FUNCTION trg_enforce_audit_immutability();

-- -----------------------------------------------------------------------------
-- PERFORMANCE INDEXES
-- Optimized for high-concurrency matching, inventory queries, and RBAC filtering.
-- -----------------------------------------------------------------------------

-- Inventory lookup for matching engine (PRD Section 7 Phase 1 Eligibility)
CREATE INDEX idx_inventory_lookup ON blood_inventory (blood_group, component_type, is_available, expiry_date);
CREATE INDEX idx_inventory_bank ON blood_inventory (blood_bank_id);
CREATE INDEX idx_inventory_expiry ON blood_inventory (expiry_date);

-- Request status & queue prioritisation (PRD Section 7 Phase 2 Priority)
CREATE INDEX idx_requests_status_urgency ON blood_requests (status, clinician_urgency DESC, request_timestamp ASC);
CREATE INDEX idx_requests_hospital ON blood_requests (hospital_id);
CREATE INDEX idx_requests_code ON blood_requests (request_code);

-- Hold reservations and timeout release index (PRD Section 8.4, 8.5)
CREATE INDEX idx_reservations_status_expires ON reservations (status, expires_at);
CREATE INDEX idx_reservations_request ON reservations (request_id);
CREATE INDEX idx_reservations_inventory ON reservations (inventory_id);

-- Matching results lookup
CREATE INDEX idx_matches_request_rank ON matching_results (request_id, rank);
CREATE INDEX idx_matches_active ON matching_results (request_id, is_active);

-- Real-time alerts polling (PRD Section 8.6: polls every 5-10s)
CREATE INDEX idx_alerts_polling ON alerts (recipient_role, recipient_org_id, is_read, created_at DESC);
CREATE INDEX idx_alerts_user ON alerts (recipient_user_id, is_read);

-- Distance matrix fast lookup
CREATE INDEX idx_distances_lookup ON location_distances (hospital_id, blood_bank_id);

-- User login and RBAC verification
CREATE INDEX idx_users_username ON users (username);
CREATE INDEX idx_users_email ON users (email);
CREATE INDEX idx_users_org ON users (affiliated_org_type, affiliated_org_id);

-- Audit log query index for auditors
CREATE INDEX idx_audit_timestamp ON audit_logs (timestamp DESC);
CREATE INDEX idx_audit_resource ON audit_logs (resource_type, resource_id);
CREATE INDEX idx_audit_seq ON audit_logs (sequence_number);

-- Deliveries tracking indexes
CREATE INDEX idx_deliveries_request ON deliveries (request_id);
CREATE INDEX idx_deliveries_hospital ON deliveries (hospital_id);
CREATE INDEX idx_deliveries_status ON deliveries (status);

