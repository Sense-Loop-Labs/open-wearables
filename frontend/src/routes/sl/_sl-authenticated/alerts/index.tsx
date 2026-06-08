/**
 * Sense Loop Alerts List Page
 * Clinical-themed alert management with filtering, acknowledge and resolve actions
 */

import { createFileRoute, Link } from '@tanstack/react-router';
import {
  AlertTriangle,
  Bell,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Filter,
  Info,
  Search,
} from 'lucide-react';
import { useState } from 'react';
import { cn } from '@/lib/utils';

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
      page: 1,
    }));
  };

  const handlePageChange = (page: number) => {
    setFilters((prev) => ({ ...prev, page }));
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="sl-page-header">
        <h1 className="sl-page-title">Alerts</h1>
        <p className="sl-page-subtitle">Monitor and respond to patient alerts</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <StatCard label="Active" value={stats?.active ?? 0} variant="default" />
        <StatCard label="Critical" value={stats?.critical ?? 0} variant="critical" />
        <StatCard label="Warning" value={stats?.warning ?? 0} variant="warning" />
        <StatCard label="Acknowledged" value={stats?.acknowledged ?? 0} variant="info" />
        <StatCard label="Resolved Today" value={stats?.resolved_today ?? 0} variant="success" />
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4">
        <div className="sl-search-input flex-1 min-w-[200px] max-w-md">
          <Search className="icon" />
          <input
            type="text"
            placeholder="Search by patient name or MRN..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-[var(--sl-text-muted)]" />
          <select
            value={filters.status || 'all'}
            onChange={(e) => handleFilterChange('status', e.target.value)}
            className="sl-select"
          >
            <option value="all">All Status</option>
            <option value="active">Active</option>
            <option value="acknowledged">Acknowledged</option>
            <option value="resolved">Resolved</option>
            <option value="escalated">Escalated</option>
          </select>
        </div>

        <select
          value={filters.severity || 'all'}
          onChange={(e) => handleFilterChange('severity', e.target.value as AlertSeverity)}
          className="sl-select"
        >
          <option value="all">All Severity</option>
          <option value="critical">Critical</option>
          <option value="warning">Warning</option>
          <option value="info">Info</option>
        </select>

        <select
          value={filters.category || 'all'}
          onChange={(e) => handleFilterChange('category', e.target.value as AlertCategory)}
          className="sl-select"
        >
          <option value="all">All Categories</option>
          <option value="vital_sign">Vital Sign</option>
          <option value="questionnaire">Questionnaire</option>
          <option value="activity">Activity</option>
          <option value="system">System</option>
        </select>
      </div>

      {/* Table */}
      <div className="sl-table-container">
        {isLoading ? (
          <div className="sl-no-data">
            <div className="sl-spinner" />
            <span className="ml-2">Loading alerts...</span>
          </div>
        ) : !alerts?.items?.length ? (
          <div className="flex flex-col items-center justify-center py-12">
            <Bell className="h-8 w-8 text-[var(--sl-text-muted)] mb-2" />
            <p className="text-[var(--sl-text-muted)]">No alerts found</p>
          </div>
        ) : (
          <>
            <table className="sl-table">
              <thead>
                <tr>
                  <th>Alert</th>
                  <th>Patient</th>
                  <th>Severity</th>
                  <th>Status</th>
                  <th>Details</th>
                  <th>Triggered</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {alerts.items
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
                  ))}
              </tbody>
            </table>

            {/* Pagination */}
            {alerts.pages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-[var(--sl-border)]">
                <p className="text-sm text-[var(--sl-text-muted)]">
                  Showing {(alerts.page - 1) * alerts.page_size + 1} to{' '}
                  {Math.min(alerts.page * alerts.page_size, alerts.total)} of {alerts.total} alerts
                </p>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handlePageChange(alerts.page - 1)}
                    disabled={alerts.page <= 1}
                    className="sl-btn sl-btn-secondary p-2"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <span className="text-sm text-[var(--sl-text-muted)]">
                    Page {alerts.page} of {alerts.pages}
                  </span>
                  <button
                    onClick={() => handlePageChange(alerts.page + 1)}
                    disabled={alerts.page >= alerts.pages}
                    className="sl-btn sl-btn-secondary p-2"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Acknowledge Dialog */}
      {acknowledgeDialog && (
        <AcknowledgeAlertDialog
          alert={acknowledgeDialog}
          onClose={() => setAcknowledgeDialog(null)}
        />
      )}

      {/* Resolve Dialog */}
      {resolveDialog && (
        <ResolveAlertDialog
          alert={resolveDialog}
          onClose={() => setResolveDialog(null)}
        />
      )}
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
    default: 'bg-[var(--sl-bg-card)] border-[var(--sl-border)]',
    critical: 'bg-[var(--sl-risk-critical-bg)] border-[var(--sl-risk-critical)]',
    warning: 'bg-[var(--sl-risk-high-bg)] border-[var(--sl-risk-high)]',
    info: 'bg-blue-50 border-blue-500',
    success: 'bg-[var(--sl-risk-low-bg)] border-[var(--sl-risk-low)]',
  };

  const textColors = {
    default: 'text-[var(--sl-brand)]',
    critical: 'text-[var(--sl-risk-critical)]',
    warning: 'text-[var(--sl-risk-high)]',
    info: 'text-blue-700',
    success: 'text-[var(--sl-risk-low)]',
  };

  return (
    <div className={cn('rounded-lg border p-4', colors[variant])}>
      <p className="text-sm text-[var(--sl-text-muted)]">{label}</p>
      <p className={cn('text-2xl font-bold mt-1', textColors[variant])}>
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
    <tr>
      <td>
        <div className="flex items-center gap-3">
          <SeverityIcon severity={alert.severity} />
          <div>
            <p className="text-sm font-medium text-[var(--sl-text-primary)]">{alert.title}</p>
            {alert.message && (
              <p className="text-xs text-[var(--sl-text-muted)] line-clamp-1">{alert.message}</p>
            )}
          </div>
        </div>
      </td>
      <td>
        <Link
          to="/sl/patients/$patientId"
          params={{ patientId: alert.patient_id }}
          className="text-sm text-[var(--sl-brand)] hover:underline"
        >
          {alert.patient_name || 'Unknown'}
        </Link>
        {alert.patient_mrn && (
          <p className="text-xs text-[var(--sl-text-muted)]">MRN: {alert.patient_mrn}</p>
        )}
      </td>
      <td>
        <SeverityBadge severity={alert.severity} />
      </td>
      <td>
        <StatusBadge status={alert.status} />
      </td>
      <td>
        <AlertDetails alert={alert} />
      </td>
      <td>
        <div className="text-sm text-[var(--sl-text-secondary)]">
          {formatTimeAgo(alert.triggered_at)}
        </div>
        {alert.days_post_surgery !== null && (
          <p className="text-xs text-[var(--sl-text-muted)]">Day {alert.days_post_surgery}</p>
        )}
      </td>
      <td className="text-right">
        <AlertActions
          alert={alert}
          onAcknowledge={onAcknowledge}
          onResolve={onResolve}
        />
      </td>
    </tr>
  );
}

