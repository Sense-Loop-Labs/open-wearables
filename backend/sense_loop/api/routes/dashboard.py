"""Dashboard aggregation endpoints."""

from datetime import date, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import and_, func, select

from app.database import DbSession
from sense_loop.access import CurrentPractitioner, Permission, PolicyEngine
from sense_loop.models import Alert, Patient, PatientSummary

router = APIRouter()


@router.get("/overview")
async def get_dashboard_overview(
    db: DbSession,
    practitioner: CurrentPractitioner,
    organization_id: UUID | None = Query(None),
):
    """Get dashboard overview with key metrics."""
    engine = PolicyEngine(db)

    # Determine which orgs to query
    if organization_id:
        if not engine.has_permission(
            practitioner, Permission.MANAGE_PATIENTS, organization_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this organization",
            )
        org_ids = [organization_id]
    else:
        org_ids = engine.get_accessible_org_ids(practitioner)

    if not org_ids:
        return {
            "patients": {"total": 0, "active": 0, "critical": 0, "warning": 0},
            "alerts": {"active": 0, "critical": 0, "acknowledged": 0, "resolved_today": 0},
            "activity": {"new_patients_7d": 0, "discharged_7d": 0, "alerts_7d": 0},
        }

    # Patient counts
    total_patients = db.execute(
        select(func.count())
        .select_from(Patient)
        .where(Patient.organization_id.in_(org_ids))
    ).scalar() or 0

    active_patients = db.execute(
        select(func.count())
        .select_from(Patient)
        .where(
            Patient.organization_id.in_(org_ids),
            Patient.is_active == True,  # noqa: E712
            Patient.enrollment_status.in_(["activated", "active"]),
        )
    ).scalar() or 0

    # Patients with critical/warning status
    critical_patients = db.execute(
        select(func.count())
        .select_from(PatientSummary)
        .join(Patient, PatientSummary.patient_id == Patient.id)
        .where(
            Patient.organization_id.in_(org_ids),
            Patient.is_active == True,  # noqa: E712
            PatientSummary.overall_status == "critical",
        )
    ).scalar() or 0

    warning_patients = db.execute(
        select(func.count())
        .select_from(PatientSummary)
        .join(Patient, PatientSummary.patient_id == Patient.id)
        .where(
            Patient.organization_id.in_(org_ids),
            Patient.is_active == True,  # noqa: E712
            PatientSummary.overall_status == "warning",
        )
    ).scalar() or 0

    # Alert counts
    active_alerts = db.execute(
        select(func.count())
        .select_from(Alert)
        .where(
            Alert.organization_id.in_(org_ids),
            Alert.status == "active",
        )
    ).scalar() or 0

    critical_alerts = db.execute(
        select(func.count())
        .select_from(Alert)
        .where(
            Alert.organization_id.in_(org_ids),
            Alert.status == "active",
            Alert.severity == "critical",
        )
    ).scalar() or 0

    acknowledged_alerts = db.execute(
        select(func.count())
        .select_from(Alert)
        .where(
            Alert.organization_id.in_(org_ids),
            Alert.status == "acknowledged",
        )
    ).scalar() or 0

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

    # 7-day activity
    week_ago = datetime.utcnow() - timedelta(days=7)

    new_patients_7d = db.execute(
        select(func.count())
        .select_from(Patient)
        .where(
            Patient.organization_id.in_(org_ids),
            Patient.created_at >= week_ago,
        )
    ).scalar() or 0

    discharged_7d = db.execute(
        select(func.count())
        .select_from(Patient)
        .where(
            Patient.organization_id.in_(org_ids),
            Patient.discharged_at >= week_ago,
        )
    ).scalar() or 0

    alerts_7d = db.execute(
        select(func.count())
        .select_from(Alert)
        .where(
            Alert.organization_id.in_(org_ids),
            Alert.triggered_at >= week_ago,
        )
    ).scalar() or 0

    return {
        "patients": {
            "total": total_patients,
            "active": active_patients,
            "critical": critical_patients,
            "warning": warning_patients,
        },
        "alerts": {
            "active": active_alerts,
            "critical": critical_alerts,
            "acknowledged": acknowledged_alerts,
            "resolved_today": resolved_today,
        },
        "activity": {
            "new_patients_7d": new_patients_7d,
            "discharged_7d": discharged_7d,
            "alerts_7d": alerts_7d,
        },
    }


