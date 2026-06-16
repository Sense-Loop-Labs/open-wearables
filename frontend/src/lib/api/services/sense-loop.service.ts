/**
 * Sense Loop API Service
 * Handles all API calls to the Sense Loop clinical dashboard endpoints
 */

import { slApiClient, slPublicApiClient } from '../sl-client';
import type {
  AcceptInviteRequest,
  ActivityTemplate,
  ActivityTemplateCreate,
  ActivityTemplateQueryParams,
  ActivityTemplateUpdate,
  Alert,
  AlertAcknowledgeRequest,
  AlertQueryParams,
  AlertResolveRequest,
  AlertsByDay,
  AlertStats,
  ClinicalAction,
  ClinicalActionCreate,
  CriticalPatient,
  DashboardOverview,
  ForgotPasswordRequest,
  InstructionTemplate,
  InstructionTemplateCreate,
  InstructionTemplatePreview,
  InstructionTemplateQueryParams,
  InstructionTemplateUpdate,
  InviteClinicianRequest,
  Organization,
  OrganizationCreate,
  OrganizationUpdate,
  PaginatedActivityTemplates,
  PaginatedAlerts,
  PaginatedClinicalActions,
  PaginatedClinicians,
  PaginatedInstructionTemplates,
  PaginatedPatientPlans,
  PaginatedPatients,
  PaginatedQuestionnaires,
  Patient,
  PatientCreate,
  PatientInstructionPlan,
  PatientPlanAssign,
  PatientPlanContentResponse,
  PatientPlanUpdate,
  PatientQueryParams,
  PatientUpdate,
  PractitionerInvite,
  PractitionerLoginRequest,
  PractitionerLoginResponse,
  PractitionerWithRoles,
  QuestionCreate,
  QuestionnaireCreate,
  QuestionnaireQueryParams,
  QuestionnaireQuestion,
  QuestionnaireTemplate,
  QuestionnaireTemplateDetail,
  QuestionnaireUpdate,
  QuestionUpdate,
  RecentAlert,
  ResetPasswordRequest,
  RoleDefinition,
  ValueSet,
  ValueSetItem,
  VitalsHistoryResponse,
  VitalsQueryParams,
  PatientQuestionnaire,
  PatientQuestionnaireList,
  QuestionnaireResponseDetail,
} from '../types/sense-loop';

const SL_BASE = '/api/v1/sl';

// ============================================================================
// Auth
// ============================================================================

export const slAuthService = {
  async login(
    credentials: PractitionerLoginRequest
  ): Promise<PractitionerLoginResponse> {
    return slPublicApiClient.post<PractitionerLoginResponse>(
      `${SL_BASE}/auth/practitioner/login`,
      credentials
    );
  },

  async logout(): Promise<void> {
    return slApiClient.post(`${SL_BASE}/auth/practitioner/logout`);
  },

  async forgotPassword(
    data: ForgotPasswordRequest
  ): Promise<{ success: boolean; message: string }> {
    return slPublicApiClient.post(
      `${SL_BASE}/auth/practitioner/forgot-password`,
      data
    );
  },

  async resetPassword(
    data: ResetPasswordRequest
  ): Promise<{ success: boolean; message: string }> {
    return slPublicApiClient.post(
      `${SL_BASE}/auth/practitioner/reset-password`,
      data
    );
  },

  async acceptInvite(
    data: AcceptInviteRequest
  ): Promise<{ success: boolean; message: string }> {
    return slPublicApiClient.post(`${SL_BASE}/clinicians/invites/accept`, {
      invite_id: data.invite_id,
      invite_secret: data.invite_secret,
      password: data.password,
      password_confirm: data.password_confirm,
    });
  },
};

// ============================================================================
// Dashboard
// ============================================================================

