import { useEffect, useState } from 'react';

function readDarkMode(): boolean {
  return typeof document !== 'undefined' && document.documentElement.classList.contains('dark');
}

export default function ThemeToggle() {
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    const syncWithDocument = () => setIsDark(readDarkMode());
    syncWithDocument();
    const observer = new MutationObserver(syncWithDocument);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);

  const toggle = () => {
    const nextIsDark = !readDarkMode();
    document.documentElement.classList.toggle('dark', nextIsDark);
    try { localStorage.setItem('clpz-theme', nextIsDark ? 'dark' : 'light'); } catch {}
    setIsDark(nextIsDark);
  };

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={isDark ? 'Dark mode on. Switch to light' : 'Light mode on. Switch to dark'}
      className="relative flex h-9 w-9 items-center justify-center rounded-full border border-gray-200 bg-white text-gray-900 transition hover:border-gray-400 hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gray-400 focus-visible:ring-offset-2 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100 dark:hover:border-gray-500"
    >
      {/* Sun */}
      <svg
        aria-hidden="true"
        className={`absolute h-5 w-5 transition-all duration-300 ${isDark ? 'scale-0 rotate-[-90deg] opacity-0' : 'scale-100 rotate-0 opacity-100'}`}
        viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      >
        <circle cx="12" cy="12" r="5" /><line x1="12" y1="1" x2="12" y2="3" /><line x1="12" y1="21" x2="12" y2="23" />
        <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" /><line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
        <line x1="1" y1="12" x2="3" y2="12" /><line x1="21" y1="12" x2="23" y2="12" />
        <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" /><line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
      </svg>
      {/* Moon */}
      <svg
        aria-hidden="true"
        className={`absolute h-5 w-5 transition-all duration-300 ${isDark ? 'scale-100 rotate-0 opacity-100' : 'scale-0 rotate-90 opacity-0'}`}
        viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      >
        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
      </svg>
    </button>
  );
}
