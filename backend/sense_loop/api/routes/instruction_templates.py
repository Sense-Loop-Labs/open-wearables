"""Instruction template API routes for clinicians."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.database import DbSession
from sense_loop.access import CurrentPractitioner, Permission, PolicyEngine
from sense_loop.audit import AuditLogger, get_audit_context
from sense_loop.models import Patient
from sense_loop.schemas.instruction_template import (
    ActivityTemplateCreate,
    ActivityTemplateListResponse,
    ActivityTemplateResponse,
    ActivityTemplateUpdate,
    InstructionTemplateCreate,
    InstructionTemplateListResponse,
    InstructionTemplatePreview,
    InstructionTemplateResponse,
    InstructionTemplateUpdate,
    PatientPlanAssign,
    PatientPlanContent,
    PatientPlanListResponse,
    PatientPlanResponse,
    PatientPlanUpdate,
)
from sense_loop.services import (
    ActivityTemplateService,
    InstructionTemplateService,
    PatientInstructionPlanService,
    PatientService,
    TaskGenerationService,
)

router = APIRouter()


# =============================================================================
# Activity Templates
# =============================================================================


@router.get("/activities", response_model=ActivityTemplateListResponse)
async def list_activity_templates(
    db: DbSession,
    practitioner: CurrentPractitioner,
    organization_id: UUID | None = Query(None),
    include_shared: bool = Query(True),
    status: str | None = Query(None),
    category: str | None = Query(None),
):
    """List activity templates."""
    # Check access
    engine = PolicyEngine(db)
    if organization_id and not engine.has_permission(
        practitioner, Permission.MANAGE_CARE_PLANS, organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access templates in this organization",
        )

    service = ActivityTemplateService(db)
    templates = service.list(
        organization_id=organization_id,
        include_shared=include_shared,
        status=status,
        category=category,
    )

    return ActivityTemplateListResponse(
        items=[_activity_to_response(t) for t in templates],
        total=len(templates),
    )


@router.get("/activities/{template_id}", response_model=ActivityTemplateResponse)
async def get_activity_template(
    template_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Get an activity template by ID."""
    service = ActivityTemplateService(db)
    template = service.get_by_id(template_id)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity template not found",
        )

    return _activity_to_response(template)


