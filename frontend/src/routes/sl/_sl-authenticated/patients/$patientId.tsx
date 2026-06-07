/**
 * Sense Loop Patient Detail Page
 * View patient vitals, alerts, and care plan details
 */

import { createFileRoute, Link } from '@tanstack/react-router';
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  Bell,
  Calendar,
  Check,
  CheckCircle2,
  Clock,
  Clipboard,
  Copy,
  Footprints,
  Heart,
  Loader2,
  Moon,
  Thermometer,
  TrendingDown,
  TrendingUp,
  User,
  Wind,
} from 'lucide-react';
import { useState } from 'react';

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
} from '@/hooks/api/use-sl-patients';
import type { Alert, Patient, PatientSummary } from '@/lib/api/types/sense-loop';
import { toast } from 'sonner';

export const Route = createFileRoute('/sl/_sl-authenticated/patients/$patientId')({
  component: SlPatientDetailPage,
});

function SlPatientDetailPage() {
  const { patientId } = Route.useParams();
  const { data: patient, isLoading } = useSlPatient(patientId);
  const { data: alerts } = useSlAlerts({ patient_id: patientId, page_size: 50 });

  const [dischargeDialogOpen, setDischargeDialogOpen] = useState(false);
  const [acknowledgeDialog, setAcknowledgeDialog] = useState<Alert | null>(null);
  const [resolveDialog, setResolveDialog] = useState<Alert | null>(null);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-8 w-8 animate-spin text-zinc-500" />
      </div>
    );
  }

  if (!patient) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <User className="h-12 w-12 text-zinc-600" />
        <p className="text-zinc-500">Patient not found</p>
        <Link to="/sl/patients">
          <Button variant="outline" className="border-zinc-700">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Patients
          </Button>
        </Link>
      </div>
    );
  }

  const activeAlerts = alerts?.items?.filter((a) => a.status === 'active') ?? [];
  const acknowledgedAlerts = alerts?.items?.filter((a) => a.status === 'acknowledged') ?? [];

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-4">
          <Link to="/sl/patients">
            <Button variant="ghost" size="sm" className="text-zinc-400 hover:text-white">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-semibold text-white">{patient.full_name}</h1>
              <StatusBadge status={patient.summary?.overall_status} />
              <EnrollmentBadge status={patient.enrollment_status} />
            </div>
            <div className="flex items-center gap-4 mt-1 text-sm text-zinc-500">
              {patient.mrn && <span>MRN: {patient.mrn}</span>}
              {patient.primary_diagnosis && <span>{patient.primary_diagnosis}</span>}
              {patient.days_post_surgery !== null && (
                <span className="flex items-center gap-1">
                  <Calendar className="h-4 w-4" />
                  Day {patient.days_post_surgery} post-surgery
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <ActivationCodeButton patient={patient} />
          {patient.enrollment_status !== 'discharged' && (
            <Button
              variant="outline"
              onClick={() => setDischargeDialogOpen(true)}
              className="border-zinc-700 text-zinc-300"
            >
              <CheckCircle2 className="h-4 w-4 mr-2" />
              Discharge
            </Button>
          )}
        </div>
      </div>

      {/* Content Tabs */}
      <Tabs defaultValue="vitals" className="space-y-6">
        <TabsList className="bg-zinc-900 border border-zinc-800">
          <TabsTrigger value="vitals" className="data-[state=active]:bg-zinc-800">
            <Activity className="h-4 w-4 mr-2" />
            Vitals
          </TabsTrigger>
          <TabsTrigger value="alerts" className="data-[state=active]:bg-zinc-800">
            <Bell className="h-4 w-4 mr-2" />
            Alerts
            {activeAlerts.length > 0 && (
              <Badge variant="destructive" className="ml-2 text-xs">
                {activeAlerts.length}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="info" className="data-[state=active]:bg-zinc-800">
            <Clipboard className="h-4 w-4 mr-2" />
            Info
          </TabsTrigger>
        </TabsList>

        <TabsContent value="vitals" className="space-y-6">
          <VitalsOverview summary={patient.summary} />
        </TabsContent>

        <TabsContent value="alerts" className="space-y-6">
          <AlertsSection
            activeAlerts={activeAlerts}
            acknowledgedAlerts={acknowledgedAlerts}
            allAlerts={alerts?.items ?? []}
            onAcknowledge={setAcknowledgeDialog}
            onResolve={setResolveDialog}
          />
        </TabsContent>

        <TabsContent value="info" className="space-y-6">
          <PatientInfoSection patient={patient} />
        </TabsContent>
      </Tabs>

      {/* Dialogs */}
      <DischargeDialog
        patient={patient}
        open={dischargeDialogOpen}
        onClose={() => setDischargeDialogOpen(false)}
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

function StatusBadge({ status }: { status?: string }) {
  const variants: Record<string, string> = {
    good: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    warning: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    critical: 'bg-red-500/20 text-red-400 border-red-500/30',
    no_data: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30',
  };

  const labels: Record<string, string> = {
    good: 'Good',
    warning: 'Warning',
    critical: 'Critical',
    no_data: 'No Data',
  };

  const key = status || 'no_data';

  return (
    <Badge variant="outline" className={`text-xs ${variants[key]}`}>
      {labels[key]}
    </Badge>
  );
}

function EnrollmentBadge({ status }: { status: string }) {
  const variants: Record<string, string> = {
    pending: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30',
    activated: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    active: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    discharged: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
    inactive: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30',
  };

  return (
    <Badge variant="outline" className={`text-xs ${variants[status]}`}>
      {status}
    </Badge>
  );
}

function ActivationCodeButton({ patient }: { patient: Patient }) {
  const { mutate: generateCode, isPending } = useGenerateActivationCode();
  const [copiedCode, setCopiedCode] = useState(false);

  const handleCopyCode = async () => {
    if (patient.activation_code) {
      await navigator.clipboard.writeText(patient.activation_code);
      setCopiedCode(true);
      toast.success('Activation code copied to clipboard');
      setTimeout(() => setCopiedCode(false), 2000);
    }
  };

  if (patient.enrollment_status === 'active' || patient.enrollment_status === 'discharged') {
    return null;
  }

  // If patient has an activation code, show it with copy button
  if (patient.activation_code) {
    const isExpired = patient.activation_code_expires_at
      ? new Date(patient.activation_code_expires_at) < new Date()
      : false;

    return (
      <div className="flex items-center gap-2">
        <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border ${isExpired ? 'border-red-800 bg-red-950/30' : 'border-emerald-800 bg-emerald-950/30'}`}>
          <span className={`font-mono text-lg font-bold tracking-wider ${isExpired ? 'text-red-400' : 'text-emerald-400'}`}>
            {patient.activation_code}
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleCopyCode}
            className="h-7 w-7 p-0 hover:bg-emerald-900/50"
          >
            {copiedCode ? (
              <Check className="h-4 w-4 text-emerald-400" />
            ) : (
              <Copy className="h-4 w-4 text-zinc-400" />
            )}
          </Button>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => generateCode(patient.id)}
          disabled={isPending}
          className="border-zinc-700 text-zinc-300"
        >
          {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : (isExpired ? 'Regenerate' : 'New Code')}
        </Button>
      </div>
    );
  }

  // No code yet, show generate button
  return (
    <Button
      variant="outline"
      onClick={() => generateCode(patient.id)}
      disabled={isPending}
      className="border-zinc-700 text-zinc-300"
    >
      {isPending ? (
        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
      ) : (
        <Copy className="h-4 w-4 mr-2" />
      )}
      Generate Code
    </Button>
  );
}

function VitalsOverview({ summary }: { summary?: PatientSummary }) {
  if (!summary) {
    return (
      <div className="text-center py-12">
        <Activity className="h-12 w-12 mx-auto text-zinc-600 mb-4" />
        <p className="text-zinc-500">No vitals data available yet</p>
        <p className="text-sm text-zinc-600 mt-1">
          Data will appear once the patient starts using the app
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Core Vitals */}
      <div>
        <h3 className="text-sm font-medium text-zinc-400 mb-4">Core Vitals</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <VitalCard
            icon={Heart}
            label="Heart Rate"
            value={summary.latest_heart_rate}
            unit="bpm"
            timestamp={summary.latest_heart_rate_at}
            normalRange="60-100"
          />
          <VitalCard
            icon={Activity}
            label="SpO2"
            value={summary.latest_spo2}
            unit="%"
            timestamp={summary.latest_spo2_at}
            normalRange=">95"
          />
          <VitalCard
            icon={Thermometer}
            label="Temperature"
            value={summary.latest_temperature}
            unit="°F"
            timestamp={summary.latest_temperature_at}
            normalRange="97.8-99.1"
          />
          <VitalCard
            icon={Wind}
            label="Respiratory Rate"
            value={summary.latest_respiratory_rate}
            unit="/min"
            timestamp={summary.latest_respiratory_rate_at}
            normalRange="12-20"
          />
        </div>
      </div>

      {/* Recovery Metrics */}
      <div>
        <h3 className="text-sm font-medium text-zinc-400 mb-4">Recovery Metrics</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <VitalCard
            icon={TrendingUp}
            label="HRV"
            value={summary.latest_hrv}
            unit="ms"
            timestamp={summary.latest_hrv_at}
          />
          <VitalCard
            icon={TrendingUp}
            label="Recovery Score"
            value={summary.latest_recovery_score}
            unit="%"
            timestamp={summary.latest_recovery_score_at}
          />
          <VitalCard
            icon={TrendingUp}
            label="Readiness"
            value={summary.latest_readiness_score}
            unit="%"
            timestamp={summary.latest_readiness_score_at}
          />
          <VitalCard
            icon={Clock}
            label="Last Sync"
            value={summary.last_sync_at ? 'Active' : 'None'}
            timestamp={summary.last_sync_at}
            isText
          />
        </div>
      </div>

      {/* Activity */}
      <div>
        <h3 className="text-sm font-medium text-zinc-400 mb-4">Today's Activity</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <VitalCard
            icon={Footprints}
            label="Steps"
            value={summary.today_steps}
            unit=""
          />
          <VitalCard
            icon={Activity}
            label="Active Minutes"
            value={summary.today_active_minutes}
            unit="min"
          />
          <VitalCard
            icon={TrendingDown}
            label="Active Calories"
            value={summary.today_active_calories}
            unit="kcal"
          />
          <VitalCard
            icon={Moon}
            label="Sleep"
            value={summary.last_sleep_duration_minutes ? Math.round(summary.last_sleep_duration_minutes / 60 * 10) / 10 : null}
            unit="hrs"
          />
        </div>
      </div>
    </div>
  );
}

interface VitalCardProps {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: number | string | null;
  unit?: string;
  timestamp?: string | null;
  normalRange?: string;
  isText?: boolean;
}

function VitalCard({ icon: Icon, label, value, unit, timestamp, normalRange, isText }: VitalCardProps) {
  const hasValue = value !== null && value !== undefined;

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
      <div className="flex items-center gap-2 mb-2">
        <Icon className="h-4 w-4 text-zinc-500" />
        <span className="text-xs text-zinc-500">{label}</span>
      </div>
      <div className="flex items-baseline gap-1">
        {hasValue ? (
          <>
            <span className={`text-2xl font-bold ${isText ? 'text-emerald-400' : 'text-white'}`}>
              {value}
            </span>
            {unit && <span className="text-sm text-zinc-500">{unit}</span>}
          </>
        ) : (
          <span className="text-lg text-zinc-600">--</span>
        )}
      </div>
      {timestamp && (
        <p className="text-xs text-zinc-600 mt-1">{formatTimeAgo(timestamp)}</p>
      )}
      {normalRange && (
        <p className="text-xs text-zinc-600 mt-1">Normal: {normalRange}</p>
      )}
    </div>
  );
}

interface AlertsSectionProps {
  activeAlerts: Alert[];
  acknowledgedAlerts: Alert[];
  allAlerts: Alert[];
  onAcknowledge: (alert: Alert) => void;
  onResolve: (alert: Alert) => void;
}

function AlertsSection({
  activeAlerts,
  acknowledgedAlerts,
  allAlerts,
  onAcknowledge,
  onResolve,
}: AlertsSectionProps) {
  if (allAlerts.length === 0) {
    return (
      <div className="text-center py-12">
        <Bell className="h-12 w-12 mx-auto text-zinc-600 mb-4" />
        <p className="text-zinc-500">No alerts for this patient</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Active Alerts */}
      {activeAlerts.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-red-400 mb-4 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4" />
            Active Alerts ({activeAlerts.length})
          </h3>
          <div className="space-y-3">
            {activeAlerts.map((alert) => (
              <AlertCard
                key={alert.id}
                alert={alert}
                onAcknowledge={() => onAcknowledge(alert)}
                onResolve={() => onResolve(alert)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Acknowledged Alerts */}
      {acknowledgedAlerts.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-blue-400 mb-4 flex items-center gap-2">
            <Check className="h-4 w-4" />
            Acknowledged ({acknowledgedAlerts.length})
          </h3>
          <div className="space-y-3">
            {acknowledgedAlerts.map((alert) => (
              <AlertCard
                key={alert.id}
                alert={alert}
                onResolve={() => onResolve(alert)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Resolved Alerts */}
      {allAlerts.filter((a) => a.status === 'resolved').length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-zinc-400 mb-4 flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4" />
            Resolved ({allAlerts.filter((a) => a.status === 'resolved').length})
          </h3>
          <div className="space-y-3">
            {allAlerts
              .filter((a) => a.status === 'resolved')
              .slice(0, 5)
              .map((alert) => (
                <AlertCard key={alert.id} alert={alert} />
              ))}
          </div>
        </div>
      )}
    </div>
  );
}

interface AlertCardProps {
  alert: Alert;
  onAcknowledge?: () => void;
  onResolve?: () => void;
}

function AlertCard({ alert, onAcknowledge, onResolve }: AlertCardProps) {
  const severityColors: Record<string, string> = {
    critical: 'border-red-900 bg-red-950/30',
    warning: 'border-yellow-900 bg-yellow-950/30',
    info: 'border-blue-900 bg-blue-950/30',
  };

  return (
    <div className={`rounded-lg border p-4 ${severityColors[alert.severity] || 'border-zinc-800 bg-zinc-900'}`}>
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3">
          <SeverityIcon severity={alert.severity} />
          <div>
            <p className="text-sm font-medium text-white">{alert.title}</p>
            {alert.message && (
              <p className="text-xs text-zinc-400 mt-1">{alert.message}</p>
            )}
            <div className="flex items-center gap-4 mt-2 text-xs text-zinc-500">
              <span>{formatTimeAgo(alert.triggered_at)}</span>
              {alert.vital_type && (
                <span>
                  {formatVitalType(alert.vital_type)}: {alert.observed_value}
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {alert.status === 'active' && onAcknowledge && (
            <Button
              variant="outline"
              size="sm"
              onClick={onAcknowledge}
              className="border-blue-700 hover:bg-blue-900/20"
            >
              <Check className="h-4 w-4" />
            </Button>
          )}
          {(alert.status === 'active' || alert.status === 'acknowledged') && onResolve && (
            <Button
              variant="outline"
              size="sm"
              onClick={onResolve}
              className="border-emerald-700 hover:bg-emerald-900/20"
            >
              <CheckCircle2 className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

function SeverityIcon({ severity }: { severity: string }) {
  const icons: Record<string, React.ReactNode> = {
    critical: <AlertTriangle className="h-5 w-5 text-red-500" />,
    warning: <AlertTriangle className="h-5 w-5 text-yellow-500" />,
    info: <Bell className="h-5 w-5 text-blue-500" />,
  };

  return icons[severity] || icons.info;
}

function PatientInfoSection({ patient }: { patient: Patient }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* Personal Info */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6">
        <h3 className="text-sm font-medium text-zinc-400 mb-4">Personal Information</h3>
        <dl className="space-y-3">
          <InfoRow label="Full Name" value={patient.full_name} />
          <InfoRow label="Date of Birth" value={patient.date_of_birth ? formatDate(patient.date_of_birth) : null} />
          <InfoRow label="Gender" value={patient.gender} />
          <InfoRow label="Email" value={patient.email} />
          <InfoRow label="Phone" value={patient.phone} />
        </dl>
      </div>

      {/* Medical Info */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6">
        <h3 className="text-sm font-medium text-zinc-400 mb-4">Medical Information</h3>
        <dl className="space-y-3">
          <InfoRow label="MRN" value={patient.mrn} />
          <InfoRow label="Primary Diagnosis" value={patient.primary_diagnosis} />
          <InfoRow label="Surgery Date" value={patient.surgery_date ? formatDate(patient.surgery_date) : null} />
          <InfoRow label="Discharge Date" value={patient.discharge_date ? formatDate(patient.discharge_date) : null} />
          <InfoRow label="Days Post-Surgery" value={patient.days_post_surgery?.toString()} />
        </dl>
      </div>

      {/* Monitoring Info */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6">
        <h3 className="text-sm font-medium text-zinc-400 mb-4">Monitoring Status</h3>
        <dl className="space-y-3">
          <InfoRow label="Enrollment Status" value={patient.enrollment_status} />
          <InfoRow label="Monitoring Start" value={patient.monitoring_start_date ? formatDate(patient.monitoring_start_date) : null} />
          <InfoRow label="Monitoring End" value={patient.monitoring_end_date ? formatDate(patient.monitoring_end_date) : null} />
          <InfoRow label="Created" value={formatDate(patient.created_at)} />
          <InfoRow label="Last Updated" value={formatDate(patient.updated_at)} />
        </dl>
      </div>

      {/* Summary Stats */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6">
        <h3 className="text-sm font-medium text-zinc-400 mb-4">Summary</h3>
        <dl className="space-y-3">
          <InfoRow label="Overall Status" value={patient.summary?.overall_status || 'No data'} />
          <InfoRow label="Active Alerts" value={patient.summary?.active_alerts_count?.toString() || '0'} />
          <InfoRow label="Critical Alerts" value={patient.summary?.active_critical_alerts_count?.toString() || '0'} />
          <InfoRow label="Last Data" value={patient.summary?.last_data_received_at ? formatTimeAgo(patient.summary.last_data_received_at) : 'None'} />
          <InfoRow label="Last Alert" value={patient.summary?.last_alert_at ? formatTimeAgo(patient.summary.last_alert_at) : 'None'} />
        </dl>
      </div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="flex justify-between">
      <dt className="text-sm text-zinc-500">{label}</dt>
      <dd className="text-sm text-white">{value || '-'}</dd>
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
      <DialogContent className="bg-zinc-950 border-zinc-800 text-white">
        <DialogHeader>
          <DialogTitle>Discharge Patient</DialogTitle>
          <DialogDescription className="text-zinc-400">
            Mark {patient.full_name} as discharged. This will end monitoring and
            disable their app access.
          </DialogDescription>
        </DialogHeader>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={onClose}
            disabled={isPending}
            className="border-zinc-700"
          >
            Cancel
          </Button>
          <Button
            onClick={handleDischarge}
            disabled={isPending}
            className="bg-emerald-600 hover:bg-emerald-700"
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
      <DialogContent className="bg-zinc-950 border-zinc-800 text-white">
        <DialogHeader>
          <DialogTitle>Acknowledge Alert</DialogTitle>
          <DialogDescription className="text-zinc-400">
            Mark this alert as acknowledged.
          </DialogDescription>
        </DialogHeader>

        {alert && (
          <div className="py-4">
            <div className="rounded-lg bg-zinc-900 p-4">
              <p className="text-sm font-medium text-white">{alert.title}</p>
              {alert.vital_type && (
                <p className="text-sm text-zinc-400 mt-1">
                  {formatVitalType(alert.vital_type)}: {alert.observed_value}
                </p>
              )}
            </div>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isPending} className="border-zinc-700">
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={isPending} className="bg-blue-600 hover:bg-blue-700">
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
      <DialogContent className="bg-zinc-950 border-zinc-800 text-white">
        <DialogHeader>
          <DialogTitle>Resolve Alert</DialogTitle>
          <DialogDescription className="text-zinc-400">
            Mark this alert as resolved.
          </DialogDescription>
        </DialogHeader>

        {alert && (
          <div className="py-4">
            <div className="rounded-lg bg-zinc-900 p-4">
              <p className="text-sm font-medium text-white">{alert.title}</p>
            </div>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isPending} className="border-zinc-700">
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={isPending} className="bg-emerald-600 hover:bg-emerald-700">
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

function formatTimeAgo(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString();
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
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
