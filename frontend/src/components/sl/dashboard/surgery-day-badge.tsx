import { cn } from '@/lib/utils';

interface SurgeryDayBadgeProps {
  daysSinceSurgery: number | null;
  className?: string;
}

export function SurgeryDayBadge({ daysSinceSurgery, className }: SurgeryDayBadgeProps) {
  if (daysSinceSurgery === null) return null;

  return (
    <span className={cn('sl-surgery-day-badge', className)}>
      S+{daysSinceSurgery}
    </span>
  );
}
