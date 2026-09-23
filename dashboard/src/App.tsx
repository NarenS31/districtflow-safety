import { useEffect, useMemo, useState } from 'react';
import { api } from './api/client';
import DisparityPanel from './components/DisparityPanel';
import Header from './components/Header';
import MapView from './components/MapView';
import SegmentDetail from './components/SegmentDetail';
import TopNPanel from './components/TopNPanel';
import type {
  CounterfactualsPayload,
  DisparityPayload,
  PriorityEntry,
  SegmentsPayload,
} from './types';

type LeftTab = 'priority' | 'disparity';

export default function App() {
  const [segments, setSegments] = useState<SegmentsPayload | null>(null);
  const [priority, setPriority] = useState<PriorityEntry[] | null>(null);
  const [disparity, setDisparity] = useState<DisparityPayload | null>(null);
  const [counterfactuals, setCounterfactuals] = useState<CounterfactualsPayload | null>(null);
  const [nSegments, setNSegments] = useState<number | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [leftTab, setLeftTab] = useState<LeftTab>('priority');
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    api.meta().then((m) => setNSegments(m.n_segments)).catch(() => {});
    api.segments().then(setSegments).catch((e) => setLoadError(String(e)));
    api.priorityList().then(setPriority).catch((e) => setLoadError(String(e)));
    api.disparity().then(setDisparity).catch((e) => setLoadError(String(e)));
    api.counterfactuals().then(setCounterfactuals).catch(() => {});
  }, []);

  const selectedEntry = useMemo(
    () => priority?.find((p) => p.segment_id === selectedId) ?? null,
    [priority, selectedId],
  );

  return (
    <div className="h-screen flex flex-col">
      <Header nSegments={nSegments} />

      {loadError && (
        <div className="bg-status-critical/10 text-status-critical text-xs px-4 py-2">
          Failed to load dashboard data — has{' '}
          <code>evaluation/export_dashboard_data.py</code> been run? ({loadError})
        </div>
      )}

      <div className="flex-1 flex min-h-0">
        <aside className="w-80 border-r border-grid-light dark:border-grid-dark flex flex-col min-h-0">
          <div className="flex border-b border-grid-light dark:border-grid-dark text-xs">
            <TabButton active={leftTab === 'priority'} onClick={() => setLeftTab('priority')}>
              Top-N priority
            </TabButton>
            <TabButton active={leftTab === 'disparity'} onClick={() => setLeftTab('disparity')}>
              Disparity
            </TabButton>
          </div>
          <div className="flex-1 min-h-0 overflow-hidden">
            {leftTab === 'priority' ? (
              <TopNPanel entries={priority} selectedId={selectedId} onSelect={setSelectedId} />
            ) : (
              <div className="h-full overflow-y-auto">
                <DisparityPanel data={disparity} />
              </div>
            )}
          </div>
        </aside>

        <main className="flex-1 min-w-0">
          <MapView data={segments} onSelect={setSelectedId} />
        </main>

        <aside className="w-96 border-l border-grid-light dark:border-grid-dark min-h-0">
          <SegmentDetail entry={selectedEntry} counterfactuals={counterfactuals} />
        </aside>
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={
        active
          ? 'flex-1 px-3 py-2 font-medium border-b-2 border-risk-450 text-risk-600 dark:text-risk-300'
          : 'flex-1 px-3 py-2 text-ink-secondary-light dark:text-ink-secondary-dark hover:bg-grid-light dark:hover:bg-grid-dark'
      }
    >
      {children}
    </button>
  );
}