export const slDashboardService = {
  async getOverview(organizationId?: string): Promise<DashboardOverview> {
    const params = organizationId
      ? { organization_id: organizationId }
      : undefined;
    return slApiClient.request<DashboardOverview>(
      `${SL_BASE}/dashboard/overview`,
      {
        method: 'GET',
        params,
      }
    );
  },

  async getCriticalPatients(
    organizationId?: string,
    limit = 10
  ): Promise<CriticalPatient[]> {
    const params: Record<string, string | number> = { limit };
    if (organizationId) params.organization_id = organizationId;
    return slApiClient.request<CriticalPatient[]>(
      `${SL_BASE}/dashboard/critical-patients`,
      {
        method: 'GET',
        params,
      }
    );
  },

  async getRecentAlerts(
    organizationId?: string,
    limit = 10
  ): Promise<RecentAlert[]> {
    const params: Record<string, string | number> = { limit };
    if (organizationId) params.organization_id = organizationId;
    return slApiClient.request<RecentAlert[]>(
      `${SL_BASE}/dashboard/recent-alerts`,
      {
        method: 'GET',
        params,
      }
    );
  },

  async getAlertsByDay(
    organizationId?: string,
    days = 7
  ): Promise<AlertsByDay[]> {
    const params: Record<string, string | number> = { days };
    if (organizationId) params.organization_id = organizationId;
    return slApiClient.request<AlertsByDay[]>(
      `${SL_BASE}/dashboard/alerts-by-day`,
      {
        method: 'GET',
        params,
      }
    );
  },
};

// ============================================================================
// Patients
// ============================================================================

export const slPatientsService = {
  async getAll(params?: PatientQueryParams): Promise<PaginatedPatients> {
    return slApiClient.request<PaginatedPatients>(`${SL_BASE}/patients`, {
      method: 'GET',
      params: params as Record<string, string | number | boolean>,
    });
  },

  async getById(id: string): Promise<Patient> {
    return slApiClient.request<Patient>(`${SL_BASE}/patients/${id}`, {
      method: 'GET',
    });
  },

  async create(data: PatientCreate): Promise<Patient> {
    return slApiClient.post<Patient>(`${SL_BASE}/patients`, data);
  },

  async update(id: string, data: PatientUpdate): Promise<Patient> {
    return slApiClient.patch<Patient>(`${SL_BASE}/patients/${id}`, data);
  },

  async generateActivationCode(
    id: string
  ): Promise<{ activation_code: string; expires_at: string }> {
    return slApiClient.post(
      `${SL_BASE}/patients/${id}/generate-activation-code`
    );
  },

  async discharge(id: string): Promise<Patient> {
    return slApiClient.post<Patient>(`${SL_BASE}/patients/${id}/discharge`);
  },

  async getVitals(
    id: string,
    params?: VitalsQueryParams
  ): Promise<VitalsHistoryResponse> {
    return slApiClient.request<VitalsHistoryResponse>(
      `${SL_BASE}/patients/${id}/vitals`,
      {
        method: 'GET',
        params: params as Record<string, string | number | boolean>,
      }
    );
  },
};

// ============================================================================
// Alerts
// ============================================================================

export const slAlertsService = {
  async getAll(params?: AlertQueryParams): Promise<PaginatedAlerts> {
    return slApiClient.request<PaginatedAlerts>(`${SL_BASE}/alerts`, {
      method: 'GET',
      params: params as Record<string, string | number | boolean>,
    });
  },

  async getById(id: string): Promise<Alert> {
    return slApiClient.request<Alert>(`${SL_BASE}/alerts/${id}`, {
      method: 'GET',
    });
  },

  async acknowledge(
    id: string,
    data?: AlertAcknowledgeRequest
  ): Promise<{ success: boolean }> {
    return slApiClient.post(`${SL_BASE}/alerts/${id}/acknowledge`, data || {});
  },

  async resolve(
    id: string,
    data: AlertResolveRequest
  ): Promise<{ success: boolean }> {
    return slApiClient.post(`${SL_BASE}/alerts/${id}/resolve`, data);
  },

  async getStats(organizationId?: string): Promise<AlertStats> {
    const params = organizationId
      ? { organization_id: organizationId }
      : undefined;
    return slApiClient.request<AlertStats>(`${SL_BASE}/alerts/stats/summary`, {
      method: 'GET',
      params,
    });
  },
};

