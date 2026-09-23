import type {
  CounterfactualsPayload,
  DisparityPayload,
  PriorityEntry,
  SegmentsPayload,
} from '../types';

// Static-first (brief §9: reliably load for judges, no backend risk). Every
// file here is a build artifact from evaluation/export_dashboard_data.py —
// this client never fabricates data if a fetch 404s, it surfaces the gap.
const BASE = `${import.meta.env.BASE_URL}data`;

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}/${path}`);
  if (!res.ok) {
    throw new Error(`Failed to load ${path}: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  segments: () => getJSON<SegmentsPayload>('segments.json'),
  priorityList: () => getJSON<PriorityEntry[]>('priority_list.json'),
  disparity: () => getJSON<DisparityPayload>('disparity.json'),
  counterfactuals: () => getJSON<CounterfactualsPayload>('counterfactuals.json'),
  meta: () => getJSON<{ n_segments: number; generated_from: string }>('meta.json'),
};
