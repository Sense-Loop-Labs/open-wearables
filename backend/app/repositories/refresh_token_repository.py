from datetime import datetime, timedelta, timezone
from typing import cast
from uuid import UUID

from sqlalchemy import CursorResult, select, update

from app.database import DbSession
from app.models import RefreshToken

# Grace period in minutes for recently revoked tokens
# If a token was revoked within this time and has a replacement, it can still be used
REFRESH_TOKEN_GRACE_PERIOD_MINUTES = 5


class RefreshTokenRepository:
    """Repository for refresh token database operations."""

    def __init__(self) -> None:
        self.model = RefreshToken

    def create(self, db_session: DbSession, token: RefreshToken) -> RefreshToken:
        """Create a new refresh token."""
        db_session.add(token)
        db_session.commit()
        db_session.refresh(token)
        return token

    def get_valid_token(self, db_session: DbSession, token_id: str) -> RefreshToken | None:
        """Get a refresh token if it exists and is not revoked."""
        stmt = select(self.model).where(self.model.id == token_id, self.model.revoked_at.is_(None))
        return db_session.execute(stmt).scalar_one_or_none()

    def get_token_with_grace_period(
        self, db_session: DbSession, token_id: str
    ) -> tuple[RefreshToken | None, RefreshToken | None]:
        """Get a refresh token, including recently revoked tokens within grace period.

        Returns:
            Tuple of (token, replacement_token):
            - If token is valid (not revoked): (token, None)
            - If token is revoked but within grace period with replacement: (token, replacement)
            - If token is invalid/expired: (None, None)
        """
        stmt = select(self.model).where(self.model.id == token_id)
        token = db_session.execute(stmt).scalar_one_or_none()

        if not token:
            return None, None

        # Token is valid (not revoked)
        if token.revoked_at is None:
            return token, None

        # Token is revoked - check if within grace period
        grace_cutoff = datetime.now(timezone.utc) - timedelta(minutes=REFRESH_TOKEN_GRACE_PERIOD_MINUTES)

        if token.revoked_at >= grace_cutoff and token.replaced_by_id:
            # Within grace period and has a replacement - fetch the replacement
            replacement = self.get_valid_token(db_session, token.replaced_by_id)
            if replacement:
                return token, replacement

        # Revoked and either outside grace period or no valid replacement
        return None, None

    def get_by_user_id(self, db_session: DbSession, user_id: UUID) -> list[RefreshToken]:
        """Get all refresh tokens for a user."""
        stmt = select(self.model).where(self.model.user_id == user_id, self.model.revoked_at.is_(None))
        return list(db_session.execute(stmt).scalars().all())

    def get_by_developer_id(self, db_session: DbSession, developer_id: UUID) -> list[RefreshToken]:
        """Get all refresh tokens for a developer."""
        stmt = select(self.model).where(self.model.developer_id == developer_id, self.model.revoked_at.is_(None))
        return list(db_session.execute(stmt).scalars().all())

    def revoke_token(
        self, db_session: DbSession, token: RefreshToken, replaced_by_id: str | None = None
    ) -> RefreshToken:
        """Revoke a single refresh token.

        Args:
            db_session: Database session
            token: The token to revoke
            replaced_by_id: Optional ID of the replacement token (for rotation)
        """
        token.revoked_at = datetime.now(timezone.utc)
        token.replaced_by_id = replaced_by_id
        db_session.commit()
        db_session.refresh(token)
        return token

    def revoke_all_for_user(self, db_session: DbSession, user_id: UUID) -> int:
        """Revoke all refresh tokens for a user. Returns count of revoked tokens."""
        now = datetime.now(timezone.utc)
        stmt = (
            update(self.model)
            .where(self.model.user_id == user_id, self.model.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        result = cast(CursorResult[tuple[()]], db_session.execute(stmt))
        db_session.commit()
        return result.rowcount or 0

    def revoke_all_for_developer(self, db_session: DbSession, developer_id: UUID) -> int:
        """Revoke all refresh tokens for a developer. Returns count of revoked tokens."""
        now = datetime.now(timezone.utc)
        stmt = (
            update(self.model)
            .where(self.model.developer_id == developer_id, self.model.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        result = cast(CursorResult[tuple[()]], db_session.execute(stmt))
        db_session.commit()
        return result.rowcount or 0

    def update_last_used(self, db_session: DbSession, token: RefreshToken) -> RefreshToken:
        """Update the last_used_at timestamp of a token."""
        token.last_used_at = datetime.now(timezone.utc)
        db_session.commit()
        db_session.refresh(token)
        return token


refresh_token_repository = RefreshTokenRepository()
