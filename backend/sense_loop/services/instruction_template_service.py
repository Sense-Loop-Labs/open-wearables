"""Instruction template service - manage complete instruction/care plan templates."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select, or_
from sqlalchemy.orm import Session, joinedload

from sense_loop.models import (
    ActivityTemplate,
    InstructionTemplate,
    InstructionTemplateHealthFocus,
    Practitioner,
)

logger = logging.getLogger(__name__)


class InstructionTemplateService:
    """Service for managing instruction templates."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(
        self, template_id: UUID, *, load_health_focuses: bool = True
    ) -> InstructionTemplate | None:
        """Get instruction template by ID."""
        stmt = select(InstructionTemplate).where(InstructionTemplate.id == template_id)

        if load_health_focuses:
            stmt = stmt.options(joinedload(InstructionTemplate.health_focuses))

        return self.db.execute(stmt).unique().scalar_one_or_none()

    def get_by_name(self, name: str) -> InstructionTemplate | None:
        """Get instruction template by unique name."""
        stmt = (
            select(InstructionTemplate)
            .where(InstructionTemplate.name == name)
            .options(joinedload(InstructionTemplate.health_focuses))
        )
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def list(
        self,
        *,
        organization_id: UUID | None = None,
        include_shared: bool = True,
        status: str | None = None,
        health_focus: str | None = None,
    ) -> list[InstructionTemplate]:
        """List instruction templates.

        Args:
            organization_id: Filter to org-specific templates
            include_shared: Include shared (global) templates
            status: Filter by status (draft, active, retired)
            health_focus: Filter by health focus code
        """
        conditions = []

        if organization_id and include_shared:
            conditions.append(
                or_(
                    InstructionTemplate.organization_id == organization_id,
                    InstructionTemplate.organization_id.is_(None),
                )
            )
        elif organization_id:
            conditions.append(InstructionTemplate.organization_id == organization_id)
        elif include_shared:
            conditions.append(InstructionTemplate.organization_id.is_(None))

        if status:
            conditions.append(InstructionTemplate.status == status)

        stmt = (
            select(InstructionTemplate)
            .where(*conditions)
            .options(joinedload(InstructionTemplate.health_focuses))
            .order_by(InstructionTemplate.title)
        )

        templates = list(self.db.execute(stmt).unique().scalars().all())

        # Filter by health focus if specified
        if health_focus:
            templates = [
                t for t in templates if health_focus in t.health_focus_codes
            ]

        return templates

    def create(
        self,
        *,
        title: str,
        description: str,
        created_by: Practitioner,
        organization_id: UUID | None = None,
        content: dict | None = None,
        health_focus_codes: list[str] | None = None,
        notification_config: dict | None = None,
    ) -> InstructionTemplate:
        """Create a new instruction template."""
        name = self._generate_unique_name(title)

        template = InstructionTemplate(
            id=uuid4(),
            organization_id=organization_id,
            name=name,
            title=title,
            description=description,
            status="draft",
            version="1.0.0",
            content=content or {"sections": []},
            notification_config=notification_config,
            created_by_id=created_by.id,
        )

        self.db.add(template)
        self.db.flush()

        # Add health focus associations
        if health_focus_codes:
            for code in health_focus_codes:
                health_focus = InstructionTemplateHealthFocus(
                    id=uuid4(),
                    template_id=template.id,
                    health_focus_code=code,
                )
                self.db.add(health_focus)

        self.db.flush()

        logger.info(
            "Created instruction template %s (%s) by %s",
            template.id,
            template.name,
            created_by.email,
        )
        return template

    def update(
        self,
        template: InstructionTemplate,
        *,
        title: str | None = None,
        description: str | None = None,
        content: dict | None = None,
        health_focus_codes: list[str] | None = None,
        notification_config: dict | None = None,
        status: str | None = None,
        version: str | None = None,
    ) -> InstructionTemplate:
        """Update an instruction template."""
        if title is not None:
            template.title = title
        if description is not None:
            template.description = description
        if content is not None:
            template.content = content
        if notification_config is not None:
            template.notification_config = notification_config
        if status is not None:
            template.status = status
        if version is not None:
            template.version = version

        # Update health focus associations if provided
        if health_focus_codes is not None:
            # Remove existing associations
            for hf in list(template.health_focuses):
                self.db.delete(hf)

            # Add new associations
            for code in health_focus_codes:
                health_focus = InstructionTemplateHealthFocus(
                    id=uuid4(),
                    template_id=template.id,
                    health_focus_code=code,
                )
                self.db.add(health_focus)

        template.updated_at = datetime.utcnow()
        self.db.flush()

        logger.info("Updated instruction template %s", template.id)
        return template

    def activate(self, template: InstructionTemplate) -> InstructionTemplate:
        """Activate a template."""
        template.status = "active"
        template.updated_at = datetime.utcnow()
        self.db.flush()

        logger.info("Activated instruction template %s", template.id)
        return template

    def retire(self, template: InstructionTemplate) -> InstructionTemplate:
        """Retire a template (soft delete)."""
        template.status = "retired"
        template.updated_at = datetime.utcnow()
        self.db.flush()

        logger.info("Retired instruction template %s", template.id)
        return template

    def duplicate(
        self,
        template: InstructionTemplate,
        *,
        created_by: Practitioner,
        to_organization_id: UUID | None = None,
        new_title: str | None = None,
    ) -> InstructionTemplate:
        """Duplicate a template."""
        title = new_title or f"{template.title} (Copy)"

        return self.create(
            title=title,
            description=template.description,
            created_by=created_by,
            organization_id=to_organization_id,
            content=template.content,
            health_focus_codes=template.health_focus_codes,
            notification_config=template.notification_config,
        )

    def get_resolved_content(
        self,
        template: InstructionTemplate,
        activity_service: "ActivityTemplateService" = None,
    ) -> dict:
        """Get template content with activity references resolved.

        Expands activity_template_id references to include the full
        activity details (title, description, timing, etc.).
        """
        from sense_loop.services.activity_template_service import ActivityTemplateService

        if activity_service is None:
            activity_service = ActivityTemplateService(self.db)

        content = template.content.copy()
        sections = content.get("sections", [])

        # Cache activity templates to avoid repeated queries
        activity_ids = template.get_activity_template_ids()
        activities_by_id = {}
        for activity_id in activity_ids:
            try:
                activity = activity_service.get_by_id(UUID(activity_id))
                if activity:
                    activities_by_id[activity_id] = activity
            except (ValueError, TypeError):
                logger.warning("Invalid activity ID: %s", activity_id)

        # Resolve activity references in each section
        resolved_sections = []
        for section in sections:
            resolved_section = section.copy()
            resolved_items = []

            for item in section.get("items", []):
                resolved_item = item.copy()

                # Resolve activity reference if activity_template_id is present
                activity_id = item.get("activity_template_id")
                if activity_id:
                    activity = activities_by_id.get(activity_id)

                    if activity:
                        # Merge activity details into item
                        resolved_item["activity"] = {
                            "id": str(activity.id),
                            "name": activity.name,
                            "title": activity.title,
                            "description": activity.description,
                            "category_code": activity.category_code,
                            "kind": activity.kind,
                            "completion_method": activity.completion_method,
                            "data_trigger_types": activity.data_trigger_types,
                            "data_threshold": activity.data_threshold,
                            "confirmation_prompt": activity.confirmation_prompt,
                            "content": activity.content,
                        }

                        # Use item timing override or fall back to activity default
                        if not resolved_item.get("timing") and activity.default_timing:
                            resolved_item["timing"] = activity.default_timing

                        # Use activity title if item has no title
                        if not resolved_item.get("title"):
                            resolved_item["title"] = activity.title

                resolved_items.append(resolved_item)

            resolved_section["items"] = resolved_items
            resolved_sections.append(resolved_section)

        content["sections"] = resolved_sections
        return content

    def preview(self, template: InstructionTemplate) -> dict:
        """Get a preview of the template with all references resolved."""
        resolved_content = self.get_resolved_content(template)

        return {
            "id": str(template.id),
            "name": template.name,
            "title": template.title,
            "description": template.description,
            "version": template.version,
            "status": template.status,
            "health_focus_codes": template.health_focus_codes,
            "content": resolved_content,
            "notification_config": template.notification_config,
        }

    def _generate_unique_name(self, title: str) -> str:
        """Generate a unique slug name from title."""
        base_name = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")

        if len(base_name) > 80:
            base_name = base_name[:80].rsplit("-", 1)[0]

        name = base_name
        counter = 1
        while self.get_by_name(name) is not None:
            name = f"{base_name}-{counter}"
            counter += 1

        return name
