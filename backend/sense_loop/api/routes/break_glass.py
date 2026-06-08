"""Break-the-glass emergency access API endpoints.

Provides endpoints for activating and revoking emergency access
to patient data with full audit trail.
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.database import DbSession
from sense_loop.access import CurrentPractitioner, Permission, PolicyEngine
from sense_loop.access.cedar.break_glass import (
    BreakTheGlassManager,
    EmergencyType,
)
from sense_loop.audit import AuditLogger, get_audit_context

router = APIRouter()


class BTGActivateRequest(BaseModel):
    """Request to activate break-the-glass access."""

    organization_id: UUID
    resource_type: str = Field(..., description="Type of resource to access (e.g., 'patient', 'alert')")
    resource_id: UUID | None = Field(None, description="Specific resource ID, or None for type-level access")
    reason: str = Field(..., min_length=20, description="Required justification for emergency access")
    emergency_type: str = Field(
        ...,
        description="Type of emergency: medical_emergency, system_outage, disaster_recovery, critical_care, life_threatening, other",
    )
    duration_hours: int | None = Field(
        None,
        ge=1,
        le=24,
        description="Access duration in hours (default: 4, max: 24)",
    )


class BTGActivateResponse(BaseModel):
    """Response from break-the-glass activation."""

    success: bool
    btg_access_id: str | None
    message: str
    expires_at: str | None


class BTGRevokeRequest(BaseModel):
    """Request to revoke break-the-glass access."""

    reason: str | None = Field(None, description="Optional reason for revocation")


class BTGRevokeResponse(BaseModel):
    """Response from break-the-glass revocation."""

    success: bool
    message: str
    access_count: int


class BTGAccessResponse(BaseModel):
    """Break-the-glass access record response."""

    id: str
    practitioner_id: str
    organization_id: str
    resource_type: str
    resource_id: str | None
    reason: str
    emergency_type: str
    activated_at: str
    expires_at: str
    revoked_at: str | None
    access_count: int
    is_active: bool


@router.post("/activate", response_model=BTGActivateResponse)
async def activate_break_glass(
    request: BTGActivateRequest,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Activate break-the-glass emergency access.

    This endpoint grants time-limited emergency access to resources
    that the practitioner would not normally have access to.

    Requirements:
    - Practitioner must have an active role in the organization
    - Reason must be at least 20 characters
    - All activations are logged and supervisor notifications are sent

    Access is automatically revoked after the duration expires.
    """
    # Check that practitioner has some role in the organization
    engine = PolicyEngine(db)
    role = engine.get_role_for_org(practitioner, request.organization_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this organization",
        )

    # Set audit context
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    ctx.organization_id = request.organization_id

    # Activate BTG access
    btg_manager = BreakTheGlassManager(db)
    result = btg_manager.activate(
        practitioner=practitioner,
        organization_id=request.organization_id,
        resource_type=request.resource_type,
        reason=request.reason,
        emergency_type=request.emergency_type,
        resource_id=request.resource_id,
        duration_hours=request.duration_hours,
    )

    # Log the activation attempt
    audit = AuditLogger(db)
    audit.log(
        action="btg_activate" if result.success else "btg_activate_failed",
        resource_type="break_glass_access",
        resource_id=result.btg_access_id,
        details={
            "success": result.success,
            "target_resource_type": request.resource_type,
            "target_resource_id": str(request.resource_id) if request.resource_id else None,
            "emergency_type": request.emergency_type,
            "reason": request.reason,
            "message": result.message,
        },
    )

    if result.success:
        db.commit()

    return BTGActivateResponse(
        success=result.success,
        btg_access_id=str(result.btg_access_id) if result.btg_access_id else None,
        message=result.message,
        expires_at=result.expires_at.isoformat() if result.expires_at else None,
    )


