/**
 * Sense Loop Dashboard
 * At-home Recovering Patients - Clinician Command Center
 */

import { useState, useMemo } from 'react';
import { createFileRoute } from '@tanstack/react-router';
import {
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  XCircle,
  Activity,
  Filter,
  Clock,
  Heart,
  Droplets,
  ArrowUpDown,
  Thermometer,
  Wind,
  Footprints,
  Moon,
  MessageSquare,
  GraduationCap,
  ArrowUpCircle,
  AlertOctagon,
  Plus,
} from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

import { useSlPatients } from '@/hooks/api/use-sl-patients';
import { useSlAlerts } from '@/hooks/api/use-sl-alerts';
import { useSlClinicalActions, useCreateSlClinicalAction } from '@/hooks/api/use-sl-clinical-actions';
import { ActionModal } from '@/components/sl/dashboard/action-modal';
import type { Patient, Alert, ClinicalAction, ClinicalActionType } from '@/lib/api/types/sense-loop';

export const Route = createFileRoute('/sl/_sl-authenticated/dashboard')({
  component: SlDashboardPage,
});

type RiskLevel = 'critical' | 'high' | 'medium' | 'low';

function getRiskLevel(daysSinceSurgery: number | null): RiskLevel {
  if (daysSinceSurgery === null) return 'low';
  if (daysSinceSurgery <= 7) return 'critical';
  if (daysSinceSurgery <= 14) return 'high';
  if (daysSinceSurgery <= 30) return 'medium';
  return 'low';
}

function calculateAge(dateOfBirth: string | null): number | null {
  if (!dateOfBirth) return null;
  const today = new Date();
  const birth = new Date(dateOfBirth);
  let age = today.getFullYear() - birth.getFullYear();
  const m = today.getMonth() - birth.getMonth();
  if (m < 0 || (m === 0 && today.getDate() < birth.getDate())) {
    age--;
  }
  return age;
}

