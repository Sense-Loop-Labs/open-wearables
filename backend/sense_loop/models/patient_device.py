"""Patient device model - stores FCM device tokens for push notifications."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import BaseDbModel
from app.mappings import PrimaryKey, str_50, str_255


class PatientDevice(BaseDbModel):
    """Device registration for push notifications.

    Stores FCM device tokens for sending push notifications to patient mobile apps.
    A patient can have multiple devices (phone, tablet, etc.).
    """

    __tablename__ = "sl_patient_device"

    id: Mapped[PrimaryKey[UUID]]

    # Link to patient
    patient_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_patient.id", ondelete="CASCADE"),
        index=True,
    )

    # FCM device token
    device_token: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    # Device info
    platform: Mapped[str_50] = mapped_column(default="ios")  # ios, android
    device_name: Mapped[str_255 | None] = mapped_column(nullable=True)
    app_version: Mapped[str_50 | None] = mapped_column(nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)
    last_used_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    patient: Mapped["Patient"] = relationship(back_populates="devices")


# Add back_populates to Patient model via import
from sense_loop.models.patient import Patient

Patient.devices = relationship(
    "PatientDevice",
    back_populates="patient",
    cascade="all, delete-orphan",
)
