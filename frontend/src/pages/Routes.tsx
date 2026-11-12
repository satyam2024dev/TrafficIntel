import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { MapPin, Navigation, AlertTriangle, Eye, ArrowRight, Gauge, Clock } from 'lucide-react';
import { LeafletRouteMap } from '../components/LeafletRouteMap';
import { PlateBadge } from '../components/PlateBadge';
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
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Navigation className="w-5 h-5 text-cyan-400" />
            <span>Reconstructed Multi-Camera Trajectories</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Reconstructed vehicle paths across camera topology with kinematics and anomaly detection.
          </p>
        </div>
        <div className="text-xs font-mono text-slate-400 bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-lg">
          Active Routes: <span className="text-cyan-400 font-bold">{routes.length}</span>
        </div>
      </div>

      <div className="rounded-lg border border-amber-800/70 bg-amber-950/30 px-4 py-3 text-xs text-amber-200" role="note">
        These legacy corridor records come from the dashboard simulation tables. They are not verified GPS observations or calibrated camera estimates. Use the job and live-camera route panels for source-labelled geographic data.
      </div>

      {/* Main Grid: Selected Route Map (Top) & Route List (Bottom) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Interactive Map of Selected Route (2 cols) */}
        <div className="lg:col-span-2 glass-panel p-5 rounded-xl border border-slate-800 flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <span>Selected Route:</span>
                <span className="font-mono text-cyan-400">{selectedRoute?.global_vehicle_id || 'Corridor Overview'}</span>
                {selectedRoute?.is_anomalous && (
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-950 text-rose-400 border border-rose-800 font-bold">
                    ANOMALY FLAGGED
                  </span>
                )}
              </h2>
              <p className="text-xs text-slate-400 font-mono mt-0.5">
                Cameras Visited: {selectedRoute?.cameras_visited.join(' → ') || 'C01 → C02 → C03 → C04'}
              </p>
            </div>
            {selectedRoute && (
              <Link
                to={`/vehicles/${selectedRoute.global_vehicle_id}`}
                className="text-xs font-mono text-cyan-400 hover:text-cyan-300 flex items-center gap-1 transition"
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
          <div className="glass-panel p-5 rounded-xl border border-slate-800 space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <Gauge className="w-4 h-4 text-cyan-400" />
              <span>Trajectory Telemetry</span>
            </h3>

            {selectedRoute ? (
              <div className="space-y-3 text-xs">
                <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 flex justify-between items-center">
                  <span className="text-slate-400">Total Distance</span>
                  <span className="font-mono font-bold text-white text-sm">{selectedRoute.distance_km} km</span>
                </div>
                <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 flex justify-between items-center">
                  <span className="text-slate-400">Corridor Duration</span>
                  <span className="font-mono font-bold text-white text-sm">
                    {formatDuration(selectedRoute.duration_minutes)}
                  </span>
                </div>
                <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 flex justify-between items-center">
                  <span className="text-slate-400">Average Transit Speed</span>
                  <span className="font-mono font-bold text-cyan-400 text-sm">{selectedRoute.avg_speed_kmh} km/h</span>
                </div>
                <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 flex justify-between items-center">
                  <span className="text-slate-400">Start Camera</span>
                  <span className="font-mono font-bold text-slate-200">{selectedRoute.start_camera_id || 'C01'}</span>
                </div>
                <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 flex justify-between items-center">
                  <span className="text-slate-400">Terminal Camera</span>
                  <span className="font-mono font-bold text-slate-200">{selectedRoute.end_camera_id || 'C04'}</span>
                </div>
                <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 flex justify-between items-center">
                  <span className="text-slate-400">Journey Started</span>
                  <span className="font-mono text-slate-300 text-[11px]">{formatDate(selectedRoute.started_at)}</span>
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
      <div className="glass-panel p-5 rounded-xl border border-slate-800">
        <h3 className="text-sm font-bold text-white mb-4">All Reconstructed Routes</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-900/90 text-slate-400 font-mono uppercase text-[10px] border-b border-slate-800">
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
            <tbody className="divide-y divide-slate-800/60 font-medium">
              {routes.map((rt) => {
                const isSelected = selectedRoute?.id === rt.id;
                return (
                  <tr
                    key={rt.id}
                    onClick={() => setSelectedRoute(rt)}
                    className={`cursor-pointer transition ${
                      isSelected ? 'bg-cyan-950/40 border-l-2 border-cyan-400' : 'hover:bg-slate-900/50'
                    }`}
                  >
                    <td className="py-3 px-4 font-mono font-bold text-cyan-400">
                      {rt.global_vehicle_id}
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-200">
                      <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800">
                        {rt.cameras_visited.join(' → ')}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-mono">{rt.distance_km} km</td>
                    <td className="py-3 px-4 font-mono">{formatDuration(rt.duration_minutes)}</td>
                    <td className="py-3 px-4 font-mono text-emerald-400">{rt.avg_speed_kmh} km/h</td>
                    <td className="py-3 px-4">
                      {rt.is_anomalous ? (
                        <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-rose-500/20 text-rose-400 border border-rose-500/40">
                          Anomaly
                        </span>
                      ) : (
                        <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/40">
                          Nominal
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-400 text-[11px]">
                      {formatDate(rt.started_at)}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedRoute(rt);
                        }}
                        className="px-2.5 py-1 rounded bg-slate-800 text-cyan-400 hover:bg-slate-700 text-[11px] font-mono mr-2"
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
