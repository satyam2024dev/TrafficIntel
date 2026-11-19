import React, { useState } from 'react';
import { Play, Pause, RotateCcw, Radio, Bell, ShieldCheck, Activity, LogOut } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTrafficData } from '../hooks/useTrafficData';

interface NavbarProps {
  wsConnected: boolean;
  isSimRunning: boolean;
  isSimPaused: boolean;
  activeAlertsCount: number;
  onSimStateChange?: () => void;
  role?: string;
  username?: string;
  onLogout?: () => Promise<void>;
}

export const Navbar: React.FC<Partial<NavbarProps>> = (props) => {
  const context = useTrafficData();
  const wsConnected = props.wsConnected !== undefined ? props.wsConnected : context.wsConnected;
  const isSimRunning = props.isSimRunning !== undefined ? props.isSimRunning : context.isSimRunning;
  const isSimPaused = props.isSimPaused !== undefined ? props.isSimPaused : context.isSimPaused;
  const activeAlertsCount = props.activeAlertsCount !== undefined ? props.activeAlertsCount : context.alerts.filter(a => !a.is_resolved).length;

  const [loading, setLoading] = useState<string | null>(null);

  const handleStart = async () => {
    try {
      setLoading('start');
      await context.startSimulation();
      props.onSimStateChange?.();
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(null);
    }
  };

  const handlePause = async () => {
    try {
      setLoading('pause');
      await context.pauseSimulation();
      props.onSimStateChange?.();
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(null);
    }
  };

  const handleReset = async () => {
    try {
      setLoading('reset');
      await context.resetSimulation();
      props.onSimStateChange?.();
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(null);
    }
  };

  return (
    <header className="h-16 border-b border-[#E2E8F0] bg-white sticky top-0 z-40 px-4 lg:px-6 flex items-center justify-between shadow-sm">
      {/* Brand & Tactical Label */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-teal-50 border border-teal-200 flex items-center justify-center text-[#00A8C6] shadow-sm">
            <Activity className="w-5 h-5 text-[#00A8C6]" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-sm lg:text-base tracking-tight text-[#0F172A]">
                TRAFFIC<span className="text-[#00A8C6]">INTEL</span>
              </span>
              <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-teal-50 text-[#0891B2] border border-teal-200 font-bold hidden sm:inline-block">
                ANPR v1.0
              </span>
            </div>
            <p className="text-[10px] text-slate-500 hidden md:block">
              Route Tracking & All-Weather Plate Recognition
            </p>
          </div>
        </div>

        {/* DEMO MODE Academic Integrity Badge */}
        <div className="hidden xl:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-50 border border-amber-200 text-amber-800 text-xs font-mono">
          <ShieldCheck className="w-3.5 h-3.5 text-amber-600" />
          <span className="font-semibold">SIMULATION DATA IS SEPARATE</span>
        </div>
      </div>

      {/* Center/Right: Demo Controls & Status */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Simulation Control Group */}
        {props.role === 'admin' && (
          <div className="flex items-center bg-slate-100/90 border border-slate-200 rounded-lg p-1 gap-1 shadow-sm">
            <button
              onClick={handleStart}
              disabled={loading !== null || (isSimRunning && !isSimPaused)}
              title="Start Continuous Simulation"
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
                isSimRunning && !isSimPaused
                  ? 'bg-emerald-600 text-white shadow-sm font-bold'
                  : 'text-slate-600 hover:text-emerald-700 hover:bg-white'
              }`}
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span className="hidden sm:inline">START DEMO</span>
            </button>

            <button
              onClick={handlePause}
              disabled={loading !== null || !isSimRunning || isSimPaused}
              title="Pause Simulation"
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
                isSimPaused
                  ? 'bg-amber-500 text-white shadow-sm font-bold'
                  : 'text-slate-600 hover:text-amber-700 hover:bg-white'
              }`}
            >
              <Pause className="w-3.5 h-3.5 fill-current" />
              <span className="hidden sm:inline">PAUSE</span>
            </button>

            <button
              onClick={handleReset}
              disabled={loading !== null}
              title="Reset Simulation State"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold text-slate-500 hover:text-rose-600 hover:bg-white transition-all"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">RESET</span>
            </button>
          </div>
        )}

        {/* Live WebSocket Status Dot */}
        <div
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono border ${
            wsConnected
              ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
              : 'bg-rose-50 border-rose-200 text-rose-700'
          }`}
          title={wsConnected ? 'WebSocket Live Stream Active' : 'WebSocket Reconnecting...'}
        >
          <span
            className={`w-2 h-2 rounded-full ${
              wsConnected ? 'bg-emerald-500 animate-ping' : 'bg-rose-500'
            }`}
          />
          <Radio className="w-3 h-3" />
          <span className="hidden lg:inline">{wsConnected ? 'LIVE FEED' : 'OFFLINE'}</span>
        </div>

        {/* Alerts Bell Link */}
        <Link
          to="/alerts"
          className="relative p-2 rounded-lg bg-white border border-[#E2E8F0] text-slate-600 hover:text-blue-600 hover:border-slate-300 transition shadow-sm"
          title="Active Alerts"
        >
          <Bell className="w-4 h-4" />
          {activeAlertsCount > 0 && (
            <span className="absolute -top-1 -right-1 px-1.5 py-0.2 rounded-full bg-rose-600 text-[10px] font-mono font-bold text-white shadow-sm">
              {activeAlertsCount}
            </span>
          )}
        </Link>
        <span className="hidden md:inline-flex items-center text-xs font-mono px-2.5 py-1 rounded bg-slate-100 border border-slate-200 text-slate-700 font-medium">
          {props.username} • {props.role}
        </span>
        <button
          onClick={() => void props.onLogout?.()}
          className="rounded-lg border border-[#E2E8F0] bg-white p-2 text-slate-500 hover:text-rose-600 hover:border-slate-300 transition shadow-sm"
          title="Sign out"
          aria-label="Sign out"
        >
          <LogOut size={15} />
        </button>
      </div>
    </header>
  );
};
