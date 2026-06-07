"""Patient management endpoints for clinicians."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.database import DbSession
from sense_loop.access import CurrentPractitioner, Permission, PolicyEngine
from sense_loop.audit import AuditLogger, get_audit_context
from sense_loop.schemas.patient import (
    PatientCreate,
    PatientListResponse,
    PatientResponse,
    PatientSummaryResponse,
    PatientUpdate,
)
from sense_loop.services import EnrollmentService, PatientService

router = APIRouter()


def _patient_to_response(patient) -> PatientResponse:
    """Convert patient model to response schema."""
    summary = None
    if patient.summary:
        summary = PatientSummaryResponse(
            latest_heart_rate=patient.summary.latest_heart_rate,
            latest_heart_rate_at=patient.summary.latest_heart_rate_at,
            latest_spo2=patient.summary.latest_spo2,
            latest_spo2_at=patient.summary.latest_spo2_at,
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
    # Check access
    engine = PolicyEngine(db)
    if not engine.has_permission(
        practitioner, Permission.MANAGE_PATIENTS, organization_id
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

    return PatientListResponse(
        items=[_patient_to_response(p) for p in patients],
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

    # Check access
    engine = PolicyEngine(db)
    if not engine.can_access_patient(practitioner, patient.organization_id):
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

    return _patient_to_response(patient)


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

    return _patient_to_response(patient)


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

    return _patient_to_response(patient)


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
