"""Enrollment service - patient activation and verification."""

from __future__ import annotations

import logging
import secrets
import string
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from sense_loop.config import sl_settings
from sense_loop.models import Patient

logger = logging.getLogger(__name__)


class EnrollmentService:
    """Service for patient enrollment and activation."""

    def __init__(self, db: Session):
        self.db = db

    def generate_activation_code(self, patient: Patient) -> str:
        """Generate and set activation code for a patient.

        Format: SL-XXXXXX (6 alphanumeric characters, no ambiguous chars)
        "SL" prefix stands for "Sense Loop".
        Matches the Medplum patient-creation-bot implementation.
        """
        # Safe alphabet - excludes ambiguous characters: 0, O, I, 1, L
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

        # Generate 6 random characters and add SL- prefix
        random_part = "".join(secrets.choice(alphabet) for _ in range(6))
        code = f"SL-{random_part}"

        # Set on patient
        patient.activation_code = code
        patient.activation_code_expires_at = datetime.now(timezone.utc) + timedelta(
            hours=sl_settings.activation_code_expire_hours
        )
        self.db.flush()

        logger.info("Generated activation code for patient %s", patient.id)
        return code

    def validate_activation_code(self, code: str) -> tuple[bool, Patient | None, str | None]:
        """Validate an activation code.

        Returns:
            Tuple of (is_valid, patient, error_message)
        """
        from sqlalchemy import select

        stmt = select(Patient).where(Patient.activation_code == code.upper())
        patient = self.db.execute(stmt).scalar_one_or_none()

        if not patient:
            return False, None, "Invalid activation code"

        if not patient.is_active:
            return False, None, "Patient account is not active"

        if patient.enrollment_status not in ("pending", "activated"):
            return False, None, "Patient is already enrolled"

        if patient.activation_code_expires_at and datetime.now(timezone.utc) > patient.activation_code_expires_at:
            return False, patient, "Activation code has expired"

        return True, patient, None

    def verify_identity(
        self,
        patient: Patient,
        date_of_birth: str,
        phone_last_four: str,
    ) -> tuple[bool, str | None]:
        """Verify patient identity during activation.

        Returns:
            Tuple of (is_verified, error_message)
        """
        from datetime import date

        # Parse DOB
        try:
            if isinstance(date_of_birth, str):
                dob = date.fromisoformat(date_of_birth)
            else:
                dob = date_of_birth
        except ValueError:
            return False, "Invalid date format"

        # Check DOB
        if patient.date_of_birth != dob:
            logger.warning(
                "Identity verification failed for patient %s: DOB mismatch",
                patient.id,
            )
            return False, "Identity verification failed"

        # Check phone (last 4 digits)
        if not patient.phone:
            # If no phone on file, skip phone verification
            logger.info(
                "Skipping phone verification for patient %s (no phone on file)",
                patient.id,
            )
        else:
            # Extract last 4 digits from stored phone
            stored_digits = "".join(c for c in patient.phone if c.isdigit())[-4:]
            if stored_digits != phone_last_four:
                logger.warning(
                    "Identity verification failed for patient %s: phone mismatch",
                    patient.id,
                )
                return False, "Identity verification failed"

        return True, None

    def activate_patient(self, patient: Patient) -> str:
        """Activate patient after identity verification.

        Returns:
            Temporary activation token for setting password
        """
        # Generate activation token
        token = secrets.token_urlsafe(32)

        # Update patient status
        patient.enrollment_status = "activated"

        # Store token temporarily (you might use Redis in production)
        # For now, we'll use a simple approach
        patient.activation_code = f"TOKEN:{token}"
        patient.activation_code_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        self.db.flush()

        logger.info("Activated patient %s", patient.id)
        return token

    def set_password(self, token: str, password: str) -> tuple[bool, Patient | None, str | None]:
        """Set password for activated patient.

        Returns:
            Tuple of (success, patient, error_message)
        """
        from passlib.hash import pbkdf2_sha256
        from sqlalchemy import select

        # Find patient by token
        stmt = select(Patient).where(Patient.activation_code == f"TOKEN:{token}")
        patient = self.db.execute(stmt).scalar_one_or_none()

        if not patient:
            return False, None, "Invalid activation token"

        if patient.activation_code_expires_at and datetime.now(timezone.utc) > patient.activation_code_expires_at:
            return False, None, "Activation token has expired"

        if patient.enrollment_status != "activated":
            return False, None, "Patient is not in activated state"

        # Hash password
        patient.password_hash = pbkdf2_sha256.hash(password)

        # Clear activation code
        patient.activation_code = None
        patient.activation_code_expires_at = None

        # Mark as enrolled
        patient.enrollment_status = "active"
        patient.enrolled_at = datetime.now(timezone.utc)

        self.db.flush()

        logger.info("Set password and enrolled patient %s", patient.id)
        return True, patient, None

    def create_ow_user(self, patient: Patient) -> UUID:
        """Create an OW User for the patient.

        Returns:
            The new OW User ID
        """
        from uuid import uuid4

        from app.models import User

        # Create OW User
        ow_user = User(
            id=uuid4(),
            first_name=patient.first_name,
            last_name=patient.last_name,
            email=patient.email,
        )

        self.db.add(ow_user)
        self.db.flush()

        # Link to patient
        patient.ow_user_id = ow_user.id
        self.db.flush()

        logger.info("Created OW user %s for patient %s", ow_user.id, patient.id)
        return ow_user.id