// ============================================================================
// Clinicians
// ============================================================================

export const slCliniciansService = {
  async getAll(organizationId?: string): Promise<PaginatedClinicians> {
    const params = organizationId
      ? { organization_id: organizationId }
      : undefined;
    return slApiClient.request<PaginatedClinicians>(`${SL_BASE}/clinicians`, {
      method: 'GET',
      params,
    });
  },

  async getPendingInvites(
    organizationId: string
  ): Promise<PractitionerInvite[]> {
    return slApiClient.request<PractitionerInvite[]>(
      `${SL_BASE}/clinicians/invites`,
      {
        method: 'GET',
        params: { organization_id: organizationId },
      }
    );
  },

  async resendInvite(
    inviteId: string
  ): Promise<{ success: boolean; message: string }> {
    return slApiClient.post(`${SL_BASE}/clinicians/invites/${inviteId}/resend`);
  },

  async revokeInvite(
    inviteId: string
  ): Promise<{ success: boolean; message: string }> {
    return slApiClient.post(`${SL_BASE}/clinicians/invites/${inviteId}/revoke`);
  },

  async getById(id: string): Promise<PractitionerWithRoles> {
    return slApiClient.request<PractitionerWithRoles>(
      `${SL_BASE}/clinicians/${id}`,
      {
        method: 'GET',
      }
    );
  },

  async invite(
    organizationId: string,
    data: InviteClinicianRequest
  ): Promise<PractitionerInvite> {
    return slApiClient.post<PractitionerInvite>(
      `${SL_BASE}/clinicians/invite`,
      {
        ...data,
        organization_id: organizationId,
      }
    );
  },

  async deactivate(
    id: string,
    organizationId: string
  ): Promise<{ success: boolean }> {
    return slApiClient.post(
      `${SL_BASE}/clinicians/${id}/deactivate`,
      undefined,
      {
        params: { organization_id: organizationId },
      }
    );
  },

  async update(
    id: string,
    data: {
      first_name?: string;
      last_name?: string;
      phone?: string;
      npi_number?: string;
      credentials?: string;
    },
    organizationId: string
  ): Promise<PractitionerWithRoles> {
    return slApiClient.patch<PractitionerWithRoles>(
      `${SL_BASE}/clinicians/${id}`,
      data,
      {
        params: { organization_id: organizationId },
      }
    );
  },

  async getRoles(organizationId: string): Promise<RoleDefinition[]> {
    return slApiClient.request<RoleDefinition[]>(
      `${SL_BASE}/clinicians/roles`,
      {
        method: 'GET',
        params: { organization_id: organizationId },
      }
    );
  },
};

// ============================================================================
// Organizations
// ============================================================================

export const slOrganizationsService = {
  async getAll(): Promise<Organization[]> {
    return slApiClient.request<Organization[]>(`${SL_BASE}/organizations`, {
      method: 'GET',
    });
  },

  async getById(id: string): Promise<Organization> {
    return slApiClient.request<Organization>(`${SL_BASE}/organizations/${id}`, {
      method: 'GET',
    });
  },

  async create(data: OrganizationCreate): Promise<Organization> {
    return slApiClient.post<Organization>(`${SL_BASE}/organizations`, data);
  },

  async update(id: string, data: OrganizationUpdate): Promise<Organization> {
    return slApiClient.patch<Organization>(
      `${SL_BASE}/organizations/${id}`,
      data
    );
  },
};

// ============================================================================
// Value Sets
// ============================================================================

