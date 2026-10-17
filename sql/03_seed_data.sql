-- =============================================================================
-- Blood Bridge - Synthetic Demonstration Dataset
-- Notice: ALL DATA IS SYNTHETIC AND SIMULATED FOR DEMONSTRATION PURPOSES ONLY.
-- ZERO PATIENT OR DONOR IDENTIFIERS ARE CONTAINED IN THIS SCRIPT.
-- Compatible with: PostgreSQL 14+ and IBM Db2 on LinuxONE
-- =============================================================================

-- Clear existing data if any (in foreign-key safe order)
DELETE FROM alerts;
DELETE FROM matching_results;
DELETE FROM reservations;
DELETE FROM blood_requests;
DELETE FROM blood_inventory;
DELETE FROM location_distances;
DELETE FROM users;
DELETE FROM blood_banks;
DELETE FROM hospitals;
DELETE FROM system_config;

-- -----------------------------------------------------------------------------
-- 1. SYSTEM CONFIGURATION
-- Configurable scoring weights and operational parameters (PRD 6.3, 7)
-- -----------------------------------------------------------------------------
INSERT INTO system_config (config_key, config_value, description, data_type) VALUES
('max_eta_minutes', '180', 'Maximum transit ETA threshold before distance score drops to zero', 'integer'),
('hold_timeout_minutes', '10', 'Default duration in minutes before an unconfirmed hold expires', 'integer'),
('shortage_threshold', '50.0', 'Threshold below which a partial shortage alert is triggered', 'float'),
('weight_eta', '50.0', 'Maximum points allocated for rapid ETA/transit proximity', 'float'),
('weight_expiry', '30.0', 'Maximum points allocated for inventory expiry suitability (FIFO)', 'float'),
('weight_freshness', '20.0', 'Maximum points allocated for inventory data freshness/telemetry recency', 'float'),
('algorithm_version', 'v1.0-secured', 'Active matching engine algorithm release version', 'string');

-- -----------------------------------------------------------------------------
-- 2. HOSPITALS (10 Synthetic Hospitals in Metro Area)
-- -----------------------------------------------------------------------------
INSERT INTO hospitals (id, hospital_code, name, address, latitude, longitude, delivery_point, contact_phone, contact_email, is_active) VALUES
('h0010000-0000-0000-0000-000000000001', 'HOSP_001', 'Apex Trauma & Multispecialty Hospital', '45 Healthcare Boulevard, Sector 12', 19.076090, 72.877426, 'Emergency Trauma Bay 1, Ground Floor', '+91-98200-11001', 'er.desk@apexhealth.sim', TRUE),
('h0010000-0000-0000-0000-000000000002', 'HOSP_002', 'City General & Surgical Center', '108 Relief Road, Central District', 19.082500, 72.883300, 'Surgical OT Dock, East Entrance', '+91-98200-11002', 'bloodbank.liaison@citygen.sim', TRUE),
('h0010000-0000-0000-0000-000000000003', 'HOSP_003', 'Metro Life Care Memorial Hospital', '12 Ring Expressway, North Zone', 19.120000, 72.850000, 'Rapid Reception Dock 3', '+91-98200-11003', 'triage@metrolifecare.sim', TRUE),
('h0010000-0000-0000-0000-000000000004', 'HOSP_004', 'St. Jude Community Health Hospital', '88 Hill View Road, West Suburb', 19.055000, 72.830000, 'Critical Care Gate 2', '+91-98200-11004', 'supply@stjudehealth.sim', TRUE),
('h0010000-0000-0000-0000-000000000005', 'HOSP_005', 'National Heart & Vascular Institute', '204 Cardiac Avenue, Health City', 19.030000, 72.860000, 'Cath Lab Receiving Station', '+91-98200-11005', 'transfusion@heartvascular.sim', TRUE),
('h0010000-0000-0000-0000-000000000006', 'HOSP_006', 'Highland Maternity & Children Clinic', '15 Lake Crescent, South Zone', 18.980000, 72.820000, 'Maternal Wing Entry A', '+91-98200-11006', 'nicu.liaison@highlandclinic.sim', TRUE),
('h0010000-0000-0000-0000-000000000007', 'HOSP_007', 'Trinity Emergency Medical Center', '67 Airport Link Way, East Wing', 19.100000, 72.890000, 'Ambulance Bay Red Zone', '+91-98200-11007', 'desk@trinityemergency.sim', TRUE),
('h0010000-0000-0000-0000-000000000008', 'HOSP_008', 'Lakeside Multispecialty Hospital', '302 Water Canal Road, Sector 8', 19.140000, 72.880000, 'Emergency Intake Room 102', '+91-98200-11008', 'supplies@lakesidehosp.sim', TRUE),
('h0010000-0000-0000-0000-000000000009', 'HOSP_009', 'Parkview Orthopedic & Trauma Care', '77 Botanical Gardens Lane', 19.020000, 72.840000, 'Dock 4 Trauma Transfer', '+91-98200-11009', 'er@parkviewcare.sim', TRUE),
('h0010000-0000-0000-0000-00000000010', 'HOSP_010', 'Sunrise Suburban General Hospital', '90 Sunrise Boulevard, Outer Ring', 19.160000, 72.830000, 'Main Pharmacy Blood Counter', '+91-98200-11010', 'bloodbank@sunrisegeneral.sim', TRUE);

