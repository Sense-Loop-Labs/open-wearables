/**
 * Sense Loop API Types
 * Types for the clinical dashboard extension
 */

// ============================================================================
// Organization
// ============================================================================

export interface Organization {
  id: string;
  name: string;
  slug: string;
  settings: OrganizationSettings | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface OrganizationSettings {
  notification_preferences?: {
    email?: boolean;
    sms?: boolean;
    push?: boolean;
  };
  default_alert_protocol_id?: string;
}

export interface OrganizationCreate {
  name: string;
  slug?: string;
  settings?: OrganizationSettings;
}

export interface OrganizationUpdate {
  name?: string;
  settings?: OrganizationSettings;
  is_active?: boolean;
}

// ============================================================================
// Practitioner
// ============================================================================

export interface Practitioner {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  is_active: boolean;
  email_verified_at: string | null;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PractitionerRole {
  id: string;
  practitioner_id: string;
  organization_id: string;
  role_definition_id: string;
  is_active: boolean;
  invited_at: string | null;
  accepted_at: string | null;
  organization: Organization;
  role_definition: RoleDefinition;
}

export interface PractitionerWithRoles extends Practitioner {
  practitioner_roles: PractitionerRole[];
}

export interface RoleDefinition {
  id: string;
  code: string;
  display_name: string;
  can_manage_patients: boolean;
  can_manage_alerts: boolean;
  can_resolve_alerts: boolean;
  can_acknowledge_alerts: boolean;
  can_manage_care_plans: boolean;
  can_manage_clinicians: boolean;
  can_manage_org_settings: boolean;
  can_view_audit_logs: boolean;
  is_system_role: boolean;
  is_active: boolean;
}

export interface PractitionerInvite {
  id: string;
  organization_id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  expires_at: string;
  invited_by_id: string;
  accepted_at: string | null;
  created_at: string;
}

export interface InviteClinicianRequest {
  email: string;
  first_name: string;
  last_name: string;
  role: string;
}

// ============================================================================
// Patient
// ============================================================================

export interface Patient {
  id: string;
  organization_id: string;
  ow_user_id: string | null;
  first_name: string;
  last_name: string;
  full_name: string;
  date_of_birth: string | null;
  gender: string | null;
  email: string | null;
  phone: string | null;
  mrn: string | null;
  primary_diagnosis: string | null;
  surgery_date: string | null;
  discharge_date: string | null;
  enrollment_status: PatientEnrollmentStatus;
  activation_code: string | null;
  activation_code_expires_at: string | null;
  is_active: boolean;
  monitoring_start_date: string | null;
  monitoring_end_date: string | null;
  days_post_surgery: number | null;
  created_at: string;
  updated_at: string;
  summary?: PatientSummary;
}

export type PatientEnrollmentStatus =
  | 'pending'
  | 'activated'
  | 'active'
  | 'discharged'
  | 'inactive';

export interface PatientSummary {
  id: string;
  patient_id: string;
  overall_status: PatientOverallStatus;
  active_alerts_count: number;
  active_critical_alerts_count: number;
  latest_heart_rate: number | null;
  latest_heart_rate_at: string | null;
  latest_spo2: number | null;
  latest_spo2_at: string | null;
  latest_temperature: number | null;
  latest_temperature_at: string | null;
  latest_hrv: number | null;
  latest_hrv_at: string | null;
  latest_respiratory_rate: number | null;
  latest_respiratory_rate_at: string | null;
  latest_blood_pressure_systolic: number | null;
  latest_blood_pressure_diastolic: number | null;
  latest_blood_pressure_at: string | null;
  latest_recovery_score: number | null;
  latest_recovery_score_at: string | null;
  latest_readiness_score: number | null;
  latest_readiness_score_at: string | null;
  today_steps: number | null;
  today_active_calories: number | null;
  today_active_minutes: number | null;
  last_sleep_duration_minutes: number | null;
  last_sleep_score: number | null;
  last_data_received_at: string | null;
  last_alert_at: string | null;
  last_sync_at: string | null;
  updated_at: string;
}

export type PatientOverallStatus = 'good' | 'warning' | 'critical' | 'no_data';

export interface PatientCreate {
  organization_id: string;
  first_name: string;
  last_name: string;
  date_of_birth?: string;
  gender?: string;
  email?: string;
  phone?: string;
  mrn?: string;
  primary_diagnosis?: string;
  surgery_type_code?: string;
  surgery_date?: string;
  discharge_date?: string;
  alert_protocol_id?: string;
  monitoring_start_date?: string;
  monitoring_end_date?: string;
}

export interface PatientUpdate {
  first_name?: string;
  last_name?: string;
  date_of_birth?: string;
  gender?: string;
  email?: string;
  phone?: string;
  mrn?: string;
  primary_diagnosis?: string;
  surgery_type_code?: string;
  surgery_date?: string;
  discharge_date?: string;
  monitoring_start_date?: string;
  monitoring_end_date?: string;
  is_active?: boolean;
}

export interface PatientQueryParams {
  organization_id?: string;
  is_active?: boolean;
  enrollment_status?: PatientEnrollmentStatus;
  search?: string;
  page?: number;
  page_size?: number;
}

// ============================================================================
// Alert
// ============================================================================

export interface Alert {
  id: string;
  patient_id: string;
  organization_id: string;
  title: string;
  message: string | null;
  severity: AlertSeverity;
  category: AlertCategory;
  status: AlertStatus;
  triggered_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
  escalated_at: string | null;
  acknowledged_by_id: string | null;
  acknowledged_by_name: string | null;
  resolved_by_id: string | null;
  resolved_by_name: string | null;
  resolution_notes: string | null;
  resolution_type: string | null;
  vital_type: string | null;
  observed_value: number | null;
  threshold_breached: string | null;
  threshold_value: number | null;
  days_post_surgery: number | null;
  patient_context: string | null;
  protocol_id: string | null;
  protocol_version: number | null;
  rule_id: string | null;
  patient_name: string | null;
  patient_mrn: string | null;
  created_at: string;
}

export type AlertSeverity = 'critical' | 'warning' | 'info';
export type AlertCategory = 'vital_sign' | 'questionnaire' | 'activity' | 'system';
export type AlertStatus = 'active' | 'acknowledged' | 'resolved' | 'escalated';

export interface AlertQueryParams {
  organization_id?: string;
  patient_id?: string;
  status?: AlertStatus | 'all';
  severity?: AlertSeverity;
  category?: AlertCategory;
  vital_type?: string;
  from_date?: string;
  to_date?: string;
  page?: number;
  page_size?: number;
}

export interface AlertAcknowledgeRequest {
  notes?: string;
}

export interface AlertResolveRequest {
  resolution_type: string;
  resolution_notes?: string;
}

export interface AlertStats {
  active: number;
  acknowledged: number;
  resolved_today: number;
  critical: number;
  warning: number;
}

// ============================================================================
// Dashboard
// ============================================================================

export interface DashboardOverview {
  patients: {
    total: number;
    active: number;
    critical: number;
    warning: number;
  };
  alerts: {
    active: number;
    critical: number;
    acknowledged: number;
    resolved_today: number;
  };
  activity: {
    new_patients_7d: number;
    discharged_7d: number;
    alerts_7d: number;
  };
}

export interface CriticalPatient {
  id: string;
  name: string;
  mrn: string | null;
  status: PatientOverallStatus;
  critical_alerts: number;
  total_alerts: number;
  days_post_surgery: number | null;
  last_data_at: string | null;
}

export interface RecentAlert {
  id: string;
  title: string;
  severity: AlertSeverity;
  status: AlertStatus;
  triggered_at: string;
  patient_id: string;
  patient_name: string | null;
  vital_type: string | null;
  observed_value: number | null;
}

export interface AlertsByDay {
  date: string;
  total: number;
  critical: number;
  warning: number;
}

// ============================================================================
// Auth
// ============================================================================

export interface PractitionerLoginRequest {
  email: string;
  password: string;
}

export interface PractitionerLoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  practitioner_id: string;
  email: string;
  first_name: string;
  last_name: string;
  organizations: PractitionerOrgInfo[];
}

export interface PractitionerOrgInfo {
  id: string;
  name: string;
  role: string;
  role_display_name: string;
}

export interface ForgotPasswordRequest {
  email: string;
}

export interface ResetPasswordRequest {
  token: string;
  password: string;
  password_confirm: string;
}

export interface AcceptInviteRequest {
  invite_id: string;
  secret: string;
  password: string;
  password_confirm: string;
}

// ============================================================================
// Pagination
// ============================================================================

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export type PaginatedPatients = PaginatedResponse<Patient>;
export type PaginatedAlerts = PaginatedResponse<Alert>;
export type PaginatedClinicians = PaginatedResponse<PractitionerWithRoles>;

// ============================================================================
// ValueSet
// ============================================================================

export interface ValueSetItem {
  value: string;
  label: string;
  coding_system: string | null;
  extra_data: Record<string, unknown> | null;
}

export interface ValueSet {
  id: string;
  code: string;
  name: string;
  description: string | null;
  organization_id: string | null;
  item_count: number;
}

// ============================================================================
// Clinical Action
// ============================================================================

export type ClinicalActionType =
  | 'phone'
  | 'in-person'
  | 'order'
  | 'education'
  | 'escalation'
  | 'note';

export interface ClinicalAction {
  id: string;
  patient_id: string;
  organization_id: string;
  practitioner_id: string;
  action_type: ClinicalActionType;
  category_display: string;
  notes: string | null;
  practitioner_name: string;
  related_alert_ids: string[] | null;
  created_at: string;
}

export interface ClinicalActionCreate {
  action_type: ClinicalActionType;
  notes?: string;
  related_alert_ids?: string[];
}

export type PaginatedClinicalActions = PaginatedResponse<ClinicalAction>;
