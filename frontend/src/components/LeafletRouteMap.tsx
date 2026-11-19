import React, { useEffect, useRef } from 'react';
import L from 'leaflet';

interface MapWaypoint {
  lat: number;
  lng: number;
  title: string;
  subtitle?: string;
  type?: 'camera' | 'vehicle' | 'incident';
}

interface LeafletRouteMapProps {
  center?: [number, number];
  zoom?: number;
  cameras?: { id: string; name: string; latitude: number; longitude: number; weather: string }[];
  routePoints?: [number, number][];
  activeVehicle?: { plate: string; globalId: string; lat: number; lng: number };
  height?: string;
}

const escapeHtml = (value: string) => value.replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character] ?? character));

export const LeafletRouteMap: React.FC<LeafletRouteMapProps> = ({
  center,
  zoom = 12,
  cameras = [],
  routePoints,
  activeVehicle,
  height = '420px',
}) => {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);

  useEffect(() => {
    if (!mapContainerRef.current) return;

    // Destroy existing instance if any
    if (mapInstanceRef.current) {
      mapInstanceRef.current.remove();
      mapInstanceRef.current = null;
    }

    // Initialize Leaflet Map
    const map = L.map(mapContainerRef.current, {
      center: center ?? routePoints?.[0] ?? (cameras.length ? [cameras[0].latitude, cameras[0].longitude] : [0, 0]),
      zoom: zoom,
      zoomControl: true,
      attributionControl: false,
    });
    mapInstanceRef.current = map;

    // Daylight Tile Layer (CartoDB Voyager)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
      maxZoom: 19,
      subdomains: 'abcd',
    }).addTo(map);

    // Camera Custom Icon
    const createCameraIcon = (id: string) =>
      L.divIcon({
        className: 'custom-camera-marker',
        html: `
          <div style="background: #ffffff; border: 2px solid #2563eb; border-radius: 6px; padding: 2px 6px; font-family: monospace; font-size: 11px; font-weight: bold; color: #1e3a8a; box-shadow: 0 2px 8px rgba(37,99,235,0.25); display: flex; align-items: center; gap: 5px;">
            <span style="display: inline-block; width: 6px; height: 6px; background: #059669; border-radius: 50%;"></span>
            ${escapeHtml(id)}
          </div>
        `,
        iconSize: [44, 24],
        iconAnchor: [22, 12],
      });

    // Add camera markers
    cameras.forEach((cam) => {
      L.marker([cam.latitude, cam.longitude], { icon: createCameraIcon(cam.id) })
        .addTo(map)
        .bindPopup(`
          <div style="color: #0f172a; font-family: sans-serif; font-size: 12px; padding: 4px;">
            <strong>Camera ${escapeHtml(cam.id)}: ${escapeHtml(cam.name)}</strong><br/>
            <span style="color: #475569;">Weather: ${escapeHtml(cam.weather.toUpperCase())}</span><br/>
            <span style="color: #64748b;">Lat: ${cam.latitude.toFixed(4)}, Lng: ${cam.longitude.toFixed(4)}</span>
          </div>
        `);
    });

    // Add Highway Corridor Route Polyline
    const corridorCoords: [number, number][] = routePoints ?? [];

    if (corridorCoords.length >= 2) {
      // Background glow line
      L.polyline(corridorCoords, {
        color: '#2563eb',
        weight: 6,
        opacity: 0.25,
      }).addTo(map);

      // Sharp central line
      L.polyline(corridorCoords, {
        color: '#1d4ed8',
        weight: 3,
        opacity: 0.95,
        dashArray: '5, 8',
      }).addTo(map);
    }

    if (corridorCoords.length) {
      map.fitBounds(L.latLngBounds(corridorCoords), { padding: [24, 24], maxZoom: 16 });
    } else if (cameras.length) {
      map.fitBounds(L.latLngBounds(cameras.map((camera) => [camera.latitude, camera.longitude])), { padding: [24, 24], maxZoom: 15 });
    } else {
      map.setView([0, 0], 1);
    }

    // Active vehicle marker
    if (activeVehicle) {
      const vehicleIcon = L.divIcon({
        className: 'custom-vehicle-marker',
        html: `
          <div style="background: #e11d48; border: 2px solid #ffffff; border-radius: 50%; width: 20px; height: 20px; box-shadow: 0 2px 8px rgba(225,29,72,0.4); display: flex; align-items: center; justify-content: center;">
            <div style="width: 6px; height: 6px; background: white; border-radius: 50%;"></div>
          </div>
        `,
        iconSize: [20, 20],
        iconAnchor: [10, 10],
      });

      L.marker([activeVehicle.lat, activeVehicle.lng], { icon: vehicleIcon })
        .addTo(map)
        .bindPopup(`
          <div style="color: #0f172a; font-family: monospace; font-size: 12px;">
            <strong>${escapeHtml(activeVehicle.globalId)}</strong><br/>
            Plate: ${escapeHtml(activeVehicle.plate)}
          </div>
        `)
        .openPopup();
    }

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, [center, zoom, cameras, routePoints, activeVehicle]);

  return (
    <div className="relative rounded-xl overflow-hidden border border-[#E2E8F0] shadow-sm">
      <div ref={mapContainerRef} style={{ height: height, width: '100%' }} />
      <div className="absolute top-3 right-3 z-[1000] bg-white/95 border border-[#E2E8F0] rounded px-2.5 py-1 text-[11px] font-mono text-blue-600 shadow-sm backdrop-blur-md font-semibold">
        {routePoints?.length ? 'Persisted route coordinates' : cameras.length ? 'Configured camera locations' : 'No geographic points available'}
      </div>
    </div>
  );
};
