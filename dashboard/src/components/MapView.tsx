import { useEffect, useMemo, useRef, useState } from 'react';
import maplibregl, { Map as MLMap } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { SegmentsPayload } from '../types';

interface Props {
  data: SegmentsPayload | null;
  selectedId: string | null;
  onSelect: (segmentId: string) => void;
}

// NC-08 rough centroid (Union/Cabarrus/Mecklenburg cluster around Charlotte).
const NC08_CENTER: [number, number] = [-80.3, 34.95];

const RISK_LOW = '#2E9E8F';
const RISK_MID = '#E85D3D';
const RISK_HIGH = '#D93B3B';
const ACCENT = '#F2A73B';

/** The real risk_exposure distribution is heavily right-skewed (median
 * ~0.0007, p99 ~0.05, max ~1.19 on the live NC-08 data) — a linear color
 * scale across [min, max] would render ~99% of the network as a single
 * flat color. Quantile breakpoints are the standard cartographic fix for
 * skewed spatial data (the same reason choropleth crime/epi maps use
 * quantile or log scales, not linear); computed from whatever data is
 * actually loaded, never hardcoded, so this stays correct if the pipeline
 * re-runs with different numbers. */
function quantileStops(values: number[]): [number, string][] {
  if (values.length === 0) return [[0, RISK_LOW], [1, RISK_HIGH]];
  const sorted = [...values].sort((a, b) => a - b);
  const q = (p: number) => sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * p))];
  return [
    [q(0), RISK_LOW],
    [q(0.5), RISK_LOW],
    [q(0.75), '#7A8F62'], // brief transitional step, teal cooling toward warm
    [q(0.9), RISK_MID],
    [q(0.99), RISK_HIGH],
    [sorted[sorted.length - 1], RISK_HIGH],
  ];
}

