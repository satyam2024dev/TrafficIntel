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
    <div className="min-h-screen bg-[#EEF2F6] flex flex-col text-[#0F172A]">
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
        <Sidebar onLogout={onLogout} role={user.role} username={user.username} />

        <main className="flex-1 overflow-y-auto p-4 lg:p-6 pb-16 bg-[#EEF2F6]">
          {/* Tactical Command Banner */}
          <div className="mb-6 p-3.5 rounded-2xl bg-white border border-slate-200/90 shadow-sm flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-2.5 text-slate-700">
              <span className="w-2.5 h-2.5 rounded-full bg-[#00A8C6] animate-ping" />
              <span className="font-bold text-[#0F172A] tracking-wide">VEHICLE ROUTE & ANPR COMMAND CENTER</span>
              <span className="hidden sm:inline text-slate-500 font-medium">| Calibrated multi-camera tracking & license plate intelligence</span>
            </div>
            <div className="text-[11px] font-mono text-emerald-800 bg-emerald-50 px-2.5 py-1 rounded-lg border border-emerald-200 font-bold">
              AUTHORITATIVE CORRIDOR OPERATIONS · C01-C05
            </div>
          </div>

          <Outlet />
        </main>
      </div>

      {/* Footer bar */}
      <footer className="h-8 border-t border-[#E2E8F0] bg-white px-4 flex items-center justify-between text-[11px] text-slate-500 font-mono shadow-sm">
        <div>ORR Autonomous Corridor C01-C05 • Tactical AI Pipeline</div>
        <div className="flex items-center gap-3">
          <span className="text-emerald-700 font-bold">AI Core: ByteTrack + PaddleOCR</span>
          <span>FastAPI + PostgreSQL</span>
        </div>
      </footer>
    </div>
  );
};
