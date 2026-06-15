/**
 * Sense Loop Patients List Page
 * Clinical-themed patient management page
 */

import { createFileRoute, useSearch, useNavigate } from '@tanstack/react-router';
import { ChevronLeft, ChevronRight, Plus, Search, Users } from 'lucide-react';
import { useState } from 'react';
import { cn } from '@/lib/utils';

import {
  SurgeryDayBadge,
  RiskCategoryBadge,
  VitalCell,
  getRiskLevel,
} from '@/components/sl/dashboard';
import { useCreateSlPatient, useSlPatients } from '@/hooks/api/use-sl-patients';
import { useSurgeryTypes } from '@/hooks/api/use-sl-value-sets';
import { useInstructionTemplates, useAssignPatientPlan } from '@/hooks/api/use-sl-instruction-templates';
import { useQuestionnaires, useAssignQuestionnaire } from '@/hooks/api/use-sl-questionnaires';
import type { PatientCreate, PatientEnrollmentStatus } from '@/lib/api/types/sense-loop';
import { getSlCurrentOrgId } from '@/lib/auth/sl-session';

interface SearchParams {
  page?: number;
  search?: string;
  status?: PatientEnrollmentStatus;
}

export const Route = createFileRoute('/sl/_sl-authenticated/patients/')({
  validateSearch: (search: Record<string, unknown>): SearchParams => ({
    page: Number(search.page) || 1,
    search: (search.search as string) || undefined,
    status: search.status as PatientEnrollmentStatus | undefined,
  }),
  component: SlPatientsPage,
});

