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
          <h1 className="text-xl font-bold text-white flex items-center gap-2 tracking-tight">
            <CameraIcon className="w-5 h-5 text-blue-500" />
            <span>Camera Sensor Topology & Telemetry</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Real-time optical sensors across Bangalore Outer Ring Road intelligent highway corridor.
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs font-mono bg-[#11131A] border border-[#222634] px-3 py-1.5 rounded-lg text-slate-300 shadow-sm">
          <span>Active Nodes:</span>
          <span className="text-emerald-400 font-bold tabular-nums">{cameras.length} / {cameras.length}</span>
        </div>
      </div>

      {/* Camera Grid Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {cameras.map((cam) => (
          <div
            key={cam.id}
            className="glass-panel p-5 rounded-xl border border-[#222634] flex flex-col justify-between hover:border-[#2B3040] transition shadow-sm"
          >
            <div>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2.5">
                  <div className="w-10 h-10 rounded-lg bg-[#171A24] border border-[#2B3040] flex items-center justify-center text-blue-400 font-mono font-bold text-sm shadow-sm">
                    {cam.id}
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white">{cam.name}</h3>
                    <p className="text-[11px] text-slate-400">{cam.location_name}</p>
                  </div>
                </div>
                <span className="flex items-center gap-1 text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  {cam.status}
                </span>
              </div>

              <div className="my-3 py-2 px-3 rounded-lg bg-[#171A24] border border-[#2B3040] space-y-2 text-xs">
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">Road Segment</span>
                  <span className="text-slate-200 text-right truncate max-w-[160px] font-mono text-[11px]">
                    {cam.road_segment}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">Coordinates</span>
                  <span className="text-slate-300 font-mono text-[11px] tabular-nums">
                    {cam.latitude.toFixed(4)}, {cam.longitude.toFixed(4)}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">Sensor Frame Rate</span>
                  <span className="font-mono text-blue-400 font-bold tabular-nums">
                    {cam.fps.toFixed(1)} FPS
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">Resolution</span>
                  <span className="font-mono text-slate-300 text-[11px]">{cam.resolution}</span>
                </div>
              </div>
            </div>

            <div className="pt-2 border-t border-[#222634] flex items-center justify-between text-xs">
              <span className="text-slate-400 text-[11px]">Atmospheric Filter:</span>
              <WeatherBadge condition={cam.weather_condition} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
