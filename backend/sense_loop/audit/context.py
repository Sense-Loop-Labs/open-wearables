"""Audit context tracking for requests."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from sense_loop.models import Practitioner


@dataclass
class AuditContext:
    """Context for audit logging within a request."""

    request_id: str = field(default_factory=lambda: str(uuid4()))

    # Actor info
    actor_type: str | None = None  # practitioner, patient, system, api_key
    actor_id: UUID | None = None
    actor_name: str | None = None
    actor_email: str | None = None

    # Organization context
    organization_id: UUID | None = None

    # Request info
    endpoint: str | None = None
    http_method: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None

    def set_practitioner(self, practitioner: "Practitioner") -> None:
        """Set actor info from a practitioner."""
        self.actor_type = "practitioner"
        self.actor_id = practitioner.id
        self.actor_name = practitioner.full_name
        self.actor_email = practitioner.email

    def set_patient(self, patient_id: UUID, patient_name: str) -> None:
        """Set actor info for a patient."""
        self.actor_type = "patient"
        self.actor_id = patient_id
        self.actor_name = patient_name

    def set_system(self, system_name: str = "system") -> None:
        """Set actor info for system operations."""
        self.actor_type = "system"
        self.actor_name = system_name

    def set_request_info(
        self,
        endpoint: str,
        method: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Set request information."""
        self.endpoint = endpoint
        self.http_method = method
        self.ip_address = ip_address
        self.user_agent = user_agent


# Context variable for the current audit context
_audit_context: ContextVar[AuditContext | None] = ContextVar(
    "audit_context", default=None
)


def get_audit_context() -> AuditContext:
    """Get the current audit context, creating one if needed."""
    ctx = _audit_context.get()
    if ctx is None:
        ctx = AuditContext()
        _audit_context.set(ctx)
    return ctx


def set_audit_context(ctx: AuditContext) -> None:
    """Set the audit context for the current request."""
    _audit_context.set(ctx)


def clear_audit_context() -> None:
    """Clear the audit context."""
    _audit_context.set(None)
