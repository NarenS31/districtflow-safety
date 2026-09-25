import { useEffect, useRef, useState } from 'react';
import { usePrefersReducedMotion } from './usePrefersReducedMotion';

/** Animates a displayed number from its previous value to `target` whenever
 * `target` changes — used for the risk score on segment selection and for
 * a counterfactual's new score, so a state change reads as something
 * happened rather than an instant number swap. Snaps immediately under
 * prefers-reduced-motion. Motion is only ever triggered by `target`
 * actually changing (a user selecting a segment or toggling an
 * intervention), never on an unrelated re-render. */
export function useCountUp(target: number, durationMs = 480): number {
  const reducedMotion = usePrefersReducedMotion();
  const [value, setValue] = useState(target);
  const fromRef = useRef(target);
  const frameRef = useRef<number>();

  useEffect(() => {
    if (reducedMotion) {
      setValue(target);
      fromRef.current = target;
      return;
    }
    const from = fromRef.current;
    const to = target;
    if (from === to) return;

    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs);
      // ease-out-cubic: fast start, gentle settle — reads as a measurement
      // arriving, not a mechanical linear ramp.
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(from + (to - from) * eased);
      if (t < 1) {
        frameRef.current = requestAnimationFrame(tick);
      } else {
        fromRef.current = to;
      }
    };
    frameRef.current = requestAnimationFrame(tick);
    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target, reducedMotion]);

  return value;
}
