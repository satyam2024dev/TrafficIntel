import React from 'react';
import { Camera as CameraIcon } from 'lucide-react';
import { WeatherBadge } from '../components/WeatherBadge';
import { useTrafficData } from '../hooks/useTrafficData';
import { CameraLocationManager } from '../components/CameraLocationManager';
import { CameraStreamManager } from '../components/CameraStreamManager';

export const Cameras: React.FC = () => {
  const { cameras } = useTrafficData();

  return (
    <div className="space-y-6">
      <CameraLocationManager />
      <CameraStreamManager />
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-extrabold text-slate-900 flex items-center gap-2.5 tracking-tight">
            <CameraIcon className="w-5 h-5 text-[#00A8C6]" />
            <span>Camera Sensor Topology & Telemetry</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Real-time optical sensors across Bangalore Outer Ring Road intelligent highway corridor.
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs font-mono bg-white border border-slate-200/90 px-3.5 py-1.5 rounded-xl text-slate-700 shadow-sm font-semibold">
          <span>Active Nodes:</span>
          <span className="text-[#00A8C6] font-extrabold tabular-nums">{cameras.length} / {cameras.length}</span>
        </div>
      </div>

      {/* Camera Grid Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {cameras.map((cam) => (
          <div
            key={cam.id}
            className="bg-white p-5 rounded-2xl border border-slate-200/90 flex flex-col justify-between hover:border-teal-300 transition shadow-sm"
          >
            <div>
              <div className="flex items-center justify-between mb-3.5">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-teal-50 border border-teal-200 flex items-center justify-center text-[#00A8C6] font-mono font-bold text-sm shadow-sm">
                    {cam.id}
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-slate-900">{cam.name}</h3>
                    <p className="text-[11px] text-slate-500 font-medium">{cam.location_name}</p>
                  </div>
                </div>
                <span className="flex items-center gap-1.5 text-[10px] uppercase font-mono px-2.5 py-0.5 rounded-lg bg-emerald-50 text-emerald-700 border border-emerald-200 font-bold">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 animate-pulse" />
                  {cam.status}
                </span>
              </div>

              <div className="my-3 py-2.5 px-3.5 rounded-xl bg-[#F8FAFC] border border-slate-200 space-y-2 text-xs">
                <div className="flex justify-between items-center">
                  <span className="text-slate-500 font-medium">Road Segment</span>
                  <span className="text-slate-800 text-right truncate max-w-[160px] font-mono text-[11px] font-semibold">
                    {cam.road_segment}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-500 font-medium">Coordinates</span>
                  <span className="text-slate-700 font-mono text-[11px] tabular-nums font-semibold">
                    {cam.latitude.toFixed(4)}, {cam.longitude.toFixed(4)}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-500 font-medium">Sensor Frame Rate</span>
                  <span className="font-mono text-[#00A8C6] font-bold tabular-nums">
                    {cam.fps.toFixed(1)} FPS
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-500 font-medium">Resolution</span>
                  <span className="font-mono text-slate-700 text-[11px] font-semibold">{cam.resolution}</span>
                </div>
              </div>
            </div>

            <div className="pt-2.5 border-t border-slate-200 flex items-center justify-between text-xs">
              <span className="text-slate-500 text-[11px] font-medium">Atmospheric Filter:</span>
              <WeatherBadge condition={cam.weather_condition} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
