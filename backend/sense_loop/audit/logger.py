"""Audit event logging."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from sense_loop.models.audit_log import AuditAction, AuditLog

from .context import AuditContext, get_audit_context

logger = logging.getLogger(__name__)


class AuditLogger:
    """Logger for HIPAA audit events."""

    def __init__(self, db: Session, context: AuditContext | None = None):
        self.db = db
        self.context = context or get_audit_context()

    def log(
        self,
        action: str,
        resource_type: str,
        resource_id: UUID | None = None,
        resource_name: str | None = None,
        outcome: str = "success",
        outcome_reason: str | None = None,
        details: dict[str, Any] | None = None,
        phi_fields_accessed: list[str] | None = None,
        changes: dict[str, dict[str, Any]] | None = None,
        organization_id: UUID | None = None,
    ) -> AuditLog:
        """Log an audit event.

        Args:
            action: The action performed (use AuditAction constants)
            resource_type: Type of resource accessed (patient, alert, etc.)
            resource_id: ID of the resource
            resource_name: Human-readable name of the resource
            outcome: Result of the action (success, failure, denied)
            outcome_reason: Reason for failure/denial
            details: Additional context
            phi_fields_accessed: List of PHI fields that were accessed
            changes: Dictionary of changes made (for updates)
            organization_id: Override context organization_id

        Returns:
            The created AuditLog entry
        """
        ctx = self.context

        audit_entry = AuditLog(
            id=uuid4(),
            # WHO
            actor_type=ctx.actor_type or "unknown",
            actor_id=ctx.actor_id,
            actor_name=ctx.actor_name,
            actor_email=ctx.actor_email,
            organization_id=organization_id or ctx.organization_id,
            # WHAT
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            # WHY
            endpoint=ctx.endpoint,
            http_method=ctx.http_method,
            request_id=ctx.request_id,
            ip_address=ctx.ip_address,
            user_agent=ctx.user_agent,
            # OUTCOME
            outcome=outcome,
            outcome_reason=outcome_reason,
            # DETAILS
            details=details,
            phi_fields_accessed=phi_fields_accessed,
            changes=changes,
        )

        self.db.add(audit_entry)

        # Log to application logger as well for monitoring
        log_level = logging.INFO if outcome == "success" else logging.WARNING
        logger.log(
            log_level,
            "Audit: %s %s %s by %s (%s) - %s",
            action,
            resource_type,
            resource_id or "",
            ctx.actor_name or "unknown",
            ctx.actor_type or "unknown",
            outcome,
            extra={
                "audit_id": str(audit_entry.id),
                "request_id": ctx.request_id,
            },
        )

        return audit_entry

    def log_access(
        self,
        resource_type: str,
        resource_id: UUID,
        resource_name: str | None = None,
        phi_fields_accessed: list[str] | None = None,
    ) -> AuditLog:
        """Log a read/view access event."""
        return self.log(
            action=AuditAction.READ,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            phi_fields_accessed=phi_fields_accessed,
        )

    def log_create(
        self,
        resource_type: str,
        resource_id: UUID,
        resource_name: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Log a create event."""
        return self.log(
            action=AuditAction.CREATE,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            details=details,
        )

    def log_update(
        self,
        resource_type: str,
        resource_id: UUID,
        resource_name: str | None = None,
        changes: dict[str, dict[str, Any]] | None = None,
    ) -> AuditLog:
        """Log an update event."""
        return self.log(
            action=AuditAction.UPDATE,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            changes=changes,
        )

    def log_delete(
        self,
        resource_type: str,
        resource_id: UUID,
        resource_name: str | None = None,
    ) -> AuditLog:
        """Log a delete event."""
        return self.log(
            action=AuditAction.DELETE,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
        )

    def log_login(
        self,
        success: bool,
        user_email: str,
        user_type: str = "practitioner",
        failure_reason: str | None = None,
    ) -> AuditLog:
        """Log a login attempt."""
        return self.log(
            action=AuditAction.LOGIN if success else AuditAction.LOGIN_FAILED,
            resource_type=user_type,
            resource_name=user_email,
            outcome="success" if success else "failure",
            outcome_reason=failure_reason,
        )

    def log_export(
        self,
        resource_type: str,
        resource_ids: list[UUID] | None = None,
        export_format: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Log a data export event."""
        return self.log(
            action=AuditAction.EXPORT,
            resource_type=resource_type,
            details={
                "format": export_format,
                "filters": filters,
                "resource_ids": [str(rid) for rid in resource_ids] if resource_ids else None,
            },
        )

    def log_alert_action(
        self,
        action: str,  # acknowledge, resolve, escalate
        alert_id: UUID,
        patient_name: str | None = None,
        notes: str | None = None,
    ) -> AuditLog:
        """Log an alert action."""
        action_map = {
            "acknowledge": AuditAction.ACKNOWLEDGE_ALERT,
            "resolve": AuditAction.RESOLVE_ALERT,
            "escalate": AuditAction.ESCALATE_ALERT,
        }
        return self.log(
            action=action_map.get(action, action),
            resource_type="alert",
            resource_id=alert_id,
            resource_name=patient_name,
            details={"notes": notes} if notes else None,
        )

    def log_denied(
        self,
        action: str,
        resource_type: str,
        resource_id: UUID | None = None,
        reason: str = "Insufficient permissions",
    ) -> AuditLog:
        """Log a denied access attempt."""
        return self.log(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome="denied",
            outcome_reason=reason,
        )
