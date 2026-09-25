interface Props {
  nSegments: number | null;
}

export default function Header({ nSegments }: Props) {
  return (
    <div className="pointer-events-none fixed inset-x-0 top-0 z-30 flex items-start justify-between p-4 sm:p-5">
      <div className="glass-panel pointer-events-auto rounded-lg px-4 py-2.5">
        <h1 className="text-sm font-semibold tracking-tight text-ink-primary">
          AfterImpact NC
        </h1>
        <p className="text-xs text-ink-secondary mt-0.5">
          NC-08 pedestrian and cyclist risk-exposure
          {nSegments !== null && (
            <>
              {' — '}
              <span className="font-data text-ink-secondary">{nSegments.toLocaleString()}</span>
              {' road segments'}
            </>
          )}
        </p>
      </div>
      <a
        href="https://github.com/NarenS31/districtflow-safety"
        target="_blank"
        rel="noreferrer"
        className="glass-panel pointer-events-auto hidden rounded-lg px-3 py-2.5 text-xs text-ink-secondary hover:text-ink-primary transition-colors sm:block"
      >
        Source and data provenance
      </a>
    </div>
  );
}
