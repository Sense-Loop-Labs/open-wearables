/**
 * Sense Loop Patient Detail Page
 * Matches the old Medplum PatientDetailPage design with SL theme
 */

import { createFileRoute, Link } from '@tanstack/react-router';
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  Bell,
  Check,
  CheckCircle2,
  Copy,
  Loader2,
  Smartphone,
  User,
} from 'lucide-react';
import { useState, useEffect } from 'react';

import { Badge } from '@/components/ui/badge';
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
  useUpdateSlPatient,
} from '@/hooks/api/use-sl-patients';
import type { Alert, Patient, PatientSummary, PatientUpdate } from '@/lib/api/types/sense-loop';
import { toast } from 'sonner';

export const Route = createFileRoute('/sl/_sl-authenticated/patients/$patientId')({
  component: SlPatientDetailPage,
});

function SlPatientDetailPage() {
  const { patientId } = Route.useParams();
  const { data: patient, isLoading } = useSlPatient(patientId);
  const { data: alerts } = useSlAlerts({ patient_id: patientId, page_size: 50 });

  const [dischargeDialogOpen, setDischargeDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [acknowledgeDialog, setAcknowledgeDialog] = useState<Alert | null>(null);
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

  const activeAlerts = alerts?.items?.filter((a) => a.status === 'active') ?? [];

  return (
    <div className="space-y-6">
      {/* Header - matches old Medplum design */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-[var(--sl-text-primary)]">{patient.full_name}</h1>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            onClick={() => setEditDialogOpen(true)}
            className="border-[var(--sl-brand)] text-[var(--sl-brand)] hover:bg-[var(--sl-brand)] hover:text-white"
          >
            Edit Patient
          </Button>
          <Link to="/sl/patients">
            <Button variant="outline" className="border-[var(--sl-border)] text-[var(--sl-text-secondary)]">
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
            <h3 className="text-lg font-medium text-[var(--sl-text-primary)] mb-4">Patient Information</h3>
            <div className="space-y-3">
              <InfoRow label="Date of Birth" value={patient.date_of_birth ? formatDate(patient.date_of_birth) : null} />
              <InfoRow label="Gender" value={patient.gender ? capitalizeFirst(patient.gender) : null} />
              <InfoRow label="Phone" value={patient.phone} />
              <InfoRow label="Email" value={patient.email} />
              <div className="flex justify-between items-center">
                <span className="text-sm text-[var(--sl-text-muted)]">Enrollment Status</span>
                <EnrollmentBadge status={patient.enrollment_status} />
              </div>
            </div>
          </div>
        </div>

        {/* Surgery Information Card */}
        <div className="sl-card">
          <div className="sl-card-body">
            <h3 className="text-lg font-medium text-[var(--sl-text-primary)] mb-4">Surgery Information</h3>
            <div className="space-y-3">
              <InfoRow label="Surgery Date" value={patient.surgery_date ? formatDate(patient.surgery_date) : null} />
              <InfoRow label="Primary Diagnosis" value={patient.primary_diagnosis} />
              <InfoRow label="Days Post-Surgery" value={patient.days_post_surgery?.toString()} />
              <InfoRow label="MRN" value={patient.mrn} />
              <InfoRow label="Discharge Date" value={patient.discharge_date ? formatDate(patient.discharge_date) : null} />
            </div>
          </div>
        </div>
      </div>

      {/* Tabs - like old Medplum */}
      <Tabs defaultValue="vitals" className="space-y-4">
        <TabsList className="bg-[var(--sl-bg-muted)] border border-[var(--sl-border)]">
          <TabsTrigger value="vitals" className="data-[state=active]:bg-white data-[state=active]:text-[var(--sl-text-primary)]">
            Vitals & Observations
          </TabsTrigger>
          <TabsTrigger value="alerts" className="data-[state=active]:bg-white data-[state=active]:text-[var(--sl-text-primary)]">
            Alerts
            {activeAlerts.length > 0 && (
              <span className="ml-2 px-2 py-0.5 text-xs rounded-full bg-red-100 text-red-600">
                {activeAlerts.length}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="responses" className="data-[state=active]:bg-white data-[state=active]:text-[var(--sl-text-primary)]">
            Responses
          </TabsTrigger>
          <TabsTrigger value="devices" className="data-[state=active]:bg-white data-[state=active]:text-[var(--sl-text-primary)]">
            Connected Devices
          </TabsTrigger>
        </TabsList>

        <TabsContent value="vitals">
          <VitalsSection summary={patient.summary} />
        </TabsContent>

        <TabsContent value="alerts">
          <AlertsSection
            alerts={alerts?.items ?? []}
            onAcknowledge={setAcknowledgeDialog}
            onResolve={setResolveDialog}
          />
        </TabsContent>

        <TabsContent value="responses">
          <ResponsesSection />
        </TabsContent>

        <TabsContent value="devices">
          <DevicesSection />
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
        <div className={`px-4 py-2 rounded border-2 border-dashed ${isExpired ? 'border-red-300 bg-red-50' : 'border-blue-300 bg-blue-100'}`}>
          <span className={`text-xl font-bold font-mono tracking-wider ${isExpired ? 'text-red-600' : 'text-blue-800'}`}>
            {patient.activation_code}
          </span>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleCopy}
          disabled={isExpired}
          className={copied ? 'border-teal-500 text-teal-600' : 'border-blue-500 text-blue-600'}
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
            {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Generate New Code'}
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
    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${colors[status] || colors.pending}`}>
      {capitalizeFirst(status)}
    </span>
  );
}

function InfoRow({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="flex justify-between">
      <span className="text-sm text-[var(--sl-text-muted)]">{label}</span>
      <span className="text-sm font-medium text-[var(--sl-text-primary)]">{value || '-'}</span>
    </div>
  );
}

function VitalsSection({ summary }: { summary?: PatientSummary }) {
  if (!summary) {
    return (
      <div className="sl-card">
        <div className="sl-no-data">
          <Activity className="h-12 w-12 mx-auto text-[var(--sl-text-muted)] mb-4" />
          <p className="text-[var(--sl-text-muted)]">No observations recorded yet.</p>
        </div>
      </div>
    );
  }

  // Helper to convert Celsius to Fahrenheit
  const celsiusToFahrenheit = (celsius: number | null | undefined): number | null => {
    if (celsius === null || celsius === undefined) return null;
    // If value is already in Fahrenheit range (>50), assume it's already converted
    if (celsius > 50) return Math.round(celsius * 10) / 10;
    // Convert from Celsius to Fahrenheit and round to 1 decimal
    return Math.round((celsius * 9/5 + 32) * 10) / 10;
  };

  // Create observation rows from summary data
  const observations = [
    { type: 'Heart Rate', value: summary.latest_heart_rate, unit: 'bpm', date: summary.latest_heart_rate_at },
    { type: 'SpO2', value: summary.latest_spo2, unit: '%', date: summary.latest_spo2_at },
    { type: 'Temperature', value: celsiusToFahrenheit(summary.latest_temperature), unit: '°F', date: summary.latest_temperature_at },
    { type: 'Respiratory Rate', value: summary.latest_respiratory_rate, unit: '/min', date: summary.latest_respiratory_rate_at },
    { type: 'HRV', value: summary.latest_hrv ? Math.round(summary.latest_hrv) : null, unit: 'ms', date: summary.latest_hrv_at },
    { type: 'Blood Pressure', value: summary.latest_blood_pressure_systolic && summary.latest_blood_pressure_diastolic ? `${summary.latest_blood_pressure_systolic}/${summary.latest_blood_pressure_diastolic}` : null, unit: 'mmHg', date: summary.latest_blood_pressure_at },
    { type: 'Steps (Today)', value: summary.today_steps, unit: '', date: null },
    { type: 'Active Minutes (Today)', value: summary.today_active_minutes, unit: 'min', date: null },
    { type: 'Sleep', value: summary.last_sleep_duration_minutes ? Math.round(summary.last_sleep_duration_minutes / 60 * 10) / 10 : null, unit: 'hrs', date: null },
  ].filter(obs => obs.value !== null && obs.value !== undefined);

  if (observations.length === 0) {
    return (
      <div className="sl-card">
        <div className="sl-no-data">
          <Activity className="h-12 w-12 mx-auto text-[var(--sl-text-muted)] mb-4" />
          <p className="text-[var(--sl-text-muted)]">No observations recorded yet.</p>
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
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {observations.map((obs, idx) => (
            <tr key={idx}>
              <td className="text-[var(--sl-text-primary)] font-medium">{obs.type}</td>
              <td>{obs.value} {obs.unit}</td>
              <td>{obs.date ? formatDateTime(obs.date) : 'Today'}</td>
              <td>
                <span className="inline-flex px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700">
                  final
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface AlertsSectionProps {
  alerts: Alert[];
  onAcknowledge: (alert: Alert) => void;
  onResolve: (alert: Alert) => void;
}

function AlertsSection({ alerts, onAcknowledge, onResolve }: AlertsSectionProps) {
  if (alerts.length === 0) {
    return (
      <div className="sl-card">
        <div className="sl-no-data">
          <Bell className="h-12 w-12 mx-auto text-[var(--sl-text-muted)] mb-4" />
          <p className="text-[var(--sl-text-muted)]">No alerts for this patient.</p>
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
              <td className="text-[var(--sl-text-primary)] font-medium">{alert.title}</td>
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
                  {(alert.status === 'active' || alert.status === 'acknowledged') && (
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
    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${colors[severity] || colors.moderate}`}>
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
    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${colors[status] || colors.active}`}>
      {capitalizeFirst(status)}
    </span>
  );
}

function ResponsesSection() {
  return (
    <div className="sl-card">
      <div className="sl-no-data">
        <Activity className="h-12 w-12 mx-auto text-[var(--sl-text-muted)] mb-4" />
        <p className="text-[var(--sl-text-muted)]">No questionnaire responses yet.</p>
      </div>
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
          <Button onClick={handleDischarge} disabled={isPending} className="bg-green-600 hover:bg-green-700 text-white">
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
  const { mutate: updatePatient, isPending } = useUpdateSlPatient();
  const [formData, setFormData] = useState<Partial<PatientUpdate>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});

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
      });
      setErrors({});
    }
  }, [open, patient]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const newErrors: Record<string, string> = {};
    if (!formData.first_name?.trim()) newErrors.first_name = 'First name is required';
    if (!formData.last_name?.trim()) newErrors.last_name = 'Last name is required';

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

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
          primary_diagnosis: formData.primary_diagnosis?.trim() || undefined,
          surgery_date: formData.surgery_date || undefined,
        },
      },
      {
        onSuccess: () => {
          onClose();
        },
      }
    );
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
              <h4 className="text-sm font-medium text-[var(--sl-text-muted)]">Personal Information</h4>
              <div className="grid grid-cols-2 gap-4">
                <div className="sl-form-group">
                  <label className="sl-form-label">
                    First Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.first_name || ''}
                    onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                    className="sl-form-input w-full"
                  />
                  {errors.first_name && (
                    <p className="text-xs text-red-500 mt-1">{errors.first_name}</p>
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
                    className="sl-form-input w-full"
                  />
                  {errors.last_name && (
                    <p className="text-xs text-red-500 mt-1">{errors.last_name}</p>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="sl-form-group">
                  <label className="sl-form-label">Date of Birth</label>
                  <input
                    type="date"
                    value={formData.date_of_birth || ''}
                    onChange={(e) => setFormData({ ...formData, date_of_birth: e.target.value })}
                    className="sl-form-input w-full"
                  />
                </div>
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
              </div>
            </div>

            {/* Contact Information */}
            <div className="space-y-3">
              <h4 className="text-sm font-medium text-[var(--sl-text-muted)]">Contact Information</h4>
              <div className="grid grid-cols-2 gap-4">
                <div className="sl-form-group">
                  <label className="sl-form-label">Email</label>
                  <input
                    type="email"
                    value={formData.email || ''}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    className="sl-form-input w-full"
                  />
                </div>
                <div className="sl-form-group">
                  <label className="sl-form-label">Phone</label>
                  <input
                    type="tel"
                    value={formData.phone || ''}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                    className="sl-form-input w-full"
                  />
                </div>
              </div>
            </div>

            {/* Medical Information */}
            <div className="space-y-3">
              <h4 className="text-sm font-medium text-[var(--sl-text-muted)]">Medical Information</h4>
              <div className="grid grid-cols-2 gap-4">
                <div className="sl-form-group">
                  <label className="sl-form-label">MRN</label>
                  <input
                    type="text"
                    value={formData.mrn || ''}
                    onChange={(e) => setFormData({ ...formData, mrn: e.target.value })}
                    className="sl-form-input w-full"
                  />
                </div>
                <div className="sl-form-group">
                  <label className="sl-form-label">Primary Diagnosis</label>
                  <input
                    type="text"
                    value={formData.primary_diagnosis || ''}
                    onChange={(e) => setFormData({ ...formData, primary_diagnosis: e.target.value })}
                    className="sl-form-input w-full"
                  />
                </div>
              </div>

              <div className="sl-form-group">
                <label className="sl-form-label">Surgery Date</label>
                <input
                  type="date"
                  value={formData.surgery_date || ''}
                  onChange={(e) => setFormData({ ...formData, surgery_date: e.target.value })}
                  className="sl-form-input w-full"
                />
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={isPending}>
              Cancel
            </Button>
            <Button type="submit" disabled={isPending} className="bg-[var(--sl-brand)] hover:bg-[var(--sl-brand-dark)] text-white">
              {isPending ? (
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

function AcknowledgeAlertDialog({ alert, onClose }: AcknowledgeAlertDialogProps) {
  const { mutate: acknowledge, isPending } = useAcknowledgeAlert();

  const handleSubmit = () => {
    if (!alert) return;

    acknowledge(
      { id: alert.id },
      { onSuccess: onClose }
    );
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
              <p className="text-sm font-medium text-[var(--sl-text-primary)]">{alert.title}</p>
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
          <Button onClick={handleSubmit} disabled={isPending} className="bg-blue-600 hover:bg-blue-700 text-white">
            {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4 mr-2" />}
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
          <DialogDescription>
            Mark this alert as resolved.
          </DialogDescription>
        </DialogHeader>

        {alert && (
          <div className="py-4">
            <div className="rounded-lg bg-[var(--sl-bg-muted)] p-4">
              <p className="text-sm font-medium text-[var(--sl-text-primary)]">{alert.title}</p>
            </div>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isPending}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={isPending} className="bg-green-600 hover:bg-green-700 text-white">
            {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4 mr-2" />}
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
  const time = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  if (date.toDateString() === now.toDateString()) {
    return `Today ${time}`;
  }

  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) {
    return `Yesterday ${time}`;
  }

  const dateStr = date.toLocaleDateString([], { month: 'short', day: 'numeric' });
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
