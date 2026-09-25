import { useEffect, useState } from 'react';

/** Reflects the OS-level prefers-reduced-motion setting, live (not just at
 * mount) — a viewer can toggle it mid-session in some OSes/browsers and
 * animation-triggering code should react, not just read it once. */
export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  );

  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handler = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  return reduced;
}
