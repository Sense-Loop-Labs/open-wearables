import { cn } from '@/lib/utils';

export type RiskLevel = 'critical' | 'high' | 'medium' | 'low' | 'unknown';

interface RiskCategoryBadgeProps {
  riskLevel: RiskLevel;
  className?: string;
}

export function getRiskLevel(daysSinceSurgery: number | null): RiskLevel {
  if (daysSinceSurgery === null) return 'unknown';
  if (daysSinceSurgery <= 7) return 'critical';
  if (daysSinceSurgery <= 14) return 'high';
  if (daysSinceSurgery <= 30) return 'medium';
  return 'low';
}

const riskLabels: Record<RiskLevel, string> = {
  critical: 'CRITICAL',
  high: 'HIGH',
  medium: 'MEDIUM',
  low: 'LOW',
  unknown: 'UNKNOWN',
};

export function RiskCategoryBadge({ riskLevel, className }: RiskCategoryBadgeProps) {
  return (
    <span className={cn('sl-badge', riskLevel, className)}>
      {riskLabels[riskLevel]}
    </span>
  );
}
