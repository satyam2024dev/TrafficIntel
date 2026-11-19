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

    // Dark Tile Layer (CartoDB DarkMatter)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      maxZoom: 19,
      subdomains: 'abcd',
    }).addTo(map);

    // Camera Custom Icon
    const createCameraIcon = (id: string) =>
      L.divIcon({
        className: 'custom-camera-marker',
        html: `
          <div style="background: #0f172a; border: 2px solid #06b6d4; border-radius: 6px; padding: 2px 6px; font-family: monospace; font-size: 11px; font-weight: bold; color: #38bdf8; box-shadow: 0 0 10px rgba(6,182,212,0.5); display: flex; align-items: center; gap: 4px;">
            <span style="display: inline-block; width: 6px; height: 6px; background: #10b981; border-radius: 50%;"></span>
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
            <span>Weather: ${escapeHtml(cam.weather.toUpperCase())}</span><br/>
            <span>Lat: ${cam.latitude.toFixed(4)}, Lng: ${cam.longitude.toFixed(4)}</span>
          </div>
        `);
    });

    // Add Highway Corridor Route Polyline
    const corridorCoords: [number, number][] = routePoints ?? [];

    if (corridorCoords.length >= 2) {
      // Glow background line
      L.polyline(corridorCoords, {
        color: '#06b6d4',
        weight: 6,
        opacity: 0.35,
      }).addTo(map);

      // Sharp central line
      L.polyline(corridorCoords, {
        color: '#38bdf8',
        weight: 3,
        opacity: 0.9,
        dashArray: '4, 8',
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
          <div style="background: #e11d48; border: 2px solid #ffffff; border-radius: 50%; width: 18px; height: 18px; box-shadow: 0 0 12px #f43f5e; display: flex; align-items: center; justify-content: center;">
            <div style="width: 6px; height: 6px; background: white; border-radius: 50%;"></div>
          </div>
        `,
        iconSize: [18, 18],
        iconAnchor: [9, 9],
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
    <div className="relative rounded-xl overflow-hidden border border-[#222634] shadow-sm">
      <div ref={mapContainerRef} style={{ height: height, width: '100%' }} />
      <div className="absolute top-3 right-3 z-[1000] bg-[#11131A]/95 border border-[#222634] rounded px-2.5 py-1 text-[11px] font-mono text-blue-400 backdrop-blur-md">
        {routePoints?.length ? 'Persisted route coordinates' : cameras.length ? 'Configured camera locations' : 'No geographic points available'}
      </div>
    </div>
  );
};