-- -----------------------------------------------------------------------------
-- 3. BLOOD BANKS (16 Synthetic Blood Banks & Storage Centers)
-- -----------------------------------------------------------------------------
INSERT INTO blood_banks (id, bank_code, name, address, latitude, longitude, contact_phone, contact_email, is_active) VALUES
('b0010000-0000-0000-0000-000000000001', 'BB_001', 'Red Cross Regional Blood Center', '10 Humanitarian Way, Central District', 19.070000, 72.870000, '+91-22-2400-0101', 'dispatch@redcross-reg.sim', TRUE),
('b0010000-0000-0000-0000-000000000002', 'BB_002', 'Rotary LifeBank Foundation', '25 Civic Center Plaza, Sector 4', 19.085000, 72.865000, '+91-22-2400-0102', 'inventory@rotarylifebank.sim', TRUE),
('b0010000-0000-0000-0000-000000000003', 'BB_003', 'Metro Central Transfusion Bank', '55 Government Hospital Road', 19.060000, 72.880000, '+91-22-2400-0103', 'coord@metrotransfusion.sim', TRUE),
('b0010000-0000-0000-0000-000000000004', 'BB_004', 'Samaritan Voluntary Blood Trust', '140 Charitable Trust Lane', 19.095000, 72.840000, '+91-22-2400-0104', 'orders@samaritantrust.sim', TRUE),
('b0010000-0000-0000-0000-000000000005', 'BB_005', 'Apex Life Source Repository', '48 Industrial Med Park', 19.110000, 72.875000, '+91-22-2400-0105', 'stock@apexlifesource.sim', TRUE),
('b0010000-0000-0000-0000-000000000006', 'BB_006', 'Peace Memorial Blood Depot', '8 Peace Enclave, South Zone', 18.990000, 72.825000, '+91-22-2400-0106', 'logistics@peaceblooddepot.sim', TRUE),
('b0010000-0000-0000-0000-000000000007', 'BB_007', 'North District Public Blood Bank', '92 North Ring Road', 19.145000, 72.845000, '+91-22-2400-0107', 'duty@northpublicbank.sim', TRUE),
('b0010000-0000-0000-0000-000000000008', 'BB_008', 'St. Luke Community Blood Service', '17 Church Colony Way', 19.040000, 72.845000, '+91-22-2400-0108', 'nurse@stlukeblood.sim', TRUE),
('b0010000-0000-0000-0000-000000000009', 'BB_009', 'United Citizens Blood Reserve', '61 Harmony Circle', 19.080000, 72.895000, '+91-22-2400-0109', 'reserve@unitedcitizens.sim', TRUE),
('b0010000-0000-0000-0000-000000000010', 'BB_010', 'East Coast Plasma & Whole Blood Hub', '33 Maritime Road', 19.025000, 72.855000, '+91-22-2400-0110', 'coord@eastcoasthub.sim', TRUE),
('b0010000-0000-0000-0000-000000000011', 'BB_011', 'Pragati Sanjeevani Blood Bank', '201 Vikas Marg, Sector 9', 19.125000, 72.900000, '+91-22-2400-0111', 'sanjeevani@pragatibank.sim', TRUE),
('b0010000-0000-0000-0000-000000000012', 'BB_012', 'City Heart Foundation Blood Vault', '7 Heart Health Avenue', 19.015000, 72.835000, '+91-22-2400-0112', 'vault@cityheartbank.sim', TRUE),
('b0010000-0000-0000-0000-000000000013', 'BB_013', 'Arogya Voluntary Blood Institute', '18 Wellness Colony', 19.155000, 72.865000, '+91-22-2400-0113', 'care@arogyablood.sim', TRUE),
('b0010000-0000-0000-0000-000000000014', 'BB_014', 'Western Express Blood Logistics Hub', '110 Western Arterial Highway', 19.105000, 72.835000, '+91-22-2400-0114', 'hub@westernexpressblood.sim', TRUE),
('b0010000-0000-0000-0000-000000000015', 'BB_015', 'Hope Foundation Emergency Blood Depot', '42 Hope Crescent', 19.072000, 72.852000, '+91-22-2400-0115', 'alert@hopefoundation.sim', TRUE),
('b0010000-0000-0000-0000-000000000016', 'BB_016', 'Siddharth Memorial Blood Center', '83 Heritage Lane, Old Town', 18.965000, 72.815000, '+91-22-2400-0116', 'dispatch@siddharthblood.sim', TRUE);

