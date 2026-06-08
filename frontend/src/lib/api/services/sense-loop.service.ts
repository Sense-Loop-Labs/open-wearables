/**
 * Sense Loop API Service
 * Handles all API calls to the Sense Loop clinical dashboard endpoints
 */

import { slApiClient, slPublicApiClient } from '../sl-client';
import type {
  AcceptInviteRequest,
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
  InviteClinicianRequest,
  Organization,
  OrganizationCreate,
  OrganizationUpdate,
  PaginatedAlerts,
  PaginatedClinicalActions,
  PaginatedClinicians,
  PaginatedPatients,
  Patient,
  PatientCreate,
  PatientQueryParams,
  PatientUpdate,
  PractitionerInvite,
  PractitionerLoginRequest,
  PractitionerLoginResponse,
  PractitionerWithRoles,
  RecentAlert,
  ResetPasswordRequest,
  RoleDefinition,
  ValueSet,
  ValueSetItem,
} from '../types/sense-loop';

const SL_BASE = '/api/v1/sl';

// ============================================================================
// Auth
// ============================================================================

export const slAuthService = {
  async login(credentials: PractitionerLoginRequest): Promise<PractitionerLoginResponse> {
    return slPublicApiClient.post<PractitionerLoginResponse>(
      `${SL_BASE}/auth/practitioner/login`,
      credentials
    );
  },

  async logout(): Promise<void> {
    return slApiClient.post(`${SL_BASE}/auth/practitioner/logout`);
  },

  async forgotPassword(data: ForgotPasswordRequest): Promise<{ success: boolean; message: string }> {
    return slPublicApiClient.post(`${SL_BASE}/auth/practitioner/forgot-password`, data);
  },

  async resetPassword(data: ResetPasswordRequest): Promise<{ success: boolean; message: string }> {
    return slPublicApiClient.post(`${SL_BASE}/auth/practitioner/reset-password`, data);
  },

  async acceptInvite(data: AcceptInviteRequest): Promise<{ success: boolean; message: string }> {
    return slPublicApiClient.post(`${SL_BASE}/clinicians/invites/${data.invite_id}/accept`, {
      secret: data.secret,
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
    const params = organizationId ? { organization_id: organizationId } : undefined;
    return slApiClient.request<DashboardOverview>(`${SL_BASE}/dashboard/overview`, {
      method: 'GET',
      params,
    });
  },

  async getCriticalPatients(
    organizationId?: string,
    limit = 10
  ): Promise<CriticalPatient[]> {
    const params: Record<string, string | number> = { limit };
    if (organizationId) params.organization_id = organizationId;
    return slApiClient.request<CriticalPatient[]>(`${SL_BASE}/dashboard/critical-patients`, {
      method: 'GET',
      params,
    });
  },

  async getRecentAlerts(organizationId?: string, limit = 10): Promise<RecentAlert[]> {
    const params: Record<string, string | number> = { limit };
    if (organizationId) params.organization_id = organizationId;
    return slApiClient.request<RecentAlert[]>(`${SL_BASE}/dashboard/recent-alerts`, {
      method: 'GET',
      params,
    });
  },

  async getAlertsByDay(organizationId?: string, days = 7): Promise<AlertsByDay[]> {
    const params: Record<string, string | number> = { days };
    if (organizationId) params.organization_id = organizationId;
    return slApiClient.request<AlertsByDay[]>(`${SL_BASE}/dashboard/alerts-by-day`, {
      method: 'GET',
      params,
    });
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
    return slApiClient.request<Patient>(`${SL_BASE}/patients/${id}`, { method: 'GET' });
  },

  async create(data: PatientCreate): Promise<Patient> {
    return slApiClient.post<Patient>(`${SL_BASE}/patients`, data);
  },

  async update(id: string, data: PatientUpdate): Promise<Patient> {
    return slApiClient.patch<Patient>(`${SL_BASE}/patients/${id}`, data);
  },

  async generateActivationCode(id: string): Promise<{ activation_code: string; expires_at: string }> {
    return slApiClient.post(`${SL_BASE}/patients/${id}/generate-activation-code`);
  },

  async discharge(id: string): Promise<Patient> {
    return slApiClient.post<Patient>(`${SL_BASE}/patients/${id}/discharge`);
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
    return slApiClient.request<Alert>(`${SL_BASE}/alerts/${id}`, { method: 'GET' });
  },

  async acknowledge(id: string, data?: AlertAcknowledgeRequest): Promise<{ success: boolean }> {
    return slApiClient.post(`${SL_BASE}/alerts/${id}/acknowledge`, data || {});
  },

  async resolve(id: string, data: AlertResolveRequest): Promise<{ success: boolean }> {
    return slApiClient.post(`${SL_BASE}/alerts/${id}/resolve`, data);
  },

  async getStats(organizationId?: string): Promise<AlertStats> {
    const params = organizationId ? { organization_id: organizationId } : undefined;
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
    const params = organizationId ? { organization_id: organizationId } : undefined;
    return slApiClient.request<PaginatedClinicians>(`${SL_BASE}/clinicians`, {
      method: 'GET',
      params,
    });
  },

  async getById(id: string): Promise<PractitionerWithRoles> {
    return slApiClient.request<PractitionerWithRoles>(`${SL_BASE}/clinicians/${id}`, {
      method: 'GET',
    });
  },

  async invite(
    organizationId: string,
    data: InviteClinicianRequest
  ): Promise<PractitionerInvite> {
    return slApiClient.post<PractitionerInvite>(`${SL_BASE}/clinicians/invite`, {
      ...data,
      organization_id: organizationId,
    });
  },

  async deactivate(id: string): Promise<{ success: boolean }> {
    return slApiClient.post(`${SL_BASE}/clinicians/${id}/deactivate`);
  },

  async getRoles(): Promise<RoleDefinition[]> {
    return slApiClient.request<RoleDefinition[]>(`${SL_BASE}/roles`, { method: 'GET' });
  },
};

// ============================================================================
// Organizations
// ============================================================================

export const slOrganizationsService = {
  async getAll(): Promise<Organization[]> {
    return slApiClient.request<Organization[]>(`${SL_BASE}/organizations`, { method: 'GET' });
  },

  async getById(id: string): Promise<Organization> {
    return slApiClient.request<Organization>(`${SL_BASE}/organizations/${id}`, { method: 'GET' });
  },

  async create(data: OrganizationCreate): Promise<Organization> {
    return slApiClient.post<Organization>(`${SL_BASE}/organizations`, data);
  },

  async update(id: string, data: OrganizationUpdate): Promise<Organization> {
    return slApiClient.patch<Organization>(`${SL_BASE}/organizations/${id}`, data);
  },
};

// ============================================================================
// Value Sets
// ============================================================================

export const slValueSetsService = {
  async getAll(organizationId?: string): Promise<ValueSet[]> {
    const params = organizationId ? { organization_id: organizationId } : undefined;
    return slApiClient.request<ValueSet[]>(`${SL_BASE}/value-sets`, {
      method: 'GET',
      params,
    });
  },

  async getByCode(code: string, organizationId?: string): Promise<ValueSet & { items: ValueSetItem[] }> {
    const params = organizationId ? { organization_id: organizationId } : undefined;
    return slApiClient.request<ValueSet & { items: ValueSetItem[] }>(`${SL_BASE}/value-sets/${code}`, {
      method: 'GET',
      params,
    });
  },

  async getItems(code: string, organizationId?: string): Promise<ValueSetItem[]> {
    const params = organizationId ? { organization_id: organizationId } : undefined;
    return slApiClient.request<ValueSetItem[]>(`${SL_BASE}/value-sets/${code}/items`, {
      method: 'GET',
      params,
    });
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

  async create(patientId: string, data: ClinicalActionCreate): Promise<ClinicalAction> {
    return slApiClient.post<ClinicalAction>(
      `${SL_BASE}/patients/${patientId}/actions`,
      data
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
};
