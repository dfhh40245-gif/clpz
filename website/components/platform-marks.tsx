/**
 * Platform marks used on the download cards.
 *
 * Inline SVG recreations of the gold-gradient Windows and Android renders:
 * no raster assets, no background box on the dark cards, crisp at any size.
 */

const GOLD_STOPS = (
  <>
    <stop offset="0" stopColor="#ffd88a" />
    <stop offset="0.55" stopColor="#ffbd52" />
    <stop offset="1" stopColor="#f08c1f" />
  </>
);

export function WindowsMark() {
  return (
    <svg className="platform-symbol" viewBox="0 0 48 48" width="34" height="34" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="clpz-win-gold" x1="0" y1="0" x2="0" y2="1">{GOLD_STOPS}</linearGradient>
      </defs>
      <g fill="none" stroke="url(#clpz-win-gold)" strokeWidth="3" strokeLinejoin="round">
        <rect x="8" y="8" width="14" height="14" rx="4" />
        <rect x="26" y="8" width="14" height="14" rx="4" />
        <rect x="8" y="26" width="14" height="14" rx="4" />
        <rect x="26" y="26" width="14" height="14" rx="4" />
      </g>
    </svg>
  );
}

export function AndroidMark() {
  return (
    <svg className="platform-symbol" viewBox="0 0 48 48" width="34" height="34" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="clpz-android-gold" x1="0" y1="0" x2="0" y2="1">{GOLD_STOPS}</linearGradient>
      </defs>
      <g fill="none" stroke="url(#clpz-android-gold)" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
        {/* head dome with flat base */}
        <path d="M10.5 21.5a13.5 10.5 0 0 1 27 0z" />
        {/* antennae */}
        <path d="M16.2 13.2 12.6 8.4M31.8 13.2l3.6-4.8" />
        {/* body */}
        <rect x="13" y="24.4" width="22" height="16.3" rx="3.6" />
        {/* arms */}
        <rect x="7" y="23.4" width="4.6" height="12.6" rx="2.3" />
        <rect x="36.4" y="23.4" width="4.6" height="12.6" rx="2.3" />
        {/* legs */}
        <path d="M18.6 40.7v3.2a1.9 1.9 0 0 0 3.8 0v-3.2M25.6 40.7v3.2a1.9 1.9 0 0 0 3.8 0v-3.2" />
      </g>
      {/* eyes */}
      <circle cx="18.6" cy="17.2" r="1.7" fill="url(#clpz-android-gold)" />
      <circle cx="29.4" cy="17.2" r="1.7" fill="url(#clpz-android-gold)" />
    </svg>
  );
}
