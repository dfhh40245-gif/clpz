import { type HTMLAttributes } from 'react';
import { clsx } from 'clsx';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  hover?: boolean;
}

export default function Card({ children, className, hover = false, ...props }: CardProps) {
  return (
    <div
      className={clsx(
        'bg-clpz-surface-1 border border-clpz-border rounded-xl',
        hover && 'transition-all duration-150 hover:border-clpz-border-strong hover:-translate-y-0.5',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}
