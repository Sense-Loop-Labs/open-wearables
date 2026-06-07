/**
 * Sense Loop Dashboard
 * Main overview page with key metrics and recent activity
 */

import { createFileRoute, Link } from '@tanstack/react-router';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Bell,
  Heart,
  TrendingUp,
  Users,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  useSlCriticalPatients,
  useSlDashboardOverview,
  useSlRecentAlerts,
} from '@/hooks/api/use-sl-dashboard';

export const Route = createFileRoute('/sl/_sl-authenticated/dashboard')({
  component: SlDashboardPage,
});

function SlDashboardPage() {
  const { data: overview, isLoading: isLoadingOverview } = useSlDashboardOverview();
  const { data: criticalPatients, isLoading: isLoadingCritical } = useSlCriticalPatients();
  const { data: recentAlerts, isLoading: isLoadingAlerts } = useSlRecentAlerts();

  return (
    <div className="p-8 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-white">Dashboard</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Monitor patient status and alerts at a glance
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          title="Total Patients"
          value={overview?.patients.total ?? 0}
          subtitle={`${overview?.patients.active ?? 0} active`}
          icon={Users}
          loading={isLoadingOverview}
        />
        <StatsCard
          title="Active Alerts"
          value={overview?.alerts.active ?? 0}
          subtitle={`${overview?.alerts.critical ?? 0} critical`}
          icon={Bell}
          loading={isLoadingOverview}
          variant={overview?.alerts.critical ? 'critical' : 'default'}
        />
        <StatsCard
          title="Critical Patients"
          value={overview?.patients.critical ?? 0}
          subtitle={`${overview?.patients.warning ?? 0} warning`}
          icon={AlertTriangle}
          loading={isLoadingOverview}
          variant={overview?.patients.critical ? 'critical' : 'default'}
        />
        <StatsCard
          title="Resolved Today"
          value={overview?.alerts.resolved_today ?? 0}
          subtitle={`${overview?.activity.alerts_7d ?? 0} this week`}
          icon={TrendingUp}
          loading={isLoadingOverview}
          variant="success"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Critical Patients */}
        <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-medium text-white">Critical Patients</h2>
            <Link to="/sl/patients">
              <Button variant="ghost" size="sm" className="text-zinc-400 hover:text-white">
                View all
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </div>

          {isLoadingCritical ? (
            <LoadingSkeleton count={3} />
          ) : !criticalPatients?.length ? (
            <EmptyState
              icon={Heart}
              title="No critical patients"
              description="All patients are within normal parameters"
            />
          ) : (
            <div className="space-y-3">
              {criticalPatients.slice(0, 5).map((patient) => (
                <Link
                  key={patient.id}
                  to="/sl/patients/$patientId"
                  params={{ patientId: patient.id }}
                  className="flex items-center justify-between p-3 rounded-lg bg-zinc-900 hover:bg-zinc-800 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <StatusIndicator status={patient.status} />
                    <div>
                      <p className="text-sm font-medium text-white">{patient.name}</p>
                      <p className="text-xs text-zinc-500">
                        {patient.mrn ? `MRN: ${patient.mrn}` : 'No MRN'}
                        {patient.days_post_surgery !== null && (
                          <span> · Day {patient.days_post_surgery}</span>
                        )}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {patient.critical_alerts > 0 && (
                      <Badge variant="destructive" className="text-xs">
                        {patient.critical_alerts} critical
                      </Badge>
                    )}
                    {patient.total_alerts > patient.critical_alerts && (
                      <Badge variant="outline" className="text-xs border-yellow-600 text-yellow-500">
                        {patient.total_alerts - patient.critical_alerts} warning
                      </Badge>
                    )}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Recent Alerts */}
        <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-medium text-white">Recent Alerts</h2>
            <Link to="/sl/alerts">
              <Button variant="ghost" size="sm" className="text-zinc-400 hover:text-white">
                View all
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </div>

          {isLoadingAlerts ? (
            <LoadingSkeleton count={3} />
          ) : !recentAlerts?.length ? (
            <EmptyState
              icon={Bell}
              title="No recent alerts"
              description="No alerts have been triggered recently"
            />
          ) : (
            <div className="space-y-3">
              {recentAlerts.slice(0, 5).map((alert) => (
                <Link
                  key={alert.id}
                  to="/sl/alerts/$alertId"
                  params={{ alertId: alert.id }}
                  className="flex items-center justify-between p-3 rounded-lg bg-zinc-900 hover:bg-zinc-800 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <SeverityIndicator severity={alert.severity} />
                    <div>
                      <p className="text-sm font-medium text-white">{alert.title}</p>
                      <p className="text-xs text-zinc-500">
                        {alert.patient_name || 'Unknown patient'}
                        {alert.vital_type && (
                          <span> · {alert.vital_type.replace('_', ' ')}</span>
                        )}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <Badge
                      variant={alert.status === 'active' ? 'destructive' : 'outline'}
                      className="text-xs"
                    >
                      {alert.status}
                    </Badge>
                    <p className="text-xs text-zinc-500 mt-1">
                      {formatTimeAgo(alert.triggered_at)}
                    </p>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Activity Summary */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-6">
        <h2 className="text-lg font-medium text-white mb-4">7-Day Activity</h2>
        <div className="grid grid-cols-3 gap-4">
          <div className="text-center p-4 rounded-lg bg-zinc-900">
            <p className="text-3xl font-bold text-white">
              {overview?.activity.new_patients_7d ?? 0}
            </p>
            <p className="text-sm text-zinc-500 mt-1">New Patients</p>
          </div>
          <div className="text-center p-4 rounded-lg bg-zinc-900">
            <p className="text-3xl font-bold text-white">
              {overview?.activity.alerts_7d ?? 0}
            </p>
            <p className="text-sm text-zinc-500 mt-1">Alerts Triggered</p>
          </div>
          <div className="text-center p-4 rounded-lg bg-zinc-900">
            <p className="text-3xl font-bold text-white">
              {overview?.activity.discharged_7d ?? 0}
            </p>
            <p className="text-sm text-zinc-500 mt-1">Discharged</p>
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Components
// ============================================================================

interface StatsCardProps {
  title: string;
  value: number;
  subtitle: string;
  icon: React.ComponentType<{ className?: string }>;
  loading?: boolean;
  variant?: 'default' | 'critical' | 'success';
}

function StatsCard({ title, value, subtitle, icon: Icon, loading, variant = 'default' }: StatsCardProps) {
  const borderColors = {
    default: 'border-zinc-800',
    critical: 'border-red-900',
    success: 'border-emerald-900',
  };

  const iconColors = {
    default: 'text-zinc-400',
    critical: 'text-red-500',
    success: 'text-emerald-500',
  };

  return (
    <div className={`rounded-xl border ${borderColors[variant]} bg-zinc-950 p-6`}>
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-zinc-400">{title}</p>
        <Icon className={`h-5 w-5 ${iconColors[variant]}`} />
      </div>
      {loading ? (
        <div className="mt-3 h-8 w-20 animate-pulse rounded bg-zinc-800" />
      ) : (
        <p className="mt-3 text-3xl font-bold text-white">{value.toLocaleString()}</p>
      )}
      <p className="mt-1 text-sm text-zinc-500">{subtitle}</p>
    </div>
  );
}

function StatusIndicator({ status }: { status: string }) {
  const colors = {
    critical: 'bg-red-500',
    warning: 'bg-yellow-500',
    good: 'bg-emerald-500',
    no_data: 'bg-zinc-500',
  };

  return (
    <span
      className={`h-3 w-3 rounded-full ${colors[status as keyof typeof colors] || colors.no_data}`}
    />
  );
}

function SeverityIndicator({ severity }: { severity: string }) {
  const colors = {
    critical: 'bg-red-500',
    warning: 'bg-yellow-500',
    info: 'bg-blue-500',
  };

  return (
    <span
      className={`h-3 w-3 rounded-full ${colors[severity as keyof typeof colors] || 'bg-zinc-500'}`}
    />
  );
}

function LoadingSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="h-16 animate-pulse rounded-lg bg-zinc-900" />
      ))}
    </div>
  );
}

function EmptyState({
  icon: Icon,
  title,
  description,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-8 text-center">
      <div className="rounded-full bg-zinc-800 p-3 mb-3">
        <Icon className="h-6 w-6 text-zinc-500" />
      </div>
      <p className="text-sm font-medium text-zinc-300">{title}</p>
      <p className="text-xs text-zinc-500 mt-1">{description}</p>
    </div>
  );
}

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
