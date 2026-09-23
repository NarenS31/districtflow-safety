// Mirrors evaluation/export_dashboard_data.py's output shapes exactly —
// change one side, change the other, or the dashboard silently shows stale
// fields (no runtime schema check on the frontend, so keep these in sync by
// hand; models/explainer/schema.py is the Python-side source of truth for
// the explanation shape).

export interface SegmentProperties {
  segment_id: string;
  segment_name: string;
  county: string;
  rural_flag: boolean;
  risk_score: number;
  risk_exposure: number;
  data_density_flag: boolean;
  ems_distance_available: boolean;
}

export interface SegmentFeature {
  type: 'Feature';
  geometry: { type: 'LineString'; coordinates: [number, number][] };
  properties: SegmentProperties;
}

export interface SegmentsGeoJSON {
  type: 'FeatureCollection';
  features: SegmentFeature[];
}

export interface SegmentsRecordList {
  type: 'RecordList';
  note: string;
  records: Record<string, unknown>[];
}

export type SegmentsPayload = SegmentsGeoJSON | SegmentsRecordList;

export interface TopFeature {
  feature_name: string;
  importance: number;
  value: number;
  modality: string;
}

export interface Countermeasure {
  category: string;
  fhwa_reference: string;
  rationale: string;
}

export interface PriorityEntry {
  rank: number;
  segment_id: string;
  segment_name: string;
  county: string;
  rural_flag: boolean;
  risk_score: number;
  risk_exposure_score: number;
  data_density_flag: boolean;
  explanation_confidence: number;
  top_features: TopFeature[];
  suggested_countermeasures: Countermeasure[];
}

export interface CountyDisparityRow {
  county: string;
  n_segments: number;
  mean_risk_exposure: number;
  median_risk_exposure: number;
  p90_risk_exposure: number;
  mean_risk_score: number;
  pct_ems_distance_available: number;
  pct_low_confidence: number;
}

export interface RuralDisparityRow extends Omit<CountyDisparityRow, 'county'> {
  rural_flag: boolean;
}

export interface DisparityPayload {
  by_county: CountyDisparityRow[];
  by_rural_suburban: RuralDisparityRow[];
  by_county_rural: (RuralDisparityRow & { county: string })[];
  gap: {
    rural_vs_suburban_exposure_ratio: number;
    rural_vs_suburban_confidence_gap_pct: number;
  };
}

export interface CounterfactualRecord {
  segment_idx: number;
  baseline_risk_score: number;
  updated_risk_score: number;
  delta: number;
}

export interface CounterfactualResult {
  applied: boolean;
  reason?: string;
  intervention?: string;
  target?: CounterfactualRecord;
  hop1_neighbors?: CounterfactualRecord[];
  hop2_neighbors?: CounterfactualRecord[];
}

// segment_id -> intervention_key -> result
export type CounterfactualsPayload = Record<string, Record<string, CounterfactualResult>>;
