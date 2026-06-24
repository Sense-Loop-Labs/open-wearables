"""Pydantic schemas for API request/response validation."""

from .patient import (
    PatientCreate,
    PatientUpdate,
    PatientResponse,
    PatientListResponse,
)
from .alert import (
    AlertResponse,
    AlertListResponse,
    AlertAcknowledgeRequest,
    AlertResolveRequest,
)
from .mobile import (
    SummaryResponse,
    CarePlanResponse,
    QuestionnaireSubmitRequest,
)
from .auth import (
    ValidateCodeRequest,
    ValidateCodeResponse,
    ActivateRequest,
    SetPasswordRequest,
    LoginRequest,
    LoginResponse,
    PractitionerLoginRequest,
    PractitionerLoginResponse,
)
from .organization import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationResponse,
)
from .practitioner import (
    PractitionerCreate,
    PractitionerUpdate,
    PractitionerResponse,
    InviteRequest,
    AcceptInviteRequest,
)
from .errors import ErrorResponse
from .clinical_action import (
    ClinicalActionCreate,
    ClinicalActionResponse,
    ClinicalActionListResponse,
)
from .instruction_template import (
    ActivityTemplateCreate,
    ActivityTemplateUpdate,
    ActivityTemplateResponse,
    ActivityTemplateListResponse,
    InstructionTemplateCreate,
    InstructionTemplateUpdate,
    InstructionTemplateResponse,
    InstructionTemplateListResponse,
    InstructionTemplatePreview,
    PatientPlanAssign,
    PatientPlanUpdate,
    PatientPlanResponse,
    PatientPlanListResponse,
    PatientPlanContent,
    TaskResponse,
    TaskListResponse,
    TaskCompleteRequest,
    TaskSkipRequest,
    TaskSnoozeRequest,
    TaskConfirmationResponse,
    TaskActionResponse,
    DailyTasksResponse,
)
from .questionnaire import (
    QuestionnaireCreate,
    QuestionnaireUpdate,
    QuestionnaireResponse,
    QuestionnaireDetailResponse,
    QuestionnaireListResponse,
    QuestionCreate,
    QuestionUpdate,
    QuestionResponse,
    QuestionReorderRequest,
    QuestionnaireAssignRequest,
    PatientQuestionnaireResponse,
    PatientQuestionnaireListResponse,
)
from .settings import (
    NotificationSettings,
    AlertSettings,
    SettingsUpdate,
    SettingsResponse,
)

__all__ = [
    # Patient
    "PatientCreate",
    "PatientUpdate",
    "PatientResponse",
    "PatientListResponse",
    # Alert
    "AlertResponse",
    "AlertListResponse",
    "AlertAcknowledgeRequest",
    "AlertResolveRequest",
    # Mobile
    "SummaryResponse",
    "CarePlanResponse",
    "QuestionnaireSubmitRequest",
    # Auth
    "ValidateCodeRequest",
    "ValidateCodeResponse",
    "ActivateRequest",
    "SetPasswordRequest",
    "LoginRequest",
    "LoginResponse",
    "PractitionerLoginRequest",
    "PractitionerLoginResponse",
    # Organization
    "OrganizationCreate",
    "OrganizationUpdate",
    "OrganizationResponse",
    # Practitioner
    "PractitionerCreate",
    "PractitionerUpdate",
    "PractitionerResponse",
    "InviteRequest",
    "AcceptInviteRequest",
    # Errors
    "ErrorResponse",
    # Clinical Action
    "ClinicalActionCreate",
    "ClinicalActionResponse",
    "ClinicalActionListResponse",
    # Instruction Templates
    "ActivityTemplateCreate",
    "ActivityTemplateUpdate",
    "ActivityTemplateResponse",
    "ActivityTemplateListResponse",
    "InstructionTemplateCreate",
    "InstructionTemplateUpdate",
    "InstructionTemplateResponse",
    "InstructionTemplateListResponse",
    "InstructionTemplatePreview",
    "PatientPlanAssign",
    "PatientPlanUpdate",
    "PatientPlanResponse",
    "PatientPlanListResponse",
    "PatientPlanContent",
    "TaskResponse",
    "TaskListResponse",
    "TaskCompleteRequest",
    "TaskSkipRequest",
    "TaskSnoozeRequest",
    "TaskConfirmationResponse",
    "TaskActionResponse",
    "DailyTasksResponse",
    # Questionnaires
    "QuestionnaireCreate",
    "QuestionnaireUpdate",
    "QuestionnaireResponse",
    "QuestionnaireDetailResponse",
    "QuestionnaireListResponse",
    "QuestionCreate",
    "QuestionUpdate",
    "QuestionResponse",
    "QuestionReorderRequest",
    "QuestionnaireAssignRequest",
    "PatientQuestionnaireResponse",
    "PatientQuestionnaireListResponse",
    # Settings
    "NotificationSettings",
    "AlertSettings",
    "SettingsUpdate",
    "SettingsResponse",
]
