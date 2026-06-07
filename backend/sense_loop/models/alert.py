"""Alert model - generated alerts with full traceability."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import BaseDbModel
from app.mappings import PrimaryKey, str_50, str_100, str_255


class Alert(BaseDbModel):
    """Generated alert with full SaMD traceability."""

    __tablename__ = "sl_alert"

    id: Mapped[PrimaryKey[UUID]]

    # Patient
    patient_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_patient.id", ondelete="CASCADE"),
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_organization.id", ondelete="CASCADE"),
        index=True,
    )

    # Alert info
    title: Mapped[str_255]
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str_50]  # info, warning, critical
    category: Mapped[str_50]  # vital_sign, questionnaire, care_plan, system

    # Status
    status: Mapped[str_50] = mapped_column(default="active", index=True)
    # Statuses: active, acknowledged, resolved, auto_resolved, escalated

    # Timing
    triggered_at: Mapped[datetime] = mapped_column(index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    escalated_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Attribution
    acknowledged_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sl_practitioner.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sl_practitioner.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Resolution
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_type: Mapped[str_50 | None] = mapped_column(nullable=True)
    # Types: normal_variation, false_positive, patient_contacted, care_plan_updated, etc.

    # SaMD Traceability (required for regulatory compliance)
    protocol_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sl_alert_protocol.id", ondelete="SET NULL"),
        nullable=True,
    )
    protocol_version: Mapped[int | None] = mapped_column(nullable=True)
    rule_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sl_alert_protocol_rule.id", ondelete="SET NULL"),
        nullable=True,
    )
    risk_window_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sl_alert_risk_window.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Context at time of alert
    days_post_surgery: Mapped[int | None] = mapped_column(nullable=True)
    patient_context: Mapped[str_50 | None] = mapped_column(nullable=True)
    # Contexts: resting, active, sleeping, post_exercise

    # Observed values that triggered the alert
    vital_type: Mapped[str_50 | None] = mapped_column(nullable=True)
    observed_value: Mapped[float | None] = mapped_column(nullable=True)
    threshold_breached: Mapped[str_50 | None] = mapped_column(nullable=True)
    # Thresholds: high_critical, high_warning, low_warning, low_critical
    threshold_value: Mapped[float | None] = mapped_column(nullable=True)

    # Additional data
    data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # For storing additional context like recent readings, trends, etc.

    # Notification tracking
    notification_sent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    notification_channels: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # ['email', 'sms', 'push']

    # Relationships
    patient: Mapped["Patient"] = relationship(back_populates="alerts")
    organization: Mapped["Organization"] = relationship(foreign_keys=[organization_id])
    acknowledged_by: Mapped["Practitioner | None"] = relationship(
        foreign_keys=[acknowledged_by_id],
    )
    resolved_by: Mapped["Practitioner | None"] = relationship(
        foreign_keys=[resolved_by_id],
    )
    protocol: Mapped["AlertProtocol | None"] = relationship(
        foreign_keys=[protocol_id],
    )
    rule: Mapped["AlertProtocolRule | None"] = relationship(
        foreign_keys=[rule_id],
    )
    risk_window: Mapped["AlertRiskWindow | None"] = relationship(
        foreign_keys=[risk_window_id],
    )

    @property
    def is_active(self) -> bool:
        """Check if alert is still active."""
        return self.status == "active"

    @property
    def is_resolved(self) -> bool:
        """Check if alert is resolved."""
        return self.status in ("resolved", "auto_resolved")

    @property
    def response_time_seconds(self) -> int | None:
        """Calculate time from trigger to acknowledgement."""
        if not self.acknowledged_at:
            return None
        return int((self.acknowledged_at - self.triggered_at).total_seconds())

    @property
    def resolution_time_seconds(self) -> int | None:
        """Calculate time from trigger to resolution."""
        if not self.resolved_at:
            return None
        return int((self.resolved_at - self.triggered_at).total_seconds())
