import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Video,
  Car,
  MapPin,
  Camera,
  ScanLine,
  BarChart3,
  AlertTriangle,
  Settings,
  Info,
} from 'lucide-react';

const NAV_ITEMS = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/live', label: 'Live Monitoring', icon: Video, badge: '4 CAMS' },
  { path: '/vehicles', label: 'Vehicles', icon: Car },
  { path: '/routes', label: 'Routes', icon: MapPin },
  { path: '/cameras', label: 'Cameras', icon: Camera },
  { path: '/detections', label: 'ANPR Detections', icon: ScanLine },
  { path: '/analytics', label: 'Analytics', icon: BarChart3 },
  { path: '/alerts', label: 'Alerts', icon: AlertTriangle },
  { path: '/settings', label: 'Settings', icon: Settings },
];

export const Sidebar: React.FC = () => {
  return (
    <aside className="w-64 border-r border-slate-800 bg-slate-950/70 backdrop-blur-md flex flex-col justify-between hidden md:flex shrink-0 min-h-[calc(100vh-4rem)]">
      <div className="py-4 px-3 space-y-1">
        <div className="px-3 pb-3 pt-1 text-[11px] font-bold uppercase tracking-wider text-slate-500 font-mono">
          Traffic Intelligence Core
        </div>
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${
                  isActive
                    ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 shadow-sm shadow-cyan-500/10 font-semibold'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
                }`
              }
            >
              <div className="flex items-center gap-3">
                <Icon className="w-4 h-4 shrink-0" />
                <span>{item.label}</span>
              </div>
              {item.badge && (
                <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-800 text-cyan-400 border border-slate-700/60 font-semibold">
                  {item.badge}
                </span>
              )}
            </NavLink>
          );
        })}
      </div>

      {/* Corridor System Info Footer */}
      <div className="p-3 border-t border-slate-800/80 bg-slate-900/40 m-3 rounded-xl">
        <div className="flex items-center gap-2 text-xs font-medium text-slate-300">
          <Info className="w-4 h-4 text-cyan-400 shrink-0" />
          <span>Outer Ring Road Corridor</span>
        </div>
        <p className="text-[11px] text-slate-400 mt-1">
          5 Autonomous Nodes (C01-C05)
        </p>
        <div className="mt-2 text-[10px] text-slate-400 font-mono flex items-center justify-between">
          <span>AI: ByteTrack + Paddle</span>
          <span className="text-emerald-400">ONLINE</span>
        </div>
      </div>
    </aside>
  );
};
