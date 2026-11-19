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

const NAV_GROUPS = [
  {
    title: 'Operations',
    items: [
      { path: '/', label: 'Dashboard', icon: LayoutDashboard },
      { path: '/live', label: 'Live Monitoring', icon: Video, badge: '4 CAMS' },
    ],
  },
  {
    title: 'Intelligence',
    items: [
      { path: '/vehicles', label: 'Vehicles', icon: Car },
      { path: '/routes', label: 'Routes', icon: MapPin },
      { path: '/cameras', label: 'Cameras', icon: Camera },
      { path: '/detections', label: 'ANPR Detections', icon: ScanLine },
    ],
  },
  {
    title: 'Analytics & Rules',
    items: [
      { path: '/analytics', label: 'Analytics', icon: BarChart3 },
      { path: '/alerts', label: 'Alerts', icon: AlertTriangle },
    ],
  },
  {
    title: 'System',
    items: [
      { path: '/settings', label: 'Settings', icon: Settings },
    ],
  },
];

export const Sidebar: React.FC = () => {
  return (
    <aside className="w-64 border-r border-[#1F2330] bg-[#0D0F16] flex flex-col justify-between hidden md:flex shrink-0 min-h-[calc(100vh-4rem)]">
      <div className="py-4 px-3 space-y-5">
        {NAV_GROUPS.map((group) => (
          <div key={group.title} className="space-y-1">
            <div className="px-3 pb-1 text-[10px] font-bold uppercase tracking-wider text-slate-400 font-mono">
              {group.title}
            </div>
            {group.items.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={({ isActive }) =>
                    `flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                      isActive
                        ? 'bg-blue-600/10 text-white border-l-2 border-l-blue-600 font-semibold'
                        : 'text-slate-400 hover:text-white hover:bg-[#171A24] border-l-2 border-l-transparent'
                    }`
                  }
                >
                  <div className="flex items-center gap-3">
                    <Icon className="w-4 h-4 shrink-0" />
                    <span>{item.label}</span>
                  </div>
                  {item.badge && (
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#171A24] text-blue-400 border border-[#2B3040] font-semibold">
                      {item.badge}
                    </span>
                  )}
                </NavLink>
              );
            })}
          </div>
        ))}
      </div>

      {/* Corridor System Info Footer */}
      <div className="p-3 border-t border-[#1F2330] bg-[#11131A] m-3 rounded-xl border border-[#222634]">
        <div className="flex items-center gap-2 text-xs font-medium text-slate-300">
          <Info className="w-4 h-4 text-blue-500 shrink-0" />
          <span>Outer Ring Road Corridor</span>
        </div>
        <p className="text-[11px] text-slate-400 mt-1">
          5 Autonomous Nodes (C01-C05)
        </p>
        <div className="mt-2 text-[10px] text-slate-400 font-mono flex items-center justify-between">
          <span>ByteTrack + Paddle</span>
          <span className="text-emerald-400 font-bold">ONLINE</span>
        </div>
      </div>
    </aside>
  );
};
