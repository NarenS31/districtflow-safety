import clsx from 'clsx';
import type { PriorityEntry } from '../types';

interface Props {
  entries: PriorityEntry[] | null;
  selectedId: string | null;
  onSelect: (segmentId: string) => void;
}

export default function TopNPanel({ entries, selectedId, onSelect }: Props) {
  if (!entries) {
    return (
      <div className="p-4 text-sm text-ink-secondary-light dark:text-ink-secondary-dark">
        Loading priority list…
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 pb-2">
        <h2 className="text-sm font-semibold">Top {entries.length} priority segments</h2>
        <p className="text-xs text-ink-secondary-light dark:text-ink-secondary-dark">
          Ranked by Risk-Exposure (risk score × EMS-distance weighting).
        </p>
      </div>
      <ul className="flex-1 overflow-y-auto px-2 pb-4 space-y-1">
        {entries.map((e) => (
          <li key={e.segment_id}>
            <button
              onClick={() => onSelect(e.segment_id)}
              className={clsx(
                'w-full text-left rounded-md px-3 py-2 text-xs transition-colors',
                selectedId === e.segment_id
                  ? 'bg-risk-450 text-white'
                  : 'hover:bg-grid-light dark:hover:bg-grid-dark',
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium truncate">
                  #{e.rank} {e.segment_name}
                </span>
                <span className="tabular-nums font-semibold shrink-0">
                  {e.risk_exposure_score.toFixed(3)}
                </span>
              </div>
              <div className="flex items-center gap-2 mt-1 opacity-80">
                <span>{e.county}</span>
                {e.rural_flag && <span>· rural</span>}
                {e.data_density_flag && (
                  <span className="inline-flex items-center gap-1 text-status-warning font-medium">
                    ⚠ low-confidence
                  </span>
                )}
              </div>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
