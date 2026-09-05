import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { clsx } from 'clsx';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'secondary', size = 'md', disabled, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled}
        className={clsx(
          'inline-flex items-center justify-center gap-2 font-semibold transition-all duration-150',
          'disabled:opacity-40 disabled:cursor-not-allowed',
          // Variants
          variant === 'primary' && 'bg-clpz-accent text-clpz-canvas hover:bg-clpz-accent-hover active:bg-clpz-accent-pressed rounded-full',
          variant === 'secondary' && 'bg-clpz-surface-1 text-clpz-text-primary border border-clpz-border hover:border-clpz-border-strong rounded-lg',
          variant === 'ghost' && 'text-clpz-text-secondary hover:text-clpz-text-primary rounded-lg',
          variant === 'danger' && 'bg-clpz-error text-clpz-canvas rounded-lg hover:opacity-90',
          // Sizes
          size === 'sm' && 'h-8 px-3 text-xs',
          size === 'md' && 'h-10 px-4 text-sm',
          size === 'lg' && 'h-11 px-6 text-sm',
          className
        )}
        {...props}
      />
    );
  }
);

Button.displayName = 'Button';
export default Button;
