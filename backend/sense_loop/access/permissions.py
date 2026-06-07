"""Permission constants for RBAC."""

from enum import StrEnum


class Permission(StrEnum):
    """Permission constants matching RoleDefinition flags."""

    # Patient management
    MANAGE_PATIENTS = "can_manage_patients"

    # Alert management
    MANAGE_ALERTS = "can_manage_alerts"
    RESOLVE_ALERTS = "can_resolve_alerts"
    ACKNOWLEDGE_ALERTS = "can_acknowledge_alerts"

    # Care plan management
    MANAGE_CARE_PLANS = "can_manage_care_plans"

    # Organization management
    MANAGE_CLINICIANS = "can_manage_clinicians"
    MANAGE_ORG_SETTINGS = "can_manage_org_settings"

    # Audit and compliance
    VIEW_AUDIT_LOGS = "can_view_audit_logs"

    # Protocol management
    MANAGE_ALERT_PROTOCOLS = "can_manage_alert_protocols"

    # Data export
    EXPORT_DATA = "can_export_data"


# Permission groups for common operations
PERMISSION_GROUPS = {
    "view_dashboard": [Permission.MANAGE_PATIENTS],
    "manage_patient": [Permission.MANAGE_PATIENTS],
    "manage_alerts": [Permission.MANAGE_ALERTS, Permission.ACKNOWLEDGE_ALERTS],
    "resolve_alert": [Permission.RESOLVE_ALERTS],
    "manage_care_plan": [Permission.MANAGE_CARE_PLANS],
    "admin": [Permission.MANAGE_CLINICIANS, Permission.MANAGE_ORG_SETTINGS],
    "compliance": [Permission.VIEW_AUDIT_LOGS, Permission.EXPORT_DATA],
}
