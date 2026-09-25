import { useState } from 'react';
import clsx from 'clsx';
import { useCountUp } from '../hooks/useCountUp';
import { usePrefersReducedMotion } from '../hooks/usePrefersReducedMotion';
import type { CounterfactualsPayload, PriorityEntry } from '../types';

interface Props {
  entry: PriorityEntry | null;
  counterfactuals: CounterfactualsPayload | null;
  onClose: () => void;
}

const INTERVENTIONS: { key: string; label: string }[] = [
  { key: 'add_crosswalk', label: 'Add crosswalk' },
  { key: 'add_sidewalk', label: 'Close sidewalk gap' },
  { key: 'add_lighting', label: 'Add lighting' },
  { key: 'reduce_speed_limit_25', label: '25 mph speed limit' },
  { key: 'reduce_speed_limit_30', label: '30 mph speed limit' },
];

export default function SegmentDetail({ entry, counterfactuals, onClose }: Props) {
  const [intervention, setIntervention] = useState<string | null>(null);

  return (
    <div
      className={clsx(
        'glass-panel pointer-events-auto rounded-xl w-[min(92vw,400px)] max-h-[min(84vh,760px)] overflow-hidden flex flex-col transition-all duration-300',
        entry ? 'translate-x-0 opacity-100' : 'translate-x-6 opacity-0 pointer-events-none',
      )}
    >
      {entry && (
        <SegmentDetailContent
          key={entry.segment_id /* remount on segment change so count-up starts fresh */}
          entry={entry}
          counterfactuals={counterfactuals}
          intervention={intervention}
          onInterventionChange={setIntervention}
          onClose={onClose}
        />
      )}
    </div>
  );
}

