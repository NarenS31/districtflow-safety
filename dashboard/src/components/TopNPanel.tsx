import clsx from 'clsx';
import type { PriorityEntry } from '../types';

interface Props {
  entries: PriorityEntry[] | null;
  selectedId: string | null;
  onSelect: (segmentId: string) => void;
}

/** Rank-based tiers within THIS list, not absolute risk magnitude — every
 * entry here is already among the district's 25 highest-priority segments
 * (the map's quantile-based coloring handles absolute severity across the
 * full network); a leaderboard's job is to differentiate WITHIN its own
 * ranking, so tiers are relative rank bands. */
function tierForRank(rank: number): { label: string; color: string; border: string } {
  if (rank <= 3) return { label: 'Critical', color: 'text-risk-high', border: 'border-risk-high' };
  if (rank <= 10) return { label: 'High', color: 'text-risk-mid', border: 'border-risk-mid' };
  return { label: 'Elevated', color: 'text-risk-low', border: 'border-risk-low' };
}

export default function TopNPanel({ entries, selectedId, onSelect }: Props) {
  if (!entries) {
    return <div className="p-4 text-sm text-ink-secondary">Loading priority list…</div>;
  }

  return (
    <ul className="px-2 pb-3 pt-1">
      {entries.map((e) => {
        const tier = tierForRank(e.rank);
        const isTop3 = e.rank <= 3;
        const selected = selectedId === e.segment_id;
        return (
          <li key={e.segment_id}>
            <button
              onClick={() => onSelect(e.segment_id)}
              className={clsx(
                'w-full text-left rounded-lg pl-3 pr-3 py-2.5 my-1 transition-colors border-l-2',
                tier.border,
                selected ? 'bg-accent/10' : 'hover:bg-white/5',
                isTop3 && !selected && 'bg-risk-high/[0.04]',
              )}
              style={isTop3 ? { boxShadow: `inset 0 0 24px -8px ${selected ? '#F2A73B33' : '#D93B3B22'}` } : undefined}
            >
              <div className="flex items-center gap-2.5">
                <span
                  className={clsx(
                    'font-data text-[11px] w-6 h-6 shrink-0 rounded-md flex items-center justify-center font-medium',
                    isTop3 ? 'bg-risk-high/15 text-risk-high' : 'bg-white/[0.06] text-ink-secondary',
                  )}
                >
                  {e.rank}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-ink-primary truncate">{e.segment_name}</p>
                  <div className="flex items-center gap-1.5 mt-0.5 text-[11px] text-ink-secondary">
                    <span>{e.county}</span>
                    {e.rural_flag && (
                      <span className="px-1.5 py-0.5 rounded bg-white/[0.06] text-[10px]">Rural</span>
                    )}
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <p className={clsx('font-data text-sm font-semibold', tier.color)}>
                    {e.risk_exposure_score.toFixed(3)}
                  </p>
                  <p className={clsx('text-[10px] font-medium', tier.color)}>{tier.label}</p>
                </div>
              </div>
              {e.data_density_flag && (
                <div className="flex items-center gap-1 mt-1.5 text-[10px] text-caution">
                  <span className="h-1 w-1 rounded-full bg-caution" />
                  Low-confidence data
                </div>
              )}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
