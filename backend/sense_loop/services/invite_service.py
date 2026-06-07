"""Invite service - clinician invitations."""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from passlib.hash import pbkdf2_sha256
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from sense_loop.config import sl_settings
from sense_loop.models import (
    Practitioner,
    PractitionerInvite,
    PractitionerRole,
    RoleDefinition,
)
from sense_loop.schemas.practitioner import InviteRequest

logger = logging.getLogger(__name__)


class InviteService:
    """Service for managing clinician invitations."""

    def __init__(self, db: Session):
        self.db = db

    def get_invite_by_id(self, invite_id: UUID) -> PractitionerInvite | None:
        """Get invite by ID."""
        stmt = (
            select(PractitionerInvite)
            .where(PractitionerInvite.id == invite_id)
            .options(joinedload(PractitionerInvite.organization))
        )
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def get_invite_by_secret(
        self, invite_id: UUID, secret: str
    ) -> PractitionerInvite | None:
        """Get invite by ID and secret."""
        stmt = (
            select(PractitionerInvite)
            .where(
                PractitionerInvite.id == invite_id,
                PractitionerInvite.invite_secret == secret,
            )
            .options(joinedload(PractitionerInvite.organization))
        )
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def list_pending_invites(
        self, organization_id: UUID
    ) -> list[PractitionerInvite]:
        """List pending invites for an organization."""
        stmt = (
            select(PractitionerInvite)
            .where(
                PractitionerInvite.organization_id == organization_id,
                PractitionerInvite.accepted_at.is_(None),
                PractitionerInvite.revoked_at.is_(None),
            )
            .options(joinedload(PractitionerInvite.organization))
            .order_by(PractitionerInvite.created_at.desc())
        )
        return list(self.db.execute(stmt).unique().scalars().all())

    def create_invite(
        self,
        data: InviteRequest,
        invited_by: Practitioner,
    ) -> PractitionerInvite:
        """Create a new invitation.

        Returns the created invite.
        """
        from sense_loop.services.practitioner_service import PractitionerService

        # Check if email already has an account
        practitioner_svc = PractitionerService(self.db)
        existing = practitioner_svc.get_by_email(data.email)
        if existing:
            # Check if already in this org
            for role in existing.practitioner_roles:
                if role.organization_id == data.organization_id:
                    raise ValueError("User is already a member of this organization")

        # Check for existing pending invite
        stmt = select(PractitionerInvite).where(
            PractitionerInvite.email == data.email.lower(),
            PractitionerInvite.organization_id == data.organization_id,
            PractitionerInvite.accepted_at.is_(None),
            PractitionerInvite.revoked_at.is_(None),
        )
        existing_invite = self.db.execute(stmt).scalar_one_or_none()
        if existing_invite:
            raise ValueError("An invitation is already pending for this email")

        # Generate secure token
        invite_secret = secrets.token_urlsafe(32)

        # Create invite
        invite = PractitionerInvite(
            id=uuid4(),
            organization_id=data.organization_id,
            email=data.email.lower(),
            first_name=data.first_name,
            last_name=data.last_name,
            role_code=data.role_code,
            invite_secret=invite_secret,
            expires_at=datetime.utcnow() + timedelta(hours=sl_settings.invite_expire_hours),
            invited_by_id=invited_by.id,
        )

        self.db.add(invite)
        self.db.flush()

        logger.info(
            "Created invite %s for %s to org %s",
            invite.id,
            data.email,
            data.organization_id,
        )

        return invite

    def accept_invite(
        self,
        invite: PractitionerInvite,
        password: str,
    ) -> Practitioner:
        """Accept an invitation and create the practitioner account.

        Returns the created practitioner.
        """
        from sense_loop.services.practitioner_service import PractitionerService

        if invite.accepted_at:
            raise ValueError("Invitation has already been accepted")

        if invite.revoked_at:
            raise ValueError("Invitation has been revoked")

        if invite.is_expired:
            raise ValueError("Invitation has expired")

        # Check if practitioner already exists (user might exist from another org)
        practitioner_svc = PractitionerService(self.db)
        practitioner = practitioner_svc.get_by_email(invite.email)

        if practitioner:
            # Add to this organization
            practitioner_svc.add_to_organization(
                practitioner,
                invite.organization_id,
                invite.role_code,
            )
        else:
            # Create new practitioner
            # Get role definition
            role_def = self._get_role_definition(
                invite.role_code, invite.organization_id
            )
            if not role_def:
                raise ValueError(f"Invalid role code: {invite.role_code}")

            practitioner = Practitioner(
                id=uuid4(),
                email=invite.email,
                password_hash=pbkdf2_sha256.hash(password),
                first_name=invite.first_name,
                last_name=invite.last_name,
                email_verified_at=datetime.utcnow(),  # Verified via invite
            )

            self.db.add(practitioner)
            self.db.flush()

            # Create role assignment
            role = PractitionerRole(
                id=uuid4(),
                practitioner_id=practitioner.id,
                organization_id=invite.organization_id,
                role_definition_id=role_def.id,
                is_primary=True,
                invited_at=invite.created_at,
                accepted_at=datetime.utcnow(),
            )

            self.db.add(role)

        # Mark invite as accepted
        invite.accepted_at = datetime.utcnow()
        self.db.flush()

        logger.info(
            "Accepted invite %s, created/updated practitioner %s",
            invite.id,
            practitioner.id,
        )

        return practitioner

    def revoke_invite(self, invite: PractitionerInvite) -> None:
        """Revoke a pending invitation."""
        if invite.accepted_at:
            raise ValueError("Cannot revoke an accepted invitation")

        invite.revoked_at = datetime.utcnow()
        self.db.flush()

        logger.info("Revoked invite %s", invite.id)

    def resend_invite(self, invite: PractitionerInvite) -> PractitionerInvite:
        """Resend an invitation (extends expiry and increments send count)."""
        if invite.accepted_at:
            raise ValueError("Cannot resend an accepted invitation")

        if invite.revoked_at:
            raise ValueError("Cannot resend a revoked invitation")

        # Generate new secret
        invite.invite_secret = secrets.token_urlsafe(32)
        invite.expires_at = datetime.utcnow() + timedelta(hours=sl_settings.invite_expire_hours)
        invite.email_send_count += 1
        self.db.flush()

        logger.info("Resent invite %s (count: %d)", invite.id, invite.email_send_count)

        return invite

    def _get_role_definition(
        self, code: str, organization_id: UUID | None
    ) -> RoleDefinition | None:
        """Get role definition by code."""
        # First try org-specific role
        if organization_id:
            stmt = select(RoleDefinition).where(
                RoleDefinition.code == code,
                RoleDefinition.organization_id == organization_id,
                RoleDefinition.is_active == True,  # noqa: E712
            )
            role = self.db.execute(stmt).scalar_one_or_none()
            if role:
                return role

        # Fall back to system role
        stmt = select(RoleDefinition).where(
            RoleDefinition.code == code,
            RoleDefinition.organization_id.is_(None),
            RoleDefinition.is_system_role == True,  # noqa: E712
            RoleDefinition.is_active == True,  # noqa: E712
        )
        return self.db.execute(stmt).scalar_one_or_none()
