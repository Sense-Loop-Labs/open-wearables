"""Compliance and audit management endpoints.

These endpoints are restricted to administrators and compliance officers
for HIPAA audit trail management.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select

from app.database import DbSession
from sense_loop.access import CurrentPractitioner, Permission, PolicyEngine
from sense_loop.audit import AuditIntegrityService, AuditLogger, get_audit_context
from sense_loop.models.audit_log import AuditLog

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


# --- Compliance Reporting Models ---


class UserAccessSummary(BaseModel):
    """PHI access summary for a single user."""

    actor_id: str | None
    actor_name: str | None
    actor_email: str | None
    actor_type: str
    total_accesses: int
    unique_resources: int
    phi_fields: list[str]
    last_access_at: datetime | None


class PHIAccessReportResponse(BaseModel):
    """Response for PHI access report by user."""

    report_start: datetime
    report_end: datetime
    total_accesses: int
    unique_actors: int
    users: list[UserAccessSummary]


class FailedAccessEntry(BaseModel):
    """A single failed access attempt."""

    id: str
    timestamp: datetime
    actor_type: str
    actor_name: str | None
    actor_email: str | None
    action: str
    resource_type: str
    resource_id: str | None
    outcome_reason: str | None
    ip_address: str | None
    endpoint: str | None


class FailedAccessReportResponse(BaseModel):
    """Response for failed access attempts report."""

    report_start: datetime
    report_end: datetime
    total_failures: int
    by_reason: dict[str, int]
    entries: list[FailedAccessEntry]


class ExportActivityEntry(BaseModel):
    """A single export activity record."""

    id: str
    timestamp: datetime
    actor_name: str | None
    actor_email: str | None
    resource_type: str
    resource_id: str | None
    resource_name: str | None
    details: dict | None
    outcome: str


class ExportActivityReportResponse(BaseModel):
    """Response for export activity report."""

    report_start: datetime
    report_end: datetime
    total_exports: int
    by_resource_type: dict[str, int]
    entries: list[ExportActivityEntry]


class EmergencyAccessEntry(BaseModel):
    """A single emergency/break-glass access record."""

    id: str
    timestamp: datetime
    actor_name: str | None
    actor_email: str | None
    action: str
    resource_type: str
    resource_id: str | None
    resource_name: str | None
    reason: str | None
    details: dict | None


class EmergencyAccessReportResponse(BaseModel):
    """Response for emergency access report."""

    report_start: datetime
    report_end: datetime
    total_emergency_accesses: int
    entries: list[EmergencyAccessEntry]


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


# --- Compliance Reports ---


def _check_admin_role(practitioner: CurrentPractitioner) -> bool:
    """Check if practitioner has admin role."""
    for role in practitioner.practitioner_roles:
        if role.is_active and role.role_definition:
            if role.role_definition.code in ("super_admin", "org_admin"):
                return True
    return False


@router.get("/reports/phi-access", response_model=PHIAccessReportResponse)
async def get_phi_access_report(
    db: DbSession,
    practitioner: CurrentPractitioner,
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    organization_id: UUID | None = Query(None, description="Filter by organization"),
):
    """Get PHI access report grouped by user.

    Shows who accessed PHI, how many times, and which fields were accessed.
    Useful for periodic compliance reviews.

    Requires super_admin or org_admin role.
    """
    if not _check_admin_role(practitioner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view PHI access reports",
        )

    report_end = datetime.now(timezone.utc)
    report_start = report_end - timedelta(days=days)

    # Build query for PHI access (actions that access patient data)
    phi_actions = ["read", "view", "list", "download", "export"]
    phi_resource_types = [
        "patient",
        "patient_vitals",
        "patient_summary",
        "patient_alert",
        "patient_task",
        "patient_questionnaire",
        "patient_device",
        "patient_workouts",
        "patient_sleep",
        "critical_patients",
        "recent_alerts",
    ]

    query = select(
        AuditLog.actor_id,
        AuditLog.actor_name,
        AuditLog.actor_email,
        AuditLog.actor_type,
        func.count(AuditLog.id).label("total_accesses"),
        func.count(func.distinct(AuditLog.resource_id)).label("unique_resources"),
        func.max(AuditLog.created_at).label("last_access_at"),
    ).where(
        AuditLog.created_at >= report_start,
        AuditLog.created_at <= report_end,
        AuditLog.action.in_(phi_actions),
        AuditLog.resource_type.in_(phi_resource_types),
        AuditLog.outcome == "success",
    )

    if organization_id:
        query = query.where(AuditLog.organization_id == organization_id)

    query = query.group_by(
        AuditLog.actor_id,
        AuditLog.actor_name,
        AuditLog.actor_email,
        AuditLog.actor_type,
    ).order_by(func.count(AuditLog.id).desc())

    results = db.execute(query).all()

    # Get PHI fields accessed per user
    users = []
    total_accesses = 0
    for row in results:
        # Query PHI fields for this actor
        phi_query = select(AuditLog.phi_fields_accessed).where(
            AuditLog.created_at >= report_start,
            AuditLog.created_at <= report_end,
            AuditLog.actor_id == row.actor_id if row.actor_id else AuditLog.actor_name == row.actor_name,
            AuditLog.phi_fields_accessed.isnot(None),
        )
        phi_results = db.execute(phi_query).scalars().all()

        # Flatten and dedupe PHI fields
        all_phi_fields = set()
        for fields in phi_results:
            if fields:
                all_phi_fields.update(fields)

        users.append(
            UserAccessSummary(
                actor_id=str(row.actor_id) if row.actor_id else None,
                actor_name=row.actor_name,
                actor_email=row.actor_email,
                actor_type=row.actor_type,
                total_accesses=row.total_accesses,
                unique_resources=row.unique_resources,
                phi_fields=sorted(all_phi_fields),
                last_access_at=row.last_access_at,
            )
        )
        total_accesses += row.total_accesses

    # Log the report access
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    audit = AuditLogger(db)
    audit.log(
        action="view",
        resource_type="phi_access_report",
        details={"days": days, "organization_id": str(organization_id) if organization_id else None},
    )
    db.commit()

    return PHIAccessReportResponse(
        report_start=report_start,
        report_end=report_end,
        total_accesses=total_accesses,
        unique_actors=len(users),
        users=users,
    )


@router.get("/reports/failed-access", response_model=FailedAccessReportResponse)
async def get_failed_access_report(
    db: DbSession,
    practitioner: CurrentPractitioner,
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    organization_id: UUID | None = Query(None, description="Filter by organization"),
    limit: int = Query(100, ge=1, le=1000, description="Max entries to return"),
):
    """Get failed access attempts report.

    Shows all denied or failed access attempts, useful for detecting
    unauthorized access patterns or security issues.

    Requires super_admin or org_admin role.
    """
    if not _check_admin_role(practitioner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view failed access reports",
        )

    report_end = datetime.now(timezone.utc)
    report_start = report_end - timedelta(days=days)

    # Query for failed/denied access
    query = select(AuditLog).where(
        AuditLog.created_at >= report_start,
        AuditLog.created_at <= report_end,
        AuditLog.outcome.in_(["failure", "denied"]),
    )

    if organization_id:
        query = query.where(AuditLog.organization_id == organization_id)

    query = query.order_by(AuditLog.created_at.desc()).limit(limit)
    results = db.execute(query).scalars().all()

    # Count by reason
    reason_counts: dict[str, int] = {}
    entries = []
    for entry in results:
        reason = entry.outcome_reason or "Unknown"
        reason_counts[reason] = reason_counts.get(reason, 0) + 1

        entries.append(
            FailedAccessEntry(
                id=str(entry.id),
                timestamp=entry.created_at,
                actor_type=entry.actor_type,
                actor_name=entry.actor_name,
                actor_email=entry.actor_email,
                action=entry.action,
                resource_type=entry.resource_type,
                resource_id=str(entry.resource_id) if entry.resource_id else None,
                outcome_reason=entry.outcome_reason,
                ip_address=entry.ip_address,
                endpoint=entry.endpoint,
            )
        )

    # Get total count (may be higher than returned entries)
    count_query = select(func.count(AuditLog.id)).where(
        AuditLog.created_at >= report_start,
        AuditLog.created_at <= report_end,
        AuditLog.outcome.in_(["failure", "denied"]),
    )
    if organization_id:
        count_query = count_query.where(AuditLog.organization_id == organization_id)
    total_failures = db.execute(count_query).scalar() or 0

    # Log the report access
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    audit = AuditLogger(db)
    audit.log(
        action="view",
        resource_type="failed_access_report",
        details={"days": days, "organization_id": str(organization_id) if organization_id else None},
    )
    db.commit()

    return FailedAccessReportResponse(
        report_start=report_start,
        report_end=report_end,
        total_failures=total_failures,
        by_reason=reason_counts,
        entries=entries,
    )


@router.get("/reports/exports", response_model=ExportActivityReportResponse)
async def get_export_activity_report(
    db: DbSession,
    practitioner: CurrentPractitioner,
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    organization_id: UUID | None = Query(None, description="Filter by organization"),
    limit: int = Query(100, ge=1, le=1000, description="Max entries to return"),
):
    """Get export activity report.

    Shows all data export operations, useful for tracking PHI disclosure
    and ensuring exports are authorized.

    Requires super_admin or org_admin role.
    """
    if not _check_admin_role(practitioner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view export activity reports",
        )

    report_end = datetime.now(timezone.utc)
    report_start = report_end - timedelta(days=days)

    # Query for export actions
    export_actions = ["export", "download"]
    query = select(AuditLog).where(
        AuditLog.created_at >= report_start,
        AuditLog.created_at <= report_end,
        AuditLog.action.in_(export_actions),
    )

    if organization_id:
        query = query.where(AuditLog.organization_id == organization_id)

    query = query.order_by(AuditLog.created_at.desc()).limit(limit)
    results = db.execute(query).scalars().all()

    # Count by resource type
    type_counts: dict[str, int] = {}
    entries = []
    for entry in results:
        type_counts[entry.resource_type] = type_counts.get(entry.resource_type, 0) + 1

        entries.append(
            ExportActivityEntry(
                id=str(entry.id),
                timestamp=entry.created_at,
                actor_name=entry.actor_name,
                actor_email=entry.actor_email,
                resource_type=entry.resource_type,
                resource_id=str(entry.resource_id) if entry.resource_id else None,
                resource_name=entry.resource_name,
                details=entry.details,
                outcome=entry.outcome,
            )
        )

    # Get total count
    count_query = select(func.count(AuditLog.id)).where(
        AuditLog.created_at >= report_start,
        AuditLog.created_at <= report_end,
        AuditLog.action.in_(export_actions),
    )
    if organization_id:
        count_query = count_query.where(AuditLog.organization_id == organization_id)
    total_exports = db.execute(count_query).scalar() or 0

    # Log the report access
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    audit = AuditLogger(db)
    audit.log(
        action="view",
        resource_type="export_activity_report",
        details={"days": days, "organization_id": str(organization_id) if organization_id else None},
    )
    db.commit()

    return ExportActivityReportResponse(
        report_start=report_start,
        report_end=report_end,
        total_exports=total_exports,
        by_resource_type=type_counts,
        entries=entries,
    )


@router.get("/reports/emergency-access", response_model=EmergencyAccessReportResponse)
async def get_emergency_access_report(
    db: DbSession,
    practitioner: CurrentPractitioner,
    days: int = Query(90, ge=1, le=365, description="Number of days to include"),
    organization_id: UUID | None = Query(None, description="Filter by organization"),
):
    """Get emergency/break-glass access report.

    Shows all emergency access events where normal authorization was bypassed.
    These should be rare and require justification.

    Requires super_admin or org_admin role.
    """
    if not _check_admin_role(practitioner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view emergency access reports",
        )

    report_end = datetime.now(timezone.utc)
    report_start = report_end - timedelta(days=days)

    # Query for emergency access actions
    # Emergency access is tracked via action type or details field
    emergency_actions = ["emergency_access", "break_glass"]

    query = select(AuditLog).where(
        AuditLog.created_at >= report_start,
        AuditLog.created_at <= report_end,
        AuditLog.action.in_(emergency_actions),
    )

    if organization_id:
        query = query.where(AuditLog.organization_id == organization_id)

    query = query.order_by(AuditLog.created_at.desc())
    results = db.execute(query).scalars().all()

    entries = []
    for entry in results:
        # Extract reason from details if available
        reason = None
        if entry.details and isinstance(entry.details, dict):
            reason = entry.details.get("reason") or entry.details.get("justification")

        entries.append(
            EmergencyAccessEntry(
                id=str(entry.id),
                timestamp=entry.created_at,
                actor_name=entry.actor_name,
                actor_email=entry.actor_email,
                action=entry.action,
                resource_type=entry.resource_type,
                resource_id=str(entry.resource_id) if entry.resource_id else None,
                resource_name=entry.resource_name,
                reason=reason,
                details=entry.details,
            )
        )

    # Log the report access
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    audit = AuditLogger(db)
    audit.log(
        action="view",
        resource_type="emergency_access_report",
        details={"days": days, "organization_id": str(organization_id) if organization_id else None},
    )
    db.commit()

    return EmergencyAccessReportResponse(
        report_start=report_start,
        report_end=report_end,
        total_emergency_accesses=len(entries),
        entries=entries,
    )
