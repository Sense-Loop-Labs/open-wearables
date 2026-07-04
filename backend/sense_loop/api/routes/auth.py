"""Authentication routes for patients and practitioners."""

from fastapi import APIRouter, HTTPException, status

from app.database import DbSession
from sense_loop.audit import AuditLogger, get_audit_context
from sense_loop.schemas.auth import (
    ActivateRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LoginResponse,
    PractitionerLoginRequest,
    PractitionerLoginResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    SetPasswordRequest,
    SetPasswordResponse,
    ValidateCodeRequest,
    ValidateCodeResponse,
)
from sense_loop.services import EnrollmentService, PractitionerAuthService

router = APIRouter()


# ============================================================================
# Patient Auth Endpoints
# ============================================================================


@router.post("/patient/validate-code", response_model=ValidateCodeResponse)
async def validate_activation_code(
    request: ValidateCodeRequest,
    db: DbSession,
):
    """Validate a patient activation code."""
    service = EnrollmentService(db)
    is_valid, patient, error = service.validate_activation_code(request.activation_code)

    if not is_valid:
        return ValidateCodeResponse(
            valid=False,
            message=error or "Invalid activation code",
        )

    return ValidateCodeResponse(
        valid=True,
        patient_id=patient.id,
        first_name=patient.first_name,
        last_name=patient.last_name,
        organization_name=patient.organization.name if patient.organization else None,
        expires_at=patient.activation_code_expires_at.isoformat() if patient.activation_code_expires_at else None,
    )


@router.post("/patient/activate")
async def activate_patient(
    request: ActivateRequest,
    db: DbSession,
):
    """Verify patient identity and activate account."""
    service = EnrollmentService(db)

    # Validate code first
    is_valid, patient, error = service.validate_activation_code(request.activation_code)
    if not is_valid or not patient:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error or "Invalid activation code",
        )

    # Verify identity
    verified, verify_error = service.verify_identity(
        patient,
        str(request.date_of_birth),
        request.phone_last_four,
    )

    if not verified:
        # Log failed attempt
        audit = AuditLogger(db)
        audit.log(
            action="activation_failed",
            resource_type="patient",
            resource_id=patient.id,
            outcome="failure",
            outcome_reason=verify_error,
        )
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=verify_error or "Identity verification failed",
        )

    # Activate patient
    token = service.activate_patient(patient)

    # Log success
    audit = AuditLogger(db)
    audit.log(
        action="activation_success",
        resource_type="patient",
        resource_id=patient.id,
    )
    db.commit()

    return {
        "success": True,
        "patient_id": str(patient.id),
        "patient_name": patient.full_name,
        "email": patient.email,
        "activation_token": token,
    }


@router.post("/patient/set-password", response_model=SetPasswordResponse)
async def set_patient_password(
    request: SetPasswordRequest,
    db: DbSession,
):
    """Set password for activated patient."""
    if request.password != request.password_confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match",
        )

    service = EnrollmentService(db)
    success, patient, error = service.set_password(
        request.activation_token,
        request.password,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error or "Failed to set password",
        )

    # Create OW User if needed
    if patient and not patient.ow_user_id:
        service.create_ow_user(patient)

    db.commit()

    return SetPasswordResponse(
        success=True,
        message="Password set successfully. You can now log in.",
    )


