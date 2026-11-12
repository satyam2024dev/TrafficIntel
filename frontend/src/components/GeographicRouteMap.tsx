import React, { useEffect, useRef } from 'react';
import type * as Leaflet from 'leaflet';
import { GeographicRouteTrack } from '../types';

interface GeographicRouteMapProps { tracks: GeographicRouteTrack[] | import('../types').LiveGeographicRouteTrack[]; height?: string; }

const escapeHtml = (value: string) => value.replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character] ?? character));

export const GeographicRouteMap: React.FC<GeographicRouteMapProps> = ({ tracks, height = '320px' }) => {
  const host = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    let cancelled = false;
    let map: Leaflet.Map | null = null;
    const initialize = async () => {
      if (cancelled || !host.current) return;
      const L = await import('leaflet');
      if (cancelled || !host.current) return;
      map = L.map(host.current, { zoomControl: true, attributionControl: true });
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap contributors' }).addTo(map);
      const bounds: Leaflet.LatLngExpression[] = [];
      tracks.forEach((track, index) => {
        const points = track.points;
        if (!points.length) return;
        const hue = Array.from(String(track.track_id)).reduce<number>((sum: number, char: string) => sum + char.charCodeAt(0), index * 47) % 360;
        const color = `hsl(${hue}, 82%, 56%)`;
        const bySource = new Map<string, typeof points>();
        points.forEach((point) => bySource.set(point.source_type, [...(bySource.get(point.source_type) ?? []), point]));
        bySource.forEach((sourcePoints, source) => {
          const coordinates: Leaflet.LatLngExpression[] = sourcePoints.map((point) => [point.latitude, point.longitude]);
          bounds.push(...coordinates);
          if (coordinates.length > 1) L.polyline(coordinates, { color: source === 'gps_observation' ? color : '#f59e0b', weight: 4, opacity: 0.85, dashArray: source === 'gps_observation' ? undefined : '7, 5' }).addTo(map!);
        });
        points.forEach((point) => {
          const location = L.circleMarker([point.latitude, point.longitude], { radius: 6, color, fillColor: color, fillOpacity: 0.9 }).addTo(map!);
          const timestamp = point.timestamp ? new Date(point.timestamp).toLocaleString() : point.media_timestamp_seconds === null ? 'Timestamp unavailable' : `Video +${point.media_timestamp_seconds.toFixed(2)} s`;
          const pointPlates = point.plate_reads.map((plate) => plate.validated_registration_number || plate.normalized_ocr_text || plate.raw_ocr_text).filter(Boolean).join(', ');
          const trackPlates = track.plate_reads.map((plate) => plate.validated_registration_number || plate.normalized_ocr_text || plate.raw_ocr_text).filter(Boolean).join(', ');
          const plateText = pointPlates ? `Detection plate: ${pointPlates}` : trackPlates ? `Track plate history (time not matched to this point): ${trackPlates}` : 'No plate read available';
          location.bindPopup(`<strong>Track #${escapeHtml(track.track_id)}</strong><br/>${escapeHtml(point.camera_name ?? point.camera_id ?? 'Camera unavailable')}<br/>${escapeHtml(timestamp)}<br/>${escapeHtml(point.source_type === 'gps_observation' ? 'GPS observation' : 'Calibrated estimate')}<br/>${escapeHtml(plateText)}`);
        });
      });
      if (bounds.length) map.fitBounds(L.latLngBounds(bounds), { padding: [24, 24], maxZoom: 17 });
      else map.setView([0, 0], 2);
      window.setTimeout(() => map?.invalidateSize(), 0);
    };
    initialize();
    return () => { cancelled = true; map?.remove(); };
  }, [tracks]);
  return <div className="overflow-hidden rounded-lg border border-slate-800" aria-label="Geographic vehicle route map"><div ref={host} style={{ height, width: '100%' }} /></div>;
};
