/**
 * Sense Loop Patient Detail Page
 * Matches the old Medplum PatientDetailPage design with SL theme
 */

import { createFileRoute, Link } from '@tanstack/react-router';
import {
  Activity,
  ArrowLeft,
  Bell,
  Check,
  CheckCircle2,
  Copy,
  Edit2,
  Loader2,
  Smartphone,
  User,
} from 'lucide-react';
import { useState, useEffect } from 'react';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  useAcknowledgeAlert,
  useResolveAlert,
  useSlAlerts,
} from '@/hooks/api/use-sl-alerts';
import {
  useDischargePatient,
  useGenerateActivationCode,
  useSlPatient,
  useSlPatientVitals,
  useUpdateSlPatient,
} from '@/hooks/api/use-sl-patients';
import {
  useInstructionTemplates,
  usePatientPlans,
  useAssignPatientPlan,
  useCancelPatientPlan,
} from '@/hooks/api/use-sl-instruction-templates';
import {
  useQuestionnaires,
  usePatientQuestionnaires,
  useAssignQuestionnaire,
  useQuestionnaireResponse,
} from '@/hooks/api/use-sl-questionnaires';
import type {
  Alert,
  Patient,
  PatientSummary,
  PatientUpdate,
  VitalReading,
  VitalType,
  QuestionnaireAnswer,
} from '@/lib/api/types/sense-loop';
import { getSlCurrentOrgId } from '@/lib/auth/sl-session';
import { toast } from 'sonner';

export const Route = createFileRoute(
  '/sl/_sl-authenticated/patients/$patientId/'
)({
  component: SlPatientDetailPage,
});

function SlPatientDetailPage() {
  const { patientId } = Route.useParams();
  const { data: patient, isLoading } = useSlPatient(patientId);
  const { data: alerts } = useSlAlerts({
    patient_id: patientId,
    page_size: 50,
  });

  const [dischargeDialogOpen, setDischargeDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [acknowledgeDialog, setAcknowledgeDialog] = useState<Alert | null>(
    null
  );
  const [resolveDialog, setResolveDialog] = useState<Alert | null>(null);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-8 w-8 animate-spin text-[var(--sl-text-muted)]" />
      </div>
    );
  }

  if (!patient) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <User className="h-12 w-12 text-[var(--sl-text-muted)]" />
        <p className="text-[var(--sl-text-muted)]">Patient not found</p>
        <Link to="/sl/patients">
          <Button variant="outline" className="border-[var(--sl-border)]">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Patients
          </Button>
        </Link>
      </div>
    );
  }

  const activeAlerts =
    alerts?.items?.filter((a) => a.status === 'active') ?? [];

  return (
    <div className="space-y-6">
      {/* Header - matches old Medplum design */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-[var(--sl-text-primary)]">
          {patient.full_name}
        </h1>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            onClick={() => setEditDialogOpen(true)}
            className="border-[var(--sl-brand)] text-[var(--sl-brand)] hover:bg-[var(--sl-brand)] hover:text-white"
          >
            Edit Patient
          </Button>
          <Link to="/sl/patients">
            <Button
              variant="outline"
              className="border-[var(--sl-border)] text-[var(--sl-text-secondary)]"
            >
              Back to Patients
            </Button>
          </Link>
        </div>
      </div>

      {/* Activation Code Alert - shown when pending */}
      {patient.enrollment_status === 'pending' && patient.activation_code && (
        <ActivationCodeAlert patient={patient} />
      )}

      {/* Patient Info Cards - Two columns like old Medplum */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Patient Information Card */}
        <div className="sl-card">
          <div className="sl-card-body">
            <h3 className="text-lg font-medium text-[var(--sl-text-primary)] mb-4">
              Patient Information
            </h3>
            <div className="space-y-3">
              <InfoRow
                label="Date of Birth"
                value={
                  patient.date_of_birth
                    ? formatDate(patient.date_of_birth)
                    : null
                }
              />
              <InfoRow
                label="Gender"
                value={patient.gender ? capitalizeFirst(patient.gender) : null}
              />
              <InfoRow label="Phone" value={patient.phone} />
              <InfoRow label="Email" value={patient.email} />
              <div className="flex justify-between items-center">
                <span className="text-sm text-[var(--sl-text-muted)]">
                  Enrollment Status
                </span>
                <EnrollmentBadge status={patient.enrollment_status} />
              </div>
            </div>
          </div>
        </div>

        {/* Surgery Information Card */}
        <div className="sl-card">
          <div className="sl-card-body">
            <h3 className="text-lg font-medium text-[var(--sl-text-primary)] mb-4">
              Surgery Information
            </h3>
            <div className="space-y-3">
              <InfoRow
                label="Surgery Date"
                value={
                  patient.surgery_date ? formatDate(patient.surgery_date) : null
                }
              />
              <InfoRow
                label="Primary Diagnosis"
                value={patient.primary_diagnosis}
              />
              <InfoRow
                label="Days Post-Surgery"
                value={patient.days_post_surgery?.toString()}
              />
              <InfoRow label="MRN" value={patient.mrn} />
              <InfoRow
                label="Discharge Date"
                value={
                  patient.discharge_date
                    ? formatDate(patient.discharge_date)
                    : null
                }
              />
            </div>
          </div>
        </div>
      </div>

      {/* Tabs - like old Medplum */}
      <Tabs defaultValue="vitals" className="space-y-4">
        <TabsList className="bg-[var(--sl-bg-muted)] border border-[var(--sl-border)]">
          <TabsTrigger
            value="vitals"
            className="data-[state=active]:bg-white data-[state=active]:text-[var(--sl-text-primary)]"
          >
            Vitals & Observations
          </TabsTrigger>
          <TabsTrigger
            value="alerts"
            className="data-[state=active]:bg-white data-[state=active]:text-[var(--sl-text-primary)]"
          >
            Alerts
            {activeAlerts.length > 0 && (
              <span className="ml-2 px-2 py-0.5 text-xs rounded-full bg-red-100 text-red-600">
                {activeAlerts.length}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger
            value="responses"
            className="data-[state=active]:bg-white data-[state=active]:text-[var(--sl-text-primary)]"
          >
            Responses
          </TabsTrigger>
          <TabsTrigger
            value="devices"
            className="data-[state=active]:bg-white data-[state=active]:text-[var(--sl-text-primary)]"
          >
            Connected Devices
          </TabsTrigger>
          <TabsTrigger
            value="care-plan"
            className="data-[state=active]:bg-white data-[state=active]:text-[var(--sl-text-primary)]"
          >
            Care Plan
          </TabsTrigger>
        </TabsList>

        <TabsContent value="vitals">
          <VitalsSection patientId={patient.id} summary={patient.summary} />
        </TabsContent>

        <TabsContent value="alerts">
          <AlertsSection
            alerts={alerts?.items ?? []}
            onAcknowledge={setAcknowledgeDialog}
            onResolve={setResolveDialog}
          />
        </TabsContent>

        <TabsContent value="responses">
          <ResponsesSection patientId={patientId} />
        </TabsContent>

        <TabsContent value="devices">
          <DevicesSection />
        </TabsContent>

        <TabsContent value="care-plan">
          <CarePlanSection patientId={patientId} />
        </TabsContent>
      </Tabs>

      {/* Dialogs */}
      <DischargeDialog
        patient={patient}
        open={dischargeDialogOpen}
        onClose={() => setDischargeDialogOpen(false)}
      />

      <EditPatientDialog
        patient={patient}
        open={editDialogOpen}
        onClose={() => setEditDialogOpen(false)}
      />

      <AcknowledgeAlertDialog
        alert={acknowledgeDialog}
        onClose={() => setAcknowledgeDialog(null)}
      />

      <ResolveAlertDialog
        alert={resolveDialog}
        onClose={() => setResolveDialog(null)}
      />
    </div>
  );
}

// ============================================================================
// Components
// ============================================================================

function ActivationCodeAlert({ patient }: { patient: Patient }) {
  const [copied, setCopied] = useState(false);
  const { mutate: generateCode, isPending } = useGenerateActivationCode();

  const handleCopy = async () => {
    if (patient.activation_code) {
      await navigator.clipboard.writeText(patient.activation_code);
      setCopied(true);
      toast.success('Activation code copied to clipboard');
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const isExpired = patient.activation_code_expires_at
    ? new Date(patient.activation_code_expires_at) < new Date()
    : false;

  return (
    <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
      <h4 className="text-sm font-medium text-blue-800 mb-2">
        {isExpired ? 'Activation Code Expired' : 'Patient Enrollment Pending'}
      </h4>
      <p className="text-sm text-blue-700 mb-3">
        {isExpired
          ? 'The activation code has expired. Generate a new code to continue enrollment.'
          : 'Share this activation code with the patient to complete enrollment in the Sense Loop mobile app:'}
      </p>
      <div className="flex items-center gap-3">
        <div
          className={`px-4 py-2 rounded border-2 border-dashed ${isExpired ? 'border-red-300 bg-red-50' : 'border-blue-300 bg-blue-100'}`}
        >
          <span
            className={`text-xl font-bold font-mono tracking-wider ${isExpired ? 'text-red-600' : 'text-blue-800'}`}
          >
            {patient.activation_code}
          </span>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleCopy}
          disabled={isExpired}
          className={
            copied
              ? 'border-teal-500 text-teal-600'
              : 'border-blue-500 text-blue-600'
          }
        >
          {copied ? (
            <>
              <Check className="h-4 w-4 mr-1" />
              Copied
            </>
          ) : (
            <>
              <Copy className="h-4 w-4 mr-1" />
              Copy
            </>
          )}
        </Button>
        {isExpired && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => generateCode(patient.id)}
            disabled={isPending}
            className="border-blue-500 text-blue-600"
          >
            {isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              'Generate New Code'
            )}
          </Button>
        )}
      </div>
    </div>
  );
}

function EnrollmentBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    pending: 'bg-yellow-100 text-yellow-700',
    activated: 'bg-blue-100 text-blue-700',
    active: 'bg-green-100 text-green-700',
    discharged: 'bg-purple-100 text-purple-700',
    blocked: 'bg-red-100 text-red-700',
  };

  return (
    <span
      className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${colors[status] || colors.pending}`}
    >
      {capitalizeFirst(status)}
    </span>
  );
}

function InfoRow({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="flex justify-between">
      <span className="text-sm text-[var(--sl-text-muted)]">{label}</span>
      <span className="text-sm font-medium text-[var(--sl-text-primary)]">
        {value || '-'}
      </span>
    </div>
  );
}

const VITAL_TYPE_LABELS: Record<VitalType, string> = {
  heart_rate: 'Heart Rate',
  blood_pressure: 'Blood Pressure',
  spo2: 'SpO2',
  temperature: 'Temperature',
  respiratory_rate: 'Respiratory Rate',
  hrv: 'HRV',
};

function VitalsSection({
  patientId,
  summary,
}: {
  patientId: string;
  summary?: PatientSummary;
}) {
  const [activeTab, setActiveTab] = useState<'all' | VitalType>('all');
  const [page, setPage] = useState(1);

  // Fetch vitals based on active tab
  const vitalsParams = {
    vital_type: activeTab === 'all' ? undefined : activeTab,
    aggregate_hr: activeTab === 'all', // Aggregate HR in "all" view
    page,
    page_size: 50,
  };

  const { data: vitalsData, isLoading } = useSlPatientVitals(
    patientId,
    vitalsParams
  );

  // Reset page when tab changes
  useEffect(() => {
    setPage(1);
  }, [activeTab]);

  const formatVitalValue = (reading: VitalReading): string => {
    if (
      reading.vital_type === 'blood_pressure' &&
      reading.value_secondary !== null
    ) {
      return `${reading.value}/${reading.value_secondary}`;
    }
    return String(reading.value);
  };

  const renderVitalsTable = (readings: VitalReading[]) => {
    if (readings.length === 0) {
      return (
        <div className="sl-card">
          <div className="sl-no-data">
            <Activity className="h-12 w-12 mx-auto text-[var(--sl-text-muted)] mb-4" />
            <p className="text-[var(--sl-text-muted)]">
              No readings recorded yet.
            </p>
          </div>
        </div>
      );
    }

    return (
      <div className="sl-table-container">
        <table className="sl-table">
          <thead>
            <tr>
              <th>Type</th>
              <th>Value</th>
              <th>Date & Time</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {readings.map((reading, idx) => (
              <tr key={idx}>
                <td className="text-[var(--sl-text-primary)] font-medium">
                  {VITAL_TYPE_LABELS[reading.vital_type]}
                  {reading.is_aggregated && (
                    <span className="ml-2 text-xs text-[var(--sl-text-muted)]">
                      (hourly avg)
                    </span>
                  )}
                </td>
                <td>
                  {formatVitalValue(reading)} {reading.unit}
                </td>
                <td>{formatDateTime(reading.recorded_at)}</td>
                <td className="text-[var(--sl-text-muted)] text-sm">
                  {reading.source || '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* Pagination */}
        {vitalsData && vitalsData.pages > 1 && (
          <div className="flex items-center justify-between mt-4 px-2">
            <span className="text-sm text-[var(--sl-text-muted)]">
              Page {vitalsData.page} of {vitalsData.pages} ({vitalsData.total}{' '}
              readings)
            </span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  setPage((p) => Math.min(vitalsData.pages, p + 1))
                }
                disabled={page === vitalsData.pages}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </div>
    );
  };

  // If no summary and no vitals data, show empty state
  if (!summary && !vitalsData?.items?.length && !isLoading) {
    return (
      <div className="sl-card">
        <div className="sl-no-data">
          <Activity className="h-12 w-12 mx-auto text-[var(--sl-text-muted)] mb-4" />
          <p className="text-[var(--sl-text-muted)]">
            No observations recorded yet.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Sub-tabs for vital types */}
      <div className="flex flex-wrap gap-2 border-b border-gray-200 pb-2">
        <button
          onClick={() => setActiveTab('all')}
          className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
            activeTab === 'all'
              ? 'bg-blue-600 text-white'
              : 'text-gray-500 hover:text-gray-900 hover:bg-gray-100'
          }`}
        >
          All
        </button>
        {(Object.keys(VITAL_TYPE_LABELS) as VitalType[]).map((vt) => (
          <button
            key={vt}
            onClick={() => setActiveTab(vt)}
            className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
              activeTab === vt
                ? 'bg-blue-600 text-white'
                : 'text-gray-500 hover:text-gray-900 hover:bg-gray-100'
            }`}
          >
            {VITAL_TYPE_LABELS[vt]}
          </button>
        ))}
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-[var(--sl-text-muted)]" />
        </div>
      )}

      {/* Vitals table */}
      {!isLoading && vitalsData && renderVitalsTable(vitalsData.items)}
    </div>
  );
}

interface AlertsSectionProps {
  alerts: Alert[];
  onAcknowledge: (alert: Alert) => void;
  onResolve: (alert: Alert) => void;
}

function AlertsSection({
  alerts,
  onAcknowledge,
  onResolve,
}: AlertsSectionProps) {
  if (alerts.length === 0) {
    return (
      <div className="sl-card">
        <div className="sl-no-data">
          <Bell className="h-12 w-12 mx-auto text-[var(--sl-text-muted)] mb-4" />
          <p className="text-[var(--sl-text-muted)]">
            No alerts for this patient.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="sl-table-container">
      <table className="sl-table">
        <thead>
          <tr>
            <th>Alert</th>
            <th>Severity</th>
            <th>When</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {alerts.map((alert) => (
            <tr key={alert.id}>
              <td className="text-[var(--sl-text-primary)] font-medium">
                {alert.title}
              </td>
              <td>
                <SeverityBadge severity={alert.severity} />
              </td>
              <td>{formatTimeAgo(alert.triggered_at)}</td>
              <td>
                <StatusBadge status={alert.status} />
              </td>
              <td>
                <div className="flex items-center gap-2">
                  {alert.status === 'active' && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onAcknowledge(alert)}
                      className="border-blue-500 text-blue-600 hover:bg-blue-50"
                    >
                      <Check className="h-3 w-3" />
                    </Button>
                  )}
                  {(alert.status === 'active' ||
                    alert.status === 'acknowledged') && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onResolve(alert)}
                      className="border-green-500 text-green-600 hover:bg-green-50"
                    >
                      <CheckCircle2 className="h-3 w-3" />
                    </Button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SeverityBadge({ severity }: { severity: string }) {
  const colors: Record<string, string> = {
    critical: 'bg-red-100 text-red-700',
    high: 'bg-orange-100 text-orange-700',
    warning: 'bg-yellow-100 text-yellow-700',
    moderate: 'bg-yellow-100 text-yellow-700',
    low: 'bg-blue-100 text-blue-700',
    info: 'bg-blue-100 text-blue-700',
  };

  return (
    <span
      className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${colors[severity] || colors.moderate}`}
    >
      {capitalizeFirst(severity)}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    active: 'bg-red-100 text-red-700',
    acknowledged: 'bg-blue-100 text-blue-700',
    resolved: 'bg-gray-100 text-gray-600',
  };

  return (
    <span
      className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${colors[status] || colors.active}`}
    >
      {capitalizeFirst(status)}
    </span>
  );
}

function ResponsesSection({ patientId }: { patientId: string }) {
  const { data: responses, isLoading } = usePatientQuestionnaires(patientId);
  const [selectedResponseId, setSelectedResponseId] = useState<string | null>(
    null
  );

  if (isLoading) {
    return (
      <div className="sl-card">
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-[var(--sl-text-muted)]" />
        </div>
      </div>
    );
  }

  if (!responses?.items?.length) {
    return (
      <div className="sl-card">
        <div className="sl-no-data">
          <Activity className="h-12 w-12 mx-auto text-[var(--sl-text-muted)] mb-4" />
          <p className="text-[var(--sl-text-muted)]">
            No questionnaire responses yet.
          </p>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="sl-card">
        <div className="divide-y divide-[var(--sl-border)]">
          {responses.items.map((response) => (
            <button
              key={response.id}
              onClick={() => setSelectedResponseId(response.id)}
              className="w-full px-4 py-3 flex items-center justify-between hover:bg-[var(--sl-surface-secondary)] transition-colors text-left"
            >
              <div className="flex-1">
                <p className="font-medium text-[var(--sl-text-primary)]">
                  {response.questionnaire_title}
                </p>
                <p className="text-sm text-[var(--sl-text-muted)]">
                  {new Date(response.created_at).toLocaleDateString('en-US', {
                    month: 'short',
                    day: 'numeric',
                    year: 'numeric',
                    hour: 'numeric',
                    minute: '2-digit',
                  })}
                </p>
              </div>
              <ResponseStatusBadge status={response.status} />
            </button>
          ))}
        </div>
      </div>

      <ResponseDetailDialog
        responseId={selectedResponseId}
        open={!!selectedResponseId}
        onClose={() => setSelectedResponseId(null)}
      />
    </>
  );
}

function ResponseStatusBadge({ status }: { status: string }) {
  const config: Record<string, { label: string; className: string }> = {
    completed: {
      label: 'Completed',
      className:
        'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
    },
    in_progress: {
      label: 'In Progress',
      className:
        'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
    },
    pending: {
      label: 'Pending',
      className:
        'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
    },
  };

  const { label, className } = config[status] || {
    label: status,
    className: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-400',
  };

  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${className}`}>
      {label}
    </span>
  );
}

