"""ValueSet API routes."""

from uuid import UUID

from fastapi import APIRouter, Query

from app.database import DbSession
from sense_loop.services import ValueSetService

router = APIRouter()


@router.get("")
async def list_value_sets(
    db: DbSession,
    organization_id: UUID | None = Query(None),
):
    """List all available value sets."""
    service = ValueSetService(db)
    value_sets = service.list_value_sets(organization_id)

    return [
        {
            "id": str(vs.id),
            "code": vs.code,
            "name": vs.name,
            "description": vs.description,
            "organization_id": str(vs.organization_id) if vs.organization_id else None,
            "item_count": len(vs.items),
        }
        for vs in value_sets
    ]


@router.get("/{code}")
async def get_value_set(
    code: str,
    db: DbSession,
    organization_id: UUID | None = Query(None),
):
    """Get a value set by code with its items."""
    service = ValueSetService(db)
    value_set = service.get_value_set(code, organization_id)

    if not value_set:
        return {"error": "Value set not found"}, 404

    return {
        "id": str(value_set.id),
        "code": value_set.code,
        "name": value_set.name,
        "description": value_set.description,
        "organization_id": str(value_set.organization_id) if value_set.organization_id else None,
        "items": [
            {
                "id": str(item.id),
                "code": item.code,
                "display": item.display,
                "coding_system": item.coding_system,
                "sort_order": item.sort_order,
                "extra_data": item.extra_data,
            }
            for item in value_set.items
            if item.is_active
        ],
    }


@router.get("/{code}/items")
async def get_value_set_items(
    code: str,
    db: DbSession,
    organization_id: UUID | None = Query(None),
):
    """Get just the items from a value set (for dropdowns)."""
    service = ValueSetService(db)
    items = service.get_value_set_items(code, organization_id)

    return [
        {
            "value": item.code,
            "label": item.display,
            "coding_system": item.coding_system,
            "extra_data": item.extra_data,
        }
        for item in items
    ]