function SegmentDetailContent({
  entry,
  counterfactuals,
  intervention,
  onInterventionChange,
  onClose,
}: {
  entry: PriorityEntry;
  counterfactuals: CounterfactualsPayload | null;
  intervention: string | null;
  onInterventionChange: (key: string | null) => void;
  onClose: () => void;
}) {
  const displayedExposure = useCountUp(entry.risk_exposure_score, 560);
  const cf = intervention ? counterfactuals?.[entry.segment_id]?.[intervention] : undefined;

  return (
    <>
      <div className="flex items-start justify-between px-4 pt-4">
        <div className="min-w-0 flex items-start gap-2.5">
          <span className="font-data text-[11px] w-6 h-6 shrink-0 mt-0.5 rounded-md flex items-center justify-center font-medium bg-white/[0.06] text-ink-secondary">
            {entry.rank}
          </span>
          <div className="min-w-0">
            <p className="text-[11px] text-ink-secondary">{entry.county} County</p>
            <h2 className="text-sm font-semibold text-ink-primary truncate mt-0.5">{entry.segment_name}</h2>
          </div>
        </div>
        <button
          onClick={onClose}
          aria-label="Close segment detail"
          className="shrink-0 h-7 w-7 rounded-md flex items-center justify-center text-ink-secondary hover:text-ink-primary hover:bg-white/5 transition-colors"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M2 2L12 12M12 2L2 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 pb-4 mt-3 space-y-4">
        {entry.data_density_flag && (
          <div className="rounded-lg border border-caution/30 bg-caution/[0.06] px-3 py-2 text-xs text-ink-secondary flex items-start gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-caution mt-1 shrink-0" />
            <span>
              Low-confidence: this segment or county has sparse crash/incident
              records. Read this score as directional, not precise.
            </span>
          </div>
        )}

        <div className="rounded-lg bg-white/[0.03] border border-asphalt-line px-4 py-3.5">
          <p className="text-xs text-ink-secondary">Risk-Exposure</p>
          <p className="font-data text-3xl font-semibold text-ink-primary mt-1 tabular-nums">
            {displayedExposure.toFixed(3)}
          </p>
          <div className="grid grid-cols-2 gap-3 mt-3 pt-3 border-t border-asphalt-line">
            <Stat label="Base risk score" value={entry.risk_score.toFixed(4)} />
            <Stat label="Explanation confidence" value={`${(entry.explanation_confidence * 100).toFixed(0)}%`} />
          </div>
        </div>

        <section>
          <h3 className="text-xs font-semibold text-ink-primary mb-2">What drove this score</h3>
          <ul className="space-y-2">
            {entry.top_features.map((f) => (
              <li key={f.feature_name}>
                <div className="flex justify-between mb-1 text-xs">
                  <span className="text-ink-secondary">{f.feature_name.replace(/_/g, ' ')}</span>
                  <span className="font-data text-ink-primary">{f.value.toFixed(2)}</span>
                </div>
                <div className="h-1 rounded-full bg-white/[0.06] overflow-hidden">
                  <div
                    className="h-full rounded-full bg-accent/70"
                    style={{ width: `${Math.min(100, f.importance * 100)}%` }}
                  />
                </div>
              </li>
            ))}
          </ul>
        </section>

        <section>
          <h3 className="text-xs font-semibold text-ink-primary mb-2">Suggested countermeasures</h3>
          <ul className="space-y-2">
            {entry.suggested_countermeasures.map((c) => (
              <li key={c.category} className="rounded-lg border border-asphalt-line px-3 py-2.5">
                <p className="text-xs font-medium text-ink-primary">{c.category}</p>
                <p className="text-[11px] text-ink-secondary mt-1 leading-relaxed">{c.rationale}</p>
                <p className="text-[10px] text-ink-muted mt-1">{c.fhwa_reference}</p>
              </li>
            ))}
          </ul>
        </section>

        <section>
          <h3 className="text-xs font-semibold text-ink-primary mb-2">What if?</h3>
          <div className="flex flex-wrap gap-1.5">
            {INTERVENTIONS.map((opt) => (
              <button
                key={opt.key}
                onClick={() => onInterventionChange(intervention === opt.key ? null : opt.key)}
                className={clsx(
                  'text-[11px] px-2.5 py-1.5 rounded-full border transition-colors',
                  intervention === opt.key
                    ? 'bg-accent/15 border-accent text-accent'
                    : 'border-asphalt-line text-ink-secondary hover:text-ink-primary hover:border-ink-muted',
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>

          <div className="mt-3 min-h-[64px]">
            {!intervention && (
              <p className="text-[11px] text-ink-muted">
                Pick an intervention to re-run the trained model on this
                segment's neighborhood.
              </p>
            )}
            {intervention && !counterfactuals && (
              <p className="text-[11px] text-ink-muted">Loading…</p>
            )}
            {intervention && counterfactuals && !cf?.applied && (
              <p className="text-[11px] text-ink-muted">
                {cf?.reason ?? 'No precomputed result for this segment/intervention.'}
              </p>
            )}
            {cf?.applied && cf.target && (
              <CounterfactualResult
                key={intervention}
                target={cf.target}
                hop1={cf.hop1_neighbors ?? []}
              />
            )}
          </div>
        </section>
      </div>
    </>
  );
}

function CounterfactualResult({
  target,
  hop1,
}: {
  target: { baseline_risk_score: number; updated_risk_score: number; delta: number };
  hop1: { delta: number }[];
}) {
  const reducedMotion = usePrefersReducedMotion();
  const animatedNew = useCountUp(target.updated_risk_score, 520);
  const improved = target.delta < 0;
  const unchanged = Math.abs(target.delta) < 1e-6;

  return (
    <div className="rounded-lg border border-asphalt-line bg-white/[0.02] px-3 py-3">
      <p className="text-[11px] text-ink-secondary mb-1.5">Predicted risk score, this segment</p>
      <div className="flex items-baseline gap-2.5">
        <span
          className={clsx(
            'font-data text-sm text-ink-muted line-through decoration-1',
            !reducedMotion && 'animate-fade-out-strike',
          )}
        >
          {target.baseline_risk_score.toFixed(4)}
        </span>
        <svg width="12" height="10" viewBox="0 0 12 10" fill="none" className="text-ink-muted shrink-0">
          <path d="M1 5H11M11 5L7 1M11 5L7 9" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span
          className={clsx(
            'font-data text-xl font-semibold tabular-nums',
            unchanged ? 'text-ink-primary' : improved ? 'text-risk-low' : 'text-risk-high',
            !reducedMotion && 'animate-value-in',
          )}
        >
          {animatedNew.toFixed(4)}
        </span>
      </div>
      <p className="text-[11px] text-ink-secondary mt-1.5">
        {unchanged
          ? 'No meaningful change predicted from this single intervention.'
          : `${improved ? 'Decrease' : 'Increase'} of ${Math.abs(target.delta).toFixed(4)}.`}
      </p>
      {hop1.length > 0 && (
        <p className="text-[10px] text-ink-muted mt-2 pt-2 border-t border-asphalt-line">
          Propagated via GNN message passing to {hop1.length} neighboring segment
          {hop1.length === 1 ? '' : 's'}, mean delta{' '}
          <span className="font-data">
            {(hop1.reduce((s, r) => s + r.delta, 0) / hop1.length).toFixed(5)}
          </span>
        </p>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[11px] text-ink-secondary">{label}</p>
      <p className="font-data text-sm font-medium text-ink-primary mt-0.5">{value}</p>
    </div>
  );
}
