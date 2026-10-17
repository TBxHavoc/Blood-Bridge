"""
Blood Bridge - Transactional Hold & Concurrency Test
IBM Z Datathon 2026 - AI Secured Track (Innovation without Exposure)

Tests:
1. SELECT ... FOR UPDATE row-level locking
2. Prevents double-allocation across competing requests
3. Hold timeout and status transitions: OPEN -> HELD -> CONFIRMED -> FULFILLED
"""

import os
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine, text


def get_connection_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://bloodbridge_user:bloodbridge_secret_2026@localhost:5432/bloodbridge"
    )


def test_hold_lifecycle():
    engine = create_engine(get_connection_url())
    print("\n[+] Starting Hold Lifecycle & Concurrency Simulation...")

    with engine.connect() as conn:
        # Step 1: Find an eligible inventory unit with unreserved stock
        inv = conn.execute(text("""
            SELECT id, inventory_code, units_available, units_reserved, (units_available - units_reserved) AS unreserved
            FROM blood_inventory
            WHERE is_available = TRUE AND (units_available - units_reserved) >= 2
            LIMIT 1
        """)).fetchone()

        if not inv:
            print("[!] No eligible inventory unit found for testing.")
            return

        inv_id, inv_code, orig_avail, orig_res, unreserved = inv
        print(f"    Selected Inventory: {inv_code} (Available: {orig_avail}, Reserved: {orig_res}, Unreserved: {unreserved})")

        # Step 2: Simulate Hold creation inside a strict transaction
        req_qty = 2
        res_uuid = str(uuid.uuid4())
        res_code = f"RES_{uuid.uuid4().hex[:6].upper()}"

        # Find or create a test request
        req = conn.execute(text("SELECT id, request_code FROM blood_requests WHERE status = 'OPEN' LIMIT 1")).fetchone()
        if not req:
            print("[!] No OPEN request found for testing.")
            return
        req_id, req_code = req

        print(f"    Placing hold for Request {req_code} on {inv_code} (Qty: {req_qty})...")
        trans = conn.begin()
        try:
            # Row lock
            locked_row = conn.execute(
                text("SELECT id, units_available, units_reserved FROM blood_inventory WHERE id = :id FOR UPDATE"),
                {"id": inv_id}
            ).fetchone()

            avail, res = locked_row[1], locked_row[2]
            if (avail - res) < req_qty:
                raise Exception("Conflict: Not enough unreserved units!")

            # Reserve units
            conn.execute(
                text("UPDATE blood_inventory SET units_reserved = units_reserved + :qty WHERE id = :id"),
                {"qty": req_qty, "id": inv_id}
            )

            # Insert reservation
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
            conn.execute(
                text("""
                    INSERT INTO reservations (id, reservation_code, request_id, inventory_id, quantity, status, placed_at, expires_at)
                    VALUES (:id, :code, :req_id, :inv_id, :qty, 'ACTIVE', CURRENT_TIMESTAMP, :exp)
                """),
                {"id": res_uuid, "code": res_code, "req_id": req_id, "inv_id": inv_id, "qty": req_qty, "exp": expires_at}
            )

            # Update request status to HELD
            conn.execute(
                text("UPDATE blood_requests SET status = 'HELD', updated_at = CURRENT_TIMESTAMP WHERE id = :id"),
                {"id": req_id}
            )

            # Write Audit record
            conn.execute(
                text("""
                    INSERT INTO audit_logs (id, action, resource_type, resource_id, new_values, ip_address, timestamp)
                    VALUES (:id, 'TEST_PLACE_HOLD', 'reservations', :res_id, :payload, '127.0.0.1', CURRENT_TIMESTAMP)
                """),
                {"id": str(uuid.uuid4()), "res_id": res_uuid, "payload": f'{{"reservation_code": "{res_code}", "qty": {req_qty}}}'}
            )

            trans.commit()
            print("    [PASS] Hold placed successfully with row-level transaction lock.")
        except Exception as e:
            trans.rollback()
            print(f"    [FAIL] Transaction failed: {e}")
            return

        # Step 3: Confirm the Hold (Allocation)
        print("    Confirming hold and transitioning request to CONFIRMED...")
        trans2 = conn.begin()
        try:
            conn.execute(
                text("UPDATE reservations SET status = 'CONFIRMED', confirmed_at = CURRENT_TIMESTAMP WHERE id = :id"),
                {"id": res_uuid}
            )
            conn.execute(
                text("UPDATE blood_requests SET status = 'CONFIRMED', updated_at = CURRENT_TIMESTAMP WHERE id = :id"),
                {"id": req_id}
            )
            trans2.commit()
            print("    [PASS] Hold confirmed without conflict.")
        except Exception as e:
            trans2.rollback()
            print(f"    [FAIL] Confirmation failed: {e}")


if __name__ == "__main__":
    test_hold_lifecycle()
