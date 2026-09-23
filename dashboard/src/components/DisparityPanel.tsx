import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { DisparityPayload } from '../types';

interface Props {
  data: DisparityPayload | null;
}

// Categorical slots 1 (blue) & 2 (orange) from the validated palette —
// identity encoding (rural vs. suburban/urban), never re-cycled per county.
const COLOR_SUBURBAN = '#2a78d6';
const COLOR_RURAL = '#eb6834';

export default function DisparityPanel({ data }: Props) {
  if (!data) {
    return (
      <div className="p-4 text-sm text-ink-secondary-light dark:text-ink-secondary-dark">
        Loading disparity summary…
      </div>
    );
  }

  const byCounty = new Map<string, { county: string; rural?: number; suburban?: number }>();
  for (const row of data.by_county_rural) {
    const entry = byCounty.get(row.county) ?? { county: row.county };
    if (row.rural_flag) entry.rural = row.mean_risk_exposure;
    else entry.suburban = row.mean_risk_exposure;
    byCounty.set(row.county, entry);
  }
  const chartData = Array.from(byCounty.values()).sort(
    (a, b) => (b.rural ?? b.suburban ?? 0) - (a.rural ?? a.suburban ?? 0),
  );

  const gap = data.gap;
  const ratioText =
    Number.isFinite(gap.rural_vs_suburban_exposure_ratio)
      ? `${gap.rural_vs_suburban_exposure_ratio.toFixed(2)}×`
      : 'n/a';

  return (
    <div className="p-4 space-y-3">
      <div>
        <h2 className="text-sm font-semibold">Rural vs. suburban disparity</h2>
        <p className="text-xs text-ink-secondary-light dark:text-ink-secondary-dark">
          Mean Risk-Exposure by county, split rural / suburban-urban (NC-08).
        </p>
      </div>

      <div className="rounded-md border border-grid-light dark:border-grid-dark p-3 text-xs">
        <p>
          Rural NC-08 segments average{' '}
          <span className="font-semibold tabular-nums">{ratioText}</span> the
          Risk-Exposure of suburban/urban segments, with{' '}
          <span className="font-semibold tabular-nums">
            {gap.rural_vs_suburban_confidence_gap_pct.toFixed(0)} pp
          </span>{' '}
          more segments flagged low-confidence (sparser crash/incident records
          — see Limitations).
        </p>
      </div>

      <div style={{ width: '100%', height: 260 }}>
        <ResponsiveContainer>
          <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--tw-grid, #e1e0d9)" vertical={false} />
            <XAxis dataKey="county" tick={{ fontSize: 11 }} interval={0} angle={-20} textAnchor="end" height={50} />
            <YAxis tick={{ fontSize: 11 }} width={40} />
            <Tooltip
              formatter={(value: number) => value?.toFixed(3)}
              contentStyle={{ fontSize: 12 }}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="suburban" name="Suburban / urban" fill={COLOR_SUBURBAN} radius={[3, 3, 0, 0]} />
            <Bar dataKey="rural" name="Rural" fill={COLOR_RURAL} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
