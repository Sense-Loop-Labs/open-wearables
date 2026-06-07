"""Organization management endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.database import DbSession
from sense_loop.access import CurrentPractitioner, Permission, PolicyEngine
from sense_loop.audit import AuditLogger, get_audit_context
from sense_loop.models import Alert, Organization, Patient, PractitionerRole
from sense_loop.schemas.organization import (
    OrganizationCreate,
    OrganizationListResponse,
    OrganizationResponse,
    OrganizationStats,
    OrganizationUpdate,
)

router = APIRouter()


def _org_to_response(org: Organization, stats: OrganizationStats | None = None) -> OrganizationResponse:
    """Convert organization model to response schema."""
    return OrganizationResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        description=org.description,
        contact_email=org.contact_email,
        contact_phone=org.contact_phone,
        address=org.address,
        settings=org.settings,
        is_active=org.is_active,
        created_at=org.created_at,
        stats=stats,
    )


def _get_org_stats(db, org_id: UUID) -> OrganizationStats:
    """Calculate organization statistics."""
    # Total patients
    total_patients = db.execute(
        select(func.count())
        .select_from(Patient)
        .where(Patient.organization_id == org_id)
    ).scalar() or 0

    # Active patients
    active_patients = db.execute(
        select(func.count())
        .select_from(Patient)
        .where(
            Patient.organization_id == org_id,
            Patient.is_active == True,  # noqa: E712
            Patient.enrollment_status.in_(["activated", "active"]),
        )
    ).scalar() or 0

    # Total practitioners
    total_practitioners = db.execute(
        select(func.count(func.distinct(PractitionerRole.practitioner_id)))
        .where(
            PractitionerRole.organization_id == org_id,
            PractitionerRole.is_active == True,  # noqa: E712
        )
    ).scalar() or 0

    # Active alerts
    active_alerts = db.execute(
        select(func.count())
        .select_from(Alert)
        .where(
            Alert.organization_id == org_id,
            Alert.status == "active",
        )
    ).scalar() or 0

    # Critical alerts
    critical_alerts = db.execute(
        select(func.count())
        .select_from(Alert)
        .where(
            Alert.organization_id == org_id,
            Alert.status == "active",
            Alert.severity == "critical",
        )
    ).scalar() or 0

    return OrganizationStats(
        total_patients=total_patients,
        active_patients=active_patients,
        total_practitioners=total_practitioners,
        active_alerts=active_alerts,
        critical_alerts=critical_alerts,
    )


@router.get("", response_model=OrganizationListResponse)
async def list_organizations(
    db: DbSession,
    practitioner: CurrentPractitioner,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List organizations the practitioner has access to."""
    engine = PolicyEngine(db)
    org_ids = engine.get_accessible_org_ids(practitioner)

    if not org_ids:
        return OrganizationListResponse(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
            pages=0,
        )

    stmt = (
        select(Organization)
        .where(Organization.id.in_(org_ids))
        .order_by(Organization.name)
    )

    # Count total
    total = len(org_ids)

    # Paginate
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    orgs = db.execute(stmt).scalars().all()

    pages = (total + page_size - 1) // page_size

    return OrganizationListResponse(
        items=[_org_to_response(o) for o in orgs],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{organization_id}", response_model=OrganizationResponse)
async def get_organization(
    organization_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
    include_stats: bool = Query(True),
):
    """Get organization details."""
    engine = PolicyEngine(db)

    # Check access
    if organization_id not in engine.get_accessible_org_ids(practitioner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this organization",
        )

    stmt = select(Organization).where(Organization.id == organization_id)
    org = db.execute(stmt).scalar_one_or_none()

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Get stats if requested
    stats = None
    if include_stats:
        stats = _get_org_stats(db, organization_id)

    # Log access
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    ctx.organization_id = organization_id

    audit = AuditLogger(db)
    audit.log_access(
        resource_type="organization",
        resource_id=org.id,
        resource_name=org.name,
    )

    return _org_to_response(org, stats)


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    request: OrganizationCreate,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Create a new organization (requires super admin)."""
    from uuid import uuid4

    # Check for super admin role
    engine = PolicyEngine(db)
    has_super_admin = False
    for role in practitioner.practitioner_roles:
        if role.role_definition.code == "super_admin":
            has_super_admin = True
            break

    if not has_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can create organizations",
        )

    # Check slug uniqueness
    existing = db.execute(
        select(Organization).where(Organization.slug == request.slug)
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization slug already exists",
        )

    # Create organization
    org = Organization(
        id=uuid4(),
        name=request.name,
        slug=request.slug,
        description=request.description,
        contact_email=request.contact_email,
        contact_phone=request.contact_phone,
        address=request.address,
        settings=request.settings,
    )

    db.add(org)

    # Log creation
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)

    audit = AuditLogger(db)
    audit.log_create(
        resource_type="organization",
        resource_id=org.id,
        resource_name=org.name,
    )

    db.commit()

    return _org_to_response(org)


@router.patch("/{organization_id}", response_model=OrganizationResponse)
async def update_organization(
    organization_id: UUID,
    request: OrganizationUpdate,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Update organization settings."""
    engine = PolicyEngine(db)

    # Check access
    if not engine.has_permission(
        practitioner, Permission.MANAGE_ORG_SETTINGS, organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this organization",
        )

    stmt = select(Organization).where(Organization.id == organization_id)
    org = db.execute(stmt).scalar_one_or_none()

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Track changes
    changes = {}
    update_data = request.model_dump(exclude_unset=True)
    for field, new_value in update_data.items():
        old_value = getattr(org, field)
        if old_value != new_value:
            changes[field] = {"old": str(old_value), "new": str(new_value)}
            setattr(org, field, new_value)

    # Log update
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    ctx.organization_id = organization_id

    audit = AuditLogger(db)
    audit.log_update(
        resource_type="organization",
        resource_id=org.id,
        resource_name=org.name,
        changes=changes,
    )

    db.commit()

    return _org_to_response(org)