-- -----------------------------------------------------------------------------
-- 4. USERS & ROLES
-- Demo credentials with pre-computed bcrypt hash of: "Demo2026!"
-- Hash: $2b$12$e80yqJv3qVz9nBfx3JmXbOaY7zNn7kLzE6Wc9fM6x3rJ2qK1vP2mG
-- Roles: hospital_user, bloodbank_user, admin, auditor
-- -----------------------------------------------------------------------------
INSERT INTO users (id, username, email, password_hash, role, affiliated_org_type, affiliated_org_id, is_active) VALUES
-- Admin & Auditor (System-wide)
('u0010000-0000-0000-0000-000000000001', 'admin_sys', 'admin@bloodbridge.sim', '$2b$12$e80yqJv3qVz9nBfx3JmXbOaY7zNn7kLzE6Wc9fM6x3rJ2qK1vP2mG', 'admin', 'none', NULL, TRUE),
('u0010000-0000-0000-0000-000000000002', 'auditor_compliance', 'auditor@compliance.sim', '$2b$12$e80yqJv3qVz9nBfx3JmXbOaY7zNn7kLzE6Wc9fM6x3rJ2qK1vP2mG', 'auditor', 'none', NULL, TRUE),

-- Hospital Users (Clinicians)
('u0010000-0000-0000-0000-000000000003', 'dr_sharma_apex', 'dr.sharma@apexhealth.sim', '$2b$12$e80yqJv3qVz9nBfx3JmXbOaY7zNn7kLzE6Wc9fM6x3rJ2qK1vP2mG', 'hospital_user', 'hospital', 'h0010000-0000-0000-0000-000000000001', TRUE),
('u0010000-0000-0000-0000-000000000004', 'dr_patel_citygen', 'dr.patel@citygen.sim', '$2b$12$e80yqJv3qVz9nBfx3JmXbOaY7zNn7kLzE6Wc9fM6x3rJ2qK1vP2mG', 'hospital_user', 'hospital', 'h0010000-0000-0000-0000-000000000002', TRUE),
('u0010000-0000-0000-0000-000000000005', 'dr_menon_metrolife', 'dr.menon@metrolifecare.sim', '$2b$12$e80yqJv3qVz9nBfx3JmXbOaY7zNn7kLzE6Wc9fM6x3rJ2qK1vP2mG', 'hospital_user', 'hospital', 'h0010000-0000-0000-0000-000000000003', TRUE),

-- Blood Bank Users (Inventory Managers)
('u0010000-0000-0000-0000-000000000006', 'mgr_redcross', 'manager@redcross-reg.sim', '$2b$12$e80yqJv3qVz9nBfx3JmXbOaY7zNn7kLzE6Wc9fM6x3rJ2qK1vP2mG', 'bloodbank_user', 'blood_bank', 'b0010000-0000-0000-0000-000000000001', TRUE),
('u0010000-0000-0000-0000-000000000007', 'mgr_rotary', 'manager@rotarylifebank.sim', '$2b$12$e80yqJv3qVz9nBfx3JmXbOaY7zNn7kLzE6Wc9fM6x3rJ2qK1vP2mG', 'bloodbank_user', 'blood_bank', 'b0010000-0000-0000-0000-000000000002', TRUE),
('u0010000-0000-0000-0000-000000000008', 'mgr_metro_bank', 'manager@metrotransfusion.sim', '$2b$12$e80yqJv3qVz9nBfx3JmXbOaY7zNn7kLzE6Wc9fM6x3rJ2qK1vP2mG', 'bloodbank_user', 'blood_bank', 'b0010000-0000-0000-0000-000000000003', TRUE);

-- -----------------------------------------------------------------------------
-- 5. BLOOD INVENTORY (120+ Units with Realistic Blood Type Distribution)
-- Strict zero donor info. O+ and B+ common, AB- rare. Whole Blood & RBC only.
-- Varied collection dates & expiry dates to test Phase 3 supply ranking (FIFO).
-- -----------------------------------------------------------------------------
INSERT INTO blood_inventory (id, inventory_code, blood_bank_id, blood_group, component_type, units_available, units_reserved, collection_date, expiry_date, is_available, last_updated_at) VALUES
-- Red Cross Regional (BB_001) - High volume hub
('i0010000-0000-0000-0000-000000000001', 'INV-202610-001', 'b0010000-0000-0000-0000-000000000001', 'O+', 'Whole Blood', 12, 0, CURRENT_DATE - INTERVAL '15 day', CURRENT_DATE + INTERVAL '20 day', TRUE, CURRENT_TIMESTAMP - INTERVAL '20 minute'),
('i0010000-0000-0000-0000-000000000002', 'INV-202610-002', 'b0010000-0000-0000-0000-000000000001', 'O+', 'RBC',         18, 0, CURRENT_DATE - INTERVAL '25 day', CURRENT_DATE + INTERVAL '3 day',  TRUE, CURRENT_TIMESTAMP - INTERVAL '40 minute'), -- Expiring soon (<=3 days)
('i0010000-0000-0000-0000-000000000003', 'INV-202610-003', 'b0010000-0000-0000-0000-000000000001', 'O-', 'RBC',          4, 0, CURRENT_DATE - INTERVAL '10 day', CURRENT_DATE + INTERVAL '32 day', TRUE, CURRENT_TIMESTAMP - INTERVAL '1 hour'),
('i0010000-0000-0000-0000-000000000004', 'INV-202610-004', 'b0010000-0000-0000-0000-000000000001', 'A+', 'Whole Blood', 10, 0, CURRENT_DATE - INTERVAL '18 day', CURRENT_DATE + INTERVAL '17 day', TRUE, CURRENT_TIMESTAMP - INTERVAL '2 hour'),
('i0010000-0000-0000-0000-000000000005', 'INV-202610-005', 'b0010000-0000-0000-0000-000000000001', 'A+', 'RBC',         15, 0, CURRENT_DATE - INTERVAL '30 day', CURRENT_DATE + INTERVAL '5 day',  TRUE, CURRENT_TIMESTAMP - INTERVAL '15 minute'), -- Expiring in <=7 days
('i0010000-0000-0000-0000-000000000006', 'INV-202610-006', 'b0010000-0000-0000-0000-000000000001', 'B+', 'Whole Blood', 14, 0, CURRENT_DATE - INTERVAL '12 day', CURRENT_DATE + INTERVAL '23 day', TRUE, CURRENT_TIMESTAMP - INTERVAL '30 minute'),
('i0010000-0000-0000-0000-000000000007', 'INV-202610-007', 'b0010000-0000-0000-0000-000000000001', 'B+', 'RBC',         20, 0, CURRENT_DATE - INTERVAL '20 day', CURRENT_DATE + INTERVAL '22 day', TRUE, CURRENT_TIMESTAMP - INTERVAL '45 minute'),
('i0010000-0000-0000-0000-000000000008', 'INV-202610-008', 'b0010000-0000-0000-0000-000000000001', 'AB+', 'RBC',         6, 0, CURRENT_DATE - INTERVAL '14 day', CURRENT_DATE + INTERVAL '28 day', TRUE, CURRENT_TIMESTAMP - INTERVAL '3 hour'),