function SeverityIcon({ severity }: { severity: AlertSeverity }) {
  const icons = {
    critical: <AlertTriangle className="h-5 w-5 text-[var(--sl-risk-critical)]" />,
    warning: <AlertTriangle className="h-5 w-5 text-[var(--sl-risk-high)]" />,
    info: <Info className="h-5 w-5 text-blue-500" />,
  };

  return icons[severity] || icons.info;
}

function SeverityBadge({ severity }: { severity: AlertSeverity }) {
  const variants = {
    critical: 'sl-alert-badge critical',
    warning: 'sl-alert-badge warning',
    info: 'bg-blue-50 text-blue-700 px-2 py-0.5 rounded text-xs font-medium',
  };

  return (
    <span className={variants[severity]}>
      {severity}
    </span>
  );
}

function StatusBadge({ status }: { status: AlertStatus }) {
  const variants: Record<AlertStatus, string> = {
    active: 'bg-red-50 text-red-700',
    acknowledged: 'bg-blue-50 text-blue-700',
    resolved: 'bg-green-50 text-green-700',
    escalated: 'bg-purple-50 text-purple-700',
  };

  const icons: Record<AlertStatus, React.ReactNode> = {
    active: <Bell className="h-3 w-3 mr-1" />,
    acknowledged: <Check className="h-3 w-3 mr-1" />,
    resolved: <CheckCircle2 className="h-3 w-3 mr-1" />,
    escalated: <AlertTriangle className="h-3 w-3 mr-1" />,
  };

  return (
    <span className={cn('inline-flex items-center px-2 py-0.5 rounded text-xs font-medium', variants[status])}>
      {icons[status]}
      {status}
    </span>
  );
}

