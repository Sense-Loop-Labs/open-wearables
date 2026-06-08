import { Heart, Droplets, Thermometer, Activity } from 'lucide-react';
import { cn } from '@/lib/utils';

type VitalType = 'heart-rate' | 'spo2' | 'blood-pressure' | 'temperature';

interface VitalCellProps {
  type: VitalType;
  value: string | number | null;
  unit?: string;
  hasAlert?: boolean;
  className?: string;
}

const vitalIcons: Record<VitalType, React.ElementType> = {
  'heart-rate': Heart,
  'spo2': Droplets,
  'blood-pressure': Activity,
  'temperature': Thermometer,
};

export function formatBp(systolic: number | null, diastolic: number | null): string | null {
  if (systolic === null || diastolic === null) return null;
  return `${systolic}/${diastolic}`;
}

export function formatTemp(tempF: number | null): string | null {
  if (tempF === null) return null;
  return `${tempF.toFixed(1)}`;
}

export function VitalCell({ type, value, unit, hasAlert, className }: VitalCellProps) {
  const Icon = vitalIcons[type];

  if (value === null) {
    return (
      <div className={cn('sl-vital-cell', className)}>
        <Icon className="icon muted" />
        <span className="value muted">--</span>
      </div>
    );
  }

  return (
    <div className={cn('sl-vital-cell', hasAlert && 'alert', className)}>
      <Icon className="icon" />
      <span className="value">
        {value}
        {unit && <span className="unit">{unit}</span>}
      </span>
    </div>
  );
}