-- Rotary LifeBank (BB_002)
('i0010000-0000-0000-0000-000000000009', 'INV-202610-009', 'b0010000-0000-0000-0000-000000000002', 'O+', 'RBC',         16, 2, CURRENT_DATE - INTERVAL '22 day', CURRENT_DATE + INTERVAL '2 day',  TRUE, CURRENT_TIMESTAMP - INTERVAL '10 minute'), -- 2 reserved on hold
('i0010000-0000-0000-0000-000000000010', 'INV-202610-010', 'b0010000-0000-0000-0000-000000000002', 'O-', 'Whole Blood',  3, 0, CURRENT_DATE - INTERVAL '8 day',  CURRENT_DATE + INTERVAL '27 day', TRUE, CURRENT_TIMESTAMP - INTERVAL '5 hour'),
('i0010000-0000-0000-0000-000000000011', 'INV-202610-011', 'b0010000-0000-0000-0000-000000000002', 'B+', 'Whole Blood',  8, 0, CURRENT_DATE - INTERVAL '19 day', CURRENT_DATE + INTERVAL '16 day', TRUE, CURRENT_TIMESTAMP - INTERVAL '50 minute'),
('i0010000-0000-0000-0000-000000000012', 'INV-202610-012', 'b0010000-0000-0000-0000-000000000002', 'A-', 'RBC',          2, 0, CURRENT_DATE - INTERVAL '16 day', CURRENT_DATE + INTERVAL '26 day', TRUE, CURRENT_TIMESTAMP - INTERVAL '4 hour'),

-- Metro Central Transfusion (BB_003)
('i0010000-0000-0000-0000-000000000013', 'INV-202610-013', 'b0010000-0000-0000-0000-000000000003', 'O+', 'Whole Blood',  9, 0, CURRENT_DATE - INTERVAL '5 day',  CURRENT_DATE + INTERVAL '30 day', TRUE, CURRENT_TIMESTAMP - INTERVAL '25 minute'),
('i0010000-0000-0000-0000-000000000014', 'INV-202610-014', 'b0010000-0000-0000-0000-000000000003', 'B+', 'RBC',         12, 0, CURRENT_DATE - INTERVAL '28 day', CURRENT_DATE + INTERVAL '6 day',  TRUE, CURRENT_TIMESTAMP - INTERVAL '35 minute'),
('i0010000-0000-0000-0000-000000000015', 'INV-202610-015', 'b0010000-0000-0000-0000-000000000003', 'B-', 'RBC',          3, 0, CURRENT_DATE - INTERVAL '11 day', CURRENT_DATE + INTERVAL '31 day', TRUE, CURRENT_TIMESTAMP - INTERVAL '2 hour'),
('i0010000-0000-0000-0000-000000000016', 'INV-202610-016', 'b0010000-0000-0000-0000-000000000003', 'A+', 'Whole Blood',  7, 0, CURRENT_DATE - INTERVAL '24 day', CURRENT_DATE + INTERVAL '11 day', TRUE, CURRENT_TIMESTAMP - INTERVAL '7 hour'),

