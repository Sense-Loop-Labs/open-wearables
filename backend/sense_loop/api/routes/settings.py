"""Settings API routes for organization configuration."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.database import DbSession
from sense_loop.access import CurrentPractitioner, Permission, PolicyEngine
from sense_loop.audit import AuditLogger, get_audit_context
from sense_loop.schemas.settings import (
    AlertSettings,
    NotificationSettings,
    SettingsResponse,
    SettingsUpdate,
)
from sense_loop.services import ConfigService

router = APIRouter()


def _config_to_response(config, defaults: dict) -> SettingsResponse:
    """Convert SystemConfig to response with defaults merged."""
    settings = config.settings or {}

    # Merge with defaults for complete response
    notifications = settings.get("notifications", {})
    alerts = settings.get("alerts", {})

    return SettingsResponse(
        id=config.id,
        organization_id=config.organization_id,
        notifications=NotificationSettings(
            enabled=notifications.get("enabled", defaults["notifications"]["enabled"]),
            patient_reminder_channel=notifications.get(
                "patient_reminder_channel",
                defaults["notifications"]["patient_reminder_channel"],
            ),
            care_team_alert_channel=notifications.get(
                "care_team_alert_channel",
                defaults["notifications"]["care_team_alert_channel"],
            ),
            quiet_hours_enabled=notifications.get(
                "quiet_hours_enabled",
                defaults["notifications"]["quiet_hours_enabled"],
            ),
            quiet_hours_start=notifications.get("quiet_hours_start"),
            quiet_hours_end=notifications.get("quiet_hours_end"),
        ),
        alerts=AlertSettings(
            auto_escalate=alerts.get(
                "auto_escalate", defaults["alerts"]["auto_escalate"]
            ),
            escalation_delay_minutes=alerts.get(
                "escalation_delay_minutes",
                defaults["alerts"]["escalation_delay_minutes"],
            ),
        ),
        updated_at=config.updated_at,
    )


@router.get("", response_model=SettingsResponse)
async def get_settings(
    db: DbSession,
    practitioner: CurrentPractitioner,
    organization_id: UUID | None = Query(None),
):
    """Get organization settings.

    Returns org-specific settings if they exist, otherwise global defaults.
    """
    # Use practitioner's current org if not specified
    if not organization_id:
        org_ids = [r.organization_id for r in practitioner.roles if r.is_active]
        if org_ids:
            organization_id = org_ids[0]

    # Check access
    engine = PolicyEngine(db)
    if organization_id and not engine.has_permission(
        practitioner, Permission.MANAGE_ORG_SETTINGS, organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view organization settings",
        )

    config_service = ConfigService(db)
    config = config_service.get_config(organization_id)

    return _config_to_response(config, config_service.DEFAULTS)


@router.patch("", response_model=SettingsResponse)
async def update_settings(
    request: SettingsUpdate,
    db: DbSession,
    practitioner: CurrentPractitioner,
    organization_id: UUID | None = Query(None),
):
    """Update organization settings.

    Requires MANAGE_ORG_SETTINGS permission.
    """
    # Use practitioner's current org if not specified
    if not organization_id:
        org_ids = [r.organization_id for r in practitioner.roles if r.is_active]
        if org_ids:
            organization_id = org_ids[0]

    # Check access
    engine = PolicyEngine(db)
    if organization_id and not engine.has_permission(
        practitioner, Permission.MANAGE_ORG_SETTINGS, organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update organization settings",
        )

    config_service = ConfigService(db)

    # Update notification settings if provided
    if request.notifications:
        notif = request.notifications
        config_service.set(
            "notifications.enabled", notif.enabled, organization_id
        )
        config_service.set(
            "notifications.patient_reminder_channel",
            notif.patient_reminder_channel,
            organization_id,
        )
        config_service.set(
            "notifications.care_team_alert_channel",
            notif.care_team_alert_channel,
            organization_id,
        )
        config_service.set(
            "notifications.quiet_hours_enabled",
            notif.quiet_hours_enabled,
            organization_id,
        )
        if notif.quiet_hours_start is not None:
            config_service.set(
                "notifications.quiet_hours_start",
                notif.quiet_hours_start,
                organization_id,
            )
        if notif.quiet_hours_end is not None:
            config_service.set(
                "notifications.quiet_hours_end",
                notif.quiet_hours_end,
                organization_id,
            )

    # Update alert settings if provided
    if request.alerts:
        alert_settings = request.alerts
        config_service.set(
            "alerts.auto_escalate", alert_settings.auto_escalate, organization_id
        )
        config_service.set(
            "alerts.escalation_delay_minutes",
            alert_settings.escalation_delay_minutes,
            organization_id,
        )

    # Audit log
    ctx = get_audit_context()
    ctx.set_practitioner(practitioner)
    if organization_id:
        ctx.organization_id = organization_id
    audit = AuditLogger(db)
    audit.log_update(
        resource_type="system_config",
        resource_id=config_service.get_config(organization_id).id,
        resource_name="Organization Settings",
        changes={
            "settings": {
                "old": None,
                "new": {
                    "notifications": request.notifications.model_dump() if request.notifications else None,
                    "alerts": request.alerts.model_dump() if request.alerts else None,
                },
            }
        },
    )

    db.commit()

    config = config_service.get_config(organization_id)
    return _config_to_response(config, config_service.DEFAULTS)
