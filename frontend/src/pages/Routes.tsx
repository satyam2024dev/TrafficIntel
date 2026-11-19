import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Navigation, ArrowRight, Gauge } from 'lucide-react';
import { LeafletRouteMap } from '../components/LeafletRouteMap';
import { api } from '../services/api';
import { Route } from '../types';
import { formatDate, formatDuration } from '../utils/formatters';

export const Routes: React.FC = () => {
  const [routes, setRoutes] = useState<Route[]>([]);
  const [selectedRoute, setSelectedRoute] = useState<Route | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    async function loadRoutes() {
      try {
        setLoading(true);
        const data = await api.getRoutes(50);
        setRoutes(data);
        if (data.length > 0) {
          setSelectedRoute(data[0]);
        }
      } catch (err) {
        console.error('Failed to load routes', err);
      } finally {
        setLoading(false);
      }
    }
    loadRoutes();
  }, []);

  const routeCoordinates: [number, number][] =
    selectedRoute?.points?.map((pt) => [pt.latitude, pt.longitude]) || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-extrabold text-slate-900 flex items-center gap-2.5 tracking-tight">
            <Navigation className="w-5 h-5 text-[#00A8C6]" />
            <span>Reconstructed Multi-Camera Trajectories</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Reconstructed vehicle paths across camera topology with kinematics and anomaly detection.
          </p>
        </div>
        <div className="text-xs font-mono text-slate-700 bg-white border border-slate-200/90 px-3.5 py-1.5 rounded-xl shadow-sm font-semibold">
          Active Routes: <span className="text-[#00A8C6] font-extrabold tabular-nums">{routes.length}</span>
        </div>
      </div>

      <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800 shadow-sm font-medium" role="note">
        These legacy corridor records come from the dashboard simulation tables. They are not verified GPS observations or calibrated camera estimates. Use the job and live-camera route panels for source-labelled geographic data.
      </div>

      {/* Main Grid: Selected Route Map (Top) & Route List (Bottom) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Interactive Map of Selected Route (2 cols) */}
        <div className="lg:col-span-2 bg-white p-5 rounded-2xl border border-slate-200/90 flex flex-col shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <span>Selected Route:</span>
                <span className="font-mono text-[#00A8C6]">{selectedRoute?.global_vehicle_id || 'Corridor Overview'}</span>
                {selectedRoute?.is_anomalous && (
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-rose-50 text-rose-700 border border-rose-300 font-bold">
                    ANOMALY FLAGGED
                  </span>
                )}
              </h2>
              <p className="text-xs text-slate-500 font-mono mt-0.5">
                Cameras Visited: {selectedRoute?.cameras_visited.join(' → ') || 'C01 → C02 → C03 → C04'}
              </p>
            </div>
            {selectedRoute && (
              <Link
                to={`/vehicles/${selectedRoute.global_vehicle_id}`}
                className="text-xs font-mono text-[#00A8C6] hover:text-[#0090AA] flex items-center gap-1 transition font-bold"
              >
                <span>View Dossier</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            )}
          </div>

          <div className="flex-1 min-h-[380px]">
            <LeafletRouteMap
              routePoints={routeCoordinates.length > 0 ? routeCoordinates : undefined}
              height="380px"
            />
          </div>
        </div>

        {/* Selected Route Telemetry Sidebar (1 col) */}
        <div className="space-y-4">
          <div className="bg-white p-5 rounded-2xl border border-slate-200/90 space-y-4 shadow-sm">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-2">
              <Gauge className="w-4 h-4 text-[#00A8C6]" />
              <span>Trajectory Telemetry</span>
            </h3>

            {selectedRoute ? (
              <div className="space-y-3 text-xs">
                <div className="p-3.5 rounded-xl bg-[#F8FAFC] border border-slate-200 flex justify-between items-center shadow-sm">
                  <span className="text-slate-500 font-medium">Total Distance</span>
                  <span className="font-mono font-extrabold text-[#00A8C6] text-sm tabular-nums">{selectedRoute.distance_km} km</span>
                </div>
                <div className="p-3.5 rounded-xl bg-[#F8FAFC] border border-slate-200 flex justify-between items-center shadow-sm">
                  <span className="text-slate-500 font-medium">Corridor Duration</span>
                  <span className="font-mono font-extrabold text-[#0F172A] text-sm tabular-nums">
                    {formatDuration(selectedRoute.duration_minutes)}
                  </span>
                </div>
                <div className="p-3.5 rounded-xl bg-[#F8FAFC] border border-slate-200 flex justify-between items-center shadow-sm">
                  <span className="text-slate-500 font-medium">Average Transit Speed</span>
                  <span className="font-mono font-extrabold text-[#F59E0B] text-sm tabular-nums">{selectedRoute.avg_speed_kmh} km/h</span>
                </div>
                <div className="p-3.5 rounded-xl bg-[#F8FAFC] border border-slate-200 flex justify-between items-center shadow-sm">
                  <span className="text-slate-500 font-medium">Start Camera</span>
                  <span className="font-mono font-bold text-slate-900">{selectedRoute.start_camera_id || 'C01'}</span>
                </div>
                <div className="p-3.5 rounded-xl bg-[#F8FAFC] border border-slate-200 flex justify-between items-center shadow-sm">
                  <span className="text-slate-500 font-medium">Terminal Camera</span>
                  <span className="font-mono font-bold text-slate-900">{selectedRoute.end_camera_id || 'C04'}</span>
                </div>
                <div className="p-3.5 rounded-xl bg-[#F8FAFC] border border-slate-200 flex justify-between items-center shadow-sm">
                  <span className="text-slate-500 font-medium">Journey Started</span>
                  <span className="font-mono text-slate-700 text-[11px] font-semibold">{formatDate(selectedRoute.started_at)}</span>
                </div>
              </div>
            ) : (
              <div className="text-xs text-slate-500 font-mono py-8 text-center">
                Select a route from the list below to inspect kinematics.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Reconstructed Routes Table */}
      <div className="bg-white p-5 rounded-2xl border border-slate-200/90 shadow-sm">
        <h3 className="text-sm font-bold text-slate-900 mb-4">All Reconstructed Routes</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#F8FAFC] text-slate-600 font-mono uppercase text-[10px] border-b border-[#E2E8F0]">
              <tr>
                <th className="py-3 px-4">Global Vehicle ID</th>
                <th className="py-3 px-4">Cameras Visited (Topology)</th>
                <th className="py-3 px-4">Distance</th>
                <th className="py-3 px-4">Duration</th>
                <th className="py-3 px-4">Avg Speed</th>
                <th className="py-3 px-4">Anomaly Status</th>
                <th className="py-3 px-4">Timestamp</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E2E8F0] font-medium">
              {routes.map((rt) => {
                const isSelected = selectedRoute?.id === rt.id;
                return (
                  <tr
                    key={rt.id}
                    onClick={() => setSelectedRoute(rt)}
                    className={`cursor-pointer transition ${
                      isSelected ? 'bg-teal-50/60 border-l-[3px] border-l-[#00A8C6]' : 'hover:bg-slate-50'
                    }`}
                  >
                    <td className="py-3.5 px-4 font-mono font-bold text-[#00A8C6]">
                      {rt.global_vehicle_id}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-800">
                      <span className="px-2 py-0.5 rounded-md bg-white border border-slate-200 shadow-sm">
                        {rt.cameras_visited.join(' → ')}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 font-mono tabular-nums">{rt.distance_km} km</td>
                    <td className="py-3.5 px-4 font-mono tabular-nums">{formatDuration(rt.duration_minutes)}</td>
                    <td className="py-3.5 px-4 font-mono tabular-nums text-[#F59E0B] font-bold">{rt.avg_speed_kmh} km/h</td>
                    <td className="py-3.5 px-4">
                      {rt.is_anomalous ? (
                        <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded-md bg-rose-50 text-rose-700 border border-rose-300 font-bold">
                          Anomaly
                        </span>
                      ) : (
                        <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700 border border-emerald-300 font-bold">
                          Nominal
                        </span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-500 text-[11px]">
                      {formatDate(rt.started_at)}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedRoute(rt);
                        }}
                        className="px-3 py-1 rounded-lg bg-[#00A8C6] hover:bg-[#0090AA] text-white text-[11px] font-mono mr-2 transition shadow-sm font-semibold"
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
