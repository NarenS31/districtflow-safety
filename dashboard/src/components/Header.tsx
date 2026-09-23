interface Props {
  nSegments: number | null;
}

export default function Header({ nSegments }: Props) {
  return (
    <header className="flex items-center justify-between border-b border-grid-light dark:border-grid-dark px-4 py-3 bg-surface-light dark:bg-surface-dark">
      <div>
        <h1 className="text-lg font-semibold">DistrictFlow Safety</h1>
        <p className="text-xs text-ink-secondary-light dark:text-ink-secondary-dark">
          NC-08 Pedestrian &amp; Cyclist Risk-Exposure Index
          {nSegments !== null && ` · ${nSegments.toLocaleString()} road segments`}
        </p>
      </div>
      <a
        href="https://github.com/NarenS31/districtflow-safety"
        target="_blank"
        rel="noreferrer"
        className="text-xs text-ink-secondary-light dark:text-ink-secondary-dark hover:underline"
      >
        Source &amp; data provenance
      </a>
    </header>
  );
}