function AlertDetails({ alert }: { alert: Alert }) {
  if (!alert.vital_type && !alert.observed_value) {
    return <span className="text-sm text-[var(--sl-text-muted)]">-</span>;
  }

  return (
    <div className="text-sm">
      {alert.vital_type && (
        <p className="text-[var(--sl-text-secondary)]">
          {formatVitalType(alert.vital_type)}
        </p>
      )}
      {alert.observed_value !== null && (
        <p className="text-xs text-[var(--sl-text-muted)]">
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
        <button
          onClick={onAcknowledge}
          className="sl-btn sl-btn-secondary p-2"
          title="Acknowledge"
        >
          <Check className="w-4 h-4" />
        </button>
      )}
      {canResolve && (
        <button
          onClick={onResolve}
          className="sl-btn sl-btn-primary p-2"
          title="Resolve"
        >
          <CheckCircle2 className="w-4 h-4" />
        </button>
      )}
      {alert.status === 'resolved' && (
        <span className="text-xs text-[var(--sl-text-muted)]">
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
  alert: Alert;
  onClose: () => void;
}

function AcknowledgeAlertDialog({ alert, onClose }: AcknowledgeAlertDialogProps) {
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
    <div className="sl-modal-overlay" onClick={onClose}>
      <div className="sl-modal" onClick={(e) => e.stopPropagation()}>
        <div className="sl-modal-header">
          <h3 className="sl-modal-title">Acknowledge Alert</h3>
          <button onClick={onClose} className="sl-btn sl-btn-ghost p-1">&times;</button>
        </div>

        <div className="sl-modal-body">
          <div className="p-4 rounded-lg bg-[var(--sl-bg-muted)] space-y-2">
            <div className="flex items-center gap-2">
              <SeverityBadge severity={alert.severity} />
              <span className="text-sm font-medium">{alert.title}</span>
            </div>
            <p className="text-sm text-[var(--sl-text-muted)]">
              Patient: {alert.patient_name || 'Unknown'}
            </p>
            {alert.vital_type && (
              <p className="text-sm text-[var(--sl-text-muted)]">
                {formatVitalType(alert.vital_type)}: {alert.observed_value}
              </p>
            )}
          </div>

          <div className="sl-form-group">
            <label className="sl-form-label">Notes (optional)</label>
            <textarea
              placeholder="Add any relevant notes..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="sl-form-textarea"
              rows={3}
            />
          </div>
        </div>

        <div className="sl-modal-footer">
          <button onClick={onClose} disabled={isPending} className="sl-btn sl-btn-ghost">
            Cancel
          </button>
          <button onClick={handleSubmit} disabled={isPending} className="sl-btn sl-btn-primary">
            {isPending ? 'Acknowledging...' : 'Acknowledge'}
          </button>
        </div>
      </div>
    </div>
  );
}

interface ResolveAlertDialogProps {
  alert: Alert;
  onClose: () => void;
}

function ResolveAlertDialog({ alert, onClose }: ResolveAlertDialogProps) {
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
    <div className="sl-modal-overlay" onClick={onClose}>
      <div className="sl-modal" onClick={(e) => e.stopPropagation()}>
        <div className="sl-modal-header">
          <h3 className="sl-modal-title">Resolve Alert</h3>
          <button onClick={onClose} className="sl-btn sl-btn-ghost p-1">&times;</button>
        </div>

        <div className="sl-modal-body">
          <div className="p-4 rounded-lg bg-[var(--sl-bg-muted)] space-y-2">
            <div className="flex items-center gap-2">
              <SeverityBadge severity={alert.severity} />
              <span className="text-sm font-medium">{alert.title}</span>
            </div>
            <p className="text-sm text-[var(--sl-text-muted)]">
              Patient: {alert.patient_name || 'Unknown'}
            </p>
            {alert.vital_type && (
              <p className="text-sm text-[var(--sl-text-muted)]">
                {formatVitalType(alert.vital_type)}: {alert.observed_value}
              </p>
            )}
          </div>

          <div className="sl-form-group">
            <label className="sl-form-label">
              Resolution Type <span className="text-red-500">*</span>
            </label>
            <select
              value={resolutionType}
              onChange={(e) => setResolutionType(e.target.value)}
              className="sl-select w-full"
            >
              <option value="">Select resolution type</option>
              <option value="patient_contacted">Patient Contacted</option>
              <option value="intervention_performed">Intervention Performed</option>
              <option value="false_positive">False Positive</option>
              <option value="self_resolved">Self Resolved</option>
              <option value="patient_discharged">Patient Discharged</option>
              <option value="other">Other</option>
            </select>
          </div>

          <div className="sl-form-group">
            <label className="sl-form-label">Resolution Notes</label>
            <textarea
              placeholder="Describe the resolution..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="sl-form-textarea"
              rows={3}
            />
          </div>
        </div>

        <div className="sl-modal-footer">
          <button onClick={onClose} disabled={isPending} className="sl-btn sl-btn-ghost">
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={isPending || !resolutionType}
            className="sl-btn sl-btn-primary"
          >
            {isPending ? 'Resolving...' : 'Resolve'}
          </button>
        </div>
      </div>
    </div>
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
