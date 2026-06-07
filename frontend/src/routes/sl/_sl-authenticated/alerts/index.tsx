/**
 * Sense Loop Alerts List Page
 * List and manage alerts with filtering, acknowledge and resolve actions
 */

import { createFileRoute, Link } from '@tanstack/react-router';
import {
  AlertTriangle,
  Bell,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Filter,
  Info,
  Loader2,
  Search,
  X,
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
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Textarea } from '@/components/ui/textarea';
import {
  useAcknowledgeAlert,
  useResolveAlert,
  useSlAlerts,
  useSlAlertStats,
} from '@/hooks/api/use-sl-alerts';
import type {
  Alert,
  AlertCategory,
  AlertQueryParams,
  AlertSeverity,
  AlertStatus,
} from '@/lib/api/types/sense-loop';

export const Route = createFileRoute('/sl/_sl-authenticated/alerts/')({
  component: SlAlertsPage,
});

function SlAlertsPage() {
  const [filters, setFilters] = useState<AlertQueryParams>({
    page: 1,
    page_size: 20,
    status: 'active',
  });
  const [search, setSearch] = useState('');

  // Dialog states
  const [acknowledgeDialog, setAcknowledgeDialog] = useState<Alert | null>(null);
  const [resolveDialog, setResolveDialog] = useState<Alert | null>(null);

  const { data: alerts, isLoading } = useSlAlerts(filters);
  const { data: stats } = useSlAlertStats();

  const handleFilterChange = (key: keyof AlertQueryParams, value: string | undefined) => {
    setFilters((prev) => ({
      ...prev,
      [key]: value === 'all' ? undefined : value,
      page: 1, // Reset to first page on filter change
    }));
  };

  const handlePageChange = (page: number) => {
    setFilters((prev) => ({ ...prev, page }));
  };

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Alerts</h1>
          <p className="text-sm text-zinc-500 mt-1">
            Monitor and respond to patient alerts
          </p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <StatCard
          label="Active"
          value={stats?.active ?? 0}
          variant="default"
        />
        <StatCard
          label="Critical"
          value={stats?.critical ?? 0}
          variant="critical"
        />
        <StatCard
          label="Warning"
          value={stats?.warning ?? 0}
          variant="warning"
        />
        <StatCard
          label="Acknowledged"
          value={stats?.acknowledged ?? 0}
          variant="info"
        />
        <StatCard
          label="Resolved Today"
          value={stats?.resolved_today ?? 0}
          variant="success"
        />
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4">
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
          <Input
            placeholder="Search by patient name or MRN..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10 bg-zinc-900 border-zinc-700 text-white placeholder:text-zinc-500"
          />
        </div>

        <Select
          value={filters.status || 'all'}
          onValueChange={(v) => handleFilterChange('status', v)}
        >
          <SelectTrigger className="w-[140px] bg-zinc-900 border-zinc-700 text-white">
            <Filter className="h-4 w-4 mr-2" />
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="acknowledged">Acknowledged</SelectItem>
            <SelectItem value="resolved">Resolved</SelectItem>
            <SelectItem value="escalated">Escalated</SelectItem>
          </SelectContent>
        </Select>

        <Select
          value={filters.severity || 'all'}
          onValueChange={(v) => handleFilterChange('severity', v as AlertSeverity)}
        >
          <SelectTrigger className="w-[140px] bg-zinc-900 border-zinc-700 text-white">
            <SelectValue placeholder="Severity" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Severity</SelectItem>
            <SelectItem value="critical">Critical</SelectItem>
            <SelectItem value="warning">Warning</SelectItem>
            <SelectItem value="info">Info</SelectItem>
          </SelectContent>
        </Select>

        <Select
          value={filters.category || 'all'}
          onValueChange={(v) => handleFilterChange('category', v as AlertCategory)}
        >
          <SelectTrigger className="w-[160px] bg-zinc-900 border-zinc-700 text-white">
            <SelectValue placeholder="Category" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Categories</SelectItem>
            <SelectItem value="vital_sign">Vital Sign</SelectItem>
            <SelectItem value="questionnaire">Questionnaire</SelectItem>
            <SelectItem value="activity">Activity</SelectItem>
            <SelectItem value="system">System</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-950 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-zinc-800 hover:bg-transparent">
              <TableHead className="text-zinc-400">Alert</TableHead>
              <TableHead className="text-zinc-400">Patient</TableHead>
              <TableHead className="text-zinc-400">Severity</TableHead>
              <TableHead className="text-zinc-400">Status</TableHead>
              <TableHead className="text-zinc-400">Details</TableHead>
              <TableHead className="text-zinc-400">Triggered</TableHead>
              <TableHead className="text-zinc-400 text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin mx-auto text-zinc-500" />
                </TableCell>
              </TableRow>
            ) : !alerts?.items?.length ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-8">
                  <Bell className="h-8 w-8 mx-auto text-zinc-600 mb-2" />
                  <p className="text-zinc-500">No alerts found</p>
                </TableCell>
              </TableRow>
            ) : (
              alerts.items
                .filter(
                  (alert) =>
                    !search ||
                    alert.patient_name?.toLowerCase().includes(search.toLowerCase()) ||
                    alert.patient_mrn?.toLowerCase().includes(search.toLowerCase()) ||
                    alert.title.toLowerCase().includes(search.toLowerCase())
                )
                .map((alert) => (
                  <AlertRow
                    key={alert.id}
                    alert={alert}
                    onAcknowledge={() => setAcknowledgeDialog(alert)}
                    onResolve={() => setResolveDialog(alert)}
                  />
                ))
            )}
          </TableBody>
        </Table>

        {/* Pagination */}
        {alerts && alerts.pages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-zinc-800">
            <p className="text-sm text-zinc-500">
              Showing {(alerts.page - 1) * alerts.page_size + 1} to{' '}
              {Math.min(alerts.page * alerts.page_size, alerts.total)} of {alerts.total} alerts
            </p>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => handlePageChange(alerts.page - 1)}
                disabled={alerts.page <= 1}
                className="border-zinc-700"
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="text-sm text-zinc-400">
                Page {alerts.page} of {alerts.pages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handlePageChange(alerts.page + 1)}
                disabled={alerts.page >= alerts.pages}
                className="border-zinc-700"
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Acknowledge Dialog */}
      <AcknowledgeAlertDialog
        alert={acknowledgeDialog}
        onClose={() => setAcknowledgeDialog(null)}
      />

      {/* Resolve Dialog */}
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

