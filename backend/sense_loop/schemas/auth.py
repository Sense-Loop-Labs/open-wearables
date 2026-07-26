"""Authentication schemas."""

from datetime import date
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# Patient Auth Schemas


class ValidateCodeRequest(BaseModel):
    """Request to validate an activation code."""

    activation_code: str = Field(..., min_length=6, max_length=20)


class ValidateCodeResponse(BaseModel):
    """Response from validating an activation code."""

    valid: bool
    patient_id: UUID | None = None
    first_name: str | None = None
    last_name: str | None = None
    organization_name: str | None = None
    expires_at: str | None = None  # ISO datetime
    message: str | None = None


class ActivateRequest(BaseModel):
    """Request to activate a patient account (verify identity)."""

    activation_code: str = Field(..., min_length=6, max_length=20)
    date_of_birth: date
    phone_last_four: str = Field(..., min_length=4, max_length=4)


class ActivateResponse(BaseModel):
    """Response from activating a patient account."""

    success: bool
    patient_id: UUID | None = None
    activation_token: str | None = None  # Temporary token for setting password
    message: str | None = None


class SetPasswordRequest(BaseModel):
    """Request to set password after activation."""

    activation_token: str  # From ActivateResponse
    password: str = Field(..., min_length=12, max_length=128)
    password_confirm: str = Field(..., min_length=12, max_length=128)


class SetPasswordResponse(BaseModel):
    """Response from setting password."""

    success: bool
    message: str | None = None


class LoginRequest(BaseModel):
    """Request to login (patient)."""

    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Response from login."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    patient_id: UUID
    ow_user_id: UUID | None = None
    organization_id: UUID
    first_name: str | None = None


class RefreshTokenRequest(BaseModel):
    """Request to refresh tokens."""

    refresh_token: str


# Practitioner Auth Schemas


class PractitionerLoginRequest(BaseModel):
    """Request to login (practitioner)."""

    email: EmailStr
    password: str


class PractitionerLoginResponse(BaseModel):
    """Response from practitioner login."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    practitioner_id: UUID
    email: str
    first_name: str
    last_name: str
    organizations: list[dict]  # [{id, name, role}]


class ForgotPasswordRequest(BaseModel):
    """Request to initiate password reset."""

    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    """Response from forgot password request."""

    success: bool
    message: str


class ResetPasswordRequest(BaseModel):
    """Request to reset password with token."""

    token: str
    password: str = Field(..., min_length=12, max_length=128)
    password_confirm: str = Field(..., min_length=12, max_length=128)


class ResetPasswordResponse(BaseModel):
    """Response from reset password."""

    success: bool
    message: str
