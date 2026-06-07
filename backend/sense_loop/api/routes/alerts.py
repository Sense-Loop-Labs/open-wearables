"""Alert management endpoints for clinicians."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import and_, func, select

from app.database import DbSession
from sense_loop.access import CurrentPractitioner, Permission, PolicyEngine
from sense_loop.audit import AuditLogger, get_audit_context
from sense_loop.models import Alert, Patient
from sense_loop.schemas.alert import (
    AlertAcknowledgeRequest,
    AlertListResponse,
    AlertResolveRequest,
    AlertResponse,
)

router = APIRouter()


def _alert_to_response(alert: Alert) -> AlertResponse:
    """Convert alert model to response schema."""
    return AlertResponse(
        id=alert.id,
        patient_id=alert.patient_id,
        organization_id=alert.organization_id,
        title=alert.title,
        message=alert.message,
        severity=alert.severity,
        category=alert.category,
        status=alert.status,
        triggered_at=alert.triggered_at,
        acknowledged_at=alert.acknowledged_at,
        resolved_at=alert.resolved_at,
        escalated_at=alert.escalated_at,
        acknowledged_by_id=alert.acknowledged_by_id,
        acknowledged_by_name=alert.acknowledged_by.full_name if alert.acknowledged_by else None,
        resolved_by_id=alert.resolved_by_id,
        resolved_by_name=alert.resolved_by.full_name if alert.resolved_by else None,
        resolution_notes=alert.resolution_notes,
        resolution_type=alert.resolution_type,
        vital_type=alert.vital_type,
        observed_value=alert.observed_value,
        threshold_breached=alert.threshold_breached,
        threshold_value=alert.threshold_value,
        days_post_surgery=alert.days_post_surgery,
        patient_context=alert.patient_context,
        protocol_id=alert.protocol_id,
        protocol_version=alert.protocol_version,
        rule_id=alert.rule_id,
        patient_name=alert.patient.full_name if alert.patient else None,
        patient_mrn=alert.patient.mrn if alert.patient else None,
        created_at=alert.created_at,
    )


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    db: DbSession,
    practitioner: CurrentPractitioner,
    organization_id: UUID | None = Query(None),
    patient_id: UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    severity: str | None = Query(None),
    category: str | None = Query(None),
    vital_type: str | None = Query(None),
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List alerts with filtering."""
    engine = PolicyEngine(db)

    # Determine which orgs to query
    if organization_id:
        if not engine.has_permission(
            practitioner, Permission.MANAGE_ALERTS, organization_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view alerts in this organization",
            )
        org_ids = [organization_id]
    else:
        org_ids = engine.get_accessible_org_ids(practitioner)

    if not org_ids:
        return AlertListResponse(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
            pages=0,
        )

    # Build query
    stmt = (
        select(Alert)
        .join(Patient, Alert.patient_id == Patient.id)
        .where(Alert.organization_id.in_(org_ids))
    )

    if patient_id:
        stmt = stmt.where(Alert.patient_id == patient_id)

    if status_filter and status_filter != "all":
        stmt = stmt.where(Alert.status == status_filter)

    if severity:
        stmt = stmt.where(Alert.severity == severity)

    if category:
        stmt = stmt.where(Alert.category == category)

    if vital_type:
        stmt = stmt.where(Alert.vital_type == vital_type)

    if from_date:
        stmt = stmt.where(Alert.triggered_at >= from_date)

    if to_date:
        stmt = stmt.where(Alert.triggered_at <= to_date)

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar() or 0

    # Order and paginate
    stmt = stmt.order_by(Alert.triggered_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    alerts = db.execute(stmt).scalars().all()

    # Set audit context
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)

    # Log access
    audit = AuditLogger(db)
    audit.log(
        action="list",
        resource_type="alert",
        details={
            "count": len(alerts),
            "filters": {
                "organization_id": str(organization_id) if organization_id else None,
                "patient_id": str(patient_id) if patient_id else None,
                "status": status_filter,
                "severity": severity,
            },
        },
    )

    pages = (total + page_size - 1) // page_size

    return AlertListResponse(
        items=[_alert_to_response(a) for a in alerts],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Get alert details."""
    stmt = select(Alert).where(Alert.id == alert_id)
    alert = db.execute(stmt).scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    # Check access
    engine = PolicyEngine(db)
    if not engine.has_permission(
        practitioner, Permission.MANAGE_ALERTS, alert.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this alert",
        )

    # Log access
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    ctx.organization_id = alert.organization_id

    audit = AuditLogger(db)
    audit.log_access(
        resource_type="alert",
        resource_id=alert.id,
        resource_name=alert.title,
    )

    return _alert_to_response(alert)


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: UUID,
    request: AlertAcknowledgeRequest,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Acknowledge an alert."""
    stmt = select(Alert).where(Alert.id == alert_id)
    alert = db.execute(stmt).scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    # Check access
    engine = PolicyEngine(db)
    if not engine.has_permission(
        practitioner, Permission.ACKNOWLEDGE_ALERTS, alert.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to acknowledge alerts",
        )

    if alert.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot acknowledge alert with status: {alert.status}",
        )

    # Acknowledge
    alert.status = "acknowledged"
    alert.acknowledged_at = datetime.utcnow()
    alert.acknowledged_by_id = practitioner.id

    # Log action
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    ctx.organization_id = alert.organization_id

    audit = AuditLogger(db)
    audit.log_alert_action(
        action="acknowledge",
        alert_id=alert.id,
        patient_name=alert.patient.full_name if alert.patient else None,
        notes=request.notes,
    )

    db.commit()

    return {"success": True, "message": "Alert acknowledged"}


