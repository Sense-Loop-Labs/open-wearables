"""Questionnaire template API routes for clinicians."""

from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.database import DbSession
from sense_loop.access import CurrentPractitioner, Permission, PolicyEngine
from sense_loop.audit import AuditLogger, get_audit_context
from sense_loop.models import Questionnaire, QuestionnaireQuestion, Patient, QuestionnaireResponse as QuestionnaireResponseModel
from sense_loop.services.questionnaire_service import QuestionnaireService
from sense_loop.schemas.questionnaire import (
    QuestionCreate,
    QuestionnaireCreate,
    QuestionnaireDetailResponse,
    QuestionnaireListResponse,
    QuestionnaireResponse,
    QuestionnaireUpdate,
    QuestionReorderRequest,
    QuestionResponse,
    QuestionUpdate,
    QuestionnaireAssignRequest,
    PatientQuestionnaireResponse,
    PatientQuestionnaireListResponse,
)

router = APIRouter()


# =============================================================================
# Questionnaire Templates
# =============================================================================


@router.get("", response_model=QuestionnaireListResponse)
async def list_questionnaires(
    db: DbSession,
    practitioner: CurrentPractitioner,
    organization_id: UUID | None = Query(None),
    include_shared: bool = Query(True),
    is_active: bool | None = Query(None),
    questionnaire_type: str | None = Query(None),
    category: str | None = Query(None),
):
    """List questionnaire templates."""
    # Check access
    engine = PolicyEngine(db)
    if organization_id and not engine.has_permission(
        practitioner, Permission.MANAGE_CARE_PLANS, organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access questionnaires in this organization",
        )

    stmt = select(Questionnaire).options(joinedload(Questionnaire.questions))

    # Filter by organization
    if organization_id:
        if include_shared:
            stmt = stmt.where(
                (Questionnaire.organization_id == organization_id) |
                (Questionnaire.organization_id.is_(None))
            )
        else:
            stmt = stmt.where(Questionnaire.organization_id == organization_id)
    elif include_shared:
        stmt = stmt.where(Questionnaire.organization_id.is_(None))

    # Filter by active status
    if is_active is not None:
        stmt = stmt.where(Questionnaire.is_active == is_active)

    # Filter by type
    if questionnaire_type:
        stmt = stmt.where(Questionnaire.questionnaire_type == questionnaire_type)

    # Filter by category
    if category:
        stmt = stmt.where(Questionnaire.category == category)

    # Order by title
    stmt = stmt.order_by(Questionnaire.title)

    result = db.execute(stmt)
    questionnaires = result.unique().scalars().all()

    return QuestionnaireListResponse(
        items=[_questionnaire_to_response(q) for q in questionnaires],
        total=len(questionnaires),
    )