interface StatCardProps {
  label: string;
  value: number;
  variant: 'default' | 'critical' | 'warning' | 'info' | 'success';
}

function StatCard({ label, value, variant }: StatCardProps) {
  const colors = {
    default: 'bg-zinc-900 border-zinc-800',
    critical: 'bg-red-950/50 border-red-900',
    warning: 'bg-yellow-950/50 border-yellow-900',
    info: 'bg-blue-950/50 border-blue-900',
    success: 'bg-emerald-950/50 border-emerald-900',
  };

  const textColors = {
    default: 'text-white',
    critical: 'text-red-400',
    warning: 'text-yellow-400',
    info: 'text-blue-400',
    success: 'text-emerald-400',
  };

  return (
    <div className={`rounded-lg border p-4 ${colors[variant]}`}>
      <p className="text-sm text-zinc-400">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${textColors[variant]}`}>
        {value.toLocaleString()}
      </p>
    </div>
  );
}

interface AlertRowProps {
  alert: Alert;
  onAcknowledge: () => void;
  onResolve: () => void;
}

function AlertRow({ alert, onAcknowledge, onResolve }: AlertRowProps) {
  return (
    <TableRow className="border-zinc-800 hover:bg-zinc-900/50">
      <TableCell>
        <div className="flex items-center gap-3">
          <SeverityIcon severity={alert.severity} />
          <div>
            <p className="text-sm font-medium text-white">{alert.title}</p>
            {alert.message && (
              <p className="text-xs text-zinc-500 line-clamp-1">{alert.message}</p>
            )}
          </div>
        </div>
      </TableCell>
      <TableCell>
        <Link
          to="/sl/patients/$patientId"
          params={{ patientId: alert.patient_id }}
          className="text-sm text-emerald-500 hover:text-emerald-400"
        >
          {alert.patient_name || 'Unknown'}
        </Link>
        {alert.patient_mrn && (
          <p className="text-xs text-zinc-500">MRN: {alert.patient_mrn}</p>
        )}
      </TableCell>
      <TableCell>
        <SeverityBadge severity={alert.severity} />
      </TableCell>
      <TableCell>
        <StatusBadge status={alert.status} />
      </TableCell>
      <TableCell>
        <AlertDetails alert={alert} />
      </TableCell>
      <TableCell>
        <div className="text-sm text-zinc-400">
          {formatTimeAgo(alert.triggered_at)}
        </div>
        {alert.days_post_surgery !== null && (
          <p className="text-xs text-zinc-500">Day {alert.days_post_surgery}</p>
        )}
      </TableCell>
      <TableCell className="text-right">
        <AlertActions
          alert={alert}
          onAcknowledge={onAcknowledge}
          onResolve={onResolve}
        />
      </TableCell>
    </TableRow>
  );
}

function SeverityIcon({ severity }: { severity: AlertSeverity }) {
  const icons = {
    critical: <AlertTriangle className="h-5 w-5 text-red-500" />,
    warning: <AlertTriangle className="h-5 w-5 text-yellow-500" />,
    info: <Info className="h-5 w-5 text-blue-500" />,
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

  const icons: Record<AlertStatus, React.ReactNode> = {
    active: <Bell className="h-3 w-3 mr-1" />,
    acknowledged: <Check className="h-3 w-3 mr-1" />,
    resolved: <CheckCircle2 className="h-3 w-3 mr-1" />,
    escalated: <AlertTriangle className="h-3 w-3 mr-1" />,
  };

  return (
    <Badge variant="outline" className={`text-xs ${variants[status]}`}>
      {icons[status]}
      {status}
    </Badge>
  );
}

function AlertDetails({ alert }: { alert: Alert }) {
  if (!alert.vital_type && !alert.observed_value) {
    return <span className="text-sm text-zinc-500">-</span>;
  }

  return (
    <div className="text-sm">
      {alert.vital_type && (
        <p className="text-zinc-300">
          {formatVitalType(alert.vital_type)}
        </p>
      )}
      {alert.observed_value !== null && (
        <p className="text-xs text-zinc-500">
          Value: {alert.observed_value}
          {alert.threshold_value !== null && (
            <span> (threshold: {alert.threshold_value})</span>
          )}
        </p>
      )}
    </div>
  );
}

function AlertActions({
  alert,
  onAcknowledge,
  onResolve,
}: {
  alert: Alert;
  onAcknowledge: () => void;
  onResolve: () => void;
}) {
  const canAcknowledge = alert.status === 'active';
  const canResolve = alert.status === 'active' || alert.status === 'acknowledged';

  return (
    <div className="flex items-center justify-end gap-2">
      {canAcknowledge && (
        <Button
          variant="outline"
          size="sm"
          onClick={onAcknowledge}
          className="border-zinc-700 hover:bg-blue-900/20 hover:border-blue-700"
        >
          <Check className="h-4 w-4" />
        </Button>
      )}
      {canResolve && (
        <Button
          variant="outline"
          size="sm"
          onClick={onResolve}
          className="border-zinc-700 hover:bg-emerald-900/20 hover:border-emerald-700"
        >
          <CheckCircle2 className="h-4 w-4" />
        </Button>
      )}
      {alert.status === 'resolved' && (
        <span className="text-xs text-zinc-500">
          {alert.resolved_by_name ? `by ${alert.resolved_by_name}` : 'Resolved'}
        </span>
      )}
    </div>
  );
}

// ============================================================================
// Dialogs
// ============================================================================

interface AcknowledgeAlertDialogProps {
  alert: Alert | null;
  onClose: () => void;
}

function AcknowledgeAlertDialog({ alert, onClose }: AcknowledgeAlertDialogProps) {
  const [notes, setNotes] = useState('');
  const { mutate: acknowledge, isPending } = useAcknowledgeAlert();

  const handleSubmit = () => {
    if (!alert) return;

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
    <Dialog open={!!alert} onOpenChange={() => onClose()}>
      <DialogContent className="bg-zinc-950 border-zinc-800 text-white">
        <DialogHeader>
          <DialogTitle>Acknowledge Alert</DialogTitle>
          <DialogDescription className="text-zinc-400">
            Mark this alert as acknowledged. Add optional notes about the action taken.
          </DialogDescription>
        </DialogHeader>

        {alert && (
          <div className="space-y-4 py-4">
            <div className="rounded-lg bg-zinc-900 p-4 space-y-2">
              <div className="flex items-center gap-2">
                <SeverityBadge severity={alert.severity} />
                <span className="text-sm font-medium text-white">{alert.title}</span>
              </div>
              <p className="text-sm text-zinc-400">
                Patient: {alert.patient_name || 'Unknown'}
              </p>
              {alert.vital_type && (
                <p className="text-sm text-zinc-400">
                  {formatVitalType(alert.vital_type)}: {alert.observed_value}
                </p>
              )}
            </div>

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
        )}

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
            onClick={handleSubmit}
            disabled={isPending}
            className="bg-blue-600 hover:bg-blue-700"
          >
            {isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Acknowledging...
              </>
            ) : (
              <>
                <Check className="mr-2 h-4 w-4" />
                Acknowledge
              </>
            )}
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
  const [resolutionType, setResolutionType] = useState('');
  const [notes, setNotes] = useState('');
  const { mutate: resolve, isPending } = useResolveAlert();

  const handleSubmit = () => {
    if (!alert || !resolutionType) return;

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
    <Dialog open={!!alert} onOpenChange={() => onClose()}>
      <DialogContent className="bg-zinc-950 border-zinc-800 text-white">
        <DialogHeader>
          <DialogTitle>Resolve Alert</DialogTitle>
          <DialogDescription className="text-zinc-400">
            Mark this alert as resolved. Select a resolution type and add notes.
          </DialogDescription>
        </DialogHeader>

        {alert && (
          <div className="space-y-4 py-4">
            <div className="rounded-lg bg-zinc-900 p-4 space-y-2">
              <div className="flex items-center gap-2">
                <SeverityBadge severity={alert.severity} />
                <span className="text-sm font-medium text-white">{alert.title}</span>
              </div>
              <p className="text-sm text-zinc-400">
                Patient: {alert.patient_name || 'Unknown'}
              </p>
              {alert.vital_type && (
                <p className="text-sm text-zinc-400">
                  {formatVitalType(alert.vital_type)}: {alert.observed_value}
                </p>
              )}
            </div>

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
              <Label htmlFor="resolution-notes" className="text-zinc-300">
                Resolution Notes
              </Label>
              <Textarea
                id="resolution-notes"
                placeholder="Describe the resolution..."
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="bg-zinc-900 border-zinc-700 text-white placeholder:text-zinc-500"
                rows={3}
              />
            </div>
          </div>
        )}

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
            onClick={handleSubmit}
            disabled={isPending || !resolutionType}
            className="bg-emerald-600 hover:bg-emerald-700"
          >
            {isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Resolving...
              </>
            ) : (
              <>
                <CheckCircle2 className="mr-2 h-4 w-4" />
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