@router.post("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: UUID,
    request: AlertResolveRequest,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Resolve an alert."""
    stmt = select(Alert).where(Alert.id == alert_id)
    alert = db.execute(stmt).scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    # Check access
    engine = PolicyEngine(db)
    if not engine.has_permission(
        practitioner, Permission.RESOLVE_ALERTS, alert.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to resolve alerts",
        )

    if alert.status == "resolved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alert is already resolved",
        )

    # Resolve
    alert.status = "resolved"
    alert.resolved_at = datetime.utcnow()
    alert.resolved_by_id = practitioner.id
    alert.resolution_type = request.resolution_type
    alert.resolution_notes = request.resolution_notes

    # Update patient summary alert counts
    from sense_loop.services import SummaryService

    summary_service = SummaryService(db)
    summary_service.update_alert_counts(alert.patient_id)

    # Log action
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    ctx.organization_id = alert.organization_id

    audit = AuditLogger(db)
    audit.log_alert_action(
        action="resolve",
        alert_id=alert.id,
        patient_name=alert.patient.full_name if alert.patient else None,
        notes=request.resolution_notes,
    )

    db.commit()

    return {"success": True, "message": "Alert resolved"}


@router.get("/stats/summary")
async def get_alert_stats(
    db: DbSession,
    practitioner: CurrentPractitioner,
    organization_id: UUID | None = Query(None),
):
    """Get alert statistics summary."""
    engine = PolicyEngine(db)

    # Determine which orgs to query
    if organization_id:
        if not engine.has_permission(
            practitioner, Permission.MANAGE_ALERTS, organization_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view alerts in this organization",
            )
        org_ids = [organization_id]
    else:
        org_ids = engine.get_accessible_org_ids(practitioner)

    if not org_ids:
        return {
            "active": 0,
            "acknowledged": 0,
            "resolved_today": 0,
            "critical": 0,
            "warning": 0,
        }

    # Count active alerts
    active = db.execute(
        select(func.count())
        .select_from(Alert)
        .where(
            Alert.organization_id.in_(org_ids),
            Alert.status == "active",
        )
    ).scalar() or 0

    # Count acknowledged alerts
    acknowledged = db.execute(
        select(func.count())
        .select_from(Alert)
        .where(
            Alert.organization_id.in_(org_ids),
            Alert.status == "acknowledged",
        )
    ).scalar() or 0

    # Count resolved today
    from datetime import date

    today_start = datetime.combine(date.today(), datetime.min.time())
    resolved_today = db.execute(
        select(func.count())
        .select_from(Alert)
        .where(
            Alert.organization_id.in_(org_ids),
            Alert.status == "resolved",
            Alert.resolved_at >= today_start,
        )
    ).scalar() or 0

    # Count by severity (active only)
    critical = db.execute(
        select(func.count())
        .select_from(Alert)
        .where(
            Alert.organization_id.in_(org_ids),
            Alert.status == "active",
            Alert.severity == "critical",
        )
    ).scalar() or 0

    warning = db.execute(
        select(func.count())
        .select_from(Alert)
        .where(
            Alert.organization_id.in_(org_ids),
            Alert.status == "active",
            Alert.severity == "warning",
        )
    ).scalar() or 0

    return {
        "active": active,
        "acknowledged": acknowledged,
        "resolved_today": resolved_today,
        "critical": critical,
        "warning": warning,
    }
