import { forwardRef, type InputHTMLAttributes } from 'react';
import { clsx } from 'clsx';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, ...props }, ref) => {
    return (
      <div className="w-full">
        {label && (
          <label className="block text-sm text-clpz-text-secondary mb-1.5">
            {label}
          </label>
        )}
        <input
          ref={ref}
          className={clsx(
            'w-full h-10 px-3.5 bg-clpz-surface-inset border rounded-lg text-clpz-text-primary text-sm',
            'placeholder:text-clpz-text-tertiary',
            'focus:outline-none focus:border-clpz-accent focus:ring-1 focus:ring-clpz-accent/30',
            'transition-colors duration-150',
            error ? 'border-clpz-error' : 'border-clpz-border',
            className
          )}
          {...props}
        />
        {error && (
          <p className="mt-1 text-xs text-clpz-error">{error}</p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';
export default Input;
