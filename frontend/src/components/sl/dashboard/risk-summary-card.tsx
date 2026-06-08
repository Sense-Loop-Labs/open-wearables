import { AlertTriangle, TrendingUp, Activity, Shield, Users } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { RiskLevel } from './risk-category-badge';

type RiskCardLevel = RiskLevel | 'total';

interface RiskSummaryCardProps {
  level: RiskCardLevel;
  count: number;
  onClick?: () => void;
}

const levelConfig: Record<RiskCardLevel, {
  label: string;
  icon: React.ElementType;
  className: string;
}> = {
  critical: {
    label: 'Critical',
    icon: AlertTriangle,
    className: 'sl-risk-card critical',
  },
  high: {
    label: 'High Risk',
    icon: TrendingUp,
    className: 'sl-risk-card high',
  },
  medium: {
    label: 'Medium Risk',
    icon: Activity,
    className: 'sl-risk-card medium',
  },
  low: {
    label: 'Low Risk',
    icon: Shield,
    className: 'sl-risk-card low',
  },
  unknown: {
    label: 'Unknown',
    icon: Users,
    className: 'sl-risk-card',
  },
  total: {
    label: 'Total Patients',
    icon: Users,
    className: 'sl-risk-card total',
  },
};

export function RiskSummaryCard({ level, count, onClick }: RiskSummaryCardProps) {
  const config = levelConfig[level];
  const Icon = config.icon;

  return (
    <button
      onClick={onClick}
      className={cn(config.className, onClick && 'cursor-pointer hover:opacity-90')}
      disabled={!onClick}
    >
      <div className="flex items-center justify-between">
        <Icon className="icon" />
        <span className="count">{count}</span>
      </div>
      <span className="label">{config.label}</span>
    </button>
  );
}
