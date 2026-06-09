import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';

import { cn } from '@/lib/utils';

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--sl-brand)] focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 cursor-pointer',
  {
    variants: {
      variant: {
        default:
          'bg-[var(--sl-brand)] text-white hover:bg-[var(--sl-brand-dark)] border border-transparent',
        destructive:
          'bg-red-600 text-white hover:bg-red-700 border border-transparent',
        'destructive-outline':
          'border border-red-300 bg-white text-red-600 hover:bg-red-50 hover:border-red-400',
        outline:
          'border border-[var(--sl-border)] bg-white text-[var(--sl-text-secondary)] hover:bg-[var(--sl-bg-hover)] hover:text-[var(--sl-text-primary)]',
        secondary:
          'bg-[var(--sl-bg-muted)] text-[var(--sl-text-secondary)] hover:bg-[var(--sl-bg-hover)] border border-[var(--sl-border)]',
        ghost:
          'border border-transparent text-[var(--sl-text-secondary)] hover:bg-[var(--sl-bg-hover)] hover:text-[var(--sl-text-primary)]',
        'ghost-faded':
          'border border-transparent text-[var(--sl-text-muted)] hover:bg-[var(--sl-bg-hover)] hover:text-[var(--sl-text-secondary)]',
        link: 'text-[var(--sl-brand)] underline-offset-4 hover:underline',
        neon: 'bg-[var(--sl-brand)] text-white border border-transparent hover:bg-[var(--sl-brand-dark)] transition-all duration-300 ease-out active:scale-[0.98]',
      },
      size: {
        default: 'h-10 px-4 py-2',
        sm: 'h-9 rounded-md px-3',
        lg: 'h-11 rounded-md px-8',
        icon: 'h-10 w-10',
        'icon-sm': 'h-8 w-8',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
);

export interface ButtonProps
  extends
    React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button';
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = 'Button';

export { Button, buttonVariants };