export const slValueSetsService = {
  async getAll(organizationId?: string): Promise<ValueSet[]> {
    const params = organizationId
      ? { organization_id: organizationId }
      : undefined;
    return slApiClient.request<ValueSet[]>(`${SL_BASE}/value-sets`, {
      method: 'GET',
      params,
    });
  },

  async getByCode(
    code: string,
    organizationId?: string
  ): Promise<ValueSet & { items: ValueSetItem[] }> {
    const params = organizationId
      ? { organization_id: organizationId }
      : undefined;
    return slApiClient.request<ValueSet & { items: ValueSetItem[] }>(
      `${SL_BASE}/value-sets/${code}`,
      {
        method: 'GET',
        params,
      }
    );
  },

  async getItems(
    code: string,
    organizationId?: string
  ): Promise<ValueSetItem[]> {
    const params = organizationId
      ? { organization_id: organizationId }
      : undefined;
    return slApiClient.request<ValueSetItem[]>(
      `${SL_BASE}/value-sets/${code}/items`,
      {
        method: 'GET',
        params,
      }
    );
  },
};

// ============================================================================
// Clinical Actions
// ============================================================================

export const slClinicalActionsService = {
  async getAll(
    patientId: string,
    params?: { page?: number; page_size?: number }
  ): Promise<PaginatedClinicalActions> {
    return slApiClient.request<PaginatedClinicalActions>(
      `${SL_BASE}/patients/${patientId}/actions`,
      {
        method: 'GET',
        params: params as Record<string, string | number>,
      }
    );
  },

  async create(
    patientId: string,
    data: ClinicalActionCreate
  ): Promise<ClinicalAction> {
    return slApiClient.post<ClinicalAction>(
      `${SL_BASE}/patients/${patientId}/actions`,
      data
    );
  },
};

// ============================================================================
// Activity Templates
// ============================================================================

export const slActivityTemplatesService = {
  async getAll(
    params?: ActivityTemplateQueryParams
  ): Promise<PaginatedActivityTemplates> {
    return slApiClient.request<PaginatedActivityTemplates>(
      `${SL_BASE}/instruction-templates/activities`,
      {
        method: 'GET',
        params: params as Record<string, string | number | boolean>,
      }
    );
  },

  async getById(id: string): Promise<ActivityTemplate> {
    return slApiClient.request<ActivityTemplate>(
      `${SL_BASE}/instruction-templates/activities/${id}`,
      { method: 'GET' }
    );
  },

  async create(data: ActivityTemplateCreate): Promise<ActivityTemplate> {
    return slApiClient.post<ActivityTemplate>(
      `${SL_BASE}/instruction-templates/activities`,
      data
    );
  },

  async update(
    id: string,
    data: ActivityTemplateUpdate
  ): Promise<ActivityTemplate> {
    return slApiClient.patch<ActivityTemplate>(
      `${SL_BASE}/instruction-templates/activities/${id}`,
      data
    );
  },

  async activate(id: string): Promise<ActivityTemplate> {
    return slApiClient.post<ActivityTemplate>(
      `${SL_BASE}/instruction-templates/activities/${id}/activate`
    );
  },

  async retire(id: string): Promise<ActivityTemplate> {
    return slApiClient.post<ActivityTemplate>(
      `${SL_BASE}/instruction-templates/activities/${id}/retire`
    );
  },
};

// ============================================================================
// Instruction Templates
// ============================================================================

export const slInstructionTemplatesService = {
  async getAll(
    params?: InstructionTemplateQueryParams
  ): Promise<PaginatedInstructionTemplates> {
    return slApiClient.request<PaginatedInstructionTemplates>(
      `${SL_BASE}/instruction-templates`,
      {
        method: 'GET',
        params: params as Record<string, string | number | boolean>,
      }
    );
  },

  async getById(id: string): Promise<InstructionTemplate> {
    return slApiClient.request<InstructionTemplate>(
      `${SL_BASE}/instruction-templates/${id}`,
      { method: 'GET' }
    );
  },

  async getPreview(id: string): Promise<InstructionTemplatePreview> {
    return slApiClient.request<InstructionTemplatePreview>(
      `${SL_BASE}/instruction-templates/${id}/preview`,
      { method: 'GET' }
    );
  },

  async create(data: InstructionTemplateCreate): Promise<InstructionTemplate> {
    return slApiClient.post<InstructionTemplate>(
      `${SL_BASE}/instruction-templates`,
      data
    );
  },

  async update(
    id: string,
    data: InstructionTemplateUpdate
  ): Promise<InstructionTemplate> {
    return slApiClient.patch<InstructionTemplate>(
      `${SL_BASE}/instruction-templates/${id}`,
      data
    );
  },

  async activate(id: string): Promise<InstructionTemplate> {
    return slApiClient.post<InstructionTemplate>(
      `${SL_BASE}/instruction-templates/${id}/activate`
    );
  },

  async retire(id: string): Promise<InstructionTemplate> {
    return slApiClient.post<InstructionTemplate>(
      `${SL_BASE}/instruction-templates/${id}/retire`
    );
  },

  async duplicate(
    id: string,
    params?: { to_organization_id?: string; new_title?: string }
  ): Promise<InstructionTemplate> {
    return slApiClient.post<InstructionTemplate>(
      `${SL_BASE}/instruction-templates/${id}/duplicate`,
      undefined,
      { params }
    );
  },
};