function SlPatientsPage() {
  const search = useSearch({ from: '/sl/_sl-authenticated/patients/' });
  const navigate = useNavigate();
  const [searchInput, setSearchInput] = useState(search.search || '');
  const [createDialogOpen, setCreateDialogOpen] = useState(false);

  const { data, isLoading } = useSlPatients({
    page: search.page,
    search: search.search,
    enrollment_status: search.status,
    page_size: 20,
  });

  const patients = data?.items ?? [];
  const totalPages = data?.pages ?? 1;
  const currentPage = data?.page ?? 1;

  const handleSearch = () => {
    navigate({
      to: '/sl/patients',
      search: { search: searchInput || undefined },
    });
  };

  const handleStatusChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const status = e.target.value === 'all' ? undefined : e.target.value as PatientEnrollmentStatus;
    navigate({
      to: '/sl/patients',
      search: { status },
    });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="sl-page-header">
          <h1 className="sl-page-title">Patients</h1>
          <p className="sl-page-subtitle">Manage and monitor patient status</p>
        </div>
        <button
          onClick={() => setCreateDialogOpen(true)}
          className="sl-btn sl-btn-primary"
        >
          <Plus className="w-4 h-4" />
          Add Patient
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="sl-search-input">
          <Search className="icon" />
          <input
            type="text"
            placeholder="Search patients..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSearch();
            }}
          />
        </div>

        <select
          value={search.status || 'all'}
          onChange={handleStatusChange}
          className="sl-select"
        >
          <option value="all">All statuses</option>
          <option value="pending">Pending</option>
          <option value="activated">Activated</option>
          <option value="active">Active</option>
          <option value="discharged">Discharged</option>
        </select>
      </div>

      {/* Table */}
      <div className="sl-table-container">
        {isLoading ? (
          <div className="sl-no-data">
            <div className="sl-spinner" />
            <span className="ml-2">Loading patients...</span>
          </div>
        ) : patients.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <div className="rounded-full bg-[var(--sl-bg-muted)] p-4 mb-4">
              <Users className="h-8 w-8 text-[var(--sl-text-muted)]" />
            </div>
            <p className="text-lg font-medium text-[var(--sl-text-primary)]">No patients found</p>
            <p className="text-sm text-[var(--sl-text-muted)] mt-1">
              {search.search
                ? 'Try adjusting your search terms'
                : 'Add your first patient to get started'}
            </p>
            <button
              onClick={() => setCreateDialogOpen(true)}
              className="sl-btn sl-btn-primary mt-4"
            >
              <Plus className="w-4 h-4" />
              Add Patient
            </button>
          </div>
        ) : (
          <>
            <table className="sl-table">
              <thead>
                <tr>
                  <th>Patient</th>
                  <th>MRN</th>
                  <th>Status</th>
                  <th>Risk</th>
                  <th>Surgery</th>
                  <th className="center">HR</th>
                  <th className="center">SpO2</th>
                  <th>Alerts</th>
                </tr>
              </thead>
              <tbody>
                {patients.map((patient) => {
                  const riskLevel = getRiskLevel(patient.days_post_surgery);

                  return (
                    <tr
                      key={patient.id}
                      onClick={() => navigate({ to: '/sl/patients/$patientId', params: { patientId: patient.id } })}
                      className="cursor-pointer hover:bg-[var(--sl-bg-muted)]"
                    >
                      <td>
                        <span className="font-medium text-[var(--sl-text-primary)]">
                          {patient.full_name}
                        </span>
                        {patient.email && (
                          <p className="text-xs text-[var(--sl-text-muted)]">{patient.email}</p>
                        )}
                      </td>
                      <td>{patient.mrn || '--'}</td>
                      <td>
                        <EnrollmentBadge status={patient.enrollment_status} />
                      </td>
                      <td>
                        <RiskCategoryBadge riskLevel={riskLevel} />
                      </td>
                      <td>
                        <SurgeryDayBadge daysSinceSurgery={patient.days_post_surgery} />
                      </td>
                      <td className="center">
                        <VitalCell
                          type="heart-rate"
                          value={patient.summary?.latest_heart_rate}
                          unit="bpm"
                        />
                      </td>
                      <td className="center">
                        <VitalCell
                          type="spo2"
                          value={patient.summary?.latest_spo2}
                          unit="%"
                        />
                      </td>
                      <td>
                        <AlertsBadges
                          critical={patient.summary?.active_critical_alerts_count ?? 0}
                          warning={(patient.summary?.active_alerts_count ?? 0) - (patient.summary?.active_critical_alerts_count ?? 0)}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {/* Pagination */}
            <div className="flex items-center justify-between px-4 py-3 border-t border-[var(--sl-border)]">
              <p className="text-sm text-[var(--sl-text-muted)]">
                Page {currentPage} of {totalPages} ({data?.total ?? 0} patients)
              </p>
              <div className="flex items-center gap-2">
                <button
                  disabled={currentPage <= 1}
                  onClick={() => navigate({
                    to: '/sl/patients',
                    search: { ...search, page: currentPage - 1 },
                  })}
                  className="sl-btn sl-btn-secondary p-2"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <button
                  disabled={currentPage >= totalPages}
                  onClick={() => navigate({
                    to: '/sl/patients',
                    search: { ...search, page: currentPage + 1 },
                  })}
                  className="sl-btn sl-btn-secondary p-2"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Create Patient Dialog */}
      {createDialogOpen && (
        <CreatePatientDialog
          onClose={() => setCreateDialogOpen(false)}
        />
      )}
    </div>
  );
}

// ============================================================================
// Components
// ============================================================================

function EnrollmentBadge({ status }: { status: PatientEnrollmentStatus }) {
  const variants: Record<PatientEnrollmentStatus, { bg: string; text: string; label: string }> = {
    pending: { bg: 'bg-gray-100', text: 'text-gray-700', label: 'Pending' },
    activated: { bg: 'bg-blue-50', text: 'text-blue-700', label: 'Activated' },
    active: { bg: 'bg-green-50', text: 'text-green-700', label: 'Active' },
    discharged: { bg: 'bg-purple-50', text: 'text-purple-700', label: 'Discharged' },
    inactive: { bg: 'bg-gray-50', text: 'text-gray-500', label: 'Inactive' },
  };

  const { bg, text, label } = variants[status] || variants.pending;

  return (
    <span className={cn('inline-flex px-2 py-0.5 rounded text-xs font-medium', bg, text)}>
      {label}
    </span>
  );
}

function AlertsBadges({ critical, warning }: { critical: number; warning: number }) {
  if (critical === 0 && warning === 0) {
    return <span className="text-[var(--sl-text-muted)] text-sm">None</span>;
  }

  return (
    <div className="flex items-center gap-1">
      {critical > 0 && (
        <span className="sl-alert-badge critical">{critical}</span>
      )}
      {warning > 0 && (
        <span className="sl-alert-badge warning">{warning}</span>
      )}
    </div>
  );
}

function CreatePatientDialog({ onClose }: { onClose: () => void }) {
  const organizationId = getSlCurrentOrgId();
  const createPatient = useCreateSlPatient();
  const assignPlan = useAssignPatientPlan();
  const assignQuestionnaire = useAssignQuestionnaire();
  const { data: surgeryTypes, isLoading: surgeryTypesLoading } = useSurgeryTypes();
  const { data: templatesData, isLoading: templatesLoading } = useInstructionTemplates({
    organization_id: organizationId || undefined,
    include_shared: true,
  });
  const { data: questionnairesData, isLoading: questionnairesLoading } = useQuestionnaires({
    organization_id: organizationId || undefined,
    is_active: true,
  });
  const [formData, setFormData] = useState<Partial<PatientCreate> & { instruction_template_id?: string; questionnaire_id?: string }>({
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    mrn: '',
    date_of_birth: '',
    gender: '',
    primary_diagnosis: '',
    surgery_type_code: '',
    surgery_date: '',
    instruction_template_id: '',
    questionnaire_id: '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const newErrors: Record<string, string> = {};
    if (!formData.first_name?.trim()) newErrors.first_name = 'First name is required';
    if (!formData.last_name?.trim()) newErrors.last_name = 'Last name is required';

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    const orgId = getSlCurrentOrgId();
    if (!orgId) {
      setErrors({ general: 'No organization selected' });
      return;
    }

    try {
      const newPatient = await createPatient.mutateAsync({
        organization_id: orgId,
        first_name: formData.first_name!.trim(),
        last_name: formData.last_name!.trim(),
        email: formData.email?.trim() || undefined,
        phone: formData.phone?.trim() || undefined,
        mrn: formData.mrn?.trim() || undefined,
        date_of_birth: formData.date_of_birth || undefined,
        gender: formData.gender || undefined,
        primary_diagnosis: formData.primary_diagnosis?.trim() || undefined,
        surgery_type_code: formData.surgery_type_code || undefined,
        surgery_date: formData.surgery_date || undefined,
      });

      // Assign instruction template if selected
      if (formData.instruction_template_id) {
        await assignPlan.mutateAsync({
          patientId: newPatient.id,
          data: {
            template_id: formData.instruction_template_id,
            reference_type: formData.surgery_date ? 'surgery_date' : 'assignment_date',
            generate_tasks: true,
          },
        });
      }

      // Assign questionnaire if selected
      if (formData.questionnaire_id) {
        await assignQuestionnaire.mutateAsync({
          patientId: newPatient.id,
          questionnaireId: formData.questionnaire_id,
        });
      }

      onClose();
    } catch {
      // Error handled by hook
    }
  };

  return (
    <div className="sl-modal-overlay" onClick={onClose}>
      <div className="sl-modal" onClick={(e) => e.stopPropagation()}>
        <div className="sl-modal-header">
          <h3 className="sl-modal-title">Add New Patient</h3>
          <button onClick={onClose} className="sl-btn sl-btn-ghost p-1">
            <span className="sr-only">Close</span>
            &times;
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="sl-modal-body">
            <div className="grid grid-cols-2 gap-4">
              <div className="sl-form-group">
                <label className="sl-form-label">
                  First Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={formData.first_name || ''}
                  onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                  className="sl-form-input"
                />
                {errors.first_name && (
                  <p className="text-xs text-red-500">{errors.first_name}</p>
                )}
              </div>

              <div className="sl-form-group">
                <label className="sl-form-label">
                  Last Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={formData.last_name || ''}
                  onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                  className="sl-form-input"
                />
                {errors.last_name && (
                  <p className="text-xs text-red-500">{errors.last_name}</p>
                )}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="sl-form-group">
                <label className="sl-form-label">Email</label>
                <input
                  type="email"
                  value={formData.email || ''}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="sl-form-input"
                />
              </div>

              <div className="sl-form-group">
                <label className="sl-form-label">Phone</label>
                <input
                  type="tel"
                  value={formData.phone || ''}
                  onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  className="sl-form-input"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="sl-form-group">
                <label className="sl-form-label">MRN</label>
                <input
                  type="text"
                  value={formData.mrn || ''}
                  onChange={(e) => setFormData({ ...formData, mrn: e.target.value })}
                  className="sl-form-input"
                />
              </div>

              <div className="sl-form-group">
                <label className="sl-form-label">Date of Birth</label>
                <input
                  type="date"
                  value={formData.date_of_birth || ''}
                  onChange={(e) => setFormData({ ...formData, date_of_birth: e.target.value })}
                  className="sl-form-input"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="sl-form-group">
                <label className="sl-form-label">Gender</label>
                <select
                  value={formData.gender || ''}
                  onChange={(e) => setFormData({ ...formData, gender: e.target.value })}
                  className="sl-select w-full"
                >
                  <option value="">Select gender</option>
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                  <option value="other">Other</option>
                </select>
              </div>

              <div className="sl-form-group">
                <label className="sl-form-label">Surgery Type</label>
                <select
                  value={formData.surgery_type_code || ''}
                  onChange={(e) => setFormData({ ...formData, surgery_type_code: e.target.value })}
                  className="sl-select w-full"
                  disabled={surgeryTypesLoading}
                >
                  <option value="">{surgeryTypesLoading ? 'Loading...' : 'Select surgery type'}</option>
                  {surgeryTypes?.map((type) => (
                    <option key={type.value} value={type.value}>
                      {type.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="sl-form-group">
                <label className="sl-form-label">Surgery Date</label>
                <input
                  type="date"
                  value={formData.surgery_date || ''}
                  onChange={(e) => setFormData({ ...formData, surgery_date: e.target.value })}
                  className="sl-form-input"
                />
              </div>

              <div className="sl-form-group">
                <label className="sl-form-label">Primary Diagnosis</label>
                <input
                  type="text"
                  value={formData.primary_diagnosis || ''}
                  onChange={(e) => setFormData({ ...formData, primary_diagnosis: e.target.value })}
                  className="sl-form-input"
                  placeholder="e.g., PAD"
                />
              </div>
            </div>

            <div className="sl-form-group">
              <label className="sl-form-label">Care Plan Template</label>
              <select
                value={formData.instruction_template_id || ''}
                onChange={(e) => setFormData({ ...formData, instruction_template_id: e.target.value })}
                className="sl-select w-full"
                disabled={templatesLoading}
              >
                <option value="">{templatesLoading ? 'Loading...' : 'Select care plan (optional)'}</option>
                {templatesData?.items?.map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.title}
                  </option>
                ))}
              </select>
            </div>

            <div className="sl-form-group">
              <label className="sl-form-label">Questionnaire</label>
              <select
                value={formData.questionnaire_id || ''}
                onChange={(e) => setFormData({ ...formData, questionnaire_id: e.target.value })}
                className="sl-select w-full"
                disabled={questionnairesLoading}
              >
                <option value="">{questionnairesLoading ? 'Loading...' : 'Select questionnaire (optional)'}</option>
                {questionnairesData?.items?.map((questionnaire) => (
                  <option key={questionnaire.id} value={questionnaire.id}>
                    {questionnaire.title}
                  </option>
                ))}
              </select>
            </div>

            {errors.general && (
              <p className="text-sm text-red-500">{errors.general}</p>
            )}
          </div>

          <div className="sl-modal-footer">
            <button type="button" onClick={onClose} className="sl-btn sl-btn-ghost">
              Cancel
            </button>
            <button
              type="submit"
              className="sl-btn sl-btn-primary"
              disabled={createPatient.isPending}
            >
              {createPatient.isPending ? 'Creating...' : 'Create Patient'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
