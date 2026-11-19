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
  LogOut,
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

interface SidebarProps {
  onLogout?: () => Promise<void>;
  role?: string;
  username?: string;
}

export const Sidebar: React.FC<SidebarProps> = ({ onLogout, role }) => {
  return (
    <aside className="w-64 border-r border-[#E2E8F0] bg-white flex flex-col justify-between hidden md:flex shrink-0 min-h-[calc(100vh-4rem)] shadow-sm">
      <div>
        {/* Brand / Operator Header at top */}
        <div className="p-4 border-b border-[#E2E8F0] flex items-center justify-between">
          <div>
            <div className="font-extrabold text-sm tracking-tight text-[#0F172A]">
              TrafficIntel ORR
            </div>
            <p className="text-[11px] text-slate-500 font-medium">Tactical Command</p>
          </div>
          <span className="text-[10px] font-mono font-bold uppercase px-2 py-0.5 rounded bg-teal-50 text-[#0891B2] border border-teal-200">
            {role?.toUpperCase() || 'OPERATIONS'}
          </span>
        </div>

        <div className="py-3 px-3 space-y-5">
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
                      `flex items-center justify-between px-3 py-2 rounded-xl text-xs transition-all ${
                        isActive
                          ? 'bg-[#ECFDF5] text-[#047857] border border-[#A7F3D0] font-bold shadow-sm'
                          : 'text-[#334155] hover:bg-slate-100 hover:text-slate-950 font-medium'
                      }`
                    }
                  >
                    <div className="flex items-center gap-3">
                      <Icon className="w-4 h-4 shrink-0" />
                      <span>{item.label}</span>
                    </div>
                    {item.badge && (
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 text-[#0891B2] border border-slate-200 font-semibold">
                        {item.badge}
                      </span>
                    )}
                  </NavLink>
                );
              })}
            </div>
          ))}
        </div>
      </div>

      {/* Corridor System Info & Sign Out Footer */}
      <div className="p-3 border-t border-[#E2E8F0] space-y-2">
        <div className="p-3 bg-[#F8FAFC] rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-800">
            <Info className="w-4 h-4 text-[#0891B2] shrink-0" />
            <span>Outer Ring Road Corridor</span>
          </div>
          <p className="text-[11px] text-slate-500 mt-1">
            5 Autonomous Nodes (C01-C05)
          </p>
          <div className="mt-2 text-[10px] text-slate-500 font-mono flex items-center justify-between">
            <span>ByteTrack + Paddle</span>
            <span className="text-emerald-700 font-bold">ONLINE</span>
          </div>
        </div>

        {onLogout && (
          <button
            onClick={() => void onLogout()}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 text-xs font-semibold text-[#DC2626] hover:bg-rose-50 hover:text-rose-700 rounded-xl transition border border-transparent hover:border-rose-200"
          >
            <LogOut className="w-4 h-4" />
            <span>Sign Out</span>
          </button>
        )}
      </div>
    </aside>
  );
};