function SlDashboardPage() {
  const [expandedPatientId, setExpandedPatientId] = useState<string | null>(null);
  const [riskFilter, setRiskFilter] = useState<string>('all');
  const [sortBy, setSortBy] = useState<string>('risk');
  const [modalPatientId, setModalPatientId] = useState<string | null>(null);

  const { data: patientsData, isLoading } = useSlPatients({ is_active: true });
  const patients = patientsData?.items ?? [];

  const createAction = useCreateSlClinicalAction();

  // Find the patient for the modal
  const modalPatient = modalPatientId ? patients.find(p => p.id === modalPatientId) : null;

  // Fetch all active alerts
  const { data: alertsData } = useSlAlerts({ status: 'active', page_size: 100 });
  const allAlerts = alertsData?.items ?? [];

  // Group alerts by patient_id
  const alertsByPatient = useMemo(() => {
    const map = new Map<string, Alert[]>();
    allAlerts.forEach((alert) => {
      const existing = map.get(alert.patient_id) ?? [];
      existing.push(alert);
      map.set(alert.patient_id, existing);
    });
    return map;
  }, [allAlerts]);

  // Calculate risk counts
  const riskCounts = useMemo(() => {
    const counts = { critical: 0, high: 0, medium: 0, low: 0, total: 0 };
    patients.forEach((patient) => {
      const risk = getRiskLevel(patient.days_post_surgery);
      counts[risk]++;
      counts.total++;
    });
    return counts;
  }, [patients]);

  // Filter and sort patients
  const filteredPatients = useMemo(() => {
    let result = [...patients];

    if (riskFilter !== 'all') {
      result = result.filter((p) => getRiskLevel(p.days_post_surgery) === riskFilter);
    }

    if (sortBy === 'risk') {
      const riskOrder = { critical: 0, high: 1, medium: 2, low: 3 };
      result.sort((a, b) => {
        const riskA = riskOrder[getRiskLevel(a.days_post_surgery)];
        const riskB = riskOrder[getRiskLevel(b.days_post_surgery)];
        return riskA - riskB;
      });
    } else if (sortBy === 'name') {
      result.sort((a, b) => a.full_name.localeCompare(b.full_name));
    } else if (sortBy === 'updated') {
      result.sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());
    }

    return result;
  }, [patients, riskFilter, sortBy]);

  const toggleExpand = (patientId: string) => {
    setExpandedPatientId(expandedPatientId === patientId ? null : patientId);
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-[var(--sl-text-primary)]">
          At-home Recovering Patients
        </h1>
        <p className="text-sm text-[var(--sl-text-muted)]">Clinician Command Center</p>
      </div>

      {/* Risk Summary Cards */}
      <div className="grid grid-cols-5 gap-4">
        <RiskCard level="critical" count={riskCounts.critical} />
        <RiskCard level="high" count={riskCounts.high} />
        <RiskCard level="medium" count={riskCounts.medium} />
        <RiskCard level="low" count={riskCounts.low} />
        <RiskCard level="total" count={riskCounts.total} />
      </div>

      {/* Filters */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-[var(--sl-text-muted)]" />
          <span className="text-sm text-[var(--sl-text-secondary)]">Filter by risk:</span>
          <select
            value={riskFilter}
            onChange={(e) => setRiskFilter(e.target.value)}
            className="sl-select"
          >
            <option value="all">All Patients</option>
            <option value="critical">Critical</option>
            <option value="high">High Risk</option>
            <option value="medium">Medium Risk</option>
            <option value="low">Low Risk</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-sm text-[var(--sl-text-secondary)]">Sort by:</span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="sl-select"
          >
            <option value="risk">Risk Level</option>
            <option value="name">Name</option>
            <option value="updated">Last Updated</option>
          </select>
        </div>
      </div>

      {/* Patient Table */}
      <div className="sl-table-container">
        {isLoading ? (
          <div className="sl-no-data">
            <div className="sl-spinner" />
            <span className="ml-2">Loading patients...</span>
          </div>
        ) : filteredPatients.length === 0 ? (
          <div className="sl-no-data">No patients found</div>
        ) : (
          <table className="sl-table">
            <thead>
              <tr>
                <th>Patient</th>
                <th>Risk</th>
                <th className="center">Heart Rate</th>
                <th className="center">SpO₂</th>
                <th className="center">BP</th>
                <th className="center">Temp</th>
                <th>Alerts</th>
                <th>Last Action</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {filteredPatients.map((patient) => (
                <PatientRow
                  key={patient.id}
                  patient={patient}
                  alerts={alertsByPatient.get(patient.id) ?? []}
                  isExpanded={expandedPatientId === patient.id}
                  onToggle={() => toggleExpand(patient.id)}
                  onOpenModal={() => setModalPatientId(patient.id)}
                />
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Action Modal */}
      <ActionModal
        isOpen={!!modalPatientId}
        onClose={() => setModalPatientId(null)}
        patientName={modalPatient?.full_name}
        isSaving={createAction.isPending}
        onSave={async (data) => {
          if (!modalPatientId) return;
          await createAction.mutateAsync({
            patientId: modalPatientId,
            data,
          });
          setModalPatientId(null);
        }}
      />
    </div>
  );
}

// ============================================================================
// Risk Summary Card
// ============================================================================

function RiskCard({ level, count }: { level: RiskLevel | 'total'; count: number }) {
  const config = {
    critical: {
      label: 'Critical',
      bg: 'bg-red-50 border-red-200',
      text: 'text-red-700',
      icon: <AlertTriangle className="w-6 h-6 text-red-400" />,
    },
    high: {
      label: 'High Risk',
      bg: 'bg-orange-50 border-orange-200',
      text: 'text-orange-700',
      icon: <XCircle className="w-6 h-6 text-orange-400" />,
    },
    medium: {
      label: 'Medium Risk',
      bg: 'bg-yellow-50 border-yellow-200',
      text: 'text-yellow-700',
      icon: null,
    },
    low: {
      label: 'Low Risk',
      bg: 'bg-green-50 border-green-200',
      text: 'text-green-700',
      icon: null,
    },
    total: {
      label: 'Total Patients',
      bg: 'bg-gray-50 border-gray-200',
      text: 'text-gray-700',
      icon: <Activity className="w-6 h-6 text-blue-400" />,
    },
  };

  const c = config[level];

  return (
    <div className={cn('rounded-lg border p-4', c.bg)}>
      <div className="flex items-start justify-between">
        <div>
          <p className={cn('text-sm font-medium', c.text)}>{c.label}</p>
          <p className={cn('text-3xl font-bold mt-1', c.text)}>{count}</p>
        </div>
        {c.icon}
      </div>
    </div>
  );
}

// ============================================================================
// Patient Row
// ============================================================================

interface PatientRowProps {
  patient: Patient;
  alerts: Alert[];
  isExpanded: boolean;
  onToggle: () => void;
  onOpenModal: () => void;
}

function PatientRow({ patient, alerts, isExpanded, onToggle, onOpenModal }: PatientRowProps) {
  const riskLevel = getRiskLevel(patient.days_post_surgery);
  const age = calculateAge(patient.date_of_birth);
  const summary = patient.summary;

  // Only fetch clinical actions when expanded
  const { data: actionsData, isLoading: actionsLoading } = useSlClinicalActions(
    patient.id,
    { page_size: 10 }
  );
  const actions = actionsData?.items ?? [];

  const createAction = useCreateSlClinicalAction();

  // Get the most recent action for the "Last Action" column
  const lastAction = actions[0];

  const formatTimeAgo = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return '1d ago';
    return `${diffDays}d ago`;
  };

  return (
    <>
      <tr
        className={cn('cursor-pointer hover:bg-gray-50 transition-colors', isExpanded && 'bg-gray-100')}
        onClick={onToggle}
      >
        {/* Patient */}
        <td>
          <div className="flex items-center gap-2">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-medium text-[var(--sl-text-primary)]">
                  {patient.full_name}
                </span>
                {patient.days_post_surgery !== null && (
                  <span className="px-1.5 py-0.5 text-xs font-medium bg-gray-100 text-gray-600 rounded">
                    S+{patient.days_post_surgery}
                  </span>
                )}
              </div>
              <p className="text-xs text-[var(--sl-text-muted)]">
                {patient.mrn && `MRN-${patient.mrn}`}
                {patient.mrn && age && ' • '}
                {age && `Age ${age}`}
              </p>
            </div>
          </div>
        </td>

        {/* Risk */}
        <td>
          <RiskBadge level={riskLevel} />
        </td>

        {/* Heart Rate */}
        <td className="center">
          <VitalValue
            icon={<Heart className="w-4 h-4" />}
            value={summary?.latest_heart_rate}
            unit="bpm"
            isAlert={summary?.latest_heart_rate ? summary.latest_heart_rate > 100 : false}
          />
        </td>

        {/* SpO2 */}
        <td className="center">
          <VitalValue
            icon={<Droplets className="w-4 h-4" />}
            value={summary?.latest_spo2}
            unit="%"
            isAlert={summary?.latest_spo2 ? summary.latest_spo2 < 92 : false}
          />
        </td>

        {/* BP */}
        <td className="center">
          <VitalValue
            icon={<ArrowUpDown className="w-4 h-4" />}
            value={summary?.latest_blood_pressure_systolic && summary?.latest_blood_pressure_diastolic
              ? `${Math.round(summary.latest_blood_pressure_systolic)}/${Math.round(summary.latest_blood_pressure_diastolic)}`
              : null}
            isAlert={summary?.latest_blood_pressure_systolic ? summary.latest_blood_pressure_systolic > 140 : false}
          />
        </td>

        {/* Temp - stored in Celsius, display in Fahrenheit */}
        <td className="center">
          <VitalValue
            icon={<Thermometer className="w-4 h-4" />}
            value={summary?.latest_temperature ? `${((summary.latest_temperature * 9/5) + 32).toFixed(1)}°F` : null}
            isAlert={summary?.latest_temperature ? summary.latest_temperature > 38.0 : false}
          />
        </td>

        {/* Alerts */}
        <td>
          <AlertBadges alerts={alerts} />
        </td>

        {/* Last Action */}
        <td>
          {lastAction ? (
            <div className="text-sm">
              <span className="font-medium text-[var(--sl-text-secondary)]">
                {lastAction.category_display}
              </span>
              <p className="text-xs text-[var(--sl-text-muted)]">
                {formatTimeAgo(lastAction.created_at)}
              </p>
            </div>
          ) : (
            <span className="text-sm text-[var(--sl-text-muted)]">No Action</span>
          )}
        </td>

        {/* Updated */}
        <td>
          <div className="flex items-center gap-2 text-sm text-[var(--sl-text-muted)]">
            <Clock className="w-4 h-4" />
            <span>{formatTimeAgo(patient.updated_at)}</span>
            {isExpanded ? (
              <ChevronUp className="w-4 h-4" />
            ) : (
              <ChevronDown className="w-4 h-4" />
            )}
          </div>
        </td>
      </tr>

      {/* Expanded Row */}
      {isExpanded && (
        <tr>
          <td colSpan={9} className="p-0 bg-gray-50">
            <ExpandedPatientDetails
              patient={patient}
              alerts={alerts}
              actions={actions}
              actionsLoading={actionsLoading}
              onCreateAction={(actionType: ClinicalActionType, notes?: string) => {
                createAction.mutate({
                  patientId: patient.id,
                  data: { action_type: actionType, notes },
                });
              }}
              isCreatingAction={createAction.isPending}
              onOpenModal={onOpenModal}
            />
          </td>
        </tr>
      )}
    </>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

function RiskBadge({ level }: { level: RiskLevel }) {
  const config = {
    critical: 'bg-red-500 text-white',
    high: 'bg-orange-500 text-white',
    medium: 'bg-yellow-500 text-white',
    low: 'bg-green-500 text-white',
  };

  const labels = {
    critical: 'CRITICAL',
    high: 'HIGH',
    medium: 'MEDIUM',
    low: 'LOW',
  };

  return (
    <span className={cn('px-2 py-1 text-xs font-bold rounded', config[level])}>
      {labels[level]}
    </span>
  );
}

function VitalValue({
  icon,
  value,
  unit,
  isAlert,
}: {
  icon: React.ReactNode;
  value: number | string | null | undefined;
  unit?: string;
  isAlert?: boolean;
}) {
  if (value === null || value === undefined) {
    return (
      <div className="flex flex-col items-center text-gray-300">
        {icon}
        <span className="text-sm">--</span>
      </div>
    );
  }

  return (
    <div className={cn('flex flex-col items-center', isAlert ? 'text-red-500' : 'text-[var(--sl-text-secondary)]')}>
      {icon}
      <span className="text-sm font-semibold">
        {value}
        {unit && <span className="text-xs font-normal ml-0.5">{unit}</span>}
      </span>
    </div>
  );
}

// Abbreviate alert titles for compact display
function abbreviateAlertTitle(title: string): string {
  const abbreviations: Record<string, string> = {
    'High Heart Rate Alert': 'High HR',
    'Low Heart Rate Alert': 'Low HR',
    'High Spo2 Alert': 'High SpO₂',
    'Low Spo2 Alert': 'Low SpO₂',
    'High Temperature Alert': 'High Temp',
    'Low Temperature Alert': 'Low Temp',
    'High Respiratory Rate Alert': 'High RR',
    'Low Respiratory Rate Alert': 'Low RR',
    'High Blood Pressure Alert': 'High BP',
    'Low Blood Pressure Alert': 'Low BP',
    'High Blood Pressure Systolic Alert': 'High BP Sys',
    'Low Blood Pressure Systolic Alert': 'Low BP Sys',
    'High Blood Pressure Diastolic Alert': 'High BP Dia',
    'Low Blood Pressure Diastolic Alert': 'Low BP Dia',
    'High Hrv Alert': 'High HRV',
    'Low Hrv Alert': 'Low HRV',
  };
  // Check exact match first, then try replacing common patterns
  if (abbreviations[title]) {
    return abbreviations[title];
  }
  // Handle variations like "Blood Pressure" -> "BP"
  return title
    .replace('Blood Pressure Systolic', 'BP Sys')
    .replace('Blood Pressure Diastolic', 'BP Dia')
    .replace('Blood Pressure', 'BP')
    .replace(' Alert', '');
}

function AlertBadges({ alerts }: { alerts: Alert[] }) {
  if (alerts.length === 0) {
    return <span className="text-sm text-[var(--sl-text-muted)]">None</span>;
  }

  const firstRow = alerts.slice(0, 2);
  const thirdAlert = alerts[2];
  const remaining = alerts.length - 3;

  const getSeverityStyle = (severity: Alert['severity']) => {
    switch (severity) {
      case 'critical':
        return 'bg-red-50 text-red-700 border-red-200';
      case 'warning':
        return 'bg-orange-50 text-orange-700 border-orange-200';
      default:
        return 'bg-blue-50 text-blue-700 border-blue-200';
    }
  };

  const renderBadge = (alert: Alert) => (
    <span
      key={alert.id}
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded border',
        getSeverityStyle(alert.severity)
      )}
    >
      <AlertTriangle className="w-3 h-3" />
      {abbreviateAlertTitle(alert.title)}
    </span>
  );

  return (
    <div className="flex flex-col gap-1">
      {/* First row: up to 2 alerts */}
      <div className="flex items-center gap-1">
        {firstRow.map(renderBadge)}
      </div>
      {/* Second row: 3rd alert + remaining count */}
      {thirdAlert && (
        <div className="flex items-center gap-1">
          {renderBadge(thirdAlert)}
          {remaining > 0 && (
            <span className="text-xs text-[var(--sl-text-muted)]">+{remaining} more</span>
          )}
        </div>
      )}
    </div>
  );
}

interface ExpandedPatientDetailsProps {
  patient: Patient;
  alerts: Alert[];
  actions: ClinicalAction[];
  actionsLoading: boolean;
  onCreateAction: (actionType: ClinicalActionType, notes?: string) => void;
  isCreatingAction: boolean;
  onOpenModal: () => void;
}

function ExpandedPatientDetails({
  patient,
  alerts,
  actions,
  actionsLoading,
  onCreateAction,
  isCreatingAction,
  onOpenModal,
}: ExpandedPatientDetailsProps) {
  const summary = patient.summary;

  const formatActionTime = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays === 1) return 'Yesterday';
    return `${diffDays}d ago`;
  };

  return (
    <div className="p-6 border-t border-gray-200">
      {/* Surgery Type */}
      {patient.primary_diagnosis && (
        <div className="mb-4">
          <span className="inline-flex items-center px-3 py-1 text-sm bg-white border border-gray-200 rounded-full">
            <span className="text-gray-500 mr-1">Surgery Type:</span>
            <span className="font-medium">{patient.primary_diagnosis}</span>
          </span>
        </div>
      )}

      <div className="grid grid-cols-3 gap-6">
        {/* Respiratory & Activity */}
        <div>
          <h4 className="text-sm font-semibold text-[var(--sl-text-primary)] mb-3">
            Respiratory & Activity
          </h4>
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm">
              <Wind className="w-4 h-4 text-gray-400" />
              <span className="text-gray-600">Respiratory Rate:</span>
              <span className="font-medium">
                {summary?.latest_respiratory_rate ?? '--'} /min
              </span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <Footprints className="w-4 h-4 text-gray-400" />
              <span className="text-gray-600">Activity:</span>
              <span className="font-medium">
                {summary?.today_active_minutes ?? '--'} min
              </span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <Moon className="w-4 h-4 text-gray-400" />
              <span className="text-gray-600">Sleep:</span>
              <span className="font-medium">
                {summary?.last_sleep_duration_minutes
                  ? `${(summary.last_sleep_duration_minutes / 60).toFixed(1)} hrs`
                  : '--'}
              </span>
            </div>
          </div>
        </div>

        {/* Latest Symptom */}
        <div>
          <h4 className="text-sm font-semibold text-[var(--sl-text-primary)] mb-3 flex items-center gap-2">
            <MessageSquare className="w-4 h-4" />
            Latest Symptom Reported
          </h4>
          <div className="bg-white border border-gray-200 rounded-lg p-3">
            <p className="text-sm text-gray-700 italic">
              "No symptoms reported"
            </p>
            <p className="text-xs text-gray-400 mt-2">
              Last checked: {new Date().toLocaleDateString()}
            </p>
          </div>
        </div>

        {/* Quick Actions */}
        <div>
          <h4 className="text-sm font-semibold text-[var(--sl-text-primary)] mb-3">
            Quick Actions
          </h4>
          <div className="space-y-2">
            <button
              onClick={() => onCreateAction('education', 'Provided patient education')}
              disabled={isCreatingAction}
              className="w-full flex items-center gap-2 px-4 py-2 bg-blue-500 text-white text-sm font-medium rounded-lg hover:bg-blue-600 transition-colors disabled:opacity-50"
            >
              <GraduationCap className="w-4 h-4" />
              Provide Education
            </button>
            <button
              onClick={() => onCreateAction('escalation', 'Escalated to PA for review')}
              disabled={isCreatingAction}
              className="w-full flex items-center gap-2 px-4 py-2 bg-orange-500 text-white text-sm font-medium rounded-lg hover:bg-orange-600 transition-colors disabled:opacity-50"
            >
              <ArrowUpCircle className="w-4 h-4" />
              Escalate to PA
            </button>
            <button
              onClick={() => onCreateAction('escalation', 'Advised patient to visit ED')}
              disabled={isCreatingAction}
              className="w-full flex items-center gap-2 px-4 py-2 bg-red-500 text-white text-sm font-medium rounded-lg hover:bg-red-600 transition-colors disabled:opacity-50"
            >
              <AlertOctagon className="w-4 h-4" />
              Advise ED
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onOpenModal();
              }}
              className="w-full flex items-center gap-2 px-4 py-2 bg-violet-500 text-white text-sm font-medium rounded-lg hover:bg-violet-600 transition-colors"
            >
              <Plus className="w-4 h-4" />
              Log Action
            </button>
          </div>
        </div>
      </div>

      {/* All Alerts & Action Log */}
      <div className="grid grid-cols-2 gap-6 mt-6 pt-6 border-t border-gray-200">
        <div>
          <h4 className="text-sm font-semibold text-[var(--sl-text-primary)] mb-3">
            All Alerts
          </h4>
          {alerts.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {alerts.map((alert) => {
                const severityStyle = alert.severity === 'critical'
                  ? 'bg-red-50 text-red-700 border-red-200'
                  : alert.severity === 'warning'
                    ? 'bg-orange-50 text-orange-700 border-orange-200'
                    : 'bg-blue-50 text-blue-700 border-blue-200';
                return (
                  <span
                    key={alert.id}
                    className={cn(
                      'inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded border',
                      severityStyle
                    )}
                  >
                    <AlertTriangle className="w-3 h-3" />
                    {abbreviateAlertTitle(alert.title)}
                  </span>
                );
              })}
            </div>
          ) : (
            <p className="text-sm text-gray-500">No active alerts</p>
          )}
        </div>

        <div>
          <h4 className="text-sm font-semibold text-[var(--sl-text-primary)] mb-3 flex items-center gap-2">
            <Clock className="w-4 h-4" />
            Action Log
          </h4>
          {actionsLoading ? (
            <p className="text-sm text-gray-500">Loading actions...</p>
          ) : actions.length === 0 ? (
            <p className="text-sm text-gray-500">No actions recorded</p>
          ) : (
            <div className="space-y-2 max-h-40 overflow-y-auto">
              {actions.slice(0, 5).map((action) => (
                <div
                  key={action.id}
                  className="bg-white border border-gray-200 rounded-lg p-2"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <span className="text-sm font-medium text-[var(--sl-text-primary)]">
                        {action.category_display}
                      </span>
                      {action.notes && (
                        <p className="text-xs text-gray-600 mt-0.5 line-clamp-2">
                          {action.notes}
                        </p>
                      )}
                    </div>
                    <span className="text-xs text-gray-400 whitespace-nowrap ml-2">
                      {formatActionTime(action.created_at)}
                    </span>
                  </div>
                  <p className="text-xs text-gray-400 mt-1">
                    by {action.practitioner_name}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