@router.post(
    "/activities",
    response_model=ActivityTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_activity_template(
    request: ActivityTemplateCreate,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Create a new activity template."""
    # Check access
    engine = PolicyEngine(db)
    if request.organization_id and not engine.has_permission(
        practitioner, Permission.MANAGE_CARE_PLANS, request.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create templates in this organization",
        )

    service = ActivityTemplateService(db)
    template = service.create(
        title=request.title,
        description=request.description,
        category_code=request.category_code,
        created_by=practitioner,
        organization_id=request.organization_id,
        kind=request.kind,
        completion_method=request.completion_method,
        data_trigger_types=request.data_trigger_types,
        data_threshold=request.data_threshold,
        confirmation_prompt=request.confirmation_prompt,
        content=request.content,
        default_timing=request.default_timing,
        code_system=request.code_system,
        code_value=request.code_value,
    )

    # Audit log
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    audit = AuditLogger(db)
    audit.log_create(
        resource_type="activity_template",
        resource_id=template.id,
        resource_name=template.title,
    )

    db.commit()
    return _activity_to_response(template)


@router.patch("/activities/{template_id}", response_model=ActivityTemplateResponse)
async def update_activity_template(
    template_id: UUID,
    request: ActivityTemplateUpdate,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Update an activity template."""
    service = ActivityTemplateService(db)
    template = service.get_by_id(template_id)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity template not found",
        )

    # Check access
    engine = PolicyEngine(db)
    if template.organization_id and not engine.has_permission(
        practitioner, Permission.MANAGE_CARE_PLANS, template.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this template",
        )

    template = service.update(
        template,
        **request.model_dump(exclude_unset=True),
    )

    # Audit log
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    audit = AuditLogger(db)
    audit.log_update(
        resource_type="activity_template",
        resource_id=template.id,
        resource_name=template.title,
    )

    db.commit()
    return _activity_to_response(template)


@router.post("/activities/{template_id}/activate", response_model=ActivityTemplateResponse)
async def activate_activity_template(
    template_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Activate an activity template."""
    service = ActivityTemplateService(db)
    template = service.get_by_id(template_id)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity template not found",
        )

    template = service.activate(template)
    db.commit()
    return _activity_to_response(template)


@router.post("/activities/{template_id}/retire", response_model=ActivityTemplateResponse)
async def retire_activity_template(
    template_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Retire an activity template."""
    service = ActivityTemplateService(db)
    template = service.get_by_id(template_id)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity template not found",
        )

    template = service.retire(template)
    db.commit()
    return _activity_to_response(template)


# =============================================================================
# Instruction Templates
# =============================================================================


@router.get("", response_model=InstructionTemplateListResponse)
async def list_instruction_templates(
    db: DbSession,
    practitioner: CurrentPractitioner,
    organization_id: UUID | None = Query(None),
    include_shared: bool = Query(True),
    status: str | None = Query(None),
    health_focus: str | None = Query(None),
):
    """List instruction templates."""
    service = InstructionTemplateService(db)
    templates = service.list(
        organization_id=organization_id,
        include_shared=include_shared,
        status=status,
        health_focus=health_focus,
    )

    return InstructionTemplateListResponse(
        items=[_template_to_response(t) for t in templates],
        total=len(templates),
    )


@router.get("/{template_id}", response_model=InstructionTemplateResponse)
async def get_instruction_template(
    template_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Get an instruction template by ID."""
    service = InstructionTemplateService(db)
    template = service.get_by_id(template_id)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instruction template not found",
        )

    return _template_to_response(template)


@router.get("/{template_id}/preview", response_model=InstructionTemplatePreview)
async def preview_instruction_template(
    template_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Get a preview of the template with all references resolved."""
    service = InstructionTemplateService(db)
    template = service.get_by_id(template_id)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instruction template not found",
        )

    return service.preview(template)


@router.post(
    "",
    response_model=InstructionTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_instruction_template(
    request: InstructionTemplateCreate,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Create a new instruction template."""
    service = InstructionTemplateService(db)
    template = service.create(
        title=request.title,
        description=request.description,
        created_by=practitioner,
        organization_id=request.organization_id,
        content=request.content,
        health_focus_codes=request.health_focus_codes,
        notification_config=request.notification_config,
    )

    # Audit log
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    audit = AuditLogger(db)
    audit.log_create(
        resource_type="instruction_template",
        resource_id=template.id,
        resource_name=template.title,
    )

    db.commit()
    return _template_to_response(template)


@router.patch("/{template_id}", response_model=InstructionTemplateResponse)
async def update_instruction_template(
    template_id: UUID,
    request: InstructionTemplateUpdate,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Update an instruction template."""
    service = InstructionTemplateService(db)
    template = service.get_by_id(template_id)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instruction template not found",
        )

    template = service.update(
        template,
        **request.model_dump(exclude_unset=True),
    )

    # Audit log
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    audit = AuditLogger(db)
    audit.log_update(
        resource_type="instruction_template",
        resource_id=template.id,
        resource_name=template.title,
    )

    db.commit()
    return _template_to_response(template)


@router.post("/{template_id}/activate", response_model=InstructionTemplateResponse)
async def activate_instruction_template(
    template_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Activate an instruction template."""
    service = InstructionTemplateService(db)
    template = service.get_by_id(template_id)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instruction template not found",
        )

    template = service.activate(template)
    db.commit()
    return _template_to_response(template)


@router.post("/{template_id}/retire", response_model=InstructionTemplateResponse)
async def retire_instruction_template(
    template_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Retire an instruction template."""
    service = InstructionTemplateService(db)
    template = service.get_by_id(template_id)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instruction template not found",
        )

    template = service.retire(template)
    db.commit()
    return _template_to_response(template)


@router.post("/{template_id}/duplicate", response_model=InstructionTemplateResponse)
async def duplicate_instruction_template(
    template_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
    to_organization_id: UUID | None = Query(None),
    new_title: str | None = Query(None),
):
    """Duplicate an instruction template."""
    service = InstructionTemplateService(db)
    template = service.get_by_id(template_id)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instruction template not found",
        )

    new_template = service.duplicate(
        template,
        created_by=practitioner,
        to_organization_id=to_organization_id,
        new_title=new_title,
    )

    db.commit()
    return _template_to_response(new_template)


# =============================================================================
# Patient Instruction Plans
# =============================================================================


@router.get("/patients/{patient_id}/plans", response_model=PatientPlanListResponse)
async def list_patient_plans(
    patient_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
    status: str | None = Query(None),
):
    """List instruction plans for a patient."""
    patient_service = PatientService(db)
    patient = patient_service.get_by_id(patient_id)

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

    service = PatientInstructionPlanService(db)
    plans = service.list_for_patient(patient_id, status=status)

    return PatientPlanListResponse(
        items=[_plan_to_response(p) for p in plans],
        total=len(plans),
    )


@router.post(
    "/patients/{patient_id}/plans",
    response_model=PatientPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assign_plan_to_patient(
    patient_id: UUID,
    request: PatientPlanAssign,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Assign an instruction template to a patient."""
    patient_service = PatientService(db)
    patient = patient_service.get_by_id(patient_id)

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

    # Get template
    template_service = InstructionTemplateService(db)
    template = template_service.get_by_id(request.template_id)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instruction template not found",
        )

    # Get task generation service
    task_service = TaskGenerationService(db) if request.generate_tasks else None

    # Assign plan
    plan_service = PatientInstructionPlanService(db)
    plan = plan_service.assign(
        patient=patient,
        template=template,
        assigned_by=practitioner,
        effective_start=request.effective_start,
        effective_end=request.effective_end,
        customizations=request.customizations,
        reference_date=request.reference_date,
        reference_type=request.reference_type,
        generate_tasks=request.generate_tasks,
        task_generation_service=task_service,
    )

    # Audit log
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    ctx.organization_id = patient.organization_id
    audit = AuditLogger(db)
    audit.log_create(
        resource_type="patient_instruction_plan",
        resource_id=plan.id,
        resource_name=template.title,
        details={"patient_id": str(patient_id), "template_id": str(template.id)},
    )

    db.commit()
    return _plan_to_response(plan)


@router.get("/patients/{patient_id}/plans/{plan_id}", response_model=PatientPlanResponse)
async def get_patient_plan(
    patient_id: UUID,
    plan_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Get a specific patient instruction plan."""
    service = PatientInstructionPlanService(db)
    plan = service.get_by_id(plan_id)

    if not plan or plan.patient_id != patient_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )

    return _plan_to_response(plan)


@router.get(
    "/patients/{patient_id}/plans/{plan_id}/content",
    response_model=PatientPlanContent,
)
async def get_patient_plan_content(
    patient_id: UUID,
    plan_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Get patient plan with fully resolved content."""
    service = PatientInstructionPlanService(db)
    plan = service.get_by_id(plan_id)

    if not plan or plan.patient_id != patient_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )

    content = service.get_resolved_content_with_activities(plan)

    return PatientPlanContent(
        id=plan.id,
        patient_id=plan.patient_id,
        template_title=plan.template.title if plan.template else "",
        status=plan.status,
        effective_start=plan.effective_start,
        effective_end=plan.effective_end,
        content=content,
    )


@router.patch(
    "/patients/{patient_id}/plans/{plan_id}",
    response_model=PatientPlanResponse,
)
async def update_patient_plan(
    patient_id: UUID,
    plan_id: UUID,
    request: PatientPlanUpdate,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Update a patient instruction plan."""
    plan_service = PatientInstructionPlanService(db)
    plan = plan_service.get_by_id(plan_id)

    if not plan or plan.patient_id != patient_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )

    # Get task generation service if needed
    task_service = (
        TaskGenerationService(db) if request.regenerate_tasks else None
    )

    plan = plan_service.update(
        plan,
        customizations=request.customizations,
        effective_end=request.effective_end,
        regenerate_tasks=request.regenerate_tasks,
        task_generation_service=task_service,
    )

    db.commit()
    return _plan_to_response(plan)


@router.post(
    "/patients/{patient_id}/plans/{plan_id}/complete",
    response_model=PatientPlanResponse,
)
async def complete_patient_plan(
    patient_id: UUID,
    plan_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Mark a patient instruction plan as completed."""
    service = PatientInstructionPlanService(db)
    plan = service.get_by_id(plan_id)

    if not plan or plan.patient_id != patient_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )

    plan = service.complete(plan)
    db.commit()
    return _plan_to_response(plan)


@router.post(
    "/patients/{patient_id}/plans/{plan_id}/cancel",
    response_model=PatientPlanResponse,
)
async def cancel_patient_plan(
    patient_id: UUID,
    plan_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
    cancel_pending_tasks: bool = Query(True),
):
    """Cancel a patient instruction plan."""
    service = PatientInstructionPlanService(db)
    plan = service.get_by_id(plan_id)

    if not plan or plan.patient_id != patient_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )

    plan = service.cancel(plan, cancel_pending_tasks=cancel_pending_tasks)
    db.commit()
    return _plan_to_response(plan)


# =============================================================================
# Helper Functions
# =============================================================================


def _activity_to_response(template) -> ActivityTemplateResponse:
    """Convert activity template model to response."""
    return ActivityTemplateResponse(
        id=template.id,
        organization_id=template.organization_id,
        name=template.name,
        title=template.title,
        description=template.description,
        status=template.status,
        version=template.version,
        category_code=template.category_code,
        kind=template.kind,
        completion_method=template.completion_method,
        data_trigger_types=template.data_trigger_types,
        data_threshold=template.data_threshold,
        confirmation_prompt=template.confirmation_prompt,
        content=template.content or {},
        default_timing=template.default_timing,
        code_system=template.code_system,
        code_value=template.code_value,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


def _template_to_response(template) -> InstructionTemplateResponse:
    """Convert instruction template model to response."""
    return InstructionTemplateResponse(
        id=template.id,
        organization_id=template.organization_id,
        name=template.name,
        title=template.title,
        description=template.description,
        status=template.status,
        version=template.version,
        content=template.content or {},
        health_focus_codes=template.health_focus_codes,
        notification_config=template.notification_config,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


def _plan_to_response(plan) -> PatientPlanResponse:
    """Convert patient instruction plan model to response."""
    return PatientPlanResponse(
        id=plan.id,
        patient_id=plan.patient_id,
        template_id=plan.template_id,
        template_name=plan.template.name if plan.template else None,
        template_title=plan.template.title if plan.template else None,
        status=plan.status,
        effective_start=plan.effective_start,
        effective_end=plan.effective_end,
        customizations=plan.customizations,
        reference_date=plan.reference_date,
        reference_type=plan.reference_type,
        tasks_generated_through=plan.tasks_generated_through,
        assigned_by_id=plan.assigned_by_id,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )
