import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Car,
  Clock,
  MapPin,
  ScanLine,
  ShieldAlert,
  ArrowLeft,
} from 'lucide-react';
import { PlateBadge } from '../components/PlateBadge';
import { WeatherBadge } from '../components/WeatherBadge';
import { LeafletRouteMap } from '../components/LeafletRouteMap';
import { api } from '../services/api';
import { Vehicle } from '../types';
import { formatDate } from '../utils/formatters';

export const VehicleDetails: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const targetId = id || 'GLOBAL-VEHICLE-892';

  const [vehicle, setVehicle] = useState<Vehicle | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchVehicle() {
      try {
        setLoading(true);
        setError(null);
        const data = await api.getVehicleById(targetId);
        setVehicle(data);
      } catch (err: any) {
        setError(err.message || 'Failed to load vehicle details');
      } finally {
        setLoading(false);
      }
    }
    fetchVehicle();
  }, [targetId]);

  if (loading) {
    return (
      <div className="py-20 text-center text-slate-500 font-mono text-xs animate-pulse">
        Fetching multi-camera vehicle intelligence dossier for {targetId}...
      </div>
    );
  }

  if (error || !vehicle) {
    return (
      <div className="bg-white p-8 rounded-xl border border-rose-200 text-center space-y-4 shadow-sm">
        <ShieldAlert className="w-10 h-10 text-rose-600 mx-auto" />
        <h2 className="text-base font-bold text-slate-900">Vehicle Record Not Found</h2>
        <p className="text-xs text-slate-500">{error || `No dossier found for ID ${targetId}`}</p>
        <Link
          to="/vehicles"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-white border border-[#CBD5E1] text-blue-600 hover:text-blue-700 text-xs font-mono transition shadow-sm font-semibold"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Fleet Directory</span>
        </Link>
      </div>
    );
  }

  // Waypoints for Route Map
  const activeRoute = vehicle.routes && vehicle.routes.length > 0 ? vehicle.routes[0] : null;
  const mapPoints: [number, number][] = activeRoute?.points?.map((pt) => [pt.latitude, pt.longitude]) || [];

  return (
    <div className="space-y-6">
      {/* Top Breadcrumb & Action */}
      <div className="flex items-center justify-between">
        <Link
          to="/vehicles"
          className="inline-flex items-center gap-2 text-xs font-mono font-semibold text-[#00A8C6] hover:text-[#0090AA] transition"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Fleet Directory</span>
        </Link>

        <span className="text-xs font-mono px-3 py-1 rounded-xl bg-white text-slate-600 border border-slate-200/90 shadow-sm font-medium">
          RE-IDENTIFICATION PROTOCOL v1.0
        </span>
      </div>

      {/* Primary Dossier Header Card */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200/90 flex flex-col lg:flex-row lg:items-center justify-between gap-6 shadow-sm border-t-[3px] border-t-[#00A8C6]">
        <div className="flex flex-col sm:flex-row sm:items-center gap-4">
          <div className="w-16 h-16 rounded-2xl bg-teal-50 border border-teal-200 flex items-center justify-center text-[#00A8C6] shadow-sm">
            <Car className="w-8 h-8 text-[#00A8C6]" />
          </div>
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-xl font-extrabold font-mono text-slate-900 tracking-tight">
                {vehicle.id}
              </h1>
              <PlateBadge
                plate={vehicle.license_plate}
                isFlagged={vehicle.status === 'flagged'}
                size="md"
              />
              <span
                className={`text-[10px] uppercase font-mono px-2.5 py-0.5 rounded-lg border ${
                  vehicle.status === 'flagged'
                    ? 'bg-rose-50 text-rose-700 border-rose-300 animate-pulse font-bold'
                    : 'bg-emerald-50 text-emerald-700 border-emerald-300 font-bold'
                }`}
              >
                {vehicle.status}
              </span>
            </div>
            <p className="text-xs text-slate-500">
              Registered Owner: <span className="text-slate-800 font-semibold">{vehicle.registered_owner || 'Commercial Transport Fleet'}</span> • Make: <span className="text-slate-700">{vehicle.vehicle_make || `${vehicle.color} ${vehicle.vehicle_type}`}</span>
            </p>
          </div>
        </div>

        {/* Quick KPI stats */}
        <div className="flex items-center gap-4 sm:gap-6 border-t lg:border-t-0 pt-4 lg:pt-0 border-slate-200 text-xs">
          <div>
            <span className="text-slate-500 block text-[10px] uppercase font-mono font-bold">Confidence</span>
            <span className="text-base font-extrabold font-mono tabular-nums text-[#00A8C6]">
              {(vehicle.confidence * 100).toFixed(1)}%
            </span>
          </div>
          <div>
            <span className="text-slate-500 block text-[10px] uppercase font-mono font-bold">Avg Speed</span>
            <span className="text-base font-extrabold font-mono tabular-nums text-[#F59E0B]">
              {vehicle.avg_speed_kmh} km/h
            </span>
          </div>
          <div>
            <span className="text-slate-500 block text-[10px] uppercase font-mono font-bold">Sightings</span>
            <span className="text-base font-extrabold font-mono tabular-nums text-[#0F172A]">
              {vehicle.total_sightings} Nodes
            </span>
          </div>
        </div>
      </div>

      {/* Middle Grid: Route Map & Camera Timeline */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Reconstructed Route Map (2 Cols) */}
        <div className="lg:col-span-2 bg-white p-5 rounded-2xl border border-slate-200/90 flex flex-col shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <MapPin className="w-4 h-4 text-[#00A8C6]" />
                <span>Reconstructed Multi-Camera Trajectory</span>
              </h3>
              <p className="text-xs text-slate-500">
                Corridor Nodes: {activeRoute?.cameras_visited.join(' → ') || 'C01 → C02 → C03 → C04'}
              </p>
            </div>
            {activeRoute && (
              <div className="text-right font-mono text-xs">
                <span className="text-[#00A8C6] font-bold tabular-nums">{activeRoute.distance_km} km</span>
                <span className="text-slate-500 text-[11px] block tabular-nums">{activeRoute.duration_minutes} min journey</span>
              </div>
            )}
          </div>

          <div className="flex-1 min-h-[340px]">
            <LeafletRouteMap
              routePoints={mapPoints.length > 0 ? mapPoints : undefined}
              height="340px"
            />
          </div>
        </div>

        {/* Spatiotemporal Timeline (1 Col) */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/90 flex flex-col shadow-sm">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 mb-4 flex items-center gap-2">
            <Clock className="w-4 h-4 text-[#00A8C6]" />
            <span>Multi-Camera Sighting Timeline</span>
          </h3>

          <div className="relative pl-6 space-y-6 before:content-[''] before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-[#E2E8F0]">
            {vehicle.observations && vehicle.observations.length > 0 ? (
              vehicle.observations.map((obs, idx) => (
                <div key={obs.id || idx} className="relative">
                  <div className="absolute -left-6 top-1 w-3 h-3 rounded-full bg-[#00A8C6] border-2 border-white shadow-sm" />
                  <div className="p-3.5 rounded-xl bg-[#F8FAFC] border border-slate-200 text-xs space-y-1 shadow-sm">
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-bold text-slate-900">
                        Camera {obs.camera_id}
                      </span>
                      <span className="text-[10px] font-mono tabular-nums text-[#F59E0B] font-bold">
                        {obs.speed_kmh} km/h
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-500 font-mono">
                      Track ID: <span className="text-[#00A8C6] font-bold">#{obs.local_track_id}</span>
                    </div>
                    <div className="flex items-center justify-between pt-1">
                      <WeatherBadge condition={obs.weather_condition} showFilter={false} />
                      <span className="text-[10px] text-slate-500 font-mono">
                        {formatDate(obs.observed_at)}
                      </span>
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-xs text-slate-500 font-mono py-8 text-center">
                No observation waypoints recorded.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Bottom Table: ANPR OCR Reads for this Vehicle */}
      <div className="bg-white p-5 rounded-2xl border border-slate-200/90 shadow-sm">
        <h3 className="text-sm font-bold text-slate-900 mb-1 flex items-center gap-2">
          <ScanLine className="w-4 h-4 text-[#00A8C6]" />
          <span>Optical Character Recognition (ANPR) Captures</span>
        </h3>
        <p className="text-xs text-slate-500 mb-4">
          Atmospheric condition, applied enhancement filter, and confidence scores across nodes.
        </p>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#F8FAFC] text-slate-600 font-mono uppercase text-[10px] border-b border-[#E2E8F0]">
              <tr>
                <th className="py-3 px-3">Camera Node</th>
                <th className="py-3 px-3">Extracted Plate</th>
                <th className="py-3 px-3">OCR Confidence</th>
                <th className="py-3 px-3">Atmospheric Condition</th>
                <th className="py-3 px-3">CV Enhancement Applied</th>
                <th className="py-3 px-3">Timestamp</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E2E8F0] font-medium">
              {vehicle.plate_detections && vehicle.plate_detections.length > 0 ? (
                vehicle.plate_detections.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50 transition">
                    <td className="py-3 px-3 font-mono font-bold text-[#00A8C6]">
                      {p.camera_id}
                    </td>
                    <td className="py-3 px-3">
                      <PlateBadge plate={p.plate_number} isFlagged={p.is_flagged} size="sm" />
                    </td>
                    <td className="py-3 px-3 font-mono tabular-nums text-slate-800 font-semibold">
                      {(p.ocr_confidence * 100).toFixed(1)}%
                    </td>
                    <td className="py-3 px-3">
                      <WeatherBadge condition={p.weather_condition} showFilter={false} />
                    </td>
                    <td className="py-3 px-3 font-mono text-[#0891B2] uppercase text-[11px] font-bold">
                      {p.enhancement_applied}
                    </td>
                    <td className="py-3 px-3 text-slate-500 font-mono text-[11px]">
                      {formatDate(p.detected_at)}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="text-center py-6 text-slate-500 font-mono text-xs">
                    No plate OCR events registered.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
