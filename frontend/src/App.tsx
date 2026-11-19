import React, { FormEvent, useEffect, useState } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import { Shield, Lock, User as UserIcon } from 'lucide-react';
import { DashboardLayout } from './layouts/DashboardLayout';
import { Dashboard } from './pages/Dashboard';
import { LiveMonitoring } from './pages/LiveMonitoring';
import { Vehicles } from './pages/Vehicles';
import { VehicleDetails } from './pages/VehicleDetails';
import { Routes as RoutesPage } from './pages/Routes';
import { Cameras } from './pages/Cameras';
import { ANPRDetections } from './pages/ANPRDetections';
import { Analytics } from './pages/Analytics';
import { Alerts } from './pages/Alerts';
import { Settings } from './pages/Settings';
import { TrafficProvider } from './context/TrafficContext';
import { api } from './services/api';

type SessionUser = { id: number; username: string; full_name: string | null; role: string };
const DEV_AUTH_BYPASS = import.meta.env?.DEV === true && import.meta.env?.VITE_DEV_AUTH_BYPASS === 'true';
const developmentUser: SessionUser = { id: 0, username: 'development', full_name: 'Development User', role: 'admin' };

const SignIn: React.FC<{ onLogin: (user: SessionUser) => void }> = ({ onLogin }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const user = await api.login(username, password);
      onLogin(user);
      navigate('/', { replace: true });
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? 'Authentication failed. Please verify credentials.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#EEF2F6] p-4 text-[#0F172A]">
      <div className="w-full max-w-md">
        {/* Tactical Command Brand Banner */}
        <div className="mb-6 text-center">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-teal-50 border border-teal-200 text-[#00A8C6] mb-3 shadow-sm">
            <Shield className="w-6 h-6" />
          </div>
          <h1 className="text-xl font-bold tracking-tight text-[#0F172A] flex items-center justify-center gap-1.5">
            TRAFFIC<span className="text-[#00A8C6]">INTEL</span>
            <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded-md bg-slate-100 text-[#0891B2] border border-slate-200 ml-1 font-bold">
              OPS v1.0
            </span>
          </h1>
          <p className="mt-1 text-xs text-slate-500">
            Tactical Traffic Intelligence & Multi-Camera ANPR Command Portal
          </p>
        </div>

        {/* Auth Card */}
        <form
          onSubmit={submit}
          className="rounded-2xl border border-slate-200/90 bg-white p-6 sm:p-8 shadow-sm space-y-5"
        >
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-800">
              Operator Sign In
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              Provide provisioned credentials to access system telemetry and camera nodes.
            </p>
          </div>

          {error && (
            <div
              role="alert"
              className="rounded-xl bg-rose-50 border border-rose-200 p-3 text-xs text-rose-700 flex items-start gap-2"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-[#EF4444] mt-1.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div className="space-y-4">
            <label className="block text-xs font-medium text-slate-700">
              <span className="flex items-center gap-1.5 mb-1.5">
                <UserIcon className="w-3.5 h-3.5 text-slate-500" />
                Username
              </span>
              <input
                autoComplete="username"
                required
                maxLength={50}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="operator_id"
                className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-sm text-[#0F172A] placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#00A8C6]/40 focus:border-[#00A8C6] focus:bg-white transition-all font-mono"
              />
            </label>

            <label className="block text-xs font-medium text-slate-700">
              <span className="flex items-center gap-1.5 mb-1.5">
                <Lock className="w-3.5 h-3.5 text-slate-500" />
                Password
              </span>
              <input
                autoComplete="current-password"
                required
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-sm text-[#0F172A] placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#00A8C6]/40 focus:border-[#00A8C6] focus:bg-white transition-all font-mono"
              />
            </label>
          </div>

          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-xl bg-[#00A8C6] hover:bg-[#0090AA] active:bg-[#007B92] py-2.5 text-sm font-semibold text-white shadow-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {busy ? (
              <>
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>Authenticating...</span>
              </>
            ) : (
              <span>Authenticate & Enter</span>
            )}
          </button>

          <div className="pt-2 border-t border-slate-200 text-center">
            <span className="text-[11px] font-mono text-slate-500">
              Secured Session • Role-Based Access Control
            </span>
          </div>
        </form>
      </div>
    </main>
  );
};

const AuthenticatedLayout: React.FC<{ user: SessionUser; onLogout: () => Promise<void> }> = ({ user, onLogout }) => (
  <TrafficProvider>
    <DashboardLayout user={user} onLogout={onLogout} />
  </TrafficProvider>
);

const ApplicationRoutes: React.FC = () => {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    let active = true;
    if(DEV_AUTH_BYPASS){setUser(developmentUser);setChecking(false);return()=>{active=false;};}
    api
      .getCurrentUser()
      .then((value) => {
        if (active) setUser(value);
      })
      .catch(() => {
        if (active) setUser(null);
      })
      .finally(() => {
        if (active) setChecking(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const logout = async () => {
    try {
      await api.logout();
    } finally {
      setUser(null);
    }
  };

  if (checking) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#F4F7FB] text-sm text-slate-600 font-mono">
        <div className="flex items-center gap-3">
          <span className="w-4 h-4 border-2 border-blue-600/30 border-t-blue-600 rounded-full animate-spin" />
          <span className="font-semibold text-slate-700">INITIALIZING COMMAND CONSOLE...</span>
        </div>
      </div>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <SignIn onLogin={setUser} />} />
      <Route element={user ? <AuthenticatedLayout user={user} onLogout={logout} /> : <Navigate to="/login" replace />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/live" element={<LiveMonitoring />} />
        <Route path="/vehicles" element={<Vehicles />} />
        <Route path="/vehicles/:id" element={<VehicleDetails />} />
        <Route path="/routes" element={<RoutesPage />} />
        <Route path="/cameras" element={<Cameras />} />
        <Route path="/detections" element={<ANPRDetections />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/alerts" element={<Alerts />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
};

export function App() {
  return (
    <BrowserRouter>
      <ApplicationRoutes />
    </BrowserRouter>
  );
}

export default App;