export default function MapView({ data, selectedId, onSelect }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MLMap | null>(null);
  // maplibregl.Map's constructor THROWS SYNCHRONOUSLY if it can't get a
  // WebGL context (older devices, some privacy modes, headless/sandboxed
  // browsers) — uncaught inside a useEffect, that unmounts the entire React
  // tree, not just the map, since there's nothing here to catch it. A
  // "professional data product" should degrade to "map unavailable, use
  // the panels" instead of going fully blank. Caught explicitly below.
  const [mapFailed, setMapFailed] = useState(false);

  const featureIndex = useMemo(() => {
    if (!data || data.type !== 'FeatureCollection') return null;
    const idx = new Map<string, GeoJSON.Feature>();
    for (const f of data.features) idx.set(String(f.properties?.segment_id), f);
    return idx;
  }, [data]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    let map: MLMap;
    try {
      map = new maplibregl.Map({
        container: containerRef.current,
        style: {
          version: 8,
          // Esri's Canvas/World_Dark_Gray_* services — genuinely free, no
          // API key required (verified by direct tile fetch; CARTO's
          // basemaps.cartocdn.com raster tiles now watermark unauthenticated
          // requests with "API KEY REQUIRED" text across the whole map,
          // caught only by actually rendering and looking at a screenshot,
          // not by the earlier curl status-code check — a 200 isn't the
          // same as a usable tile).
          sources: {
            'esri-dark-base': {
              type: 'raster',
              tiles: [
                'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
              ],
              tileSize: 256,
              attribution: 'Esri, HERE, Garmin, © OpenStreetMap contributors',
            },
            'esri-dark-labels': {
              type: 'raster',
              tiles: [
                'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}',
              ],
              tileSize: 256,
            },
          },
          layers: [
            { id: 'basemap', type: 'raster', source: 'esri-dark-base', paint: { 'raster-opacity': 0.9 } },
            { id: 'basemap-labels', type: 'raster', source: 'esri-dark-labels', paint: { 'raster-opacity': 0.6 } },
          ],
        },
        center: NC08_CENTER,
        zoom: 9,
        // One thing is allowed to move on load (brief's own carve-out): the
        // initial ease into the district view. Everything after this is
        // strictly a response to a click/toggle, never automatic.
      });
    } catch (err) {
      console.error('[MapView] WebGL map init failed, falling back:', err);
      setMapFailed(true);
      return;
    }
    map.on('error', (e) => {
      // A WebGL context can also be LOST after successful creation (GPU
      // process crash, tab backgrounding on some browsers) — same
      // fallback, not a silent dead map.
      console.error('[MapView] map runtime error:', e.error);
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !data || data.type !== 'FeatureCollection') return;

    const applyLayer = () => {
      const stops = quantileStops(
        data.features.map((f) => Number(f.properties?.risk_exposure ?? 0)),
      );
      const colorExpr: any[] = ['interpolate', ['linear'], ['get', 'risk_exposure']];
      for (const [v, c] of stops) colorExpr.push(v, c);

      if (map.getSource('segments')) {
        (map.getSource('segments') as maplibregl.GeoJSONSource).setData(data as GeoJSON.FeatureCollection);
        return;
      }
      map.addSource('segments', { type: 'geojson', data: data as GeoJSON.FeatureCollection });

      map.addLayer({
        id: 'segments-line',
        type: 'line',
        source: 'segments',
        layout: { 'line-cap': 'round' },
        paint: {
          'line-width': ['interpolate', ['linear'], ['zoom'], 8, 1.5, 14, 4],
          'line-color': colorExpr as any,
          'line-opacity': 0.9,
        },
      });

      // Selection highlight — the accent, never a risk-gradient color, so
      // "this is selected" is never confusable with "this is high risk."
      map.addLayer({
        id: 'segments-selected',
        type: 'line',
        source: 'segments',
        layout: { 'line-cap': 'round' },
        paint: {
          'line-width': ['interpolate', ['linear'], ['zoom'], 8, 4, 14, 9],
          'line-color': ACCENT,
          'line-opacity': 0.55,
          'line-blur': 1.5,
        },
        filter: ['==', ['get', 'segment_id'], ''],
      });

      map.on('click', 'segments-line', (e) => {
        const f = e.features?.[0];
        if (f?.properties?.segment_id) onSelect(String(f.properties.segment_id));
      });
      map.on('mouseenter', 'segments-line', () => {
        map.getCanvas().style.cursor = 'pointer';
      });
      map.on('mouseleave', 'segments-line', () => {
        map.getCanvas().style.cursor = '';
      });
    };

    if (map.isStyleLoaded()) applyLayer();
    else map.once('load', applyLayer);
  }, [data, onSelect]);

  // Pan/zoom to the selected segment and highlight it — triggered only by
  // selection changing (a click on the map or a leaderboard row), never on
  // an unrelated re-render. MapLibre's flyTo automatically respects
  // prefers-reduced-motion (jumps instead of easing) with no extra code.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.getLayer('segments-selected')) return;

    if (!selectedId) {
      map.setFilter('segments-selected', ['==', ['get', 'segment_id'], '']);
      return;
    }
    map.setFilter('segments-selected', ['==', ['get', 'segment_id'], selectedId]);

    const feature = featureIndex?.get(selectedId);
    if (feature?.geometry?.type === 'LineString') {
      const coords = feature.geometry.coordinates as [number, number][];
      const mid = coords[Math.floor(coords.length / 2)];
      map.flyTo({ center: mid, zoom: Math.max(map.getZoom(), 13.5), duration: 900, essential: false });
    }
  }, [selectedId, featureIndex]);

  if (data && data.type === 'RecordList') {
    return (
      <div className="h-full flex flex-col items-center justify-center p-8 text-center gap-2 bg-asphalt-base">
        <p className="text-sm font-medium text-ink-primary">Road geometry not yet integrated</p>
        <p className="text-xs text-ink-secondary max-w-md">
          {data.note} Use the priority list and disparity panel — every
          score is real, computed by RiskGNN from the assembled feature
          table; only the map's line geometry is pending ISRN/OSM integration.
        </p>
      </div>
    );
  }

  if (mapFailed) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-8 text-center gap-2 bg-asphalt-base">
        <p className="text-sm font-medium text-ink-primary">Map rendering unavailable in this browser</p>
        <p className="text-xs text-ink-secondary max-w-md">
          WebGL couldn't initialize here. The priority list, segment
          detail, and disparity panels are unaffected — every score is
          still real and live, just without the map view.
        </p>
      </div>
    );
  }

  return <div ref={containerRef} className="h-full w-full bg-asphalt-base" />;
}
