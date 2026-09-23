import { useEffect, useRef } from 'react';
import maplibregl, { Map as MLMap } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { SegmentsPayload } from '../types';

interface Props {
  data: SegmentsPayload | null;
  onSelect: (segmentId: string) => void;
}

// NC-08 rough centroid (Union/Cabarrus/Mecklenburg cluster around Charlotte).
const NC08_CENTER: [number, number] = [-80.3, 34.95];

// Sequential risk ramp (dataviz skill's validated blue ramp, light -> dark =
// low -> high Risk-Exposure). Five stops keeps the legend readable.
const RISK_COLOR_STOPS: [number, string][] = [
  [0, '#cde2fb'],
  [0.25, '#6da7ec'],
  [0.5, '#2a78d6'],
  [0.75, '#1c5cab'],
  [1, '#0d366b'],
];

export default function MapView({ data, onSelect }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MLMap | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: 'raster',
            tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
            tileSize: 256,
            attribution: '© OpenStreetMap contributors',
          },
        },
        layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
      },
      center: NC08_CENTER,
      zoom: 9,
    });
    map.addControl(new maplibregl.NavigationControl(), 'top-right');
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
      if (map.getSource('segments')) {
        (map.getSource('segments') as maplibregl.GeoJSONSource).setData(data as GeoJSON.FeatureCollection);
        return;
      }
      map.addSource('segments', { type: 'geojson', data: data as GeoJSON.FeatureCollection });
      map.addLayer({
        id: 'segments-line',
        type: 'line',
        source: 'segments',
        paint: {
          'line-width': ['interpolate', ['linear'], ['zoom'], 8, 1.5, 14, 4],
          'line-color': [
            'interpolate',
            ['linear'],
            ['get', 'risk_exposure'],
            ...RISK_COLOR_STOPS.flat(),
          ],
        },
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

  if (data && data.type === 'RecordList') {
    return (
      <div className="h-full flex flex-col items-center justify-center p-8 text-center gap-2">
        <p className="text-sm font-medium">Road geometry not yet integrated</p>
        <p className="text-xs text-ink-secondary-light dark:text-ink-secondary-dark max-w-md">
          {data.note} Use the Top-N priority list and disparity panel — every
          score below is real, computed by RiskGNN from the assembled feature
          table; only the map's line geometry is pending ISRN/OSM integration.
        </p>
      </div>
    );
  }

  return <div ref={containerRef} className="h-full w-full" />;
}