@router.post("/patient/login", response_model=LoginResponse)
async def patient_login(
    request: LoginRequest,
    db: DbSession,
):
    """Login as a patient."""
    from passlib.hash import pbkdf2_sha256
    from sqlalchemy import select

    from sense_loop.models import Patient

    # Find patient by email
    stmt = select(Patient).where(Patient.email == request.email.lower())
    patient = db.execute(stmt).scalar_one_or_none()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not patient.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please complete your account setup",
        )

    if not pbkdf2_sha256.verify(request.password, patient.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not patient.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is not active",
        )

    # Generate tokens using OW token system
    from app.config import settings
    from app.services.sdk_token_service import create_sdk_user_token
    from app.services.refresh_token_service import refresh_token_service

    expires_in = settings.access_token_expire_minutes * 60

    # Get OW user ID (required for SDK tokens)
    ow_user_id = patient.ow_user_id
    if not ow_user_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Patient does not have an Open Wearables user account",
        )

    # App ID for the Recovery Companion iOS app
    app_id = "recovery-companion"

    # Create SDK access token using OW's token service
    access_token = create_sdk_user_token(
        app_id=app_id,
        user_id=str(ow_user_id),
    )

    # Create refresh token using OW's refresh token service (stored in DB)
    refresh_token = refresh_token_service.create_sdk_refresh_token(
        db_session=db,
        user_id=ow_user_id,
        app_id=app_id,
    )

    # Log login
    audit = AuditLogger(db)
    audit.log_login(True, request.email, "patient")
    db.commit()

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=expires_in,
        patient_id=patient.id,
        ow_user_id=patient.ow_user_id,
        organization_id=patient.organization_id,
    )


# ============================================================================
# Practitioner Auth Endpoints
# ============================================================================


@router.post("/practitioner/login", response_model=PractitionerLoginResponse)
async def practitioner_login(
    request: PractitionerLoginRequest,
    db: DbSession,
):
    """Login as a practitioner."""
    auth_service = PractitionerAuthService(db)

    practitioner, error = auth_service.authenticate(
        request.email,
        request.password,
    )

    if not practitioner:
        # Log failed login
        audit = AuditLogger(db)
        ctx = get_audit_context()
        ctx.actor_type = "unknown"
        ctx.actor_email = request.email
        audit.log_login(False, request.email, "practitioner", error)
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error or "Invalid email or password",
        )

    # Generate tokens
    access_token, refresh_token, expires_in = auth_service.create_tokens(practitioner)

    # Build organization list
    orgs = []
    for role in practitioner.practitioner_roles:
        if role.is_active:
            orgs.append({
                "id": str(role.organization_id),
                "name": role.organization.name,
                "role": role.role_definition.code,
                "role_display_name": role.role_definition.display_name,
            })

    # Log successful login
    audit = AuditLogger(db)
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    audit.log_login(True, request.email, "practitioner")
    db.commit()

    return PractitionerLoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=expires_in,
        practitioner_id=practitioner.id,
        email=practitioner.email,
        first_name=practitioner.first_name,
        last_name=practitioner.last_name,
        organizations=orgs,
    )


@router.post("/practitioner/logout")
async def practitioner_logout(db: DbSession):
    """Logout (invalidate session)."""
    # For stateless JWT, just acknowledge the logout
    # In a production system, you might add the token to a blacklist

    # Log logout
    audit = AuditLogger(db)
    audit.log(
        action="logout",
        resource_type="session",
    )
    db.commit()

    return {"success": True, "message": "Logged out successfully"}


@router.post("/practitioner/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    request: ForgotPasswordRequest,
    db: DbSession,
):
    """Initiate password reset."""
    auth_service = PractitionerAuthService(db)
    success, error = auth_service.initiate_password_reset(request.email)

    # Always return success to avoid email enumeration
    db.commit()

    return ForgotPasswordResponse(
        success=True,
        message="If an account exists with this email, you will receive a password reset link.",
    )


@router.post("/practitioner/reset-password", response_model=ResetPasswordResponse)
async def reset_password(
    request: ResetPasswordRequest,
    db: DbSession,
):
    """Reset password with token."""
    if request.password != request.password_confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match",
        )

    auth_service = PractitionerAuthService(db)
    success, error = auth_service.reset_password(
        request.token,
        request.password,
    )

    if not success:
        # Log failed password reset
        audit = AuditLogger(db)
        audit.log(
            action="password_reset",
            resource_type="practitioner",
            outcome="failure",
            outcome_reason=error,
        )
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error or "Failed to reset password",
        )

    # Log successful password reset
    audit = AuditLogger(db)
    audit.log(
        action="password_reset",
        resource_type="practitioner",
        outcome="success",
    )
    db.commit()

    return ResetPasswordResponse(
        success=True,
        message="Password reset successfully. You can now log in.",
    )
