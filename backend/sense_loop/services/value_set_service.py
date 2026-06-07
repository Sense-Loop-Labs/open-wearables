"""ValueSet service for managing code lists."""

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from sense_loop.models import ValueSet, ValueSetItem


class ValueSetService:
    """Service for managing value sets and their items."""

    def __init__(self, db: Session):
        self.db = db

    def get_value_set(
        self,
        code: str,
        organization_id: UUID | None = None,
    ) -> ValueSet | None:
        """Get a value set by code.

        First looks for org-specific value set, then falls back to system-wide.
        """
        # Try org-specific first
        if organization_id:
            stmt = (
                select(ValueSet)
                .options(selectinload(ValueSet.items))
                .where(
                    ValueSet.code == code,
                    ValueSet.organization_id == organization_id,
                    ValueSet.is_active == True,
                )
            )
            result = self.db.execute(stmt).scalar_one_or_none()
            if result:
                return result

        # Fall back to system-wide
        stmt = (
            select(ValueSet)
            .options(selectinload(ValueSet.items))
            .where(
                ValueSet.code == code,
                ValueSet.organization_id.is_(None),
                ValueSet.is_active == True,
            )
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_value_set_items(
        self,
        code: str,
        organization_id: UUID | None = None,
        active_only: bool = True,
    ) -> list[ValueSetItem]:
        """Get items from a value set by code.

        Returns items sorted by sort_order.
        """
        value_set = self.get_value_set(code, organization_id)
        if not value_set:
            return []

        items = value_set.items
        if active_only:
            items = [item for item in items if item.is_active]

        return sorted(items, key=lambda x: x.sort_order)

    def list_value_sets(
        self,
        organization_id: UUID | None = None,
        include_system: bool = True,
    ) -> list[ValueSet]:
        """List all available value sets.

        Can filter by organization and optionally include system-wide sets.
        """
        conditions = [ValueSet.is_active == True]

        if organization_id and include_system:
            # Get both org-specific and system-wide
            conditions.append(
                (ValueSet.organization_id == organization_id)
                | (ValueSet.organization_id.is_(None))
            )
        elif organization_id:
            # Only org-specific
            conditions.append(ValueSet.organization_id == organization_id)
        else:
            # Only system-wide
            conditions.append(ValueSet.organization_id.is_(None))

        stmt = (
            select(ValueSet)
            .options(selectinload(ValueSet.items))
            .where(*conditions)
            .order_by(ValueSet.name)
        )

        return list(self.db.execute(stmt).scalars().all())

    def create_value_set(
        self,
        code: str,
        name: str,
        description: str | None = None,
        organization_id: UUID | None = None,
    ) -> ValueSet:
        """Create a new value set."""
        value_set = ValueSet(
            id=uuid4(),
            code=code,
            name=name,
            description=description,
            organization_id=organization_id,
        )
        self.db.add(value_set)
        self.db.flush()
        return value_set

    def add_item(
        self,
        value_set_id: UUID,
        code: str,
        display: str,
        coding_system: str | None = None,
        sort_order: int = 0,
        extra_data: dict | None = None,
    ) -> ValueSetItem:
        """Add an item to a value set."""
        item = ValueSetItem(
            id=uuid4(),
            value_set_id=value_set_id,
            code=code,
            display=display,
            coding_system=coding_system,
            sort_order=sort_order,
            extra_data=extra_data,
        )
        self.db.add(item)
        self.db.flush()
        return item

    def seed_surgery_types(self) -> ValueSet:
        """Seed the default surgery types value set.

        Creates the system-wide surgery-types value set with SNOMED codes.
        """
        # Check if already exists
        existing = self.get_value_set("surgery-types")
        if existing:
            return existing

        # Create value set
        value_set = self.create_value_set(
            code="surgery-types",
            name="Surgery Types",
            description="Vascular surgery types for patient monitoring",
        )

        # Add items (SNOMED codes from Medplum)
        surgery_types = [
            ("418285008", "Angioplasty"),
            ("397193006", "Atherectomy"),
            ("39202005", "Carotid Endarterectomy"),
            ("418632001", "Carotid Stenting"),
            ("7910003", "Surgical Aneurysmal Repair"),
            ("81266008", "Surgical Bypass"),
            ("234162008", "Endovascular Stent Graft"),
        ]

        for i, (code, display) in enumerate(surgery_types):
            self.add_item(
                value_set_id=value_set.id,
                code=code,
                display=display,
                coding_system="http://snomed.info/sct",
                sort_order=i,
            )

        return value_set

    def seed_defaults(self) -> None:
        """Seed all default value sets."""
        self.seed_surgery_types()
        self.db.commit()
