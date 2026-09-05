import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { clsx } from 'clsx';

interface ForgeButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  size?: 'sm' | 'md' | 'lg';
  pulse?: boolean;
}

/**
 * CLPZ's signature Forge button — amber glow with heartbeat animation.
 * The premium primary action across the product.
 */
const ForgeButton = forwardRef<HTMLButtonElement, ForgeButtonProps>(
  ({ className, size = 'md', pulse = true, disabled, ...props }, ref) => {
    return (
      <>
        <style>{`
          .forge-btn {
            --forge-bg: #f0a030;
            --forge-glow: rgba(240, 160, 48, 0.25);
            position: relative;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            border: 0;
            cursor: pointer;
            border-radius: 9999px;
            background: linear-gradient(135deg, #f0a030 0%, #d48a20 100%);
            color: #0a0a0b;
            font-weight: 700;
            letter-spacing: -0.01em;
            transition: all 0.2s ease;
            box-shadow:
              inset 0 1px 0 rgba(255, 255, 255, 0.25),
              inset 0 -1px 0 rgba(0, 0, 0, 0.15),
              0 0 20px var(--forge-glow),
              0 4px 12px rgba(0, 0, 0, 0.3);
          }
          .forge-btn::after {
            content: '';
            position: absolute;
            inset: 0;
            border-radius: inherit;
            background: linear-gradient(180deg, rgba(255,255,255,0.2) 0%, rgba(255,255,255,0) 50%);
            pointer-events: none;
          }
          .forge-btn:hover:not(:disabled) {
            background: linear-gradient(135deg, #f5b34d 0%, #f0a030 100%);
            box-shadow:
              inset 0 1px 0 rgba(255, 255, 255, 0.3),
              inset 0 -1px 0 rgba(0, 0, 0, 0.15),
              0 0 30px rgba(240, 160, 48, 0.35),
              0 4px 16px rgba(0, 0, 0, 0.35);
            transform: translateY(-1px);
          }
          .forge-btn:active:not(:disabled) {
            transform: translateY(1px);
            box-shadow:
              inset 0 1px 0 rgba(255, 255, 255, 0.2),
              0 0 15px rgba(240, 160, 48, 0.2),
              0 2px 6px rgba(0, 0, 0, 0.3);
          }
          .forge-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
          }

          /* Heartbeat pulse */
          @keyframes forge-heartbeat {
            0% { box-shadow: inset 0 1px 0 rgba(255,255,255,0.25), inset 0 -1px 0 rgba(0,0,0,0.15), 0 0 20px var(--forge-glow), 0 4px 12px rgba(0,0,0,0.3); }
            50% { box-shadow: inset 0 1px 0 rgba(255,255,255,0.25), inset 0 -1px 0 rgba(0,0,0,0.15), 0 0 35px rgba(240,160,48,0.35), 0 4px 20px rgba(0,0,0,0.3), 0 0 60px rgba(240,160,48,0.1); transform: scale(1.02); }
            100% { box-shadow: inset 0 1px 0 rgba(255,255,255,0.25), inset 0 -1px 0 rgba(0,0,0,0.15), 0 0 20px var(--forge-glow), 0 4px 12px rgba(0,0,0,0.3); }
          }
          .forge-btn-pulse:not(:hover):not(:disabled) {
            animation: forge-heartbeat 2.5s ease-in-out infinite;
          }

          /* Sizes */
          .forge-btn-sm { height: 32px; padding: 0 14px; font-size: 12px; }
          .forge-btn-md { height: 40px; padding: 0 20px; font-size: 13px; }
          .forge-btn-lg { height: 48px; padding: 0 28px; font-size: 15px; }
        `}</style>
        <button
          ref={ref}
          disabled={disabled}
          className={clsx(
            'forge-btn',
            `forge-btn-${size}`,
            pulse && 'forge-btn-pulse',
            className
          )}
          {...props}
        />
      </>
    );
  }
);

ForgeButton.displayName = 'ForgeButton';
export default ForgeButton;
