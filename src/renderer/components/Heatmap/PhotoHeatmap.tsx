import React, { useEffect, useRef, useState } from 'react';
import { useImages } from '../../hooks/useImages';

interface GeoPoint {
  lat: number;
  lng: number;
  count: number;
  filename: string;
}

const PhotoHeatmap: React.FC = () => {
  const mapRef = useRef<HTMLDivElement>(null);
  const [geoPoints, setGeoPoints] = useState<GeoPoint[]>([]);
  const [selectedPoint, setSelectedPoint] = useState<GeoPoint | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);

  // Load all images with GPS data
  const { data } = useImages({
    page: 1,
    pageSize: 10000,
  });

  useEffect(() => {
    if (!data?.images) return;

    const points: GeoPoint[] = [];
    for (const img of data.images) {
      if (img.metadata.latitude != null && img.metadata.longitude != null) {
        points.push({
          lat: img.metadata.latitude,
          lng: img.metadata.longitude,
          count: 1,
          filename: img.filename,
        });
      }
    }
    setGeoPoints(points);
    setMapLoaded(true);
  }, [data]);

  // Group points by proximity for cluster display
  const clusters = React.useMemo(() => {
    if (geoPoints.length === 0) return [];

    const GRID_SIZE = 0.5; // degrees
    const grid = new Map<string, GeoPoint & { items: GeoPoint[] }>();

    for (const pt of geoPoints) {
      const gridKey = `${Math.round(pt.lat / GRID_SIZE)},${Math.round(pt.lng / GRID_SIZE)}`;
      const existing = grid.get(gridKey);
      if (existing) {
        existing.count++;
        existing.items.push(pt);
        existing.lat = (existing.lat + pt.lat) / 2;
        existing.lng = (existing.lng + pt.lng) / 2;
      } else {
        grid.set(gridKey, { ...pt, items: [pt] });
      }
    }

    return Array.from(grid.values());
  }, [geoPoints]);

  // Calculate SVG map bounds
  const bounds = React.useMemo(() => {
    if (geoPoints.length === 0) return { minLat: -90, maxLat: 90, minLng: -180, maxLng: 180 };
    let minLat = 90, maxLat = -90, minLng = 180, maxLng = -180;
    for (const pt of geoPoints) {
      minLat = Math.min(minLat, pt.lat);
      maxLat = Math.max(maxLat, pt.lat);
      minLng = Math.min(minLng, pt.lng);
      maxLng = Math.max(maxLng, pt.lng);
    }
    // Add padding
    const latPad = Math.max((maxLat - minLat) * 0.2, 2);
    const lngPad = Math.max((maxLng - minLng) * 0.2, 2);
    return {
      minLat: minLat - latPad,
      maxLat: maxLat + latPad,
      minLng: minLng - lngPad,
      maxLng: maxLng + lngPad,
    };
  }, [geoPoints]);

  const toSvgCoords = (lat: number, lng: number, width: number, height: number) => {
    const x = ((lng - bounds.minLng) / (bounds.maxLng - bounds.minLng)) * width;
    const y = height - ((lat - bounds.minLat) / (bounds.maxLat - bounds.minLat)) * height;
    return { x, y };
  };

  const maxCount = Math.max(1, ...clusters.map((c) => c.count));

  return (
    <div className="flex flex-col h-full bg-gray-950">
      {/* Stats bar */}
      <div className="flex items-center gap-6 px-6 py-3 border-b border-gray-800 bg-gray-900 flex-shrink-0">
        <div className="text-sm text-gray-400">
          <span className="text-white font-semibold">{geoPoints.length}</span> geotagged photos
        </div>
        <div className="text-sm text-gray-400">
          <span className="text-white font-semibold">{clusters.length}</span> locations
        </div>
        {selectedPoint && (
          <div className="text-sm text-gray-400 ml-auto">
            <span className="text-white">{selectedPoint.filename}</span> &nbsp;
            <span className="text-gray-500">{selectedPoint.lat.toFixed(4)}, {selectedPoint.lng.toFixed(4)}</span>
          </div>
        )}
      </div>

      {/* Map */}
      <div className="flex-1 relative" ref={mapRef}>
        {!mapLoaded || geoPoints.length === 0 ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-600">
            <svg className="w-16 h-16 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1}
                d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
            </svg>
            <div className="text-lg font-medium">No geotagged photos</div>
            <div className="text-sm mt-1">Import photos with GPS data to see them on the map</div>
          </div>
        ) : (
          <svg
            className="w-full h-full"
            viewBox="0 0 1000 600"
            preserveAspectRatio="xMidYMid meet"
            onClick={() => setSelectedPoint(null)}
          >
            {/* Background */}
            <rect width="1000" height="600" fill="#0a0a0f" />

            {/* Grid lines */}
            {Array.from({ length: 10 }, (_, i) => (
              <line
                key={`h${i}`}
                x1="0" y1={i * 60} x2="1000" y2={i * 60}
                stroke="#1f2937" strokeWidth="0.5"
              />
            ))}
            {Array.from({ length: 17 }, (_, i) => (
              <line
                key={`v${i}`}
                x1={i * 62.5} y1="0" x2={i * 62.5} y2="600"
                stroke="#1f2937" strokeWidth="0.5"
              />
            ))}

            {/* Heat points */}
            {clusters.map((cluster, i) => {
              const { x, y } = toSvgCoords(cluster.lat, cluster.lng, 1000, 600);
              const radius = Math.max(8, Math.min(40, (cluster.count / maxCount) * 40 + 8));
              const opacity = 0.3 + (cluster.count / maxCount) * 0.7;
              const isSelected = selectedPoint?.filename === cluster.filename;

              return (
                <g key={i} onClick={(e) => { e.stopPropagation(); setSelectedPoint(cluster); }}>
                  {/* Glow effect */}
                  <circle
                    cx={x} cy={y}
                    r={radius * 1.8}
                    fill={`rgba(59, 130, 246, ${opacity * 0.15})`}
                  />
                  <circle
                    cx={x} cy={y}
                    r={radius}
                    fill={`rgba(59, 130, 246, ${opacity})`}
                    stroke={isSelected ? '#93c5fd' : 'rgba(147, 197, 253, 0.3)'}
                    strokeWidth={isSelected ? 2 : 0.5}
                    className="cursor-pointer transition-all hover:opacity-100"
                  />
                  {cluster.count > 1 && (
                    <text
                      x={x} y={y + 4}
                      textAnchor="middle"
                      fill="white"
                      fontSize={Math.max(8, Math.min(14, radius * 0.7))}
                      fontWeight="600"
                      className="pointer-events-none select-none"
                    >
                      {cluster.count}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>
        )}

        {/* Legend */}
        {geoPoints.length > 0 && (
          <div className="absolute bottom-4 left-4 bg-gray-900/90 border border-gray-700 rounded-lg px-3 py-2">
            <div className="text-xs text-gray-400 mb-2">Density</div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-blue-900/50" />
              <span className="text-xs text-gray-500">1 photo</span>
              <div className="w-5 h-5 rounded-full bg-blue-600/70" />
              <span className="text-xs text-gray-500">many photos</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default PhotoHeatmap;
