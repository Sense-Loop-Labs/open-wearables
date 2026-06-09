"""Patient management endpoints for clinicians."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import DbSession
from sense_loop.access import CurrentPractitioner, Permission, PolicyEngine
from sense_loop.audit import AuditLogger, get_audit_context
from sense_loop.config import sl_settings
from sense_loop.schemas.patient import (
    PatientCreate,
    PatientListResponse,
    PatientResponse,
    PatientSummaryResponse,
    PatientUpdate,
)
from sense_loop.services import EnrollmentService, PatientService

router = APIRouter()


def _get_latest_sleep_minutes(db: Session, ow_user_id: UUID | None) -> int | None:
    """Get latest sleep duration from event_record table.

    Queries the OW event_record table directly to get fresh sleep data,
    rather than relying on the potentially stale PatientSummary cache.
    """
    if not ow_user_id:
        return None

    try:
        from app.models import DataSource
        from app.models.event_record import EventRecord
        from app.models.event_record_detail import EventRecordDetail
        from app.models.sleep_details import SleepDetails

        # Query latest sleep record for this user
        stmt = (
            select(EventRecord, SleepDetails)
            .join(DataSource, EventRecord.data_source_id == DataSource.id)
            .join(EventRecordDetail, EventRecordDetail.record_id == EventRecord.id)
            .join(SleepDetails, SleepDetails.record_id == EventRecordDetail.record_id)
            .where(
                DataSource.user_id == ow_user_id,
                EventRecord.category == "sleep",
            )
            .order_by(EventRecord.end_datetime.desc())
            .limit(1)
        )
        result = db.execute(stmt).first()

        if result:
            event, sleep_details = result
            if sleep_details and sleep_details.sleep_total_duration_minutes:
                return sleep_details.sleep_total_duration_minutes
            elif event.duration_seconds:
                return int(event.duration_seconds / 60)

        return None
    except Exception:
        # If OW tables aren't available, fall back to None
        return None


def _patient_to_response(patient, db: Session) -> PatientResponse:
    """Convert patient model to response schema.

    Fetches latest sleep data directly from event_record table for freshness.
    """
    summary = None
    if patient.summary:
        # Get fresh sleep data from event_record table instead of stale PatientSummary
        latest_sleep_minutes = _get_latest_sleep_minutes(db, patient.ow_user_id)

        summary = PatientSummaryResponse(
            latest_heart_rate=patient.summary.latest_heart_rate,
            latest_heart_rate_at=patient.summary.latest_heart_rate_at,
            latest_spo2=patient.summary.latest_spo2,
            latest_spo2_at=patient.summary.latest_spo2_at,
            latest_temperature=patient.summary.latest_temperature,
            latest_temperature_at=patient.summary.latest_temperature_at,
            latest_hrv=patient.summary.latest_hrv,
            latest_hrv_at=patient.summary.latest_hrv_at,
            latest_respiratory_rate=patient.summary.latest_respiratory_rate,
            latest_respiratory_rate_at=patient.summary.latest_respiratory_rate_at,
            latest_blood_pressure_systolic=patient.summary.latest_blood_pressure_systolic,
            latest_blood_pressure_diastolic=patient.summary.latest_blood_pressure_diastolic,
            latest_blood_pressure_at=patient.summary.latest_blood_pressure_at,
            today_steps=patient.summary.today_steps,
            today_active_minutes=patient.summary.today_active_minutes,
            last_sleep_duration_minutes=latest_sleep_minutes,
            active_alerts_count=patient.summary.active_alerts_count,
            active_critical_alerts_count=patient.summary.active_critical_alerts_count,
            overall_status=patient.summary.overall_status,
            last_data_received_at=patient.summary.last_data_received_at,
        )

    return PatientResponse(
        id=patient.id,
        organization_id=patient.organization_id,
        ow_user_id=patient.ow_user_id,
        first_name=patient.first_name,
        last_name=patient.last_name,
        full_name=patient.full_name,
        date_of_birth=patient.date_of_birth,
        age=patient.age,
        gender=patient.gender,
        email=patient.email,
        phone=patient.phone,
        mrn=patient.mrn,
        primary_diagnosis=patient.primary_diagnosis,
        surgery_date=patient.surgery_date,
        discharge_date=patient.discharge_date,
        days_post_surgery=patient.days_post_surgery,
        enrollment_status=patient.enrollment_status,
        enrolled_at=patient.enrolled_at,
        activation_code=patient.activation_code,
        activation_code_expires_at=patient.activation_code_expires_at,
        monitoring_start_date=patient.monitoring_start_date,
        monitoring_end_date=patient.monitoring_end_date,
        is_monitoring_active=patient.is_monitoring_active,
        alert_protocol_id=patient.alert_protocol_id,
        is_active=patient.is_active,
        created_at=patient.created_at,
        summary=summary,
    )


@router.get("", response_model=PatientListResponse)
async def list_patients(
    db: DbSession,
    practitioner: CurrentPractitioner,
    organization_id: UUID = Query(..., description="Organization ID"),
    is_active: bool | None = Query(None),
    enrollment_status: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List patients in an organization."""
    # Check access using parallel mode (evaluates both legacy and Cedar)
    engine = PolicyEngine(db)
    if not engine.is_authorized_with_parallel_check(
        practitioner,
        Permission.MANAGE_PATIENTS,
        organization_id,
        action="read",
        resource_type="patient",
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access patients in this organization",
        )

    # Set audit context
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    ctx.organization_id = organization_id

    # List patients
    service = PatientService(db)
    patients, total = service.list_by_organization(
        organization_id,
        is_active=is_active,
        enrollment_status=enrollment_status,
        search=search,
        page=page,
        page_size=page_size,
    )

    # Log access
    audit = AuditLogger(db)
    audit.log(
        action="list",
        resource_type="patient",
        details={
            "organization_id": str(organization_id),
            "count": len(patients),
            "filters": {
                "is_active": is_active,
                "enrollment_status": enrollment_status,
                "search": search,
            },
        },
    )

    pages = (total + page_size - 1) // page_size

    # Build response items
    items = [_patient_to_response(p, db) for p in patients]

    # Filter response fields based on Cedar policies (if enabled)
    if sl_settings.use_cedar_auth:
        items = engine.filter_response_fields(
            [item.model_dump() for item in items],
            practitioner,
            "patient",
            organization_id,
        )
        # Convert back to response models
        items = [PatientResponse(**item) for item in items]

    return PatientListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Get patient details."""
    service = PatientService(db)
    patient = service.get_by_id(patient_id)

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    # Check access using parallel mode
    engine = PolicyEngine(db)
    if not engine.is_authorized_with_parallel_check(
        practitioner,
        Permission.MANAGE_PATIENTS,
        patient.organization_id,
        action="read",
        resource_type="patient",
        resource_id=patient_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this patient",
        )

    # Log access
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    ctx.organization_id = patient.organization_id

    audit = AuditLogger(db)
    audit.log_access(
        resource_type="patient",
        resource_id=patient.id,
        resource_name=patient.full_name,
        phi_fields_accessed=["first_name", "last_name", "date_of_birth", "email", "phone"],
    )

    response = _patient_to_response(patient, db)

    # Filter response fields based on Cedar policies (if enabled)
    if sl_settings.use_cedar_auth:
        filtered = engine.filter_response_fields(
            response.model_dump(),
            practitioner,
            "patient",
            patient.organization_id,
        )
        return PatientResponse(**filtered)

    return response


@router.post("", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(
    request: PatientCreate,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Create a new patient."""
    # Check access
    engine = PolicyEngine(db)
    if not engine.has_permission(
        practitioner, Permission.MANAGE_PATIENTS, request.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create patients in this organization",
        )

    # Create patient
    service = PatientService(db)
    patient = service.create(request)

    # Generate activation code
    enrollment_service = EnrollmentService(db)
    activation_code = enrollment_service.generate_activation_code(patient)

    # Log creation
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    ctx.organization_id = request.organization_id

    audit = AuditLogger(db)
    audit.log_create(
        resource_type="patient",
        resource_id=patient.id,
        resource_name=patient.full_name,
        details={"activation_code_generated": True},
    )

    db.commit()

    # Reload to get relationships
    patient = service.get_by_id(patient.id)

    return _patient_to_response(patient, db)


