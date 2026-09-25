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

// Rural vs. suburban/urban is a CATEGORICAL comparison, not a risk-magnitude
// one — reusing the risk gradient's teal/red here would visually claim
// "rural = dangerous," which the real finding does not support (rural
// measures LOWER, plausibly a reporting-density artifact, not a safety
// one). Two muted neutrals, outside the risk gradient and the accent.
const COLOR_SUBURBAN = '#5B8AA6';
const COLOR_RURAL = '#A6825B';

export default function DisparityPanel({ data }: Props) {
  if (!data) {
    return <div className="p-4 text-sm text-ink-secondary">Loading disparity summary…</div>;
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
  const ratio = gap.rural_vs_suburban_exposure_ratio;
  const ratioText = Number.isFinite(ratio)
    ? ratio >= 1
      ? `${ratio.toFixed(2)}× higher than`
      : `${(ratio * 100).toFixed(0)}% of`
    : null;

  return (
    <div className="p-4 space-y-3">
      <div className="rounded-lg border border-asphalt-line px-3 py-2.5 text-xs text-ink-secondary leading-relaxed">
        {ratioText ? (
          <p>
            Rural NC-08 segments average{' '}
            <span className="font-data font-semibold text-ink-primary">{ratioText}</span>{' '}
            suburban/urban segments' Risk-Exposure, with{' '}
            <span className="font-data font-semibold text-ink-primary">
              {Math.abs(gap.rural_vs_suburban_confidence_gap_pct).toFixed(0)} pp
            </span>{' '}
            {gap.rural_vs_suburban_confidence_gap_pct >= 0 ? 'more' : 'fewer'} rural segments
            flagged low-confidence. A lower rural score plausibly reflects
            sparser crash/incident reporting, not necessarily lower real risk.
          </p>
        ) : (
          <p>Disparity ratio unavailable (insufficient data in one group).</p>
        )}
      </div>

      <div style={{ width: '100%', height: 240 }}>
        <ResponsiveContainer>
          <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2A2E37" vertical={false} />
            <XAxis
              dataKey="county"
              tick={{ fontSize: 10, fill: '#9AA1AC' }}
              interval={0}
              angle={-20}
              textAnchor="end"
              height={48}
              axisLine={{ stroke: '#2A2E37' }}
              tickLine={false}
            />
            <YAxis tick={{ fontSize: 10, fill: '#9AA1AC' }} width={38} axisLine={false} tickLine={false} />
            <Tooltip
              formatter={(value: number) => value?.toFixed(4)}
              contentStyle={{
                fontSize: 12,
                background: '#1C1F26',
                border: '1px solid #2A2E37',
                borderRadius: 8,
                color: '#F2F3F5',
              }}
              cursor={{ fill: 'rgba(255,255,255,0.04)' }}
            />
            <Legend wrapperStyle={{ fontSize: 11, color: '#9AA1AC' }} />
            <Bar dataKey="suburban" name="Suburban / urban" fill={COLOR_SUBURBAN} radius={[3, 3, 0, 0]} />
            <Bar dataKey="rural" name="Rural" fill={COLOR_RURAL} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
