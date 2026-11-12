import React from 'react';
import { Outlet } from 'react-router-dom';
import { Navbar } from '../components/Navbar';
import { Sidebar } from '../components/Sidebar';
import { useTrafficData } from '../hooks/useTrafficData';

export const DashboardLayout: React.FC<{ user: { username: string; role: string }; onLogout: () => Promise<void> }> = ({ user, onLogout }) => {
  const {
    wsConnected,
    isSimRunning,
    isSimPaused,
    alerts,
    refreshAll,
  } = useTrafficData();

  const unresolvedAlerts = alerts.filter((a) => !a.is_resolved).length;

  return (
    <div className="min-h-screen bg-[#070b14] flex flex-col text-slate-100">
      <Navbar
        wsConnected={wsConnected}
        isSimRunning={isSimRunning}
        isSimPaused={isSimPaused}
        activeAlertsCount={unresolvedAlerts}
        onSimStateChange={refreshAll}
        role={user.role}
        username={user.username}
        onLogout={onLogout}
      />

      <div className="flex-1 flex overflow-hidden">
        <Sidebar />

        <main className="flex-1 overflow-y-auto p-4 lg:p-6 pb-16">
          {/* Top Banner Notice */}
          <div className="mb-6 p-3 rounded-xl bg-gradient-to-r from-cyan-950/40 via-slate-900/60 to-purple-950/30 border border-cyan-800/30 flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-2 text-slate-300">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
              <span className="font-semibold text-white">Vehicle route and ANPR workspace</span>
              <span className="hidden sm:inline text-slate-400">| Real inference records are separated from legacy simulation data</span>
            </div>
            <div className="text-[11px] font-mono text-amber-400 bg-amber-950/40 px-2 py-0.5 rounded border border-amber-800/40">
              RESEARCH PROTOTYPE · AUTHORIZED CAMERA USE ONLY
            </div>
          </div>

          <Outlet />
        </main>
      </div>

      {/* Footer bar */}
      <footer className="h-8 border-t border-slate-800/80 bg-slate-950 px-4 flex items-center justify-between text-[11px] text-slate-500 font-mono">
        <div>ORR Autonomous Corridor C01-C05 â€¢ Real-Time AI Pipeline</div>
        <div className="flex items-center gap-3">
          <span className="text-emerald-400">Real AI requires configured models</span>
          <span>FastAPI + PostgreSQL</span>
        </div>
      </footer>
    </div>
  );
};
