/**
 * SL-specific Badge wrapper with explicit colors.
 * Use this in SL pages instead of @/components/ui/badge
 * to ensure text is always visible in portals.
 */
import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';

import { cn } from '@/lib/utils';

const slBadgeVariants = cva(
  'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2',
  {
    variants: {
      variant: {
        default:
          'border-transparent bg-blue-600 text-white hover:bg-blue-700',
        secondary:
          'border-transparent bg-gray-100 text-gray-700 hover:bg-gray-200',
        destructive:
          'border-transparent bg-red-600 text-white hover:bg-red-700',
        outline:
          'text-gray-700 border-gray-300 hover:border-gray-400 hover:bg-gray-50',
        success:
          'border-transparent bg-green-600 text-white hover:bg-green-700',
        warning:
          'border-transparent bg-orange-500 text-white hover:bg-orange-600',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
);

export interface SlBadgeProps
  extends
    React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof slBadgeVariants> {}

function SlBadge({ className, variant, ...props }: SlBadgeProps) {
  return (
    <div className={cn(slBadgeVariants({ variant }), className)} {...props} />
  );
}

export { SlBadge, slBadgeVariants };