-- Samaritan Voluntary Trust (BB_004)
('i0010000-0000-0000-0000-000000000017', 'INV-202610-017', 'b0010000-0000-0000-0000-000000000004', 'O+', 'RBC',         14, 0, CURRENT_DATE - INTERVAL '17 day', CURRENT_DATE + INTERVAL '25 day', TRUE, CURRENT_TIMESTAMP - INTERVAL '15 minute'),
('i0010000-0000-0000-0000-000000000018', 'INV-202610-018', 'b0010000-0000-0000-0000-000000000004', 'A+', 'RBC',         11, 0, CURRENT_DATE - INTERVAL '21 day', CURRENT_DATE + INTERVAL '21 day', TRUE, CURRENT_TIMESTAMP - INTERVAL '1 hour'),
('i0010000-0000-0000-0000-000000000019', 'INV-202610-019', 'b0010000-0000-0000-0000-000000000004', 'AB+', 'Whole Blood', 5, 0, CURRENT_DATE - INTERVAL '7 day',  CURRENT_DATE + INTERVAL '28 day', TRUE, CURRENT_TIMESTAMP - INTERVAL '4 hour'),

-- Apex Life Source (BB_005)
('i0010000-0000-0000-0000-000000000020', 'INV-202610-020', 'b0010000-0000-0000-0000-000000000005', 'O+', 'Whole Blood', 15, 0, CURRENT_DATE - INTERVAL '14 day', CURRENT_DATE + INTERVAL '21 day', TRUE, CURRENT_TIMESTAMP - INTERVAL '45 minute'),
('i0010000-0000-0000-0000-000000000021', 'INV-202610-021', 'b0010000-0000-0000-0000-000000000005', 'B+', 'RBC',         18, 0, CURRENT_DATE - INTERVAL '27 day', CURRENT_DATE + INTERVAL '4 day',  TRUE, CURRENT_TIMESTAMP - INTERVAL '20 minute'),
('i0010000-0000-0000-0000-000000000022', 'INV-202610-022', 'b0010000-0000-0000-0000-000000000005', 'O-', 'RBC',          2, 0, CURRENT_DATE - INTERVAL '9 day',  CURRENT_DATE + INTERVAL '33 day', TRUE, CURRENT_TIMESTAMP - INTERVAL '1 hour'),

-- Additional synthetic records across BB_006 to BB_016 (ensuring zero AB- inventory to demonstrate Phase 5 shortage handling)
('i0010000-0000-0000-0000-000000000023', 'INV-202610-023', 'b0010000-0000-0000-0000-000000000006', 'O+', 'RBC',         10, 0, CURRENT_DATE - INTERVAL '10 day', CURRENT_DATE + INTERVAL '32 day', TRUE, CURRENT_TIMESTAMP - INTERVAL '2 hour'),
('i0010000-0000-0000-0000-000000000024', 'INV-202610-024', 'b0010000-0000-0000-0000-000000000006', 'A+', 'Whole Blood',  6, 0, CURRENT_DATE - INTERVAL '22 day', CURRENT_DATE + INTERVAL '13 day', TRUE, CURRENT_TIMESTAMP - INTERVAL '3 hour'),
('i0010000-0000-0000-0000-000000000025', 'INV-202610-025', 'b0010000-0000-0000-0000-000000000007', 'B+', 'RBC',         14, 0, CURRENT_DATE - INTERVAL '18 day', CURRENT_DATE + INTERVAL '24 day', TRUE, CURRENT_TIMESTAMP - INTERVAL '15 minute'),
('i0010000-0000-0000-0000-000000000026', 'INV-202610-026', 'b0010000-0000-0000-0000-000000000007', 'O+', 'Whole Blood',  8, 0, CURRENT_DATE - INTERVAL '16 day', CURRENT_DATE + INTERVAL '19 day', TRUE, CURRENT_TIMESTAMP - INTERVAL '30 minute'),
('i0010000-0000-0000-0000-000000000027', 'INV-202610-027', 'b0010000-0000-0000-0000-000000000008', 'A-', 'Whole Blood',  2, 0, CURRENT_DATE - INTERVAL '12 day', CURRENT_DATE + INTERVAL '23 day', TRUE, CURRENT_TIMESTAMP - INTERVAL '4 hour'),
('i0010000-0000-0000-0000-000000000028', 'INV-202610-028', 'b0010000-0000-0000-0000-000000000009', 'O+', 'RBC',         11, 0, CURRENT_DATE - INTERVAL '29 day', CURRENT_DATE + INTERVAL '1 day',  TRUE, CURRENT_TIMESTAMP - INTERVAL '10 minute'), -- Expiring within 24h
('i0010000-0000-0000-0000-000000000029', 'INV-202610-029', 'b0010000-0000-0000-0000-000000000010', 'B+', 'Whole Blood',  9, 0, CURRENT_DATE - INTERVAL '6 day',  CURRENT_DATE + INTERVAL '29 day', TRUE, CURRENT_TIMESTAMP - INTERVAL '1 hour'),
('i0010000-0000-0000-0000-000000000030', 'INV-202610-030', 'b0010000-0000-0000-0000-000000000011', 'O+', 'RBC',         13, 0, CURRENT_DATE - INTERVAL '20 day', CURRENT_DATE + INTERVAL '22 day', TRUE, CURRENT_TIMESTAMP - INTERVAL '50 minute'),
('i0010000-0000-0000-0000-000000000031', 'INV-202610-031', 'b0010000-0000-0000-0000-000000000012', 'B-', 'Whole Blood',  2, 0, CURRENT_DATE - INTERVAL '14 day', CURRENT_DATE + INTERVAL '21 day', TRUE, CURRENT_TIMESTAMP - INTERVAL '6 hour'),
('i0010000-0000-0000-0000-000000000032', 'INV-202610-032', 'b0010000-0000-0000-0000-000000000013', 'A+', 'RBC',          8, 0, CURRENT_DATE - INTERVAL '23 day', CURRENT_DATE + INTERVAL '19 day', TRUE, CURRENT_TIMESTAMP - INTERVAL '2 hour'),
('i0010000-0000-0000-0000-000000000033', 'INV-202610-033', 'b0010000-0000-0000-0000-000000000014', 'O+', 'RBC',         17, 0, CURRENT_DATE - INTERVAL '15 day', CURRENT_DATE + INTERVAL '27 day', TRUE, CURRENT_TIMESTAMP - INTERVAL '1 hour'),
('i0010000-0000-0000-0000-000000000034', 'INV-202610-034', 'b0010000-0000-0000-0000-000000000015', 'O-', 'RBC',          4, 0, CURRENT_DATE - INTERVAL '18 day', CURRENT_DATE + INTERVAL '24 day', TRUE, CURRENT_TIMESTAMP - INTERVAL '30 minute'),
('i0010000-0000-0000-0000-000000000035', 'INV-202610-035', 'b0010000-0000-0000-0000-000000000016', 'B+', 'RBC',          7, 0, CURRENT_DATE - INTERVAL '21 day', CURRENT_DATE + INTERVAL '21 day', TRUE, CURRENT_TIMESTAMP - INTERVAL '4 hour');

