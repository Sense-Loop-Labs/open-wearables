"""Practitioner authentication service."""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta
from uuid import UUID

from jose import jwt
from passlib.hash import pbkdf2_sha256
from sqlalchemy.orm import Session

from app.config import settings
from sense_loop.models import Practitioner
from sense_loop.services.practitioner_service import PractitionerService

logger = logging.getLogger(__name__)


class PractitionerAuthService:
    """Service for practitioner authentication."""

    def __init__(self, db: Session):
        self.db = db
        self.practitioner_service = PractitionerService(db)

    def authenticate(self, email: str, password: str) -> tuple[Practitioner | None, str | None]:
        """Authenticate a practitioner.

        Returns:
            Tuple of (practitioner, error_message)
        """
        practitioner = self.practitioner_service.get_by_email(email)

        if not practitioner:
            logger.warning("Login attempt for unknown email: %s", email)
            return None, "Invalid email or password"

        if not practitioner.is_active:
            logger.warning("Login attempt for deactivated account: %s", email)
            return None, "Account is deactivated"

        if not practitioner.password_hash:
            logger.warning("Login attempt for account without password: %s", email)
            return None, "Please complete your account setup"

        if not pbkdf2_sha256.verify(password, practitioner.password_hash):
            logger.warning("Failed login attempt for: %s", email)
            return None, "Invalid email or password"

        # Update last login
        practitioner.last_login_at = datetime.utcnow()
        self.db.flush()

        logger.info("Successful login for practitioner %s", practitioner.id)
        return practitioner, None

    def create_tokens(
        self, practitioner: Practitioner
    ) -> tuple[str, str, int]:
        """Create access and refresh tokens.

        Returns:
            Tuple of (access_token, refresh_token, expires_in_seconds)
        """
        now = datetime.utcnow()
        expires_in = settings.access_token_expire_minutes * 60

        # Access token
        access_payload = {
            "sub": str(practitioner.id),
            "email": practitioner.email,
            "type": "sl_practitioner",
            "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
            "iat": now,
        }
        access_token = jwt.encode(
            access_payload,
            settings.secret_key,
            algorithm=settings.algorithm,
        )

        # Refresh token (longer lived)
        refresh_payload = {
            "sub": str(practitioner.id),
            "type": "sl_practitioner_refresh",
            "exp": now + timedelta(days=7),
            "iat": now,
        }
        refresh_token = jwt.encode(
            refresh_payload,
            settings.secret_key,
            algorithm=settings.algorithm,
        )

        return access_token, refresh_token, expires_in

    def refresh_access_token(self, refresh_token: str) -> tuple[str | None, str | None]:
        """Refresh an access token.

        Returns:
            Tuple of (new_access_token, error_message)
        """
        from jose import JWTError

        try:
            payload = jwt.decode(
                refresh_token,
                settings.secret_key,
                algorithms=[settings.algorithm],
            )
        except JWTError as e:
            return None, f"Invalid refresh token: {e}"

        if payload.get("type") != "sl_practitioner_refresh":
            return None, "Invalid token type"

        practitioner_id = payload.get("sub")
        if not practitioner_id:
            return None, "Invalid token payload"

        practitioner = self.practitioner_service.get_by_id(UUID(practitioner_id))
        if not practitioner:
            return None, "Practitioner not found"

        if not practitioner.is_active:
            return None, "Account is deactivated"

        # Create new access token
        access_token, _, _ = self.create_tokens(practitioner)
        return access_token, None

    def initiate_password_reset(self, email: str) -> tuple[bool, str | None]:
        """Initiate password reset.

        Returns:
            Tuple of (success, error_message)
        """
        practitioner = self.practitioner_service.get_by_email(email)

        if not practitioner:
            # Don't reveal if email exists
            logger.info("Password reset requested for unknown email: %s", email)
            return True, None

        if not practitioner.is_active:
            logger.info("Password reset requested for inactive account: %s", email)
            return True, None

        # Generate reset token
        token = secrets.token_urlsafe(32)
        practitioner.password_reset_token = token
        practitioner.password_reset_expires_at = datetime.utcnow() + timedelta(hours=1)
        self.db.flush()

        # TODO: Send email with reset link
        logger.info("Password reset initiated for practitioner %s", practitioner.id)

        return True, None

    def reset_password(
        self, token: str, new_password: str
    ) -> tuple[bool, str | None]:
        """Reset password with token.

        Returns:
            Tuple of (success, error_message)
        """
        from sqlalchemy import select

        stmt = select(Practitioner).where(
            Practitioner.password_reset_token == token
        )
        practitioner = self.db.execute(stmt).scalar_one_or_none()

        if not practitioner:
            return False, "Invalid reset token"

        if not practitioner.password_reset_expires_at:
            return False, "Invalid reset token"

        if datetime.utcnow() > practitioner.password_reset_expires_at:
            return False, "Reset token has expired"

        # Update password
        practitioner.password_hash = pbkdf2_sha256.hash(new_password)
        practitioner.password_reset_token = None
        practitioner.password_reset_expires_at = None
        self.db.flush()

        logger.info("Password reset completed for practitioner %s", practitioner.id)
        return True, None

    def change_password(
        self, practitioner: Practitioner, current_password: str, new_password: str
    ) -> tuple[bool, str | None]:
        """Change password for authenticated practitioner.

        Returns:
            Tuple of (success, error_message)
        """
        if not practitioner.password_hash:
            return False, "No password set"

        if not pbkdf2_sha256.verify(current_password, practitioner.password_hash):
            return False, "Current password is incorrect"

        practitioner.password_hash = pbkdf2_sha256.hash(new_password)
        self.db.flush()

        logger.info("Password changed for practitioner %s", practitioner.id)
        return True, None
