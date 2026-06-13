"""Clinician management endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import or_

from app.database import DbSession
from sense_loop.access import CurrentPractitioner, Permission, PolicyEngine
from sense_loop.config import sl_settings
from sense_loop.audit import AuditLogger, get_audit_context
from sense_loop.models import RoleDefinition
from sense_loop.schemas.practitioner import (
    AcceptInviteRequest,
    AcceptInviteResponse,
    InviteRequest,
    InviteResponse,
    PendingInvite,
    PractitionerListResponse,
    PractitionerResponse,
    PractitionerRoleResponse,
    PractitionerUpdate,
    RoleDefinitionResponse,
)
from sense_loop.services import InviteService, NotificationService, PractitionerService

router = APIRouter()


@router.get("/roles", response_model=list[RoleDefinitionResponse])
async def list_assignable_roles(
    db: DbSession,
    practitioner: CurrentPractitioner,
    organization_id: UUID = Query(..., description="Organization to get roles for"),
):
    """List roles that the current user can assign when inviting clinicians.

    Returns roles where:
    - The role is active
    - The role's privilege_level <= the current user's highest privilege level
    - The role is either system-wide (org_id is None) or belongs to the specified org

    This prevents privilege escalation - users can only assign roles at or below
    their own level.
    """
    # Check that the user has permission to manage clinicians in this org
    engine = PolicyEngine(db)
    if not engine.has_permission(
        practitioner, Permission.MANAGE_CLINICIANS, organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage clinicians in this organization",
        )

    # Get the current user's highest privilege level in this organization
    user_max_privilege = 0
    for role in practitioner.practitioner_roles:
        if role.organization_id == organization_id and role.is_active:
            if role.role_definition and role.role_definition.privilege_level > user_max_privilege:
                user_max_privilege = role.role_definition.privilege_level

    if user_max_privilege == 0:
        # User has no active role in this org - shouldn't happen if they passed permission check
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active role in this organization",
        )

    # Query roles:
    # - Active roles only
    # - Privilege level <= user's level (allows assigning same level, e.g., org_admin can create org_admin)
    # - System-wide roles (org_id is None) OR org-specific roles for this org
    # - Exclude super_admin (should never be assignable via invite)
    query = (
        db.query(RoleDefinition)
        .filter(
            RoleDefinition.is_active.is_(True),
            RoleDefinition.privilege_level <= user_max_privilege,
            RoleDefinition.code != "super_admin",
            or_(
                RoleDefinition.organization_id.is_(None),
                RoleDefinition.organization_id == organization_id,
            ),
        )
        .order_by(RoleDefinition.privilege_level.desc(), RoleDefinition.display_name)
    )

    return query.all()


def _practitioner_to_response(practitioner) -> PractitionerResponse:
    """Convert practitioner model to response schema."""
    roles = []
    for role in practitioner.practitioner_roles:
        roles.append(
            PractitionerRoleResponse(
                id=role.id,
                organization_id=role.organization_id,
                organization_name=role.organization.name,
                role_code=role.role_definition.code,
                role_display_name=role.role_definition.display_name,
                is_active=role.is_active,
                is_primary=role.is_primary,
                accepted_at=role.accepted_at,
            )
        )

    return PractitionerResponse(
        id=practitioner.id,
        email=practitioner.email,
        first_name=practitioner.first_name,
        last_name=practitioner.last_name,
        full_name=practitioner.full_name,
        display_name=practitioner.display_name,
        phone=practitioner.phone,
        npi_number=practitioner.npi_number,
        credentials=practitioner.credentials,
        is_active=practitioner.is_active,
        email_verified_at=practitioner.email_verified_at,
        last_login_at=practitioner.last_login_at,
        created_at=practitioner.created_at,
        roles=roles,
    )


@router.get("", response_model=PractitionerListResponse)
async def list_clinicians(
    db: DbSession,
    practitioner: CurrentPractitioner,
    organization_id: UUID = Query(...),
    is_active: bool | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List clinicians in an organization."""
    # Check access
    engine = PolicyEngine(db)
    if not engine.has_permission(
        practitioner, Permission.MANAGE_CLINICIANS, organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage clinicians in this organization",
        )

    service = PractitionerService(db)
    practitioners, total = service.list_by_organization(
        organization_id,
        is_active=is_active,
        search=search,
        page=page,
        page_size=page_size,
    )

    # Log access
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    ctx.organization_id = organization_id

    audit = AuditLogger(db)
    audit.log(
        action="list",
        resource_type="practitioner",
        details={
            "organization_id": str(organization_id),
            "count": len(practitioners),
        },
    )

    pages = (total + page_size - 1) // page_size

    return PractitionerListResponse(
        items=[_practitioner_to_response(p) for p in practitioners],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/invites", response_model=list[PendingInvite])
async def list_pending_invites(
    db: DbSession,
    practitioner: CurrentPractitioner,
    organization_id: UUID = Query(...),
):
    """List pending invitations for an organization."""
    # Check access
    engine = PolicyEngine(db)
    if not engine.has_permission(
        practitioner, Permission.MANAGE_CLINICIANS, organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage invitations",
        )

    service = InviteService(db)
    invites = service.list_pending_invites(organization_id)

    return [
        PendingInvite(
            id=inv.id,
            email=inv.email,
            first_name=inv.first_name,
            last_name=inv.last_name,
            full_name=inv.full_name,
            role_code=inv.role_code,
            organization_id=inv.organization_id,
            organization_name=inv.organization.name,
            expires_at=inv.expires_at,
            is_expired=inv.is_expired,
            is_pending=inv.is_pending,
            created_at=inv.created_at,
        )
        for inv in invites
    ]


@router.post("/invite", response_model=InviteResponse)
async def invite_clinician(
    request: InviteRequest,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Invite a new clinician to an organization."""
    # Check access
    engine = PolicyEngine(db)
    if not engine.has_permission(
        practitioner, Permission.MANAGE_CLINICIANS, request.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to invite clinicians to this organization",
        )

    service = InviteService(db)

    try:
        invite = service.create_invite(request, practitioner)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Log action
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    ctx.organization_id = request.organization_id

    audit = AuditLogger(db)
    audit.log(
        action="invite",
        resource_type="practitioner",
        resource_id=invite.id,
        resource_name=f"{request.first_name} {request.last_name}",
        details={
            "email": request.email,
            "role": request.role_code,
        },
    )

    db.commit()

    # Send invitation email
    notification_service = NotificationService(db)
    invite_url = f"{sl_settings.app_base_url}/sl/set-password/{invite.id}/{invite.invite_secret}"

    try:
        # Run async notification in background
        import asyncio

        asyncio.create_task(
            notification_service.send_invite_email(
                invite_email=invite.email,
                invite_name=invite.full_name,
                organization_name=invite.organization.name,
                invite_url=invite_url,
            )
        )
    except Exception as e:
        # Log but don't fail the request
        import logging

        logging.error("Failed to send invite email: %s", e)

    return InviteResponse(
        success=True,
        invite_id=invite.id,
        message="Invitation sent successfully",
    )


@router.post("/invites/{invite_id}/resend", response_model=InviteResponse)
async def resend_invite(
    invite_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Resend an invitation email."""
    service = InviteService(db)
    invite = service.get_invite_by_id(invite_id)

    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        )

    # Check access
    engine = PolicyEngine(db)
    if not engine.has_permission(
        practitioner, Permission.MANAGE_CLINICIANS, invite.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage this invitation",
        )

    try:
        invite = service.resend_invite(invite)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    db.commit()

    # Send invitation email
    notification_service = NotificationService(db)
    invite_url = f"{sl_settings.app_base_url}/sl/set-password/{invite.id}/{invite.invite_secret}"

    try:
        import asyncio

        asyncio.create_task(
            notification_service.send_invite_email(
                invite_email=invite.email,
                invite_name=invite.full_name,
                organization_name=invite.organization.name,
                invite_url=invite_url,
            )
        )
    except Exception as e:
        import logging

        logging.error("Failed to send invite email: %s", e)

    return InviteResponse(
        success=True,
        invite_id=invite.id,
        message="Invitation resent successfully",
    )


@router.post("/invites/{invite_id}/revoke")
async def revoke_invite(
    invite_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Revoke a pending invitation."""
    service = InviteService(db)
    invite = service.get_invite_by_id(invite_id)

    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        )

    # Check access
    engine = PolicyEngine(db)
    if not engine.has_permission(
        practitioner, Permission.MANAGE_CLINICIANS, invite.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage this invitation",
        )

    try:
        service.revoke_invite(invite)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Log action
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    ctx.organization_id = invite.organization_id

    audit = AuditLogger(db)
    audit.log(
        action="revoke",
        resource_type="invitation",
        resource_id=invite.id,
        resource_name=invite.full_name,
    )

    db.commit()

    return {"success": True, "message": "Invitation revoked"}


@router.post("/invites/accept", response_model=AcceptInviteResponse)
async def accept_invite(
    request: AcceptInviteRequest,
    db: DbSession,
):
    """Accept an invitation and set password (public endpoint)."""
    if request.password != request.password_confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match",
        )

    service = InviteService(db)
    invite = service.get_invite_by_secret(request.invite_id, request.invite_secret)

    if not invite:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invitation",
        )

    try:
        practitioner = service.accept_invite(invite, request.password)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Log action
    audit = AuditLogger(db)
    audit.log(
        action="accept_invite",
        resource_type="practitioner",
        resource_id=practitioner.id,
        resource_name=practitioner.full_name,
        details={
            "invite_id": str(invite.id),
            "organization_id": str(invite.organization_id),
        },
    )

    db.commit()

    return AcceptInviteResponse(
        success=True,
        practitioner_id=practitioner.id,
        message="Account created successfully. You can now log in.",
    )


@router.get("/{clinician_id}", response_model=PractitionerResponse)
async def get_clinician(
    clinician_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Get clinician details."""
    service = PractitionerService(db)
    clinician = service.get_by_id(clinician_id)

    if not clinician:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clinician not found",
        )

    # Check access - must share an organization
    shared_orgs = set(
        r.organization_id for r in practitioner.practitioner_roles if r.is_active
    ) & set(r.organization_id for r in clinician.practitioner_roles if r.is_active)

    if not shared_orgs:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this clinician",
        )

    return _practitioner_to_response(clinician)


