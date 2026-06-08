import { AlertTriangle, MessageCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface AlertBadgeProps {
  code: string;
  severity: 'critical' | 'warning';
  className?: string;
}

const ALERT_CODE_LABELS: Record<string, string> = {
  'hr-high': 'HR High',
  'hr-low': 'HR Low',
  'hr-critical': 'HR Critical',
  'spo2-low': 'SpO2 Low',
  'spo2-critical': 'SpO2 Critical',
  'temp-high': 'Temp High',
  'temp-critical': 'Temp Critical',
  'bp-high': 'BP High',
  'bp-low': 'BP Low',
};

export function AlertBadge({ code, severity, className }: AlertBadgeProps) {
  const label = ALERT_CODE_LABELS[code] || code;

  return (
    <span className={cn('sl-alert-badge', severity, className)}>
      <AlertTriangle className="w-3 h-3" />
      {label}
    </span>
  );
}

interface SymptomBadgeProps {
  count: number;
  hasCritical?: boolean;
  className?: string;
}

export function SymptomBadge({ count, hasCritical, className }: SymptomBadgeProps) {
  return (
    <span className={cn('sl-alert-badge', hasCritical ? 'critical' : 'warning', className)}>
      <MessageCircle className="w-3 h-3" />
      {count} Symptom{count !== 1 ? 's' : ''}
    </span>
  );
}

export function NoAlertsBadge({ className }: { className?: string }) {
  return (
    <span className={cn('sl-no-alerts-badge', className)}>
      No Alerts
    </span>
  );
}