// ============================================================================
// Patient Instruction Plans
// ============================================================================

export const slPatientPlansService = {
  async getAll(
    patientId: string,
    status?: string
  ): Promise<PaginatedPatientPlans> {
    const params = status ? { status } : undefined;
    return slApiClient.request<PaginatedPatientPlans>(
      `${SL_BASE}/instruction-templates/patients/${patientId}/plans`,
      {
        method: 'GET',
        params,
      }
    );
  },

  async getById(
    patientId: string,
    planId: string
  ): Promise<PatientInstructionPlan> {
    return slApiClient.request<PatientInstructionPlan>(
      `${SL_BASE}/instruction-templates/patients/${patientId}/plans/${planId}`,
      { method: 'GET' }
    );
  },

  async getContent(
    patientId: string,
    planId: string
  ): Promise<PatientPlanContentResponse> {
    return slApiClient.request<PatientPlanContentResponse>(
      `${SL_BASE}/instruction-templates/patients/${patientId}/plans/${planId}/content`,
      { method: 'GET' }
    );
  },

  async assign(
    patientId: string,
    data: PatientPlanAssign
  ): Promise<PatientInstructionPlan> {
    return slApiClient.post<PatientInstructionPlan>(
      `${SL_BASE}/instruction-templates/patients/${patientId}/plans`,
      data
    );
  },

  async update(
    patientId: string,
    planId: string,
    data: PatientPlanUpdate
  ): Promise<PatientInstructionPlan> {
    return slApiClient.patch<PatientInstructionPlan>(
      `${SL_BASE}/instruction-templates/patients/${patientId}/plans/${planId}`,
      data
    );
  },

  async complete(
    patientId: string,
    planId: string
  ): Promise<PatientInstructionPlan> {
    return slApiClient.post<PatientInstructionPlan>(
      `${SL_BASE}/instruction-templates/patients/${patientId}/plans/${planId}/complete`
    );
  },

  async cancel(
    patientId: string,
    planId: string,
    cancelPendingTasks = true
  ): Promise<PatientInstructionPlan> {
    return slApiClient.post<PatientInstructionPlan>(
      `${SL_BASE}/instruction-templates/patients/${patientId}/plans/${planId}/cancel`,
      undefined,
      { params: { cancel_pending_tasks: cancelPendingTasks } }
    );
  },
};

// ============================================================================
// Questionnaire Templates
// ============================================================================

export const slQuestionnairesService = {
  async getAll(
    params?: QuestionnaireQueryParams
  ): Promise<PaginatedQuestionnaires> {
    return slApiClient.request<PaginatedQuestionnaires>(
      `${SL_BASE}/questionnaires`,
      {
        method: 'GET',
        params: params as Record<string, string | number | boolean>,
      }
    );
  },

  async getById(id: string): Promise<QuestionnaireTemplateDetail> {
    return slApiClient.request<QuestionnaireTemplateDetail>(
      `${SL_BASE}/questionnaires/${id}`,
      { method: 'GET' }
    );
  },

  async create(
    data: QuestionnaireCreate
  ): Promise<QuestionnaireTemplateDetail> {
    return slApiClient.post<QuestionnaireTemplateDetail>(
      `${SL_BASE}/questionnaires`,
      data
    );
  },

  async update(
    id: string,
    data: QuestionnaireUpdate
  ): Promise<QuestionnaireTemplateDetail> {
    return slApiClient.patch<QuestionnaireTemplateDetail>(
      `${SL_BASE}/questionnaires/${id}`,
      data
    );
  },

  async activate(id: string): Promise<QuestionnaireTemplate> {
    return slApiClient.post<QuestionnaireTemplate>(
      `${SL_BASE}/questionnaires/${id}/activate`
    );
  },

  async retire(id: string): Promise<QuestionnaireTemplate> {
    return slApiClient.post<QuestionnaireTemplate>(
      `${SL_BASE}/questionnaires/${id}/retire`
    );
  },

  async duplicate(
    id: string,
    params?: {
      to_organization_id?: string;
      new_title?: string;
      new_code?: string;
    }
  ): Promise<QuestionnaireTemplateDetail> {
    return slApiClient.post<QuestionnaireTemplateDetail>(
      `${SL_BASE}/questionnaires/${id}/duplicate`,
      undefined,
      { params }
    );
  },

  async addQuestion(
    questionnaireId: string,
    data: QuestionCreate
  ): Promise<QuestionnaireQuestion> {
    return slApiClient.post<QuestionnaireQuestion>(
      `${SL_BASE}/questionnaires/${questionnaireId}/questions`,
      data
    );
  },

  async updateQuestion(
    questionnaireId: string,
    questionId: string,
    data: QuestionUpdate
  ): Promise<QuestionnaireQuestion> {
    return slApiClient.patch<QuestionnaireQuestion>(
      `${SL_BASE}/questionnaires/${questionnaireId}/questions/${questionId}`,
      data
    );
  },

  async deleteQuestion(
    questionnaireId: string,
    questionId: string
  ): Promise<void> {
    return slApiClient.delete(
      `${SL_BASE}/questionnaires/${questionnaireId}/questions/${questionId}`
    );
  },

  async reorderQuestions(
    questionnaireId: string,
    questions: Array<{ question_id: string; order: number }>
  ): Promise<QuestionnaireTemplateDetail> {
    return slApiClient.post<QuestionnaireTemplateDetail>(
      `${SL_BASE}/questionnaires/${questionnaireId}/questions/reorder`,
      { questions }
    );
  },

  // Patient questionnaire assignment
  async assignToPatient(
    patientId: string,
    questionnaireId: string
  ): Promise<PatientQuestionnaire> {
    return slApiClient.post<PatientQuestionnaire>(
      `${SL_BASE}/questionnaires/patients/${patientId}/assign`,
      { questionnaire_id: questionnaireId }
    );
  },

  async getPatientQuestionnaires(
    patientId: string,
    status?: string
  ): Promise<PatientQuestionnaireList> {
    return slApiClient.request<PatientQuestionnaireList>(
      `${SL_BASE}/questionnaires/patients/${patientId}/assignments`,
      {
        method: 'GET',
        params: status ? { status } : undefined,
      }
    );
  },

  async getResponseDetail(
    responseId: string
  ): Promise<QuestionnaireResponseDetail> {
    return slApiClient.request<QuestionnaireResponseDetail>(
      `${SL_BASE}/questionnaires/responses/${responseId}`,
      {
        method: 'GET',
      }
    );
  },
};

// Combined export for convenience
export const slService = {
  auth: slAuthService,
  dashboard: slDashboardService,
  patients: slPatientsService,
  alerts: slAlertsService,
  clinicians: slCliniciansService,
  organizations: slOrganizationsService,
  valueSets: slValueSetsService,
  clinicalActions: slClinicalActionsService,
  activityTemplates: slActivityTemplatesService,
  instructionTemplates: slInstructionTemplatesService,
  patientPlans: slPatientPlansService,
  questionnaires: slQuestionnairesService,
};