@router.post("/{btg_access_id}/revoke", response_model=BTGRevokeResponse)
async def revoke_break_glass(
    btg_access_id: UUID,
    request: BTGRevokeRequest,
    db: DbSession,
    practitioner: CurrentPractitioner,
):
    """Revoke break-the-glass access.

    Can be called by the practitioner who activated the access,
    or by an organization admin.
    """
    from sense_loop.access.cedar.models import BreakTheGlassAccess

    # Get the BTG access record
    btg_access = db.get(BreakTheGlassAccess, btg_access_id)
    if not btg_access:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Break-the-glass access not found",
        )

    # Check authorization to revoke
    engine = PolicyEngine(db)
    can_revoke = False

    # Can revoke own access
    if btg_access.practitioner_id == practitioner.id:
        can_revoke = True

    # Org admins can revoke anyone's access
    if engine.has_permission(
        practitioner, Permission.MANAGE_CLINICIANS, btg_access.organization_id
    ):
        can_revoke = True

    if not can_revoke:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to revoke this access",
        )

    # Set audit context
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    ctx.organization_id = btg_access.organization_id

    # Revoke the access
    btg_manager = BreakTheGlassManager(db)
    result = btg_manager.revoke(
        btg_access_id=btg_access_id,
        revoked_by=practitioner,
        reason=request.reason,
    )

    # Log the revocation
    audit = AuditLogger(db)
    audit.log(
        action="btg_revoke" if result.success else "btg_revoke_failed",
        resource_type="break_glass_access",
        resource_id=btg_access_id,
        details={
            "success": result.success,
            "message": result.message,
            "access_count": result.access_count,
            "revocation_reason": request.reason,
        },
    )

    if result.success:
        db.commit()

    return BTGRevokeResponse(
        success=result.success,
        message=result.message,
        access_count=result.access_count,
    )


@router.get("/active", response_model=list[BTGAccessResponse])
async def list_active_access(
    db: DbSession,
    practitioner: CurrentPractitioner,
    organization_id: UUID = Query(..., description="Organization ID"),
):
    """List active break-the-glass access for the current practitioner."""
    # Check organization access
    engine = PolicyEngine(db)
    role = engine.get_role_for_org(practitioner, organization_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this organization",
        )

    btg_manager = BreakTheGlassManager(db)
    active = btg_manager.get_active_access(
        practitioner_id=practitioner.id,
        organization_id=organization_id,
    )

    return [
        BTGAccessResponse(
            id=str(a.id),
            practitioner_id=str(a.practitioner_id),
            organization_id=str(a.organization_id),
            resource_type=a.resource_type,
            resource_id=str(a.resource_id) if a.resource_id else None,
            reason=a.reason,
            emergency_type=a.emergency_type,
            activated_at=a.activated_at.isoformat(),
            expires_at=a.expires_at.isoformat(),
            revoked_at=a.revoked_at.isoformat() if a.revoked_at else None,
            access_count=a.access_count,
            is_active=a.is_active(),
        )
        for a in active
    ]


@router.get("/history", response_model=list[BTGAccessResponse])
async def list_btg_history(
    db: DbSession,
    practitioner: CurrentPractitioner,
    organization_id: UUID = Query(..., description="Organization ID"),
    include_active: bool = Query(True),
    include_expired: bool = Query(True),
    include_revoked: bool = Query(True),
    limit: int = Query(50, ge=1, le=200),
):
    """List break-the-glass access history for an organization.

    Requires MANAGE_CLINICIANS permission (org admin).
    """
    # Check admin access
    engine = PolicyEngine(db)
    if not engine.has_permission(
        practitioner, Permission.MANAGE_CLINICIANS, organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization admins can view BTG history",
        )

    btg_manager = BreakTheGlassManager(db)
    history = btg_manager.get_organization_btg_history(
        organization_id=organization_id,
        include_active=include_active,
        include_expired=include_expired,
        include_revoked=include_revoked,
        limit=limit,
    )

    # Log this access to audit logs
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    ctx.organization_id = organization_id

    audit = AuditLogger(db)
    audit.log(
        action="view_btg_history",
        resource_type="break_glass_access",
        details={
            "organization_id": str(organization_id),
            "record_count": len(history),
        },
    )

    return [
        BTGAccessResponse(
            id=str(a.id),
            practitioner_id=str(a.practitioner_id),
            organization_id=str(a.organization_id),
            resource_type=a.resource_type,
            resource_id=str(a.resource_id) if a.resource_id else None,
            reason=a.reason,
            emergency_type=a.emergency_type,
            activated_at=a.activated_at.isoformat(),
            expires_at=a.expires_at.isoformat(),
            revoked_at=a.revoked_at.isoformat() if a.revoked_at else None,
            access_count=a.access_count,
            is_active=a.is_active(),
        )
        for a in history
    ]