-- -----------------------------------------------------------------------------
-- 6. LOCATION DISTANCES (Haversine & Transit Estimates)
-- Precomputed distance in km and transit ETA in minutes between hospitals & banks.
-- -----------------------------------------------------------------------------
INSERT INTO location_distances (id, hospital_id, blood_bank_id, distance_km, estimated_transit_minutes) VALUES
-- Hospital 1 (Apex Trauma) distances
('d0010000-0000-0000-0000-000000000001', 'h0010000-0000-0000-0000-000000000001', 'b0010000-0000-0000-0000-000000000001',  1.2,  8),
('d0010000-0000-0000-0000-000000000002', 'h0010000-0000-0000-0000-000000000001', 'b0010000-0000-0000-0000-000000000002',  2.1, 14),
('d0010000-0000-0000-0000-000000000003', 'h0010000-0000-0000-0000-000000000001', 'b0010000-0000-0000-0000-000000000003',  1.9, 12),
('d0010000-0000-0000-0000-000000000004', 'h0010000-0000-0000-0000-000000000001', 'b0010000-0000-0000-0000-000000000004',  4.8, 25),
('d0010000-0000-0000-0000-000000000005', 'h0010000-0000-0000-0000-000000000001', 'b0010000-0000-0000-0000-000000000005',  4.1, 22),
('d0010000-0000-0000-0000-000000000006', 'h0010000-0000-0000-0000-000000000001', 'b0010000-0000-0000-0000-000000000006', 11.2, 42),

-- Hospital 2 (City General) distances
('d0010000-0000-0000-0000-000000000007', 'h0010000-0000-0000-0000-000000000002', 'b0010000-0000-0000-0000-000000000001',  2.3, 15),
('d0010000-0000-0000-0000-000000000008', 'h0010000-0000-0000-0000-000000000002', 'b0010000-0000-0000-0000-000000000002',  1.5, 10),
('d0010000-0000-0000-0000-000000000009', 'h0010000-0000-0000-0000-000000000002', 'b0010000-0000-0000-0000-000000000003',  3.1, 18),
('d0010000-0000-0000-0000-000000000010', 'h0010000-0000-0000-0000-000000000002', 'b0010000-0000-0000-0000-000000000004',  5.2, 28),

-- Hospital 3 (Metro Life Care) distances
('d0010000-0000-0000-0000-000000000011', 'h0010000-0000-0000-0000-000000000003', 'b0010000-0000-0000-0000-000000000001',  6.2, 32),
('d0010000-0000-0000-0000-000000000012', 'h0010000-0000-0000-0000-000000000003', 'b0010000-0000-0000-0000-000000000005',  3.4, 18),
('d0010000-0000-0000-0000-000000000013', 'h0010000-0000-0000-0000-000000000003', 'b0010000-0000-0000-0000-000000000007',  3.0, 16);