@router.get("/{questionnaire_id}", response_model=QuestionnaireDetailResponse)
async def get_questionnaire(
    questionnaire_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Get a questionnaire template by ID with all questions."""
    stmt = (
        select(Questionnaire)
        .where(Questionnaire.id == questionnaire_id)
        .options(joinedload(Questionnaire.questions))
    )
    questionnaire = db.execute(stmt).unique().scalar_one_or_none()

    if not questionnaire:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Questionnaire not found",
        )

    return _questionnaire_to_detail_response(questionnaire)


@router.post(
    "",
    response_model=QuestionnaireDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_questionnaire(
    request: QuestionnaireCreate,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Create a new questionnaire template."""
    # Check access
    engine = PolicyEngine(db)
    if request.organization_id and not engine.has_permission(
        practitioner, Permission.MANAGE_CARE_PLANS, request.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create questionnaires in this organization",
        )

    # Check for duplicate code
    existing = db.execute(
        select(Questionnaire).where(
            Questionnaire.code == request.code,
            (Questionnaire.organization_id == request.organization_id) if request.organization_id else Questionnaire.organization_id.is_(None),
        )
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Questionnaire with code '{request.code}' already exists",
        )

    # Create questionnaire
    questionnaire = Questionnaire(
        id=uuid4(),
        organization_id=request.organization_id,
        title=request.title,
        code=request.code,
        description=request.description,
        questionnaire_type=request.questionnaire_type,
        category=request.category,
        estimated_minutes=request.estimated_minutes,
        allow_skip=request.allow_skip,
        require_completion=request.require_completion,
        has_scoring=request.has_scoring,
        scoring_config=request.scoring_config.model_dump() if request.scoring_config else None,
        is_active=True,
        version=1,
    )

    db.add(questionnaire)
    db.flush()

    # Create questions if provided
    if request.questions:
        for idx, q in enumerate(request.questions):
            question = QuestionnaireQuestion(
                id=uuid4(),
                questionnaire_id=questionnaire.id,
                code=q.code,
                text=q.text,
                help_text=q.help_text,
                question_type=q.question_type,
                order=q.order if q.order else idx,
                is_required=q.is_required,
                validation=q.validation.model_dump() if q.validation else None,
                options=[opt.model_dump() for opt in q.options] if q.options else None,
                condition=q.condition.model_dump() if q.condition else None,
                score_weight=q.score_weight,
                alert_config=q.alert_config.model_dump() if q.alert_config else None,
                is_active=True,
            )
            db.add(question)

    # Audit log
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    audit = AuditLogger(db)
    audit.log_create(
        resource_type="questionnaire",
        resource_id=questionnaire.id,
        resource_name=questionnaire.title,
    )

    db.commit()

    # Refresh to get questions
    db.refresh(questionnaire)
    return _questionnaire_to_detail_response(questionnaire)


@router.patch("/{questionnaire_id}", response_model=QuestionnaireDetailResponse)
async def update_questionnaire(
    questionnaire_id: UUID,
    request: QuestionnaireUpdate,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Update a questionnaire template."""
    stmt = (
        select(Questionnaire)
        .where(Questionnaire.id == questionnaire_id)
        .options(joinedload(Questionnaire.questions))
    )
    questionnaire = db.execute(stmt).unique().scalar_one_or_none()

    if not questionnaire:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Questionnaire not found",
        )

    # Check access
    engine = PolicyEngine(db)
    if questionnaire.organization_id and not engine.has_permission(
        practitioner, Permission.MANAGE_CARE_PLANS, questionnaire.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this questionnaire",
        )

    # Update fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "scoring_config" and value is not None:
            setattr(questionnaire, field, value.model_dump() if hasattr(value, 'model_dump') else value)
        else:
            setattr(questionnaire, field, value)

    # Audit log
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    audit = AuditLogger(db)
    audit.log_update(
        resource_type="questionnaire",
        resource_id=questionnaire.id,
        resource_name=questionnaire.title,
        changes=update_data,
    )

    db.commit()
    db.refresh(questionnaire)
    return _questionnaire_to_detail_response(questionnaire)


@router.post("/{questionnaire_id}/activate", response_model=QuestionnaireResponse)
async def activate_questionnaire(
    questionnaire_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Activate a questionnaire template."""
    questionnaire = db.execute(
        select(Questionnaire)
        .where(Questionnaire.id == questionnaire_id)
        .options(joinedload(Questionnaire.questions))
    ).unique().scalar_one_or_none()

    if not questionnaire:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Questionnaire not found",
        )

    questionnaire.is_active = True

    # Audit log
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    audit = AuditLogger(db)
    audit.log_update(
        resource_type="questionnaire",
        resource_id=questionnaire.id,
        resource_name=questionnaire.title,
        changes={"is_active": True},
    )

    db.commit()
    db.refresh(questionnaire)
    return _questionnaire_to_response(questionnaire)


@router.post("/{questionnaire_id}/retire", response_model=QuestionnaireResponse)
async def retire_questionnaire(
    questionnaire_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Retire (deactivate) a questionnaire template."""
    questionnaire = db.execute(
        select(Questionnaire)
        .where(Questionnaire.id == questionnaire_id)
        .options(joinedload(Questionnaire.questions))
    ).unique().scalar_one_or_none()

    if not questionnaire:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Questionnaire not found",
        )

    questionnaire.is_active = False

    # Audit log
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    audit = AuditLogger(db)
    audit.log_update(
        resource_type="questionnaire",
        resource_id=questionnaire.id,
        resource_name=questionnaire.title,
        changes={"is_active": False},
    )

    db.commit()
    db.refresh(questionnaire)
    return _questionnaire_to_response(questionnaire)


@router.post("/{questionnaire_id}/duplicate", response_model=QuestionnaireDetailResponse)
async def duplicate_questionnaire(
    questionnaire_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
    to_organization_id: UUID | None = Query(None),
    new_title: str | None = Query(None),
    new_code: str | None = Query(None),
):
    """Duplicate a questionnaire template."""
    stmt = (
        select(Questionnaire)
        .where(Questionnaire.id == questionnaire_id)
        .options(joinedload(Questionnaire.questions))
    )
    source = db.execute(stmt).unique().scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Questionnaire not found",
        )

    # Use the provided organization or source organization
    target_org = to_organization_id or source.organization_id

    # Check access to target organization
    engine = PolicyEngine(db)
    if target_org and not engine.has_permission(
        practitioner, Permission.MANAGE_CARE_PLANS, target_org
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create questionnaires in target organization",
        )

    # Create duplicate
    new_questionnaire = Questionnaire(
        id=uuid4(),
        organization_id=target_org,
        title=new_title or f"{source.title} (Copy)",
        code=new_code or f"{source.code}_copy",
        description=source.description,
        questionnaire_type=source.questionnaire_type,
        category=source.category,
        estimated_minutes=source.estimated_minutes,
        allow_skip=source.allow_skip,
        require_completion=source.require_completion,
        has_scoring=source.has_scoring,
        scoring_config=source.scoring_config,
        is_active=False,  # Start as inactive
        version=1,
    )

    db.add(new_questionnaire)
    db.flush()

    # Duplicate questions
    for q in source.questions:
        new_question = QuestionnaireQuestion(
            id=uuid4(),
            questionnaire_id=new_questionnaire.id,
            code=q.code,
            text=q.text,
            help_text=q.help_text,
            question_type=q.question_type,
            order=q.order,
            is_required=q.is_required,
            validation=q.validation,
            options=q.options,
            condition=q.condition,
            score_weight=q.score_weight,
            alert_config=q.alert_config,
            is_active=q.is_active,
        )
        db.add(new_question)

    # Audit log
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    audit = AuditLogger(db)
    audit.log_create(
        resource_type="questionnaire",
        resource_id=new_questionnaire.id,
        resource_name=new_questionnaire.title,
    )

    db.commit()
    db.refresh(new_questionnaire)
    return _questionnaire_to_detail_response(new_questionnaire)


# =============================================================================
# Questions
# =============================================================================


@router.post(
    "/{questionnaire_id}/questions",
    response_model=QuestionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_question(
    questionnaire_id: UUID,
    request: QuestionCreate,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Add a question to a questionnaire."""
    questionnaire = db.execute(
        select(Questionnaire).where(Questionnaire.id == questionnaire_id)
    ).scalar_one_or_none()

    if not questionnaire:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Questionnaire not found",
        )

    # Check access
    engine = PolicyEngine(db)
    if questionnaire.organization_id and not engine.has_permission(
        practitioner, Permission.MANAGE_CARE_PLANS, questionnaire.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this questionnaire",
        )

    # Check for duplicate code
    existing = db.execute(
        select(QuestionnaireQuestion).where(
            QuestionnaireQuestion.questionnaire_id == questionnaire_id,
            QuestionnaireQuestion.code == request.code,
        )
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Question with code '{request.code}' already exists in this questionnaire",
        )

    # Get max order
    max_order_result = db.execute(
        select(QuestionnaireQuestion.order)
        .where(QuestionnaireQuestion.questionnaire_id == questionnaire_id)
        .order_by(QuestionnaireQuestion.order.desc())
        .limit(1)
    ).scalar_one_or_none()
    max_order = max_order_result if max_order_result is not None else -1

    # Create question
    question = QuestionnaireQuestion(
        id=uuid4(),
        questionnaire_id=questionnaire_id,
        code=request.code,
        text=request.text,
        help_text=request.help_text,
        question_type=request.question_type,
        order=request.order if request.order else max_order + 1,
        is_required=request.is_required,
        validation=request.validation.model_dump() if request.validation else None,
        options=[opt.model_dump() for opt in request.options] if request.options else None,
        condition=request.condition.model_dump() if request.condition else None,
        score_weight=request.score_weight,
        alert_config=request.alert_config.model_dump() if request.alert_config else None,
        is_active=True,
    )

    db.add(question)
    db.commit()
    db.refresh(question)

    return _question_to_response(question)


@router.patch(
    "/{questionnaire_id}/questions/{question_id}",
    response_model=QuestionResponse,
)
async def update_question(
    questionnaire_id: UUID,
    question_id: UUID,
    request: QuestionUpdate,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Update a question."""
    question = db.execute(
        select(QuestionnaireQuestion).where(
            QuestionnaireQuestion.id == question_id,
            QuestionnaireQuestion.questionnaire_id == questionnaire_id,
        )
    ).scalar_one_or_none()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    # Check access
    questionnaire = db.execute(
        select(Questionnaire).where(Questionnaire.id == questionnaire_id)
    ).scalar_one_or_none()

    engine = PolicyEngine(db)
    if questionnaire and questionnaire.organization_id and not engine.has_permission(
        practitioner, Permission.MANAGE_CARE_PLANS, questionnaire.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this questionnaire",
        )

    # Update fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "validation" and value is not None:
            setattr(question, field, value.model_dump() if hasattr(value, 'model_dump') else value)
        elif field == "options" and value is not None:
            setattr(question, field, [opt.model_dump() if hasattr(opt, 'model_dump') else opt for opt in value])
        elif field == "condition" and value is not None:
            setattr(question, field, value.model_dump() if hasattr(value, 'model_dump') else value)
        elif field == "alert_config" and value is not None:
            setattr(question, field, value.model_dump() if hasattr(value, 'model_dump') else value)
        else:
            setattr(question, field, value)

    db.commit()
    db.refresh(question)

    return _question_to_response(question)


@router.delete(
    "/{questionnaire_id}/questions/{question_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_question(
    questionnaire_id: UUID,
    question_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Delete a question."""
    question = db.execute(
        select(QuestionnaireQuestion).where(
            QuestionnaireQuestion.id == question_id,
            QuestionnaireQuestion.questionnaire_id == questionnaire_id,
        )
    ).scalar_one_or_none()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    # Check access
    questionnaire = db.execute(
        select(Questionnaire).where(Questionnaire.id == questionnaire_id)
    ).scalar_one_or_none()

    engine = PolicyEngine(db)
    if questionnaire and questionnaire.organization_id and not engine.has_permission(
        practitioner, Permission.MANAGE_CARE_PLANS, questionnaire.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this questionnaire",
        )

    db.delete(question)
    db.commit()


@router.post(
    "/{questionnaire_id}/questions/reorder",
    response_model=QuestionnaireDetailResponse,
)
async def reorder_questions(
    questionnaire_id: UUID,
    request: QuestionReorderRequest,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Reorder questions in a questionnaire."""
    questionnaire = db.execute(
        select(Questionnaire)
        .where(Questionnaire.id == questionnaire_id)
        .options(joinedload(Questionnaire.questions))
    ).unique().scalar_one_or_none()

    if not questionnaire:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Questionnaire not found",
        )

    # Check access
    engine = PolicyEngine(db)
    if questionnaire.organization_id and not engine.has_permission(
        practitioner, Permission.MANAGE_CARE_PLANS, questionnaire.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this questionnaire",
        )

    # Update order for each question
    question_map = {q.id: q for q in questionnaire.questions}
    for item in request.questions:
        if item.question_id in question_map:
            question_map[item.question_id].order = item.order

    db.commit()
    db.refresh(questionnaire)

    return _questionnaire_to_detail_response(questionnaire)


# =============================================================================
# Patient Questionnaire Assignment
# =============================================================================


@router.post(
    "/patients/{patient_id}/assign",
    response_model=PatientQuestionnaireResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assign_questionnaire_to_patient(
    patient_id: UUID,
    request: QuestionnaireAssignRequest,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Assign a questionnaire to a patient (creates a pending response)."""
    # Get patient
    patient = db.execute(
        select(Patient).where(Patient.id == patient_id)
    ).scalar_one_or_none()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    # Check access to patient's organization
    engine = PolicyEngine(db)
    if not engine.has_permission(
        practitioner, Permission.MANAGE_PATIENTS, patient.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to assign questionnaires to this patient",
        )

    # Get questionnaire
    questionnaire = db.execute(
        select(Questionnaire).where(Questionnaire.id == request.questionnaire_id)
    ).scalar_one_or_none()

    if not questionnaire:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Questionnaire not found",
        )

    if not questionnaire.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot assign inactive questionnaire",
        )

    # Create response using service
    service = QuestionnaireService(db)
    response = service.create_response(
        patient_id=patient_id,
        questionnaire_id=request.questionnaire_id,
    )
    db.commit()

    return PatientQuestionnaireResponse(
        id=response.id,
        patient_id=response.patient_id,
        questionnaire_id=response.questionnaire_id,
        questionnaire_title=questionnaire.title,
        status=response.status,
        created_at=response.created_at,
        due_at=response.due_at,
    )


@router.get(
    "/patients/{patient_id}/assignments",
    response_model=PatientQuestionnaireListResponse,
)
async def list_patient_questionnaires(
    patient_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
    status_filter: str | None = Query(None, alias="status"),
):
    """List questionnaire assignments for a patient."""
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
    if not engine.has_permission(
        practitioner, Permission.MANAGE_PATIENTS, patient.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this patient's questionnaires",
        )

    # Get responses using service
    service = QuestionnaireService(db)
    responses = service.list_responses_for_patient(
        patient_id,
        status=status_filter,
    )

    items = []
    for response in responses:
        items.append(
            PatientQuestionnaireResponse(
                id=response.id,
                patient_id=response.patient_id,
                questionnaire_id=response.questionnaire_id,
                questionnaire_title=response.questionnaire.title if response.questionnaire else "Unknown",
                status=response.status,
                created_at=response.created_at,
                due_at=response.due_at,
            )
        )

    return PatientQuestionnaireListResponse(
        items=items,
        total=len(items),
    )


# =============================================================================
# Helper Functions
# =============================================================================


def _questionnaire_to_response(questionnaire: Questionnaire) -> QuestionnaireResponse:
    """Convert a questionnaire model to response schema."""
    return QuestionnaireResponse(
        id=questionnaire.id,
        organization_id=questionnaire.organization_id,
        title=questionnaire.title,
        code=questionnaire.code,
        description=questionnaire.description,
        questionnaire_type=questionnaire.questionnaire_type,
        category=questionnaire.category,
        estimated_minutes=questionnaire.estimated_minutes,
        allow_skip=questionnaire.allow_skip,
        require_completion=questionnaire.require_completion,
        has_scoring=questionnaire.has_scoring,
        scoring_config=questionnaire.scoring_config,
        is_active=questionnaire.is_active,
        version=questionnaire.version,
        question_count=len(questionnaire.questions) if questionnaire.questions else 0,
        created_at=questionnaire.created_at,
        updated_at=None,  # Model doesn't have updated_at
    )


def _questionnaire_to_detail_response(questionnaire: Questionnaire) -> QuestionnaireDetailResponse:
    """Convert a questionnaire model to detail response schema."""
    return QuestionnaireDetailResponse(
        id=questionnaire.id,
        organization_id=questionnaire.organization_id,
        title=questionnaire.title,
        code=questionnaire.code,
        description=questionnaire.description,
        questionnaire_type=questionnaire.questionnaire_type,
        category=questionnaire.category,
        estimated_minutes=questionnaire.estimated_minutes,
        allow_skip=questionnaire.allow_skip,
        require_completion=questionnaire.require_completion,
        has_scoring=questionnaire.has_scoring,
        scoring_config=questionnaire.scoring_config,
        is_active=questionnaire.is_active,
        version=questionnaire.version,
        question_count=len(questionnaire.questions) if questionnaire.questions else 0,
        created_at=questionnaire.created_at,
        updated_at=None,  # Model doesn't have updated_at
        questions=[_question_to_response(q) for q in sorted(questionnaire.questions, key=lambda x: x.order)] if questionnaire.questions else [],
    )


def _question_to_response(question: QuestionnaireQuestion) -> QuestionResponse:
    """Convert a question model to response schema."""
    return QuestionResponse(
        id=question.id,
        questionnaire_id=question.questionnaire_id,
        code=question.code,
        text=question.text,
        help_text=question.help_text,
        question_type=question.question_type,
        order=question.order,
        is_required=question.is_required,
        validation=question.validation,
        options=question.options,
        condition=question.condition,
        score_weight=question.score_weight,
        alert_config=question.alert_config,
        is_active=question.is_active,
        created_at=question.created_at,
        updated_at=None,  # Model doesn't have updated_at
    )
