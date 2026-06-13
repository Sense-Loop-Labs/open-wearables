"""Activity template service - manage reusable instruction building blocks."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from sense_loop.models import ActivityTemplate, Organization, Practitioner

logger = logging.getLogger(__name__)


class ActivityTemplateService:
    """Service for managing activity templates."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, template_id: UUID) -> ActivityTemplate | None:
        """Get activity template by ID."""
        stmt = select(ActivityTemplate).where(ActivityTemplate.id == template_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_name(self, name: str) -> ActivityTemplate | None:
        """Get activity template by unique name."""
        stmt = select(ActivityTemplate).where(ActivityTemplate.name == name)
        return self.db.execute(stmt).scalar_one_or_none()

    def list(
        self,
        *,
        organization_id: UUID | None = None,
        include_shared: bool = True,
        status: str | None = None,
        category: str | None = None,
    ) -> list[ActivityTemplate]:
        """List activity templates.

        Args:
            organization_id: Filter to org-specific templates
            include_shared: Include shared (global) templates
            status: Filter by status (draft, active, retired)
            category: Filter by category code
        """
        conditions = []

        if organization_id and include_shared:
            # Include both org-specific and shared
            conditions.append(
                or_(
                    ActivityTemplate.organization_id == organization_id,
                    ActivityTemplate.organization_id.is_(None),
                )
            )
        elif organization_id:
            # Only org-specific
            conditions.append(ActivityTemplate.organization_id == organization_id)
        elif include_shared:
            # Only shared
            conditions.append(ActivityTemplate.organization_id.is_(None))

        if status:
            conditions.append(ActivityTemplate.status == status)

        if category:
            conditions.append(ActivityTemplate.category_code == category)

        stmt = (
            select(ActivityTemplate)
            .where(*conditions)
            .order_by(ActivityTemplate.title)
        )

        return list(self.db.execute(stmt).scalars().all())

    def create(
        self,
        *,
        title: str,
        description: str,
        category_code: str,
        created_by: Practitioner,
        organization_id: UUID | None = None,
        kind: str = "task",
        completion_method: str = "manual",
        data_trigger_types: list[str] | None = None,
        data_threshold: dict | None = None,
        confirmation_prompt: str | None = None,
        content: dict | None = None,
        default_timing: dict | None = None,
        code_system: str | None = None,
        code_value: str | None = None,
    ) -> ActivityTemplate:
        """Create a new activity template."""
        # Generate unique name from title
        name = self._generate_unique_name(title)

        template = ActivityTemplate(
            id=uuid4(),
            organization_id=organization_id,
            name=name,
            title=title,
            description=description,
            status="draft",
            version="1.0.0",
            category_code=category_code,
            kind=kind,
            completion_method=completion_method,
            data_trigger_types=data_trigger_types,
            data_threshold=data_threshold,
            confirmation_prompt=confirmation_prompt,
            content=content or {},
            default_timing=default_timing,
            code_system=code_system,
            code_value=code_value,
            created_by_id=created_by.id,
        )

        self.db.add(template)
        self.db.flush()

        logger.info(
            "Created activity template %s (%s) by %s",
            template.id,
            template.name,
            created_by.email,
        )
        return template

    def update(
        self,
        template: ActivityTemplate,
        *,
        title: str | None = None,
        description: str | None = None,
        category_code: str | None = None,
        kind: str | None = None,
        completion_method: str | None = None,
        data_trigger_types: list[str] | None = None,
        data_threshold: dict | None = None,
        confirmation_prompt: str | None = None,
        content: dict | None = None,
        default_timing: dict | None = None,
        code_system: str | None = None,
        code_value: str | None = None,
        status: str | None = None,
    ) -> ActivityTemplate:
        """Update an activity template."""
        if title is not None:
            template.title = title
        if description is not None:
            template.description = description
        if category_code is not None:
            template.category_code = category_code
        if kind is not None:
            template.kind = kind
        if completion_method is not None:
            template.completion_method = completion_method
        if data_trigger_types is not None:
            template.data_trigger_types = data_trigger_types
        if data_threshold is not None:
            template.data_threshold = data_threshold
        if confirmation_prompt is not None:
            template.confirmation_prompt = confirmation_prompt
        if content is not None:
            template.content = content
        if default_timing is not None:
            template.default_timing = default_timing
        if code_system is not None:
            template.code_system = code_system
        if code_value is not None:
            template.code_value = code_value
        if status is not None:
            template.status = status

        template.updated_at = datetime.utcnow()
        self.db.flush()

        logger.info("Updated activity template %s", template.id)
        return template

    def activate(self, template: ActivityTemplate) -> ActivityTemplate:
        """Activate a template (set status to active)."""
        template.status = "active"
        template.updated_at = datetime.utcnow()
        self.db.flush()

        logger.info("Activated activity template %s", template.id)
        return template

    def retire(self, template: ActivityTemplate) -> ActivityTemplate:
        """Retire a template (soft delete)."""
        template.status = "retired"
        template.updated_at = datetime.utcnow()
        self.db.flush()

        logger.info("Retired activity template %s", template.id)
        return template

    def duplicate(
        self,
        template: ActivityTemplate,
        *,
        created_by: Practitioner,
        to_organization_id: UUID | None = None,
        new_title: str | None = None,
    ) -> ActivityTemplate:
        """Duplicate a template.

        Args:
            template: Template to duplicate
            created_by: Practitioner creating the duplicate
            to_organization_id: Target org (None for shared)
            new_title: Override title (default: "{original} (Copy)")
        """
        title = new_title or f"{template.title} (Copy)"

        return self.create(
            title=title,
            description=template.description,
            category_code=template.category_code,
            created_by=created_by,
            organization_id=to_organization_id,
            kind=template.kind,
            completion_method=template.completion_method,
            data_trigger_types=template.data_trigger_types,
            data_threshold=template.data_threshold,
            confirmation_prompt=template.confirmation_prompt,
            content=template.content,
            default_timing=template.default_timing,
            code_system=template.code_system,
            code_value=template.code_value,
        )

    def _generate_unique_name(self, title: str) -> str:
        """Generate a unique slug name from title."""
        # Convert to lowercase and replace spaces with hyphens
        base_name = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")

        # Truncate to reasonable length
        if len(base_name) > 80:
            base_name = base_name[:80].rsplit("-", 1)[0]

        # Check if name exists and append number if needed
        name = base_name
        counter = 1
        while self.get_by_name(name) is not None:
            name = f"{base_name}-{counter}"
            counter += 1

        return name
