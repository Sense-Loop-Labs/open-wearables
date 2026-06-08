"""Clinical action endpoints for logging clinician actions on patients."""

from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, func

from app.database import DbSession
from sense_loop.access import CurrentPractitioner, PolicyEngine
from sense_loop.audit import AuditLogger, get_audit_context
from sense_loop.models import ClinicalAction, Patient
from sense_loop.schemas.clinical_action import (
    ClinicalActionCreate,
    ClinicalActionResponse,
    ClinicalActionListResponse,
)

router = APIRouter()


def _action_to_response(action: ClinicalAction) -> ClinicalActionResponse:
    """Convert clinical action model to response schema."""
    return ClinicalActionResponse(
        id=action.id,
        patient_id=action.patient_id,
        organization_id=action.organization_id,
        practitioner_id=action.practitioner_id,
        action_type=action.action_type,
        category_display=action.category_display,
        notes=action.notes,
        practitioner_name=action.practitioner_name,
        related_alert_ids=action.related_alert_ids,
        created_at=action.created_at,
    )


@router.get("/{patient_id}/actions", response_model=ClinicalActionListResponse)
async def list_clinical_actions(
    patient_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List clinical actions for a patient."""
    # Get patient
    patient = db.execute(
        select(Patient).where(Patient.id == patient_id)
    ).scalar_one_or_none()

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

    # Count total
    total = db.execute(
        select(func.count())
        .select_from(ClinicalAction)
        .where(ClinicalAction.patient_id == patient_id)
    ).scalar() or 0

    # Get paginated actions
    offset = (page - 1) * page_size
    actions = db.execute(
        select(ClinicalAction)
        .where(ClinicalAction.patient_id == patient_id)
        .order_by(ClinicalAction.created_at.desc())
        .offset(offset)
        .limit(page_size)
    ).scalars().all()

    pages = (total + page_size - 1) // page_size

    return ClinicalActionListResponse(
        items=[_action_to_response(a) for a in actions],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post(
    "/{patient_id}/actions",
    response_model=ClinicalActionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_clinical_action(
    patient_id: UUID,
    request: ClinicalActionCreate,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Create a new clinical action for a patient."""
    # Get patient
    patient = db.execute(
        select(Patient).where(Patient.id == patient_id)
    ).scalar_one_or_none()

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

    # Create action
    action = ClinicalAction(
        id=uuid4(),
        patient_id=patient_id,
        organization_id=patient.organization_id,
        practitioner_id=practitioner.id,
        action_type=request.action_type,
        notes=request.notes,
        related_alert_ids=[str(aid) for aid in request.related_alert_ids]
        if request.related_alert_ids
        else None,
    )
    db.add(action)

    # Log action
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    ctx.organization_id = patient.organization_id

    audit = AuditLogger(db)
    audit.log_create(
        resource_type="clinical_action",
        resource_id=action.id,
        resource_name=f"{action.category_display} for {patient.full_name}",
        details={
            "action_type": action.action_type,
            "patient_id": str(patient_id),
        },
    )

    db.commit()
    db.refresh(action)

    return _action_to_response(action)
