"""Blood-request endpoints and the priority match queue."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, require_roles
from app.constants import REQUEST_STATUSES
from app.core.audit import write_audit
from app.core.envelope import envelope
from app.core.errors import bad_request, forbidden, not_found
from app.core.ratelimit import check_rate_limit
from app.database import get_db
from app.models import BloodRequest, Hospital, User, utcnow
from app.schemas.request import RequestCreate
from app.services.codes import next_code
from app.services.matching_service import priority_ordered_query, run_matching
from app.services.read import request_out
from app.services.reservations import release_all_for_request

router = APIRouter(prefix="/requests", tags=["requests"])
match_router = APIRouter(prefix="/match", tags=["matching"])

hospital_only = require_roles("hospital_user")
# PRD 8.3: requests are owned by hospitals; admins may act across all of them.
hospital_or_admin = require_roles("hospital_user", "admin")
# PRD 8.3: only oversight roles may read the cross-hospital priority queue.
queue_roles = require_roles("admin", "auditor")

CANCELLABLE = {"OPEN", "HELD", "CONFIRMED"}

CREATE_REQUEST_LIMIT = 60
CREATE_REQUEST_WINDOW_SECONDS = 60


def _can_view(user: User, row: BloodRequest) -> bool:
    if user.role == "admin":
        return True
    if user.role == "hospital_user":
        return user.affiliated_org_id == row.hospital_id
    return False


def _load_visible(user: User, request_id: str, db: Session) -> BloodRequest:
    row = db.get(BloodRequest, request_id)
    if row is None:
        raise not_found("Request not found.")
    if not _can_view(user, row):
        raise forbidden("You do not have access to this request.")
    return row


@router.post("")
def create_request(
    payload: RequestCreate,
    request: Request,
    user: User = Depends(hospital_only),
    db: Session = Depends(get_db),
) -> dict:
    hospital_id = user.affiliated_org_id
    if not hospital_id or db.get(Hospital, hospital_id) is None:
        raise bad_request("Your account is not linked to a hospital.")

    check_rate_limit(
        f"create_request:{user.id}", CREATE_REQUEST_LIMIT, CREATE_REQUEST_WINDOW_SECONDS
    )

    row = BloodRequest(
        code=next_code(db, BloodRequest, "REQ_", 6),
        hospital_id=hospital_id,
        blood_group=payload.blood_group,
        component_type=payload.component_type,
        quantity_units=payload.quantity_units,
        urgency=payload.urgency,
        required_by_timestamp=payload.required_by_timestamp,
        status="OPEN",
        request_timestamp=utcnow(),
        created_by_user_id=user.id,
    )
    db.add(row)
    db.flush()

    run_matching(db, row, persist=True)
    write_audit(
        db,
        action_type="CREATE_REQUEST",
        user_id=user.id,
        resource_type="blood_request",
        resource_id=row.id,
        new_value={"code": row.code, "blood_group": row.blood_group, "urgency": row.urgency},
        ip_address=get_client_ip(request),
    )
    db.commit()
    return envelope(request_out(db, row).model_dump())


@router.get("")
def list_requests(
    status: str | None = Query(default=None),
    user: User = Depends(hospital_or_admin),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(BloodRequest)
    if user.role == "hospital_user":
        stmt = stmt.where(BloodRequest.hospital_id == user.affiliated_org_id)
    if status:
        if status not in REQUEST_STATUSES:
            raise bad_request(f"status must be one of {REQUEST_STATUSES}")
        stmt = stmt.where(BloodRequest.status == status)
    stmt = stmt.order_by(
        BloodRequest.request_timestamp.desc(), BloodRequest.id.desc()
    )
    rows = db.scalars(stmt).all()
    return envelope([request_out(db, row).model_dump() for row in rows])


@router.get("/{request_id}")
def get_request(
    request_id: str,
    user: User = Depends(hospital_or_admin),
    db: Session = Depends(get_db),
) -> dict:
    row = _load_visible(user, request_id, db)
    return envelope(request_out(db, row).model_dump())


@router.post("/{request_id}/rematch")
def rematch_request(
    request_id: str,
    request: Request,
    user: User = Depends(hospital_or_admin),
    db: Session = Depends(get_db),
) -> dict:
    row = _load_visible(user, request_id, db)
    if row.status not in {"OPEN", "HELD"}:
        raise bad_request(f"Cannot rematch a request in status {row.status}.")
    run_matching(db, row, persist=True)
    write_audit(
        db,
        action_type="REMATCH_REQUEST",
        user_id=user.id,
        resource_type="blood_request",
        resource_id=row.id,
        ip_address=get_client_ip(request),
    )
    db.commit()
    return envelope(request_out(db, row).model_dump())


@router.post("/{request_id}/cancel")
def cancel_request(
    request_id: str,
    request: Request,
    user: User = Depends(hospital_or_admin),
    db: Session = Depends(get_db),
) -> dict:
    row = _load_visible(user, request_id, db)
    if row.status not in CANCELLABLE:
        raise bad_request(f"Cannot cancel a request in status {row.status}.")
    old_status = row.status
    released = release_all_for_request(db, row)
    row.status = "CANCELLED"
    write_audit(
        db,
        action_type="CANCEL_REQUEST",
        user_id=user.id,
        resource_type="blood_request",
        resource_id=row.id,
        old_value={"status": old_status},
        new_value={"status": "CANCELLED", "released_reservations": released},
        ip_address=get_client_ip(request),
    )
    db.commit()
    return envelope(request_out(db, row).model_dump())


@match_router.get("/queue")
def match_queue(
    limit: int = Query(default=50, ge=1, le=200),
    _: User = Depends(queue_roles),
    db: Session = Depends(get_db),
) -> dict:
    """Open requests in priority order (urgency desc, then oldest first)."""
    rows = db.scalars(priority_ordered_query().limit(limit)).all()
    return envelope([request_out(db, row, with_matches=False).model_dump() for row in rows])
