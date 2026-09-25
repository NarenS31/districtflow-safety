import { useEffect, useMemo, useState } from 'react';
import { api } from './api/client';
import DisparityPanel from './components/DisparityPanel';
import ErrorBoundary from './components/ErrorBoundary';
import FloatingPanel from './components/FloatingPanel';
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
    <div className="h-screen w-screen relative overflow-hidden bg-asphalt-base">
      {/* The map is the hero — full-bleed, base layer, everything else floats over it. */}
      <ErrorBoundary
        fallback={
          <div className="h-full flex flex-col items-center justify-center p-8 text-center gap-2 bg-asphalt-base">
            <p className="text-sm font-medium text-ink-primary">Map view hit an unexpected error</p>
            <p className="text-xs text-ink-secondary max-w-md">
              The priority list, segment detail, and disparity panels are
              unaffected — every score is still real and live.
            </p>
          </div>
        }
      >
        <MapView data={segments} selectedId={selectedId} onSelect={setSelectedId} />
      </ErrorBoundary>

      <Header nSegments={nSegments} />

      {loadError && (
        <div className="pointer-events-none fixed inset-x-0 top-20 z-30 flex justify-center px-4">
          <div className="glass-panel pointer-events-auto rounded-lg px-3 py-2 text-xs text-risk-high">
            Failed to load dashboard data — has <code className="font-data">evaluation/export_dashboard_data.py</code> been run? ({loadError})
          </div>
        </div>
      )}

      {/* Leaderboard / disparity — top-left on desktop, a bottom sheet on
          mobile that yields to the segment detail sheet once something is
          selected (two competing bottom sheets would fight for the same
          screen real estate on a phone). */}
      <div
        className={
          selectedEntry
            ? 'hidden md:flex pointer-events-none fixed z-20 top-20 left-4'
            : 'flex pointer-events-none fixed z-20 inset-x-0 bottom-0 p-3 md:inset-x-auto md:bottom-auto md:p-0 md:top-20 md:left-4'
        }
      >
        <FloatingPanel
          title="Priority segments"
          side="left"
          collapsible
          tabs={[
            { key: 'priority', label: 'Top 25' },
            { key: 'disparity', label: 'Disparity' },
          ]}
          activeTab={leftTab}
          onTabChange={(k) => setLeftTab(k as LeftTab)}
        >
          {leftTab === 'priority' ? (
            <TopNPanel entries={priority} selectedId={selectedId} onSelect={setSelectedId} />
          ) : (
            <DisparityPanel data={disparity} />
          )}
        </FloatingPanel>
      </div>

      {/* Segment detail — top-right on desktop, a bottom sheet on mobile.
          Always mounted (never display:none) so SegmentDetail's own
          opacity/translate transition can actually animate the slide-in —
          toggling display would make the entry transition invisible since
          a browser can't interpolate from a non-rendered state. Visibility
          when nothing is selected is handled by SegmentDetail itself
          (opacity-0 + pointer-events-none), not by this wrapper. */}
      <div className="flex pointer-events-none fixed z-20 inset-x-0 bottom-0 p-3 md:inset-x-auto md:bottom-auto md:p-0 md:top-20 md:right-4">
        <SegmentDetail
          entry={selectedEntry}
          counterfactuals={counterfactuals}
          onClose={() => setSelectedId(null)}
        />
      </div>
    </div>
  );
}