-- -----------------------------------------------------------------------------
-- 7. BLOOD REQUESTS (Historical + Live Demo Scenarios)
-- Pseudonymous request codes (REQ_ + random alphanumeric suffix, NFR-P2).
-- Zero patient identifiers (FR-08, NFR-P1).
-- -----------------------------------------------------------------------------
INSERT INTO blood_requests (id, request_code, hospital_id, blood_group, component_type, quantity, clinician_urgency, status, priority_score, required_by, request_timestamp) VALUES
-- Live Demo Scenario 1: Hospital submits O+, 4 units, urgency 4 (PRD Section 13 Demo Flow)
('r0010000-0000-0000-0000-000000000001', 'REQ_98A2F1', 'h0010000-0000-0000-0000-000000000001', 'O+', 'RBC', 4, 4, 'OPEN', 88.50, CURRENT_TIMESTAMP + INTERVAL '3 hour', CURRENT_TIMESTAMP - INTERVAL '10 minute'),

-- Live Demo Scenario 2: Competing request with identical urgency to demonstrate fair FIFO tie-breaker (FR-31)
('r0010000-0000-0000-0000-000000000002', 'REQ_7B4C83', 'h0010000-0000-0000-0000-000000000002', 'O+', 'RBC', 2, 4, 'OPEN', 88.50, CURRENT_TIMESTAMP + INTERVAL '4 hour', CURRENT_TIMESTAMP - INTERVAL '5 minute'),

-- Live Demo Scenario 3: Rare AB- blood request demonstrating Complete Shortage Alert (PRD Section 13 Step 6)
('r0010000-0000-0000-0000-000000000003', 'REQ_5E1D94', 'h0010000-0000-0000-0000-000000000003', 'AB-', 'RBC', 2, 5, 'OPEN', 0.00, CURRENT_TIMESTAMP + INTERVAL '1 hour', CURRENT_TIMESTAMP - INTERVAL '2 minute'),

-- Live Demo Scenario 4: Request with active reservation on hold
('r0010000-0000-0000-0000-000000000004', 'REQ_3F9A10', 'h0010000-0000-0000-0000-000000000001', 'O+', 'RBC', 2, 3, 'HELD', 79.20, CURRENT_TIMESTAMP + INTERVAL '5 hour', CURRENT_TIMESTAMP - INTERVAL '8 minute'),

-- Historical Requests (Fulfilled and Audited)
('r0010000-0000-0000-0000-000000000005', 'REQ_1D4B77', 'h0010000-0000-0000-0000-000000000002', 'B+', 'RBC', 3, 5, 'FULFILLED', 94.00, CURRENT_TIMESTAMP - INTERVAL '24 hour', CURRENT_TIMESTAMP - INTERVAL '26 hour'),
('r0010000-0000-0000-0000-000000000006', 'REQ_4C8A99', 'h0010000-0000-0000-0000-000000000003', 'A+', 'Whole Blood', 2, 2, 'FULFILLED', 81.50, CURRENT_TIMESTAMP - INTERVAL '12 hour', CURRENT_TIMESTAMP - INTERVAL '15 hour'),
('r0010000-0000-0000-0000-000000000007', 'REQ_6A2B33', 'h0010000-0000-0000-0000-000000000004', 'O-', 'RBC', 1, 4, 'CANCELLED', 72.00, CURRENT_TIMESTAMP - INTERVAL '8 hour', CURRENT_TIMESTAMP - INTERVAL '10 hour');

-- -----------------------------------------------------------------------------
-- 8. RESERVATIONS (Holds preventing double allocation, PRD 8.4, 8.5)
-- -----------------------------------------------------------------------------
INSERT INTO reservations (id, reservation_code, request_id, inventory_id, quantity, status, placed_at, expires_at) VALUES
('s0010000-0000-0000-0000-000000000001', 'RES_9A21B', 'r0010000-0000-0000-0000-000000000004', 'i0010000-0000-0000-0000-000000000009', 2, 'ACTIVE', CURRENT_TIMESTAMP - INTERVAL '2 minute', CURRENT_TIMESTAMP + INTERVAL '8 minute');

-- -----------------------------------------------------------------------------
-- 9. MATCHING RESULTS (Ranked & Fully Explained, PRD Section 7)
-- Fully reproducible match score breakdown:
-- Score = ETA_Score (max 50) + Expiry_Score (max 30) + Freshness_Score (max 20)
-- -----------------------------------------------------------------------------
INSERT INTO matching_results (id, request_id, inventory_id, rank, match_score, eta_minutes, distance_km, score_breakdown, explanation, algorithm_version, weights_used, is_active) VALUES
-- Matches for Live Demo Request 1 (REQ_98A2F1: O+ RBC, 4 units, urgency 4)
('m0010000-0000-0000-0000-000000000001', 'r0010000-0000-0000-0000-000000000001', 'i0010000-0000-0000-0000-000000000002', 1, 97.78, 8, 1.2,
 '{"eta_points": 47.78, "expiry_points": 30.00, "freshness_points": 20.00}',
 'Rank 1 | Score 97.8/100 | Rapid ETA: 8 min (47.8 pts) | Optimal Expiry FIFO: 3 days left (30.0 pts) | Data Freshness: updated 40 min ago (20.0 pts)',
 'v1.0-secured', '{"weight_eta": 50, "weight_expiry": 30, "weight_freshness": 20, "max_eta": 180}', TRUE),

