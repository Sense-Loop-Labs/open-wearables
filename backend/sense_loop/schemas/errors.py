"""Error response schemas."""

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    message: str
    details: dict | None = None


class ValidationErrorDetail(BaseModel):
    """Validation error detail."""

    field: str
    message: str
    type: str


class ValidationErrorResponse(BaseModel):
    """Validation error response."""

    error: str = "validation_error"
    message: str = "Validation failed"
    details: list[ValidationErrorDetail]
