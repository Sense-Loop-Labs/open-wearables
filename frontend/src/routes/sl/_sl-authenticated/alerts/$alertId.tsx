/**
 * Sense Loop Alert Detail Page
 * View individual alert details with acknowledge/resolve actions
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
  Info,
  Loader2,
  User,
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
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import {
  useAcknowledgeAlert,
  useResolveAlert,
  useSlAlert,
} from '@/hooks/api/use-sl-alerts';
import type { Alert, AlertSeverity, AlertStatus } from '@/lib/api/types/sense-loop';

export const Route = createFileRoute('/sl/_sl-authenticated/alerts/$alertId')({
  component: SlAlertDetailPage,
});

function SlAlertDetailPage() {
  const { alertId } = Route.useParams();
  const { data: alert, isLoading } = useSlAlert(alertId);

  const [acknowledgeDialogOpen, setAcknowledgeDialogOpen] = useState(false);
  const [resolveDialogOpen, setResolveDialogOpen] = useState(false);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-8 w-8 animate-spin text-zinc-500" />
      </div>
    );
  }

  if (!alert) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <Bell className="h-12 w-12 text-zinc-600" />
        <p className="text-zinc-500">Alert not found</p>
        <Link to="/sl/alerts">
          <Button variant="outline" className="border-zinc-700">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Alerts
          </Button>
        </Link>
      </div>
    );
  }

  const canAcknowledge = alert.status === 'active';
  const canResolve = alert.status === 'active' || alert.status === 'acknowledged';

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-4">
          <Link to="/sl/alerts">
            <Button variant="ghost" size="sm" className="text-zinc-400 hover:text-white">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <div className="flex items-center gap-3">
              <SeverityIcon severity={alert.severity} />
              <h1 className="text-2xl font-semibold text-white">{alert.title}</h1>
              <SeverityBadge severity={alert.severity} />
              <StatusBadge status={alert.status} />
            </div>
            {alert.message && (
              <p className="text-sm text-zinc-400 mt-2">{alert.message}</p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {canAcknowledge && (
            <Button
              onClick={() => setAcknowledgeDialogOpen(true)}
              variant="outline"
              className="border-blue-700 text-blue-400 hover:bg-blue-900/20"
            >
              <Check className="h-4 w-4 mr-2" />
              Acknowledge
            </Button>
          )}
          {canResolve && (
            <Button
              onClick={() => setResolveDialogOpen(true)}
              className="bg-emerald-600 hover:bg-emerald-700"
            >
              <CheckCircle2 className="h-4 w-4 mr-2" />
              Resolve
            </Button>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Info */}
        <div className="lg:col-span-2 space-y-6">
          {/* Patient Info */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-6">
            <h2 className="text-lg font-medium text-white mb-4 flex items-center gap-2">
              <User className="h-5 w-5 text-zinc-500" />
              Patient
            </h2>
            <div className="flex items-center justify-between">
              <div>
                <Link
                  to="/sl/patients/$patientId"
                  params={{ patientId: alert.patient_id }}
                  className="text-emerald-500 hover:text-emerald-400 font-medium"
                >
                  {alert.patient_name || 'Unknown Patient'}
                </Link>
                {alert.patient_mrn && (
                  <p className="text-sm text-zinc-500 mt-1">MRN: {alert.patient_mrn}</p>
                )}
              </div>
              {alert.days_post_surgery !== null && (
                <div className="text-right">
                  <p className="text-sm text-zinc-400">Post-Surgery</p>
                  <p className="text-lg font-semibold text-white">
                    Day {alert.days_post_surgery}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Vital Details */}
          {alert.vital_type && (
            <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-6">
              <h2 className="text-lg font-medium text-white mb-4 flex items-center gap-2">
                <Activity className="h-5 w-5 text-zinc-500" />
                Vital Sign Details
              </h2>
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <p className="text-sm text-zinc-500">Vital Type</p>
                  <p className="text-lg font-medium text-white mt-1">
                    {formatVitalType(alert.vital_type)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-zinc-500">Observed Value</p>
                  <p className="text-lg font-medium text-white mt-1">
                    {alert.observed_value ?? '-'}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-zinc-500">Threshold Breached</p>
                  <p className="text-lg font-medium text-white mt-1">
                    {alert.threshold_breached || '-'}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-zinc-500">Threshold Value</p>
                  <p className="text-lg font-medium text-white mt-1">
                    {alert.threshold_value ?? '-'}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Resolution Info */}
          {alert.status === 'resolved' && (
            <div className="rounded-xl border border-emerald-900 bg-emerald-950/30 p-6">
              <h2 className="text-lg font-medium text-emerald-400 mb-4 flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5" />
                Resolution
              </h2>
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <p className="text-sm text-zinc-500">Resolution Type</p>
                  <p className="text-white mt-1">
                    {formatResolutionType(alert.resolution_type)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-zinc-500">Resolved By</p>
                  <p className="text-white mt-1">
                    {alert.resolved_by_name || 'Unknown'}
                  </p>
                </div>
                {alert.resolved_at && (
                  <div>
                    <p className="text-sm text-zinc-500">Resolved At</p>
                    <p className="text-white mt-1">
                      {formatDateTime(alert.resolved_at)}
                    </p>
                  </div>
                )}
                {alert.resolution_notes && (
                  <div className="col-span-2">
                    <p className="text-sm text-zinc-500">Notes</p>
                    <p className="text-white mt-1">{alert.resolution_notes}</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Timeline */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-6">
            <h2 className="text-lg font-medium text-white mb-4 flex items-center gap-2">
              <Clock className="h-5 w-5 text-zinc-500" />
              Timeline
            </h2>
            <div className="space-y-4">
              <TimelineItem
                icon={AlertTriangle}
                label="Triggered"
                time={alert.triggered_at}
                color="text-red-500"
              />
              {alert.acknowledged_at && (
                <TimelineItem
                  icon={Check}
                  label={`Acknowledged by ${alert.acknowledged_by_name || 'Unknown'}`}
                  time={alert.acknowledged_at}
                  color="text-blue-500"
                />
              )}
              {alert.escalated_at && (
                <TimelineItem
                  icon={AlertTriangle}
                  label="Escalated"
                  time={alert.escalated_at}
                  color="text-purple-500"
                />
              )}
              {alert.resolved_at && (
                <TimelineItem
                  icon={CheckCircle2}
                  label={`Resolved by ${alert.resolved_by_name || 'Unknown'}`}
                  time={alert.resolved_at}
                  color="text-emerald-500"
                />
              )}
            </div>
          </div>

          {/* Protocol Info */}
          {alert.protocol_id && (
            <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-6">
              <h2 className="text-lg font-medium text-white mb-4 flex items-center gap-2">
                <Info className="h-5 w-5 text-zinc-500" />
                Protocol Info
              </h2>
              <div className="space-y-3">
                <div>
                  <p className="text-sm text-zinc-500">Protocol Version</p>
                  <p className="text-white mt-1">v{alert.protocol_version || 1}</p>
                </div>
                {alert.rule_id && (
                  <div>
                    <p className="text-sm text-zinc-500">Rule ID</p>
                    <p className="text-white mt-1 font-mono text-xs">
                      {alert.rule_id}
                    </p>
                  </div>
                )}
                {alert.patient_context && (
                  <div>
                    <p className="text-sm text-zinc-500">Context</p>
                    <p className="text-white mt-1">{alert.patient_context}</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Meta Info */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-6">
            <h2 className="text-lg font-medium text-white mb-4">Details</h2>
            <div className="space-y-3">
              <div>
                <p className="text-sm text-zinc-500">Category</p>
                <p className="text-white mt-1">{formatCategory(alert.category)}</p>
              </div>
              <div>
                <p className="text-sm text-zinc-500">Alert ID</p>
                <p className="text-white mt-1 font-mono text-xs">{alert.id}</p>
              </div>
              <div>
                <p className="text-sm text-zinc-500">Created</p>
                <p className="text-white mt-1">{formatDateTime(alert.created_at)}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Dialogs */}
      <AcknowledgeDialog
        alert={alert}
        open={acknowledgeDialogOpen}
        onClose={() => setAcknowledgeDialogOpen(false)}
      />

      <ResolveDialog
        alert={alert}
        open={resolveDialogOpen}
        onClose={() => setResolveDialogOpen(false)}
      />
    </div>
  );
}

// ============================================================================
// Components
// ============================================================================

function SeverityIcon({ severity }: { severity: AlertSeverity }) {
  const icons = {
    critical: <AlertTriangle className="h-6 w-6 text-red-500" />,
    warning: <AlertTriangle className="h-6 w-6 text-yellow-500" />,
    info: <Info className="h-6 w-6 text-blue-500" />,
  };

  return icons[severity] || icons.info;
}

function SeverityBadge({ severity }: { severity: AlertSeverity }) {
  const variants = {
    critical: 'bg-red-500/20 text-red-400 border-red-500/30',
    warning: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    info: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  };

  return (
    <Badge variant="outline" className={`text-xs ${variants[severity]}`}>
      {severity}
    </Badge>
  );
}

function StatusBadge({ status }: { status: AlertStatus }) {
  const variants: Record<AlertStatus, string> = {
    active: 'bg-red-500/20 text-red-400 border-red-500/30',
    acknowledged: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    resolved: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    escalated: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  };

  return (
    <Badge variant="outline" className={`text-xs ${variants[status]}`}>
      {status}
    </Badge>
  );
}

interface TimelineItemProps {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  time: string;
  color: string;
}

function TimelineItem({ icon: Icon, label, time, color }: TimelineItemProps) {
  return (
    <div className="flex items-start gap-3">
      <div className={`mt-0.5 ${color}`}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="flex-1">
        <p className="text-sm text-white">{label}</p>
        <p className="text-xs text-zinc-500">{formatDateTime(time)}</p>
      </div>
    </div>
  );
}

// ============================================================================
// Dialogs
// ============================================================================

interface AcknowledgeDialogProps {
  alert: Alert;
  open: boolean;
  onClose: () => void;
}

function AcknowledgeDialog({ alert, open, onClose }: AcknowledgeDialogProps) {
  const [notes, setNotes] = useState('');
  const { mutate: acknowledge, isPending } = useAcknowledgeAlert();

  const handleSubmit = () => {
    acknowledge(
      { id: alert.id, data: notes ? { notes } : undefined },
      {
        onSuccess: () => {
          setNotes('');
          onClose();
        },
      }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="bg-zinc-950 border-zinc-800 text-white">
        <DialogHeader>
          <DialogTitle>Acknowledge Alert</DialogTitle>
          <DialogDescription className="text-zinc-400">
            Mark this alert as acknowledged.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="notes" className="text-zinc-300">
              Notes (optional)
            </Label>
            <Textarea
              id="notes"
              placeholder="Add any relevant notes..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="bg-zinc-900 border-zinc-700 text-white placeholder:text-zinc-500"
              rows={3}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isPending} className="border-zinc-700">
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={isPending} className="bg-blue-600 hover:bg-blue-700">
            {isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <>
                <Check className="h-4 w-4 mr-2" />
                Acknowledge
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface ResolveDialogProps {
  alert: Alert;
  open: boolean;
  onClose: () => void;
}

function ResolveDialog({ alert, open, onClose }: ResolveDialogProps) {
  const [resolutionType, setResolutionType] = useState('');
  const [notes, setNotes] = useState('');
  const { mutate: resolve, isPending } = useResolveAlert();

  const handleSubmit = () => {
    if (!resolutionType) return;

    resolve(
      {
        id: alert.id,
        data: {
          resolution_type: resolutionType,
          resolution_notes: notes || undefined,
        },
      },
      {
        onSuccess: () => {
          setResolutionType('');
          setNotes('');
          onClose();
        },
      }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="bg-zinc-950 border-zinc-800 text-white">
        <DialogHeader>
          <DialogTitle>Resolve Alert</DialogTitle>
          <DialogDescription className="text-zinc-400">
            Mark this alert as resolved.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="resolution-type" className="text-zinc-300">
              Resolution Type <span className="text-red-500">*</span>
            </Label>
            <Select value={resolutionType} onValueChange={setResolutionType}>
              <SelectTrigger className="bg-zinc-900 border-zinc-700 text-white">
                <SelectValue placeholder="Select resolution type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="patient_contacted">Patient Contacted</SelectItem>
                <SelectItem value="intervention_performed">Intervention Performed</SelectItem>
                <SelectItem value="false_positive">False Positive</SelectItem>
                <SelectItem value="self_resolved">Self Resolved</SelectItem>
                <SelectItem value="patient_discharged">Patient Discharged</SelectItem>
                <SelectItem value="other">Other</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="notes" className="text-zinc-300">
              Resolution Notes
            </Label>
            <Textarea
              id="notes"
              placeholder="Describe the resolution..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="bg-zinc-900 border-zinc-700 text-white placeholder:text-zinc-500"
              rows={3}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isPending} className="border-zinc-700">
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={isPending || !resolutionType}
            className="bg-emerald-600 hover:bg-emerald-700"
          >
            {isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <>
                <CheckCircle2 className="h-4 w-4 mr-2" />
                Resolve
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ============================================================================
// Helpers
// ============================================================================

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

function formatCategory(category: string): string {
  const names: Record<string, string> = {
    vital_sign: 'Vital Sign',
    questionnaire: 'Questionnaire',
    activity: 'Activity',
    system: 'System',
  };

  return names[category] || category.replace(/_/g, ' ');
}

function formatResolutionType(type: string | null): string {
  if (!type) return '-';

  const names: Record<string, string> = {
    patient_contacted: 'Patient Contacted',
    intervention_performed: 'Intervention Performed',
    false_positive: 'False Positive',
    self_resolved: 'Self Resolved',
    patient_discharged: 'Patient Discharged',
    other: 'Other',
  };

  return names[type] || type.replace(/_/g, ' ');
}

function formatDateTime(dateString: string): string {
  return new Date(dateString).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}