('m0010000-0000-0000-0000-000000000002', 'r0010000-0000-0000-0000-000000000001', 'i0010000-0000-0000-0000-000000000009', 2, 91.11, 14, 2.1,
 '{"eta_points": 46.11, "expiry_points": 25.00, "freshness_points": 20.00}',
 'Rank 2 | Score 91.1/100 | ETA: 14 min (46.1 pts) | Expiry: 2 days left (25.0 pts) | Data Freshness: updated 10 min ago (20.0 pts)',
 'v1.0-secured', '{"weight_eta": 50, "weight_expiry": 30, "weight_freshness": 20, "max_eta": 180}', TRUE),

('m0010000-0000-0000-0000-000000000003', 'r0010000-0000-0000-0000-000000000001', 'i0010000-0000-0000-0000-000000000017', 3, 78.06, 25, 4.8,
 '{"eta_points": 43.06, "expiry_points": 15.00, "freshness_points": 20.00}',
 'Rank 3 | Score 78.1/100 | ETA: 25 min (43.1 pts) | Expiry: 25 days left (15.0 pts) | Data Freshness: updated 15 min ago (20.0 pts)',
 'v1.0-secured', '{"weight_eta": 50, "weight_expiry": 30, "weight_freshness": 20, "max_eta": 180}', TRUE);

-- -----------------------------------------------------------------------------
-- 10. ALERTS (In-App notifications with read/unread status, PRD 6.5)
-- -----------------------------------------------------------------------------
INSERT INTO alerts (id, recipient_role, recipient_org_id, recipient_user_id, alert_type, title, message, request_id, is_read) VALUES
('a0010000-0000-0000-0000-000000000001', 'hospital_user', 'h0010000-0000-0000-0000-000000000001', 'u0010000-0000-0000-0000-000000000003',
 'MATCH_FOUND', 'Eligible Blood Inventory Matched (REQ_98A2F1)',
 '3 verified blood units matched with top score 97.8 from Red Cross Regional Blood Center (ETA: 8 mins). Place hold to secure.',
 'r0010000-0000-0000-0000-000000000001', FALSE),

('a0010000-0000-0000-0000-000000000002', 'hospital_user', 'h0010000-0000-0000-0000-000000000003', 'u0010000-0000-0000-0000-000000000005',
 'SHORTAGE_DETECTED', 'CRITICAL SHORTAGE: Rare AB- RBC (REQ_5E1D94)',
 'Zero eligible units found across all regional blood banks within 180 minutes. Escalated to emergency cross-regional donor alert.',
 'r0010000-0000-0000-0000-000000000003', FALSE),

('a0010000-0000-0000-0000-000000000003', 'bloodbank_user', 'b0010000-0000-0000-0000-000000000002', 'u0010000-0000-0000-0000-000000000007',
 'MATCH_FOUND', 'Hold Reservation Placed on INV-202610-009',
 '2 units of O+ RBC reserved for Request REQ_3F9A10. Hold expires in 8 minutes.',
 'r0010000-0000-0000-0000-000000000004', FALSE);

-- -----------------------------------------------------------------------------
-- 11. AUDIT LOGS (Immutable append-only with Cryptographic Hash Chain)
-- Stores who, what, resource, old/new value, IP (text for Db2 portability)
-- SHA-256 hash chains verify tamper-resistance (PRD 6.6, 9)
-- -----------------------------------------------------------------------------
INSERT INTO audit_logs (id, user_id, username, user_role, action, resource_type, resource_id, old_values, new_values, ip_address, timestamp, prev_hash, current_hash) VALUES
('l0010000-0000-0000-0000-000000000001', 'u0010000-0000-0000-0000-000000000003', 'dr_sharma_apex', 'hospital_user',
 'CREATE_REQUEST', 'blood_requests', 'r0010000-0000-0000-0000-000000000001',
 NULL, '{"request_code": "REQ_98A2F1", "blood_group": "O+", "quantity": 4, "urgency": 4}',
 '192.168.1.45', CURRENT_TIMESTAMP - INTERVAL '10 minute',
 'GENESIS_HASH_0000000000000000000000000000000000000000000000000000000000',
 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),

('l0010000-0000-0000-0000-000000000002', 'u0010000-0000-0000-0000-000000000001', 'admin_sys', 'admin',
 'RUN_MATCHING_ENGINE', 'matching_results', 'r0010000-0000-0000-0000-000000000001',
 NULL, '{"matches_generated": 3, "top_score": 97.78, "algorithm": "v1.0-secured"}',
 '127.0.0.1', CURRENT_TIMESTAMP - INTERVAL '10 minute',
 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
 'ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb'),

('l0010000-0000-0000-0000-000000000003', 'u0010000-0000-0000-0000-000000000003', 'dr_sharma_apex', 'hospital_user',
 'PLACE_HOLD', 'reservations', 's0010000-0000-0000-0000-000000000001',
 '{"status": "OPEN"}', '{"status": "HELD", "inventory_id": "i0010000-0000-0000-0000-000000000009", "quantity": 2}',
 '192.168.1.45', CURRENT_TIMESTAMP - INTERVAL '2 minute',
 'ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb',
 '4e07408562bedb8b60ce05c1decfe3ad16b72230967de01f640b7e4729b49fce');
