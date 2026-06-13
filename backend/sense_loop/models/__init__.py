"""Sense Loop database models.

All tables use the 'sl_' prefix to avoid conflicts with OW core tables.
"""

from .organization import Organization
from .role_definition import RoleDefinition
from .practitioner import Practitioner
from .practitioner_role import PractitionerRole
from .practitioner_invite import PractitionerInvite
from .patient import Patient
from .patient_device import PatientDevice
from .alert_protocol import AlertProtocol, AlertProtocolRule, AlertRiskWindow
from .alert import Alert
from .patient_summary import PatientSummary
from .care_plan import CarePlan
from .questionnaire import Questionnaire, QuestionnaireQuestion
from .questionnaire_response import QuestionnaireResponse, QuestionnaireAnswer
from .audit_log import AuditLog
from .value_set import ValueSet, ValueSetItem
from .clinical_action import ClinicalAction
from .system_config import SystemConfig

# Instruction template models
from .activity_template import ActivityTemplate
from .instruction_template import InstructionTemplate, InstructionTemplateHealthFocus
from .patient_instruction_plan import PatientInstructionPlan
from .patient_instruction_task import PatientInstructionTask
from .task_notification_log import TaskNotificationLog

# Cedar-based access control models
from sense_loop.access.cedar.models import (
    AccessPolicy,
    RoleAccessPolicy,
    PractitionerAccessPolicy,
    BreakTheGlassAccess,
)

__all__ = [
    "Organization",
    "RoleDefinition",
    "Practitioner",
    "PractitionerRole",
    "PractitionerInvite",
    "Patient",
    "PatientDevice",
    "AlertProtocol",
    "AlertProtocolRule",
    "AlertRiskWindow",
    "Alert",
    "PatientSummary",
    "CarePlan",
    "Questionnaire",
    "QuestionnaireQuestion",
    "QuestionnaireResponse",
    "QuestionnaireAnswer",
    "AuditLog",
    "ValueSet",
    "ValueSetItem",
    "ClinicalAction",
    "SystemConfig",
    # Instruction templates
    "ActivityTemplate",
    "InstructionTemplate",
    "InstructionTemplateHealthFocus",
    "PatientInstructionPlan",
    "PatientInstructionTask",
    "TaskNotificationLog",
    # Cedar access control
    "AccessPolicy",
    "RoleAccessPolicy",
    "PractitionerAccessPolicy",
    "BreakTheGlassAccess",
]