@router.get("/critical-patients")
async def get_critical_patients(
    db: DbSession,
    practitioner: CurrentPractitioner,
    organization_id: UUID | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
):
    """Get list of patients with critical status."""
    engine = PolicyEngine(db)

    # Determine which orgs to query
    if organization_id:
        if not engine.has_permission(
            practitioner, Permission.MANAGE_PATIENTS, organization_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this organization",
            )
        org_ids = [organization_id]
    else:
        org_ids = engine.get_accessible_org_ids(practitioner)

    if not org_ids:
        return []

    stmt = (
        select(Patient)
        .join(PatientSummary, Patient.id == PatientSummary.patient_id)
        .where(
            Patient.organization_id.in_(org_ids),
            Patient.is_active == True,  # noqa: E712
            PatientSummary.overall_status.in_(["critical", "warning"]),
        )
        .order_by(
            # Critical first, then warning
            PatientSummary.overall_status.desc(),
            PatientSummary.active_critical_alerts_count.desc(),
        )
        .limit(limit)
    )

    patients = db.execute(stmt).scalars().all()

    return [
        {
            "id": p.id,
            "name": p.full_name,
            "mrn": p.mrn,
            "status": p.summary.overall_status if p.summary else "unknown",
            "critical_alerts": p.summary.active_critical_alerts_count if p.summary else 0,
            "total_alerts": p.summary.active_alerts_count if p.summary else 0,
            "days_post_surgery": p.days_post_surgery,
            "last_data_at": p.summary.last_data_received_at if p.summary else None,
        }
        for p in patients
    ]


@router.get("/recent-alerts")
async def get_recent_alerts(
    db: DbSession,
    practitioner: CurrentPractitioner,
    organization_id: UUID | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
):
    """Get list of recent alerts."""
    engine = PolicyEngine(db)

    # Determine which orgs to query
    if organization_id:
        if not engine.has_permission(
            practitioner, Permission.MANAGE_ALERTS, organization_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access alerts",
            )
        org_ids = [organization_id]
    else:
        org_ids = engine.get_accessible_org_ids(practitioner)

    if not org_ids:
        return []

    stmt = (
        select(Alert)
        .join(Patient, Alert.patient_id == Patient.id)
        .where(Alert.organization_id.in_(org_ids))
        .order_by(Alert.triggered_at.desc())
        .limit(limit)
    )

    alerts = db.execute(stmt).scalars().all()

    return [
        {
            "id": a.id,
            "title": a.title,
            "severity": a.severity,
            "status": a.status,
            "triggered_at": a.triggered_at,
            "patient_id": a.patient_id,
            "patient_name": a.patient.full_name if a.patient else None,
            "vital_type": a.vital_type,
            "observed_value": a.observed_value,
        }
        for a in alerts
    ]


@router.get("/alerts-by-day")
async def get_alerts_by_day(
    db: DbSession,
    practitioner: CurrentPractitioner,
    organization_id: UUID | None = Query(None),
    days: int = Query(7, ge=1, le=30),
):
    """Get alert counts by day for charting."""
    engine = PolicyEngine(db)

    # Determine which orgs to query
    if organization_id:
        if not engine.has_permission(
            practitioner, Permission.MANAGE_ALERTS, organization_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access alerts",
            )
        org_ids = [organization_id]
    else:
        org_ids = engine.get_accessible_org_ids(practitioner)

    if not org_ids:
        return []

    start_date = date.today() - timedelta(days=days - 1)

    # Get daily counts
    results = []
    for i in range(days):
        day = start_date + timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day + timedelta(days=1), datetime.min.time())

        total = db.execute(
            select(func.count())
            .select_from(Alert)
            .where(
                Alert.organization_id.in_(org_ids),
                Alert.triggered_at >= day_start,
                Alert.triggered_at < day_end,
            )
        ).scalar() or 0

        critical = db.execute(
            select(func.count())
            .select_from(Alert)
            .where(
                Alert.organization_id.in_(org_ids),
                Alert.triggered_at >= day_start,
                Alert.triggered_at < day_end,
                Alert.severity == "critical",
            )
        ).scalar() or 0

        warning = db.execute(
            select(func.count())
            .select_from(Alert)
            .where(
                Alert.organization_id.in_(org_ids),
                Alert.triggered_at >= day_start,
                Alert.triggered_at < day_end,
                Alert.severity == "warning",
            )
        ).scalar() or 0

        results.append({
            "date": day.isoformat(),
            "total": total,
            "critical": critical,
            "warning": warning,
        })

    return results