@router.patch("/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_id: UUID,
    request: PatientUpdate,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Update a patient."""
    service = PatientService(db)
    patient = service.get_by_id(patient_id)

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    # Check access
    engine = PolicyEngine(db)
    if not engine.can_access_patient(practitioner, patient.organization_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this patient",
        )

    # Track changes for audit
    changes = {}
    update_data = request.model_dump(exclude_unset=True)
    for field, new_value in update_data.items():
        old_value = getattr(patient, field)
        if old_value != new_value:
            changes[field] = {"old": str(old_value), "new": str(new_value)}

    # Update patient
    patient = service.update(patient, request)

    # Log update
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    ctx.organization_id = patient.organization_id

    audit = AuditLogger(db)
    audit.log_update(
        resource_type="patient",
        resource_id=patient.id,
        resource_name=patient.full_name,
        changes=changes,
    )

    db.commit()

    return _patient_to_response(patient, db)


@router.post("/{patient_id}/generate-activation-code")
async def generate_activation_code(
    patient_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Generate a new activation code for a patient."""
    service = PatientService(db)
    patient = service.get_by_id(patient_id)

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    # Check access
    engine = PolicyEngine(db)
    if not engine.can_access_patient(practitioner, patient.organization_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage this patient",
        )

    # Generate new code
    enrollment_service = EnrollmentService(db)
    code = enrollment_service.generate_activation_code(patient)

    # Log action
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    ctx.organization_id = patient.organization_id

    audit = AuditLogger(db)
    audit.log(
        action="generate_activation_code",
        resource_type="patient",
        resource_id=patient.id,
        resource_name=patient.full_name,
    )

    db.commit()

    return {
        "activation_code": code,
        "expires_at": patient.activation_code_expires_at.isoformat(),
    }


@router.post("/{patient_id}/discharge")
async def discharge_patient(
    patient_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Discharge a patient from monitoring."""
    service = PatientService(db)
    patient = service.get_by_id(patient_id)

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    # Check access
    engine = PolicyEngine(db)
    if not engine.can_access_patient(practitioner, patient.organization_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage this patient",
        )

    # Discharge
    service.discharge(patient)

    # Log action
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    ctx.organization_id = patient.organization_id

    audit = AuditLogger(db)
    audit.log(
        action="discharge",
        resource_type="patient",
        resource_id=patient.id,
        resource_name=patient.full_name,
    )

    db.commit()

    return {"success": True, "message": "Patient discharged successfully"}
