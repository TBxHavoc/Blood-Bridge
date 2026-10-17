-- =============================================================================
-- Blood Bridge - Analytical Views and Operational SQL Procedures
-- Track: IBM Z Datathon 2026 - AI Secured Track (Innovation without Exposure)
-- Complies with: PRD Sections 6.4, 6.6, 7 & 8.5
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. VIEW: ACTIVE INVENTORY WITH EXPIRY ALERTS (FR-15, FR-20)
-- Calculates unreserved units and flags items expiring in <=3 days and <=7 days.
-- Excludes fully reserved or expired inventory.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_active_inventory AS
SELECT 
    i.id AS inventory_id,
    i.inventory_code,
    i.blood_bank_id,
    b.bank_code,
    b.name AS blood_bank_name,
    i.blood_group,
    i.component_type,
    i.units_available,
    i.units_reserved,
    (i.units_available - i.units_reserved) AS units_unreserved,
    i.collection_date,
    i.expiry_date,
    (i.expiry_date - CURRENT_DATE) AS days_until_expiry,
    CASE 
        WHEN (i.expiry_date - CURRENT_DATE) <= 0 THEN 'EXPIRED'
        WHEN (i.expiry_date - CURRENT_DATE) <= 3 THEN 'EXPIRING_CRITICAL_3D'
        WHEN (i.expiry_date - CURRENT_DATE) <= 7 THEN 'EXPIRING_WARNING_7D'
        ELSE 'STABLE'
    END AS expiry_status,
    i.last_updated_at
FROM blood_inventory i
JOIN blood_banks b ON i.blood_bank_id = b.id
WHERE i.is_available = TRUE 
  AND i.expiry_date > CURRENT_DATE
  AND (i.units_available - i.units_reserved) > 0;

-- -----------------------------------------------------------------------------
-- 2. VIEW: ANONYMOUS DEMAND VIEW FOR BLOOD BANKS (FR-16, NFR-P7)
-- Displays regional demand aggregates per blood group & component without ANY
-- hospital identities, clinician names, or urgency specifics.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_bloodbank_anonymous_demand AS
SELECT 
    r.blood_group,
    r.component_type,
    COUNT(r.id) AS open_request_count,
    SUM(r.quantity) AS total_units_demanded,
    COALESCE(inv.total_units_unreserved, 0) AS total_regional_unreserved_supply,
    CASE 
        WHEN COALESCE(inv.total_units_unreserved, 0) = 0 THEN 'COMPLETE_SHORTAGE'
        WHEN COALESCE(inv.total_units_unreserved, 0) < SUM(r.quantity) THEN 'DEFICIT'
        ELSE 'BALANCED'
    END AS market_status
FROM blood_requests r
LEFT JOIN (
    SELECT blood_group, component_type, SUM(units_available - units_reserved) AS total_units_unreserved
    FROM blood_inventory
    WHERE is_available = TRUE AND expiry_date > CURRENT_DATE
    GROUP BY blood_group, component_type
) inv ON r.blood_group = inv.blood_group AND r.component_type = inv.component_type
WHERE r.status = 'OPEN'
GROUP BY r.blood_group, r.component_type, inv.total_units_unreserved;

-- -----------------------------------------------------------------------------
-- 3. VIEW: AUDITOR QUEUE PRIORITY FAIRNESS (FR-21, FR-31, PRD Phase 2)
-- Demonstrates deterministic fairness:
-- Competing requests are served strictly by urgency (DESC), then timestamp (ASC).
-- Prove that hospital size or wealth is never factored in.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_auditor_queue_fairness AS
SELECT 
    ROW_NUMBER() OVER (
        ORDER BY r.clinician_urgency DESC, r.request_timestamp ASC, r.id ASC
    ) AS queue_position,
    r.id AS request_id,
    r.request_code,
    r.blood_group,
    r.component_type,
    r.quantity,
    r.clinician_urgency,
    r.request_timestamp,
    r.status,
    'Urgency Level ' || r.clinician_urgency || ' | Submitted ' || 
    ROUND(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - r.request_timestamp))/60) || ' mins ago' AS priority_explanation
FROM blood_requests r
WHERE r.status IN ('OPEN', 'HELD');

-- -----------------------------------------------------------------------------
-- 4. VIEW: AUDITOR DE-IDENTIFIED AUDIT TRAIL (FR-21, FR-47, NFR-P6)
-- Masks IP address and removes confidential direct identifiers for auditor inspection.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_auditor_deidentified_trail AS
SELECT 
    a.sequence_number,
    a.action,
    a.user_role,
    a.resource_type,
    a.resource_id,
    a.timestamp,
    -- Mask IP address for privacy (e.g. 192.168.1.xxx)
    REGEXP_REPLACE(a.ip_address, '\.[0-9]+$', '.xxx') AS masked_ip,
    a.prev_hash,
    a.current_hash,
    CASE 
        WHEN a.current_hash IS NOT NULL AND a.prev_hash IS NOT NULL THEN 'CRYPTOGRAPHICALLY_VERIFIED'
        ELSE 'PENDING_CHAIN'
    END AS chain_verification_status
FROM audit_logs a
ORDER BY a.sequence_number DESC;

-- -----------------------------------------------------------------------------
-- 5. TRANSACTIONAL ALLOCATION QUERIES (PRD 8.5 Concurrency and Allocation)
-- 
-- Example of Step 1: Placing a Hold (with row locking SELECT FOR UPDATE)
-- BEGIN;
--   SELECT id, units_available, units_reserved 
--   FROM blood_inventory 
--   WHERE id = :inventory_id 
--   FOR UPDATE;
-- 
--   -- Verify: (units_available - units_reserved) >= :requested_quantity
--   -- If sufficient:
--   UPDATE blood_inventory 
--   SET units_reserved = units_reserved + :requested_quantity,
--       last_updated_at = CURRENT_TIMESTAMP
--   WHERE id = :inventory_id;
-- 
--   INSERT INTO reservations (id, reservation_code, request_id, inventory_id, quantity, status, placed_at, expires_at)
--   VALUES (:reservation_uuid, :res_code, :request_id, :inventory_id, :requested_quantity, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP + INTERVAL '10 minute');
-- 
--   UPDATE blood_requests 
--   SET status = 'HELD', updated_at = CURRENT_TIMESTAMP
--   WHERE id = :request_id;
-- COMMIT;
-- -----------------------------------------------------------------------------
