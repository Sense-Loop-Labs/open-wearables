import * as React from 'react';

import { cn } from '@/lib/utils';

const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.ComponentProps<'textarea'>
>(({ className, ...props }, ref) => {
  return (
    <textarea
      className={cn(
        'flex min-h-[80px] w-full rounded-md border border-border/50 bg-background px-3 py-2 text-base ring-offset-background',
        'placeholder:text-muted-foreground',
        'transition-all duration-300 ease-out',
        'hover:border-primary/30',
        'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring',
        'focus-visible:border-primary/50 focus-visible:shadow-[0_0_15px_hsla(185,100%,50%,0.15)]',
        'disabled:cursor-not-allowed disabled:opacity-50',
        'md:text-sm',
        className
      )}
      ref={ref}
      {...props}
    />
  );
});
Textarea.displayName = 'Textarea';

export { Textarea };
