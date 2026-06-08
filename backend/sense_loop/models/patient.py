"""Patient model - links OW User to clinical data."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import BaseDbModel
from app.mappings import PrimaryKey, Unique, str_50, str_100, str_255


class Patient(BaseDbModel):
    """Patient in the clinical system.

    Links to OW User for wearable data collection.
    Maintains its own clinical profile and enrollment state.
    """

    __tablename__ = "sl_patient"

    id: Mapped[PrimaryKey[UUID]]

    # Link to OW User (wearable data)
    ow_user_id: Mapped[Unique[UUID] | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Organization
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_organization.id", ondelete="CASCADE"),
        index=True,
    )

    # Patient identity
    mrn: Mapped[str_50 | None] = mapped_column(nullable=True, index=True)  # Medical Record Number
    first_name: Mapped[str_100]
    last_name: Mapped[str_100]
    date_of_birth: Mapped[date]
    gender: Mapped[str_50 | None] = mapped_column(nullable=True)  # male, female, other, unknown

    # Contact (PHI - encrypted at rest)
    email: Mapped[str_255 | None] = mapped_column(nullable=True)
    phone: Mapped[str_50 | None] = mapped_column(nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Auth (for web/mobile login)
    password_hash: Mapped[str_255 | None] = mapped_column(nullable=True)

    # Enrollment
    activation_code: Mapped[str_50 | None] = mapped_column(nullable=True, index=True)
    activation_code_expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    enrollment_status: Mapped[str_50] = mapped_column(default="pending")
    # Statuses: pending, activated, active, discharged, withdrawn

    enrolled_at: Mapped[datetime | None] = mapped_column(nullable=True)
    discharged_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Clinical info
    primary_diagnosis: Mapped[str_255 | None] = mapped_column(nullable=True)
    surgery_type_code: Mapped[str_100 | None] = mapped_column(nullable=True)  # SNOMED code from surgery-types ValueSet
    surgery_date: Mapped[date | None] = mapped_column(nullable=True, index=True)
    discharge_date: Mapped[date | None] = mapped_column(nullable=True)

    # Monitoring settings
    monitoring_start_date: Mapped[date | None] = mapped_column(nullable=True)
    monitoring_end_date: Mapped[date | None] = mapped_column(nullable=True)

    # Alert protocol
    alert_protocol_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sl_alert_protocol.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Custom thresholds (overrides protocol defaults)
    custom_thresholds: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Example:
    # {
    #     "heart_rate": {"high_critical": 130, "high_warning": 110},
    #     "spo2": {"low_critical": 85}
    # }

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="patients")
    ow_user: Mapped["User | None"] = relationship(foreign_keys=[ow_user_id])
    alert_protocol: Mapped["AlertProtocol | None"] = relationship(
        foreign_keys=[alert_protocol_id],
    )
    summary: Mapped["PatientSummary | None"] = relationship(
        back_populates="patient",
        uselist=False,
        cascade="all, delete-orphan",
    )
    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    care_plans: Mapped[list["CarePlan"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    questionnaire_responses: Mapped[list["QuestionnaireResponse"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    clinical_actions: Mapped[list["ClinicalAction"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
        order_by="desc(ClinicalAction.created_at)",
    )

    @property
    def full_name(self) -> str:
        """Get patient's full name."""
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self) -> int | None:
        """Calculate patient's age."""
        if not self.date_of_birth:
            return None
        today = date.today()
        return (
            today.year
            - self.date_of_birth.year
            - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        )

    @property
    def days_post_surgery(self) -> int | None:
        """Calculate days since surgery."""
        if not self.surgery_date:
            return None
        return (date.today() - self.surgery_date).days

    @property
    def is_enrolled(self) -> bool:
        """Check if patient is enrolled and active."""
        return self.enrollment_status in ("activated", "active") and self.is_active

    @property
    def is_monitoring_active(self) -> bool:
        """Check if monitoring is currently active."""
        if not self.is_enrolled:
            return False
        today = date.today()
        if self.monitoring_start_date and today < self.monitoring_start_date:
            return False
        if self.monitoring_end_date and today > self.monitoring_end_date:
            return False
        return True
