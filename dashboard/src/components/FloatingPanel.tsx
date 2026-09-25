import { useState } from 'react';
import clsx from 'clsx';

interface Props {
  title: string;
  subtitle?: string;
  collapsible?: boolean;
  defaultCollapsed?: boolean;
  side: 'left' | 'right';
  tabs?: { key: string; label: string }[];
  activeTab?: string;
  onTabChange?: (key: string) => void;
  children: React.ReactNode;
}

/** The one glass surface treatment every floating panel shares, so the map
 * (no card treatment) and the leaderboard rows (tier-coded borders, not
 * glass) read as deliberately different surfaces rather than "everything's
 * the same rounded grey card." */
export default function FloatingPanel({
  title,
  subtitle,
  collapsible,
  defaultCollapsed = false,
  side,
  tabs,
  activeTab,
  onTabChange,
  children,
}: Props) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  return (
    <div
      className={clsx(
        'glass-panel pointer-events-auto flex flex-col rounded-xl overflow-hidden',
        'w-[min(92vw,360px)] max-h-[min(70vh,640px)]',
      )}
    >
      <div className="flex items-center justify-between px-4 pt-3.5 pb-2 shrink-0">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-ink-primary truncate">{title}</h2>
          {subtitle && <p className="text-xs text-ink-secondary mt-0.5">{subtitle}</p>}
        </div>
        {collapsible && (
          <button
            onClick={() => setCollapsed((c) => !c)}
            aria-label={collapsed ? `Expand ${title}` : `Collapse ${title}`}
            aria-expanded={!collapsed}
            className="shrink-0 h-7 w-7 rounded-md flex items-center justify-center text-ink-secondary hover:text-accent hover:bg-white/5 transition-colors"
          >
            <ChevronIcon collapsed={collapsed} side={side} />
          </button>
        )}
      </div>

      {tabs && (
        <div className="flex px-2 gap-1 shrink-0">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => onTabChange?.(t.key)}
              className={clsx(
                'px-2.5 py-1.5 text-xs rounded-md transition-colors',
                activeTab === t.key
                  ? 'text-accent bg-accent/10'
                  : 'text-ink-secondary hover:text-ink-primary hover:bg-white/5',
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
      )}

      {!collapsed && <div className="flex-1 min-h-0 overflow-y-auto">{children}</div>}
    </div>
  );
}

function ChevronIcon({ collapsed, side }: { collapsed: boolean; side: 'left' | 'right' }) {
  // Points toward "collapse direction" when expanded, away when collapsed —
  // the icon itself, not a color, carries the state (never color alone).
  const rotate = collapsed ? (side === 'left' ? -90 : 90) : 0;
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ transform: `rotate(${rotate}deg)`, transition: 'transform 200ms ease' }}>
      <path d="M4 5.5L7 8.5L10 5.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
