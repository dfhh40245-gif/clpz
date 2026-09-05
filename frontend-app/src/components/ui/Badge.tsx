import { clsx } from 'clsx';

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'accent' | 'success' | 'error' | 'warning';
  className?: string;
}

export default function Badge({ children, variant = 'default', className }: BadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-semibold uppercase tracking-wider',
        variant === 'default' && 'bg-clpz-surface-2 text-clpz-text-secondary border border-clpz-border',
        variant === 'accent' && 'bg-clpz-accent/10 text-clpz-accent border border-clpz-accent/25',
        variant === 'success' && 'bg-clpz-success/10 text-clpz-success border border-clpz-success/25',
        variant === 'error' && 'bg-clpz-error/10 text-clpz-error border border-clpz-error/25',
        variant === 'warning' && 'bg-clpz-warning/10 text-clpz-warning border border-clpz-warning/25',
        className
      )}
    >
      {children}
    </span>
  );
}
