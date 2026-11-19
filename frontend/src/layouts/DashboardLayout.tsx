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
    <div className="min-h-screen bg-[#090A0F] flex flex-col text-[#F8FAFC]">
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
          {/* Tactical Command Banner */}
          <div className="mb-6 p-3 rounded-xl bg-[#11131A] border border-[#222634] shadow-sm flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-2.5 text-slate-300">
              <span className="w-2 h-2 rounded-full bg-blue-500 animate-ping" />
              <span className="font-semibold text-white tracking-wide">VEHICLE ROUTE & ANPR COMMAND CENTER</span>
              <span className="hidden sm:inline text-slate-400">| Calibrated multi-camera tracking & license plate intelligence</span>
            </div>
            <div className="text-[11px] font-mono text-amber-400 bg-amber-950/40 px-2 py-0.5 rounded border border-amber-800/40">
              AUTHORITATIVE CORRIDOR OPERATIONS · C01-C05
            </div>
          </div>

          <Outlet />
        </main>
      </div>

      {/* Footer bar */}
      <footer className="h-8 border-t border-[#1F2330] bg-[#0D0F16] px-4 flex items-center justify-between text-[11px] text-slate-400 font-mono">
        <div>ORR Autonomous Corridor C01-C05 • Tactical AI Pipeline</div>
        <div className="flex items-center gap-3">
          <span className="text-emerald-400">AI Core: ByteTrack + PaddleOCR</span>
          <span>FastAPI + PostgreSQL</span>
        </div>
      </footer>
    </div>
  );
};
