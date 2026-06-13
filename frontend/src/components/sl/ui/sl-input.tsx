/**
 * SL-specific Input wrapper with explicit colors.
 * Use this in SL pages instead of @/components/ui/input
 * to ensure text is always visible in portals.
 */
import * as React from 'react';

import { cn } from '@/lib/utils';

const SlInput = React.forwardRef<HTMLInputElement, React.ComponentProps<'input'>>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          'flex h-10 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-base text-gray-900 ring-offset-white',
          'file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-gray-900',
          'placeholder:text-gray-400',
          'transition-all duration-300 ease-out',
          'hover:border-gray-400',
          'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-blue-500',
          'focus-visible:border-blue-400 focus-visible:shadow-sm',
          'disabled:cursor-not-allowed disabled:opacity-50',
          'md:text-sm',
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
SlInput.displayName = 'SlInput';

export { SlInput };
