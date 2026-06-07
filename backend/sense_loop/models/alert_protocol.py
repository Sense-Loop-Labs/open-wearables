"""Alert protocol models - immutable versioned alert rules for SaMD compliance."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import BaseDbModel
from app.mappings import PrimaryKey, str_50, str_100, str_255


class AlertProtocol(BaseDbModel):
    """Immutable versioned alert protocol for SaMD compliance.

    Once published, protocols cannot be modified.
    New versions must be created for any changes.
    """

    __tablename__ = "sl_alert_protocol"

    id: Mapped[PrimaryKey[UUID]]

    # Protocol identity
    name: Mapped[str_255]
    code: Mapped[str_100]  # e.g., 'cardiac_surgery_v1'
    version: Mapped[int] = mapped_column(default=1)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Ownership
    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sl_organization.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )  # None = system-wide protocol

    # Lifecycle
    status: Mapped[str_50] = mapped_column(default="draft")
    # Statuses: draft, pending_approval, approved, published, deprecated

    # Integrity (SaMD requirement)
    rules_hash: Mapped[str_100 | None] = mapped_column(nullable=True)  # SHA-256 of rules JSON

    # Approval (regulatory requirement)
    approved_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sl_practitioner.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    deprecated_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Replaced by (for versioning)
    replaced_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sl_alert_protocol.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    organization: Mapped["Organization | None"] = relationship(
        foreign_keys=[organization_id],
    )
    approved_by: Mapped["Practitioner | None"] = relationship(
        foreign_keys=[approved_by_id],
    )
    replaced_by: Mapped["AlertProtocol | None"] = relationship(
        foreign_keys=[replaced_by_id],
        remote_side="AlertProtocol.id",
    )
    rules: Mapped[list["AlertProtocolRule"]] = relationship(
        back_populates="protocol",
        cascade="all, delete-orphan",
        order_by="AlertProtocolRule.priority",
    )
    risk_windows: Mapped[list["AlertRiskWindow"]] = relationship(
        back_populates="protocol",
        cascade="all, delete-orphan",
        order_by="AlertRiskWindow.start_day",
    )

    @property
    def is_published(self) -> bool:
        """Check if protocol is published and active."""
        return self.status == "published" and self.deprecated_at is None

    @property
    def is_modifiable(self) -> bool:
        """Check if protocol can be modified."""
        return self.status == "draft"


class AlertProtocolRule(BaseDbModel):
    """Individual alert rule within a protocol."""

    __tablename__ = "sl_alert_protocol_rule"

    id: Mapped[PrimaryKey[UUID]]

    protocol_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_alert_protocol.id", ondelete="CASCADE"),
        index=True,
    )

    # Rule identity
    code: Mapped[str_100]  # e.g., 'hr_high_resting'
    name: Mapped[str_255]  # e.g., 'High Resting Heart Rate'
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Vital type
    vital_type: Mapped[str_50]  # heart_rate, spo2, temperature, blood_pressure, etc.

    # Thresholds
    high_critical: Mapped[float | None] = mapped_column(nullable=True)
    high_warning: Mapped[float | None] = mapped_column(nullable=True)
    low_warning: Mapped[float | None] = mapped_column(nullable=True)
    low_critical: Mapped[float | None] = mapped_column(nullable=True)

    # Context conditions
    context: Mapped[str_50 | None] = mapped_column(nullable=True)
    # Contexts: resting, active, sleeping, post_exercise, any

    # Rule settings
    priority: Mapped[int] = mapped_column(default=100)  # Lower = higher priority
    is_active: Mapped[bool] = mapped_column(default=True)

    # Alert configuration
    alert_severity: Mapped[str_50] = mapped_column(default="warning")
    # Severities: info, warning, critical

    sustained_seconds: Mapped[int | None] = mapped_column(nullable=True)
    # How long the condition must persist before alerting

    cooldown_minutes: Mapped[int] = mapped_column(default=60)
    # Minimum time between duplicate alerts

    # Notification settings
    notify_patient: Mapped[bool] = mapped_column(default=False)
    notify_care_team: Mapped[bool] = mapped_column(default=True)
    escalation_minutes: Mapped[int | None] = mapped_column(nullable=True)
    # Time before escalating unacknowledged alert

    # Relationships
    protocol: Mapped["AlertProtocol"] = relationship(back_populates="rules")


class AlertRiskWindow(BaseDbModel):
    """Time-based risk windows for post-operative monitoring.

    Different thresholds apply at different points in recovery.
    """

    __tablename__ = "sl_alert_risk_window"

    id: Mapped[PrimaryKey[UUID]]

    protocol_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_alert_protocol.id", ondelete="CASCADE"),
        index=True,
    )

    # Window definition (days post-surgery)
    name: Mapped[str_100]  # e.g., 'Immediate Post-Op'
    start_day: Mapped[int]  # inclusive
    end_day: Mapped[int | None] = mapped_column(nullable=True)  # None = no end

    # Risk level
    risk_level: Mapped[str_50] = mapped_column(default="moderate")
    # Levels: low, moderate, high, critical

    # Threshold adjustments (multipliers or absolute overrides)
    threshold_adjustments: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Example:
    # {
    #     "heart_rate": {
    #         "high_critical_adjustment": 10,  # Add 10 to base threshold
    #         "high_warning_adjustment": 5
    #     }
    # }

    # Description
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    protocol: Mapped["AlertProtocol"] = relationship(back_populates="risk_windows")