function ResponseDetailDialog({
  responseId,
  open,
  onClose,
}: {
  responseId: string | null;
  open: boolean;
  onClose: () => void;
}) {
  const { data: response, isLoading } = useQuestionnaireResponse(
    responseId ?? undefined
  );

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {response?.questionnaire_title || 'Questionnaire Response'}
          </DialogTitle>
          {response?.questionnaire_description && (
            <DialogDescription>
              {response.questionnaire_description}
            </DialogDescription>
          )}
        </DialogHeader>

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-[var(--sl-text-muted)]" />
          </div>
        ) : response ? (
          <div className="space-y-6">
            {/* Summary - only show score info if available */}
            {(response.total_score !== null ||
              response.score_interpretation ||
              response.completed_at) && (
              <div className="flex items-center gap-4 p-3 bg-[var(--sl-surface-secondary)] rounded-lg">
                {response.total_score !== null &&
                  response.total_score !== undefined && (
                    <div className="flex-1">
                      <p className="text-sm text-[var(--sl-text-muted)]">
                        Score
                      </p>
                      <p className="font-medium">{response.total_score}</p>
                    </div>
                  )}
                {response.score_interpretation && (
                  <div className="flex-1">
                    <p className="text-sm text-[var(--sl-text-muted)]">
                      Interpretation
                    </p>
                    <p className="font-medium capitalize">
                      {response.score_interpretation}
                    </p>
                  </div>
                )}
                {response.completed_at && (
                  <div className="flex-1">
                    <p className="text-sm text-[var(--sl-text-muted)]">
                      Completed
                    </p>
                    <p className="font-medium">
                      {new Date(response.completed_at).toLocaleDateString(
                        'en-US',
                        {
                          month: 'short',
                          day: 'numeric',
                          year: 'numeric',
                        }
                      )}
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Questions with Answers */}
            {response.answers.length > 0 ? (
              <div className="space-y-6">
                {response.answers.map((answer, index) => (
                  <QuestionWithAnswer
                    key={answer.id}
                    answer={answer}
                    index={index}
                  />
                ))}
              </div>
            ) : (
              <p className="text-[var(--sl-text-muted)] text-center py-4">
                No questions in this questionnaire.
              </p>
            )}
          </div>
        ) : null}

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function QuestionWithAnswer({
  answer,
  index,
}: {
  answer: QuestionnaireAnswer;
  index: number;
}) {
  const questionType = answer.question_type;

  // Get selected value(s) for highlighting
  const getSelectedValue = (): string | string[] | null => {
    if (answer.value_text) return answer.value_text;
    if (answer.value_boolean !== null && answer.value_boolean !== undefined) {
      return answer.value_boolean ? 'true' : 'false';
    }
    if (
      answer.value_json?.selected &&
      Array.isArray(answer.value_json.selected)
    ) {
      return answer.value_json.selected as string[];
    }
    return null;
  };

  const selectedValue = getSelectedValue();
  const isSelected = (value: string): boolean => {
    if (selectedValue === null) return false;
    if (Array.isArray(selectedValue)) return selectedValue.includes(value);
    return selectedValue === value;
  };

  return (
    <div className="space-y-3">
      <div>
        <p className="font-medium text-[var(--sl-text-primary)]">
          {index + 1}. {answer.question_text}
          {answer.question_is_required && (
            <span className="text-red-500 ml-1">*</span>
          )}
        </p>
        {answer.question_help_text && (
          <p className="text-sm text-[var(--sl-text-muted)] mt-1">
            {answer.question_help_text}
          </p>
        )}
      </div>

      {answer.skipped ? (
        <p className="text-sm italic text-[var(--sl-text-muted)]">Skipped</p>
      ) : (
        <>
          {/* Boolean question */}
          {questionType === 'boolean' && (
            <div className="flex gap-3">
              <div
                className={`flex-1 py-3 px-4 border rounded-lg text-center transition-colors ${
                  isSelected('true')
                    ? 'border-green-500 bg-green-50 dark:bg-green-950'
                    : 'border-[var(--sl-border)] text-[var(--sl-text-primary)]'
                }`}
              >
                {isSelected('true') && (
                  <Check className="inline h-4 w-4 mr-2 text-green-600" />
                )}
                <span
                  className={
                    isSelected('true')
                      ? 'text-green-700 dark:text-green-400'
                      : ''
                  }
                >
                  Yes
                </span>
              </div>
              <div
                className={`flex-1 py-3 px-4 border rounded-lg text-center transition-colors ${
                  isSelected('false')
                    ? 'border-green-500 bg-green-50 dark:bg-green-950'
                    : 'border-[var(--sl-border)] text-[var(--sl-text-primary)]'
                }`}
              >
                {isSelected('false') && (
                  <Check className="inline h-4 w-4 mr-2 text-green-600" />
                )}
                <span
                  className={
                    isSelected('false')
                      ? 'text-green-700 dark:text-green-400'
                      : ''
                  }
                >
                  No
                </span>
              </div>
            </div>
          )}

          {/* Single/Multi choice questions */}
          {(questionType === 'single_choice' ||
            questionType === 'multi_choice') &&
            answer.question_options && (
              <div className="space-y-2">
                {answer.question_options.map((option, idx) => {
                  const optionSelected = isSelected(option.value);
                  return (
                    <div
                      key={idx}
                      className={`flex items-center gap-3 p-3 border rounded-lg transition-colors ${
                        optionSelected
                          ? 'border-green-500 bg-green-50 dark:bg-green-950'
                          : 'border-[var(--sl-border)]'
                      }`}
                    >
                      <div
                        className={`h-4 w-4 flex-shrink-0 flex items-center justify-center border ${
                          questionType === 'multi_choice'
                            ? 'rounded'
                            : 'rounded-full'
                        } ${
                          optionSelected
                            ? 'border-green-500 bg-green-500'
                            : 'border-gray-300 dark:border-gray-600'
                        }`}
                      >
                        {optionSelected && (
                          <Check className="h-3 w-3 text-white" />
                        )}
                      </div>
                      <span
                        className={
                          optionSelected
                            ? 'text-green-700 dark:text-green-400'
                            : 'text-[var(--sl-text-primary)]'
                        }
                      >
                        {option.label || option.value}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}

          {/* Scale question */}
          {questionType === 'scale' &&
            answer.value_number !== null &&
            answer.value_number !== undefined && (
              <div className="flex justify-center">
                <span className="px-4 py-2 bg-green-50 dark:bg-green-950 border border-green-500 rounded-lg text-green-700 dark:text-green-400 font-medium">
                  {answer.value_number}
                </span>
              </div>
            )}

          {/* Number question */}
          {questionType === 'number' &&
            answer.value_number !== null &&
            answer.value_number !== undefined && (
              <div className="p-3 border border-[var(--sl-border)] rounded-lg bg-[var(--sl-surface-secondary)]">
                <span className="font-medium text-[var(--sl-text-primary)]">
                  {answer.value_number}
                </span>
              </div>
            )}

          {/* Text question */}
          {questionType === 'text' && answer.value_text && (
            <div className="p-3 border border-[var(--sl-border)] rounded-lg bg-[var(--sl-surface-secondary)]">
              <p className="text-[var(--sl-text-primary)] whitespace-pre-wrap">
                {answer.value_text}
              </p>
            </div>
          )}

          {/* No answer provided */}
          {!answer.value_text &&
            answer.value_number === null &&
            answer.value_boolean === null &&
            !answer.value_json && (
              <p className="text-sm italic text-[var(--sl-text-muted)]">
                No answer provided
              </p>
            )}
        </>
      )}
    </div>
  );
}

function DevicesSection() {
  return (
    <div className="sl-card">
      <div className="sl-no-data">
        <Smartphone className="h-12 w-12 mx-auto text-[var(--sl-text-muted)] mb-4" />
        <p className="text-[var(--sl-text-muted)]">No connected devices.</p>
      </div>
    </div>
  );
}

function CarePlanSection({ patientId }: { patientId: string }) {
  const { data: plans, isLoading: plansLoading } = usePatientPlans(patientId);
  const { data: questionnaires, isLoading: questionnairesLoading } =
    usePatientQuestionnaires(patientId);

  const isLoading = plansLoading || questionnairesLoading;

  // Filter to show active instructions, all questionnaires
  const activeInstructions =
    plans?.items?.filter((p) => p.status === 'active') ?? [];
  const assignedQuestionnaires = questionnaires?.items ?? [];

  if (isLoading) {
    return (
      <div className="sl-card">
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-[var(--sl-text-muted)]" />
        </div>
      </div>
    );
  }

  const hasNoAssignments =
    activeInstructions.length === 0 && assignedQuestionnaires.length === 0;

  if (hasNoAssignments) {
    return (
      <div className="sl-card">
        <div className="sl-no-data">
          <Activity className="h-12 w-12 mx-auto text-[var(--sl-text-muted)] mb-4" />
          <p className="text-[var(--sl-text-muted)]">
            No active care plan assignments.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Assigned Instructions */}
      {activeInstructions.length > 0 && (
        <div className="sl-card">
          <div className="sl-card-body">
            <h3 className="text-lg font-medium text-[var(--sl-text-primary)] mb-4">
              Assigned Instructions
            </h3>
            <div className="divide-y divide-[var(--sl-border)]">
              {activeInstructions.map((plan) => (
                <div key={plan.id} className="py-3 first:pt-0 last:pb-0">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-[var(--sl-text-primary)]">
                        {plan.template_title ||
                          plan.template_name ||
                          'Untitled'}
                      </p>
                      <p className="text-sm text-[var(--sl-text-muted)]">
                        Started{' '}
                        {new Date(plan.effective_start).toLocaleDateString(
                          'en-US',
                          {
                            month: 'short',
                            day: 'numeric',
                            year: 'numeric',
                          }
                        )}
                        {plan.effective_end && (
                          <>
                            {' '}
                            · Ends{' '}
                            {new Date(plan.effective_end).toLocaleDateString(
                              'en-US',
                              {
                                month: 'short',
                                day: 'numeric',
                                year: 'numeric',
                              }
                            )}
                          </>
                        )}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {plan.status === 'active' && (
                        <Link
                          to="/sl/patients/$patientId/plans/$planId/edit"
                          params={{ patientId, planId: plan.id }}
                        >
                          <Button
                            variant="outline"
                            size="sm"
                            className="border-[var(--sl-brand)] text-[var(--sl-brand)] hover:bg-[var(--sl-brand)] hover:text-white"
                          >
                            <Edit2 className="h-3 w-3 mr-1" />
                            Edit
                          </Button>
                        </Link>
                      )}
                      <PlanStatusBadge status={plan.status} />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Assigned Questionnaires */}
      {assignedQuestionnaires.length > 0 && (
        <div className="sl-card">
          <div className="sl-card-body">
            <h3 className="text-lg font-medium text-[var(--sl-text-primary)] mb-4">
              Assigned Questionnaires
            </h3>
            <div className="divide-y divide-[var(--sl-border)]">
              {assignedQuestionnaires.map((q) => (
                <div key={q.id} className="py-3 first:pt-0 last:pb-0">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-[var(--sl-text-primary)]">
                        {q.questionnaire_title}
                      </p>
                      <p className="text-sm text-[var(--sl-text-muted)]">
                        Assigned{' '}
                        {new Date(q.created_at).toLocaleDateString('en-US', {
                          month: 'short',
                          day: 'numeric',
                          year: 'numeric',
                        })}
                        {q.due_at && (
                          <>
                            {' '}
                            · Due{' '}
                            {new Date(q.due_at).toLocaleDateString('en-US', {
                              month: 'short',
                              day: 'numeric',
                              year: 'numeric',
                            })}
                          </>
                        )}
                      </p>
                    </div>
                    <QuestionnaireStatusBadge status={q.status} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function PlanStatusBadge({ status }: { status: string }) {
  const config: Record<string, { label: string; className: string }> = {
    active: {
      label: 'Active',
      className:
        'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
    },
    completed: {
      label: 'Completed',
      className:
        'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-400',
    },
    cancelled: {
      label: 'Cancelled',
      className: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
    },
  };

  const { label, className } = config[status] || {
    label: status,
    className: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-400',
  };

  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${className}`}>
      {label}
    </span>
  );
}

function QuestionnaireStatusBadge({ status }: { status: string }) {
  const config: Record<string, { label: string; className: string }> = {
    pending: {
      label: 'Pending',
      className:
        'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
    },
    in_progress: {
      label: 'In Progress',
      className:
        'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
    },
    completed: {
      label: 'Completed',
      className:
        'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
    },
  };

  const { label, className } = config[status] || {
    label: status,
    className: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-400',
  };

  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${className}`}>
      {label}
    </span>
  );
}

// ============================================================================
// Dialogs
// ============================================================================

interface DischargeDialogProps {
  patient: Patient;
  open: boolean;
  onClose: () => void;
}

function DischargeDialog({ patient, open, onClose }: DischargeDialogProps) {
  const { mutate: discharge, isPending } = useDischargePatient();

  const handleDischarge = () => {
    discharge(patient.id, {
      onSuccess: () => {
        onClose();
      },
    });
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Discharge Patient</DialogTitle>
          <DialogDescription>
            Mark {patient.full_name} as discharged. This will end monitoring and
            disable their app access.
          </DialogDescription>
        </DialogHeader>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isPending}>
            Cancel
          </Button>
          <Button
            onClick={handleDischarge}
            disabled={isPending}
            className="bg-green-600 hover:bg-green-700 text-white"
          >
            {isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Discharging...
              </>
            ) : (
              <>
                <CheckCircle2 className="mr-2 h-4 w-4" />
                Discharge
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface EditPatientDialogProps {
  patient: Patient;
  open: boolean;
  onClose: () => void;
}

function EditPatientDialog({ patient, open, onClose }: EditPatientDialogProps) {
  const organizationId = getSlCurrentOrgId();
  const { mutate: updatePatient, isPending } = useUpdateSlPatient();
  const assignPlan = useAssignPatientPlan();
  const cancelPlan = useCancelPatientPlan();
  const assignQuestionnaire = useAssignQuestionnaire();
  const { data: templatesData, isLoading: templatesLoading } =
    useInstructionTemplates({
      organization_id: organizationId || undefined,
      status: 'active',
      include_shared: true,
    });
  const { data: questionnairesData, isLoading: questionnairesLoading } =
    useQuestionnaires({
      organization_id: organizationId || undefined,
      is_active: true,
    });
  const { data: plansData } = usePatientPlans(patient.id, 'active');
  const { data: patientQuestionnaires } = usePatientQuestionnaires(
    patient.id,
    'in_progress'
  );

  const [formData, setFormData] = useState<
    Partial<PatientUpdate> & {
      instruction_template_id?: string;
      questionnaire_id?: string;
    }
  >({});
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Get current active plan
  const currentPlan = plansData?.items?.[0];
  const currentTemplateId = currentPlan?.template_id || '';

  // Get currently assigned questionnaire (if any pending)
  const currentQuestionnaireId =
    patientQuestionnaires?.items?.[0]?.questionnaire_id || '';

  // Initialize form data when dialog opens
  useEffect(() => {
    if (open) {
      setFormData({
        first_name: patient.first_name || '',
        last_name: patient.last_name || '',
        email: patient.email || '',
        phone: patient.phone || '',
        mrn: patient.mrn || '',
        date_of_birth: patient.date_of_birth || '',
        gender: patient.gender || '',
        primary_diagnosis: patient.primary_diagnosis || '',
        surgery_date: patient.surgery_date || '',
        instruction_template_id: currentTemplateId,
        questionnaire_id: currentQuestionnaireId,
      });
      setErrors({});
    }
  }, [open, patient, currentTemplateId, currentQuestionnaireId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const newErrors: Record<string, string> = {};
    if (!formData.first_name?.trim())
      newErrors.first_name = 'First name is required';
    if (!formData.last_name?.trim())
      newErrors.last_name = 'Last name is required';

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    try {
      // Update patient info
      await new Promise<void>((resolve, reject) => {
        updatePatient(
          {
            id: patient.id,
            data: {
              first_name: formData.first_name?.trim(),
              last_name: formData.last_name?.trim(),
              email: formData.email?.trim() || undefined,
              phone: formData.phone?.trim() || undefined,
              mrn: formData.mrn?.trim() || undefined,
              date_of_birth: formData.date_of_birth || undefined,
              gender: formData.gender || undefined,
              primary_diagnosis:
                formData.primary_diagnosis?.trim() || undefined,
              surgery_date: formData.surgery_date || undefined,
            },
          },
          {
            onSuccess: () => resolve(),
            onError: (error) => reject(error),
          }
        );
      });

      // Handle care plan changes
      const newTemplateId = formData.instruction_template_id || '';
      const planChanged = newTemplateId !== currentTemplateId;

      if (planChanged) {
        // Cancel current plan if exists
        if (currentPlan) {
          await cancelPlan.mutateAsync({
            patientId: patient.id,
            planId: currentPlan.id,
            cancelPendingTasks: true,
          });
        }

        // Assign new plan if selected
        if (newTemplateId) {
          await assignPlan.mutateAsync({
            patientId: patient.id,
            data: {
              template_id: newTemplateId,
              reference_type: patient.surgery_date
                ? 'surgery_date'
                : 'assignment_date',
              generate_tasks: true,
            },
          });
        }
      }

      // Handle questionnaire assignment (only assign new ones, don't remove existing)
      const newQuestionnaireId = formData.questionnaire_id || '';
      if (newQuestionnaireId && newQuestionnaireId !== currentQuestionnaireId) {
        await assignQuestionnaire.mutateAsync({
          patientId: patient.id,
          questionnaireId: newQuestionnaireId,
        });
      }

      onClose();
    } catch {
      // Errors handled by hooks
    }
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Edit Patient</DialogTitle>
          <DialogDescription>
            Update patient information for {patient.full_name}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit}>
          <div className="space-y-4 py-4">
            {/* Personal Information */}
            <div className="space-y-3">
              <h4 className="text-sm font-medium text-[var(--sl-text-muted)]">
                Personal Information
              </h4>
              <div className="grid grid-cols-2 gap-4">
                <div className="sl-form-group">
                  <label className="sl-form-label">
                    First Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.first_name || ''}
                    onChange={(e) =>
                      setFormData({ ...formData, first_name: e.target.value })
                    }
                    className="sl-form-input w-full"
                  />
                  {errors.first_name && (
                    <p className="text-xs text-red-500 mt-1">
                      {errors.first_name}
                    </p>
                  )}
                </div>
                <div className="sl-form-group">
                  <label className="sl-form-label">
                    Last Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.last_name || ''}
                    onChange={(e) =>
                      setFormData({ ...formData, last_name: e.target.value })
                    }
                    className="sl-form-input w-full"
                  />
                  {errors.last_name && (
                    <p className="text-xs text-red-500 mt-1">
                      {errors.last_name}
                    </p>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="sl-form-group">
                  <label className="sl-form-label">Date of Birth</label>
                  <input
                    type="date"
                    value={formData.date_of_birth || ''}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        date_of_birth: e.target.value,
                      })
                    }
                    className="sl-form-input w-full"
                  />
                </div>
                <div className="sl-form-group">
                  <label className="sl-form-label">Gender</label>
                  <select
                    value={formData.gender || ''}
                    onChange={(e) =>
                      setFormData({ ...formData, gender: e.target.value })
                    }
                    className="sl-select w-full"
                  >
                    <option value="">Select gender</option>
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                    <option value="other">Other</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Contact Information */}
            <div className="space-y-3">
              <h4 className="text-sm font-medium text-[var(--sl-text-muted)]">
                Contact Information
              </h4>
              <div className="grid grid-cols-2 gap-4">
                <div className="sl-form-group">
                  <label className="sl-form-label">Email</label>
                  <input
                    type="email"
                    value={formData.email || ''}
                    onChange={(e) =>
                      setFormData({ ...formData, email: e.target.value })
                    }
                    className="sl-form-input w-full"
                  />
                </div>
                <div className="sl-form-group">
                  <label className="sl-form-label">Phone</label>
                  <input
                    type="tel"
                    value={formData.phone || ''}
                    onChange={(e) =>
                      setFormData({ ...formData, phone: e.target.value })
                    }
                    className="sl-form-input w-full"
                  />
                </div>
              </div>
            </div>

            {/* Medical Information */}
            <div className="space-y-3">
              <h4 className="text-sm font-medium text-[var(--sl-text-muted)]">
                Medical Information
              </h4>
              <div className="grid grid-cols-2 gap-4">
                <div className="sl-form-group">
                  <label className="sl-form-label">MRN</label>
                  <input
                    type="text"
                    value={formData.mrn || ''}
                    onChange={(e) =>
                      setFormData({ ...formData, mrn: e.target.value })
                    }
                    className="sl-form-input w-full"
                  />
                </div>
                <div className="sl-form-group">
                  <label className="sl-form-label">Primary Diagnosis</label>
                  <input
                    type="text"
                    value={formData.primary_diagnosis || ''}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        primary_diagnosis: e.target.value,
                      })
                    }
                    className="sl-form-input w-full"
                  />
                </div>
              </div>

              <div className="sl-form-group">
                <label className="sl-form-label">Surgery Date</label>
                <input
                  type="date"
                  value={formData.surgery_date || ''}
                  onChange={(e) =>
                    setFormData({ ...formData, surgery_date: e.target.value })
                  }
                  className="sl-form-input w-full"
                />
              </div>
            </div>

            {/* Care Plan */}
            <div className="space-y-3">
              <h4 className="text-sm font-medium text-[var(--sl-text-muted)]">
                Care Plan
              </h4>
              <div className="sl-form-group">
                <label className="sl-form-label">Instruction Template</label>
                <select
                  value={formData.instruction_template_id || ''}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      instruction_template_id: e.target.value,
                    })
                  }
                  className="sl-select w-full"
                  disabled={templatesLoading}
                >
                  <option value="">
                    {templatesLoading ? 'Loading...' : 'No care plan assigned'}
                  </option>
                  {templatesData?.items?.map((template) => (
                    <option key={template.id} value={template.id}>
                      {template.title}
                    </option>
                  ))}
                </select>
                {currentPlan &&
                  formData.instruction_template_id !== currentTemplateId && (
                    <p className="text-xs text-amber-600 mt-1">
                      Changing the care plan will cancel the current plan and
                      its pending tasks.
                    </p>
                  )}
              </div>

              <div className="sl-form-group">
                <label className="sl-form-label">Questionnaire</label>
                <select
                  value={formData.questionnaire_id || ''}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      questionnaire_id: e.target.value,
                    })
                  }
                  className="sl-select w-full"
                  disabled={questionnairesLoading}
                >
                  <option value="">
                    {questionnairesLoading
                      ? 'Loading...'
                      : 'Select questionnaire (optional)'}
                  </option>
                  {questionnairesData?.items?.map((questionnaire) => (
                    <option key={questionnaire.id} value={questionnaire.id}>
                      {questionnaire.title}
                    </option>
                  ))}
                </select>
                {currentQuestionnaireId && (
                  <p className="text-xs text-[var(--sl-text-muted)] mt-1">
                    Patient has an assigned questionnaire. Selecting a new one
                    will add to their assignments.
                  </p>
                )}
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              disabled={
                isPending ||
                assignPlan.isPending ||
                cancelPlan.isPending ||
                assignQuestionnaire.isPending
              }
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={
                isPending ||
                assignPlan.isPending ||
                cancelPlan.isPending ||
                assignQuestionnaire.isPending
              }
              className="bg-[var(--sl-brand)] hover:bg-[var(--sl-brand-dark)] text-white"
            >
              {isPending ||
              assignPlan.isPending ||
              cancelPlan.isPending ||
              assignQuestionnaire.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                'Save Changes'
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

interface AcknowledgeAlertDialogProps {
  alert: Alert | null;
  onClose: () => void;
}

function AcknowledgeAlertDialog({
  alert,
  onClose,
}: AcknowledgeAlertDialogProps) {
  const { mutate: acknowledge, isPending } = useAcknowledgeAlert();

  const handleSubmit = () => {
    if (!alert) return;

    acknowledge({ id: alert.id }, { onSuccess: onClose });
  };

  return (
    <Dialog open={!!alert} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Acknowledge Alert</DialogTitle>
          <DialogDescription>
            Mark this alert as acknowledged.
          </DialogDescription>
        </DialogHeader>

        {alert && (
          <div className="py-4">
            <div className="rounded-lg bg-[var(--sl-bg-muted)] p-4">
              <p className="text-sm font-medium text-[var(--sl-text-primary)]">
                {alert.title}
              </p>
              {alert.vital_type && (
                <p className="text-sm text-[var(--sl-text-muted)] mt-1">
                  {formatVitalType(alert.vital_type)}: {alert.observed_value}
                </p>
              )}
            </div>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isPending}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={isPending}
            className="bg-blue-600 hover:bg-blue-700 text-white"
          >
            {isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Check className="h-4 w-4 mr-2" />
            )}
            Acknowledge
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface ResolveAlertDialogProps {
  alert: Alert | null;
  onClose: () => void;
}

function ResolveAlertDialog({ alert, onClose }: ResolveAlertDialogProps) {
  const { mutate: resolve, isPending } = useResolveAlert();

  const handleSubmit = () => {
    if (!alert) return;

    resolve(
      { id: alert.id, data: { resolution_type: 'patient_contacted' } },
      { onSuccess: onClose }
    );
  };

  return (
    <Dialog open={!!alert} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Resolve Alert</DialogTitle>
          <DialogDescription>Mark this alert as resolved.</DialogDescription>
        </DialogHeader>

        {alert && (
          <div className="py-4">
            <div className="rounded-lg bg-[var(--sl-bg-muted)] p-4">
              <p className="text-sm font-medium text-[var(--sl-text-primary)]">
                {alert.title}
              </p>
            </div>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isPending}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={isPending}
            className="bg-green-600 hover:bg-green-700 text-white"
          >
            {isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <CheckCircle2 className="h-4 w-4 mr-2" />
            )}
            Resolve
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ============================================================================
// Helpers
// ============================================================================

function capitalizeFirst(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1);
}

function formatTimeAgo(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins} min ago`;
  if (diffHours < 24) return `${diffHours} hr ago`;
  if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;

  return date.toLocaleDateString();
}

function formatDate(dateString: string): string {
  // Handle date-only strings (YYYY-MM-DD) to avoid timezone issues
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateString);
  if (dateOnly) {
    const [, y, m, d] = dateOnly;
    return new Date(Number(y), Number(m) - 1, Number(d)).toLocaleDateString();
  }
  return new Date(dateString).toLocaleDateString();
}

function formatDateTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const time = date.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  });

  if (date.toDateString() === now.toDateString()) {
    return `Today ${time}`;
  }

  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) {
    return `Yesterday ${time}`;
  }

  const dateStr = date.toLocaleDateString([], {
    month: 'short',
    day: 'numeric',
  });
  return `${dateStr} ${time}`;
}

function formatVitalType(vitalType: string): string {
  const names: Record<string, string> = {
    heart_rate: 'Heart Rate',
    spo2: 'SpO2',
    temperature: 'Temperature',
    hrv: 'HRV',
    respiratory_rate: 'Respiratory Rate',
    blood_pressure: 'Blood Pressure',
    blood_glucose: 'Blood Glucose',
  };

  return names[vitalType] || vitalType.replace(/_/g, ' ');
}
