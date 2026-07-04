"""Compliance and audit management endpoints.

These endpoints are restricted to administrators and compliance officers
for HIPAA audit trail management.
"""

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.database import DbSession
from sense_loop.access import CurrentPractitioner, Permission, PolicyEngine
from sense_loop.audit import AuditIntegrityService, AuditLogger, get_audit_context

router = APIRouter()


class IntegrityCheckResponse(BaseModel):
    """Response for audit log integrity check."""

    is_valid: bool
    entries_checked: int
    first_invalid_sequence: int | None = None
    first_invalid_id: str | None = None
    error_message: str | None = None
    gaps_detected: list[int] | None = None


class ChainSummaryResponse(BaseModel):
    """Response for audit log chain summary."""

    total_entries: int
    hashed_entries: int
    unhashed_entries: int
    sequence_start: int | None
    sequence_end: int | None
    latest_entry_at: str | None
    chain_coverage_percent: float


class BackfillResponse(BaseModel):
    """Response for hash backfill operation."""

    entries_updated: int
    message: str


@router.get("/audit/integrity", response_model=IntegrityCheckResponse)
async def verify_audit_integrity(
    db: DbSession,
    practitioner: CurrentPractitioner,
    start_sequence: int | None = Query(None, description="Starting sequence number"),
    end_sequence: int | None = Query(None, description="Ending sequence number"),
    limit: int = Query(10000, le=100000, description="Max entries to check"),
):
    """Verify audit log integrity using hash chain.

    This endpoint checks that the audit log has not been tampered with
    by verifying the cryptographic hash chain. Each entry's hash includes
    the previous entry's hash, so any modification breaks the chain.

    Requires super_admin or compliance officer role.
    """
    # Check for super_admin or similar high-privilege role
    # For now, check if user has any admin role
    has_admin_role = False
    for role in practitioner.practitioner_roles:
        if role.is_active and role.role_definition:
            if role.role_definition.code in ("super_admin", "org_admin"):
                has_admin_role = True
                break

    if not has_admin_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can verify audit log integrity",
        )

    service = AuditIntegrityService(db)
    result = service.verify_chain(
        start_sequence=start_sequence,
        end_sequence=end_sequence,
        limit=limit,
    )

    # Log the integrity check itself
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    audit = AuditLogger(db)
    audit.log(
        action="verify",
        resource_type="audit_log_integrity",
        details={
            "start_sequence": start_sequence,
            "end_sequence": end_sequence,
            "entries_checked": result.entries_checked,
            "is_valid": result.is_valid,
        },
    )
    db.commit()

    return IntegrityCheckResponse(
        is_valid=result.is_valid,
        entries_checked=result.entries_checked,
        first_invalid_sequence=result.first_invalid_sequence,
        first_invalid_id=str(result.first_invalid_id) if result.first_invalid_id else None,
        error_message=result.error_message,
        gaps_detected=result.gaps_detected,
    )


@router.get("/audit/summary", response_model=ChainSummaryResponse)
async def get_audit_summary(
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Get summary statistics about the audit log.

    Returns information about total entries, hash coverage,
    and sequence range.

    Requires super_admin or org_admin role.
    """
    has_admin_role = False
    for role in practitioner.practitioner_roles:
        if role.is_active and role.role_definition:
            if role.role_definition.code in ("super_admin", "org_admin"):
                has_admin_role = True
                break

    if not has_admin_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view audit log summary",
        )

    service = AuditIntegrityService(db)
    summary = service.get_chain_summary()

    # Log the access
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    audit = AuditLogger(db)
    audit.log(
        action="view",
        resource_type="audit_log_summary",
    )
    db.commit()

    return ChainSummaryResponse(**summary)


@router.post("/audit/backfill-hashes", response_model=BackfillResponse)
async def backfill_audit_hashes(
    db: DbSession,
    practitioner: CurrentPractitioner,
    batch_size: int = Query(1000, le=10000, description="Entries per batch"),
):
    """Backfill hashes for existing audit entries.

    This is used to add hash chain verification to entries created
    before the hash chain feature was implemented.

    Requires super_admin role only.
    """
    is_super_admin = False
    for role in practitioner.practitioner_roles:
        if role.is_active and role.role_definition:
            if role.role_definition.code == "super_admin":
                is_super_admin = True
                break

    if not is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super administrators can backfill audit hashes",
        )

    service = AuditIntegrityService(db)
    updated = service.backfill_hashes(batch_size=batch_size)

    # Log the backfill operation
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    audit = AuditLogger(db)
    audit.log(
        action="backfill",
        resource_type="audit_log_hashes",
        details={
            "batch_size": batch_size,
            "entries_updated": updated,
        },
    )
    db.commit()

    return BackfillResponse(
        entries_updated=updated,
        message=f"Backfilled hashes for {updated} entries" if updated > 0 else "No entries need backfilling",
    )
