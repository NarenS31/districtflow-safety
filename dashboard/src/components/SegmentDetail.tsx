import { useState } from 'react';
import type { CounterfactualsPayload, PriorityEntry } from '../types';

interface Props {
  entry: PriorityEntry | null;
  counterfactuals: CounterfactualsPayload | null;
}

const INTERVENTION_LABELS: Record<string, string> = {
  add_crosswalk: 'Add a marked crosswalk',
  add_sidewalk: 'Close the sidewalk gap',
  add_lighting: 'Add street lighting',
  reduce_speed_limit_25: 'Reduce speed limit to 25 mph',
  reduce_speed_limit_30: 'Reduce speed limit to 30 mph',
};

export default function SegmentDetail({ entry, counterfactuals }: Props) {
  const [intervention, setIntervention] = useState<string>('add_crosswalk');

  if (!entry) {
    return (
      <div className="p-4 text-sm text-ink-secondary-light dark:text-ink-secondary-dark">
        Select a segment from the priority list or map to see its
        Risk-Exposure breakdown.
      </div>
    );
  }

  const cf = counterfactuals?.[entry.segment_id]?.[intervention];

  return (
    <div className="p-4 space-y-4 overflow-y-auto h-full">
      <div>
        <h2 className="text-sm font-semibold">{entry.segment_name}</h2>
        <p className="text-xs text-ink-secondary-light dark:text-ink-secondary-dark">
          {entry.county} County {entry.rural_flag ? '· Rural' : '· Suburban/Urban'}
        </p>
      </div>

      {entry.data_density_flag && (
        <div className="rounded-md border border-status-warning/40 bg-status-warning/10 px-3 py-2 text-xs flex items-start gap-2">
          <span className="text-status-warning font-semibold">⚠</span>
          <span>
            Low-confidence: this segment or its county has sparse crash/
            incident records. Treat this score as directional, not precise.
          </span>
        </div>
      )}

      <div className="grid grid-cols-2 gap-2">
        <StatTile label="Risk-Exposure" value={entry.risk_exposure_score.toFixed(3)} highlight />
        <StatTile label="Base risk score" value={entry.risk_score.toFixed(4)} />
        <StatTile
          label="Explanation confidence"
          value={`${(entry.explanation_confidence * 100).toFixed(0)}%`}
        />
        <StatTile label="Rank" value={`#${entry.rank}`} />
      </div>

      <section>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-secondary-light dark:text-ink-secondary-dark mb-2">
          What drove this score
        </h3>
        <ul className="space-y-1.5">
          {entry.top_features.map((f) => (
            <li key={f.feature_name} className="text-xs">
              <div className="flex justify-between mb-0.5">
                <span className="truncate">{f.feature_name.replace(/_/g, ' ')}</span>
                <span className="tabular-nums text-ink-secondary-light dark:text-ink-secondary-dark">
                  {f.value.toFixed(2)}
                </span>
              </div>
              <div className="h-1.5 rounded-full bg-grid-light dark:bg-grid-dark overflow-hidden">
                <div
                  className="h-full bg-risk-450"
                  style={{ width: `${Math.min(100, f.importance * 100)}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-secondary-light dark:text-ink-secondary-dark mb-2">
          Suggested countermeasures
        </h3>
        <ul className="space-y-2">
          {entry.suggested_countermeasures.map((c) => (
            <li key={c.category} className="rounded-md border border-grid-light dark:border-grid-dark p-2 text-xs">
              <p className="font-medium">{c.category}</p>
              <p className="text-ink-secondary-light dark:text-ink-secondary-dark mt-0.5">{c.rationale}</p>
              <p className="text-ink-muted mt-0.5 italic">{c.fhwa_reference}</p>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-secondary-light dark:text-ink-secondary-dark mb-2">
          What if? (counterfactual)
        </h3>
        <select
          value={intervention}
          onChange={(e) => setIntervention(e.target.value)}
          className="w-full text-xs rounded-md border border-grid-light dark:border-grid-dark bg-surface-light dark:bg-surface-dark px-2 py-1.5"
        >
          {Object.entries(INTERVENTION_LABELS).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>

        {!counterfactuals && (
          <p className="text-xs text-ink-muted mt-2">Loading…</p>
        )}
        {counterfactuals && !cf?.applied && (
          <p className="text-xs text-ink-muted mt-2">
            {cf?.reason ?? 'No precomputed result for this segment/intervention.'}
          </p>
        )}
        {cf?.applied && cf.target && (
          <div className="mt-2 space-y-2 text-xs">
            <div className="rounded-md border border-grid-light dark:border-grid-dark p-2">
              <p className="font-medium mb-1">This segment</p>
              <DeltaRow record={cf.target} />
            </div>
            {(cf.hop1_neighbors?.length ?? 0) > 0 && (
              <div className="rounded-md border border-grid-light dark:border-grid-dark p-2">
                <p className="font-medium mb-1">
                  1-hop neighbors ({cf.hop1_neighbors!.length}) — via GNN message passing
                </p>
                <p className="text-ink-secondary-light dark:text-ink-secondary-dark">
                  Mean delta:{' '}
                  <span className="tabular-nums font-semibold">
                    {(
                      cf.hop1_neighbors!.reduce((s, r) => s + r.delta, 0) /
                      cf.hop1_neighbors!.length
                    ).toFixed(5)}
                  </span>
                </p>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}

function StatTile({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div
      className={
        highlight
          ? 'rounded-md bg-risk-450 text-white p-2'
          : 'rounded-md border border-grid-light dark:border-grid-dark p-2'
      }
    >
      <p className="text-[10px] uppercase tracking-wide opacity-80">{label}</p>
      <p className="text-lg font-semibold tabular-nums">{value}</p>
    </div>
  );
}

function DeltaRow({ record }: { record: { baseline_risk_score: number; updated_risk_score: number; delta: number } }) {
  const improved = record.delta < 0;
  return (
    <p className="tabular-nums">
      {record.baseline_risk_score.toFixed(4)} →{' '}
      <span className={improved ? 'text-status-good font-semibold' : 'text-status-critical font-semibold'}>
        {record.updated_risk_score.toFixed(4)}
      </span>{' '}
      <span className="text-ink-secondary-light dark:text-ink-secondary-dark">
        ({record.delta >= 0 ? '+' : ''}
        {record.delta.toFixed(4)})
      </span>
    </p>
  );
}