@router.patch("/{clinician_id}", response_model=PractitionerResponse)
async def update_clinician(
    clinician_id: UUID,
    request: PractitionerUpdate,
    db: DbSession,
    practitioner: CurrentPractitioner,
    organization_id: UUID = Query(...),
):
    """Update a clinician's info or role."""
    service = PractitionerService(db)
    clinician = service.get_by_id(clinician_id)

    if not clinician:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clinician not found",
        )

    # Check access
    engine = PolicyEngine(db)
    if not engine.has_permission(
        practitioner, Permission.MANAGE_CLINICIANS, organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage clinicians",
        )

    # Update
    clinician = service.update(clinician, request)

    # Log action
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    ctx.organization_id = organization_id

    audit = AuditLogger(db)
    audit.log_update(
        resource_type="practitioner",
        resource_id=clinician.id,
        resource_name=clinician.full_name,
    )

    db.commit()

    return _practitioner_to_response(clinician)


@router.post("/{clinician_id}/deactivate")
async def deactivate_clinician(
    clinician_id: UUID,
    db: DbSession,
    practitioner: CurrentPractitioner,
    organization_id: UUID = Query(...),
):
    """Deactivate a clinician."""
    service = PractitionerService(db)
    clinician = service.get_by_id(clinician_id)

    if not clinician:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clinician not found",
        )

    # Check access
    engine = PolicyEngine(db)
    if not engine.has_permission(
        practitioner, Permission.MANAGE_CLINICIANS, organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage clinicians",
        )

    # Can't deactivate yourself
    if clinician.id == practitioner.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account",
        )

    service.deactivate(clinician)

    # Log action
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    ctx.organization_id = organization_id

    audit = AuditLogger(db)
    audit.log(
        action="deactivate",
        resource_type="practitioner",
        resource_id=clinician.id,
        resource_name=clinician.full_name,
    )

    db.commit()

    return {"success": True, "message": "Clinician deactivated"}
