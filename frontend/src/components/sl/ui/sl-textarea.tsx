/**
 * SL-specific Textarea wrapper with explicit colors.
 * Use this in SL pages instead of @/components/ui/textarea
 * to ensure text is always visible in portals.
 */
import * as React from 'react';

import { cn } from '@/lib/utils';

const SlTextarea = React.forwardRef<
  HTMLTextAreaElement,
  React.ComponentProps<'textarea'>
>(({ className, ...props }, ref) => {
  return (
    <textarea
      className={cn(
        'flex min-h-[80px] w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-base text-gray-900 ring-offset-white',
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
});
SlTextarea.displayName = 'SlTextarea';

export { SlTextarea };
