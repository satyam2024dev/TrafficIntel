import React, { FormEvent, useEffect, useState } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from 'react-router-dom';
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
  const [username,setUsername]=useState(''); const [password,setPassword]=useState(''); const [error,setError]=useState(''); const [busy,setBusy]=useState(false); const navigate=useNavigate();
  const submit=async(event:FormEvent)=>{event.preventDefault();setBusy(true);setError('');try{const user=await api.login(username,password);onLogin(user);navigate('/',{replace:true});}catch(e:any){setError(e?.response?.data?.detail??'Sign in failed.');}finally{setBusy(false);}};
  return <main className="flex min-h-screen items-center justify-center bg-[#070b14] p-4 text-slate-100"><form onSubmit={submit} className="w-full max-w-sm space-y-4 rounded-xl border border-slate-800 bg-slate-950 p-6 shadow-xl"><div><h1 className="text-lg font-bold text-white">TrafficIntel sign in</h1><p className="mt-1 text-xs text-slate-400">Use an account provisioned by your system administrator.</p></div><label className="block text-xs text-slate-400">Username<input autoComplete="username" required maxLength={50} value={username} onChange={e=>setUsername(e.target.value)} className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 p-2 text-sm text-white"/></label><label className="block text-xs text-slate-400">Password<input autoComplete="current-password" required type="password" value={password} onChange={e=>setPassword(e.target.value)} className="mt-1 block w-full rounded border border-slate-700 bg-slate-900 p-2 text-sm text-white"/></label>{error&&<p role="alert" className="text-xs text-rose-300">{error}</p>}<button disabled={busy} className="w-full rounded bg-cyan-500 p-2 text-sm font-semibold text-slate-950 disabled:opacity-50">{busy?'Signing in…':'Sign in'}</button></form></main>;
};

const AuthenticatedLayout: React.FC<{ user: SessionUser; onLogout: () => Promise<void> }> = ({user,onLogout}) => <TrafficProvider><DashboardLayout user={user} onLogout={onLogout}/></TrafficProvider>;

const ApplicationRoutes: React.FC = () => {
  const [user,setUser]=useState<SessionUser|null>(null); const [checking,setChecking]=useState(true);
  useEffect(()=>{let active=true;if(DEV_AUTH_BYPASS){setUser(developmentUser);setChecking(false);return()=>{active=false;};}api.getCurrentUser().then(value=>{if(active)setUser(value);}).catch(()=>{if(active)setUser(null);}).finally(()=>{if(active)setChecking(false);});return()=>{active=false;};},[]);
  const logout=async()=>{try{await api.logout();}finally{setUser(null);}};
  if(checking)return <div className="flex min-h-screen items-center justify-center bg-[#070b14] text-sm text-slate-400">Checking session…</div>;
  return <Routes>
    <Route path="/login" element={user?<Navigate to="/" replace/>:<SignIn onLogin={setUser}/>}/>
    <Route element={user?<AuthenticatedLayout user={user} onLogout={logout}/>:<Navigate to="/login" replace/>}>
      <Route path="/" element={<Dashboard/>}/><Route path="/live" element={<LiveMonitoring/>}/>
      <Route path="/vehicles" element={<Vehicles/>}/><Route path="/vehicles/:id" element={<VehicleDetails/>}/>
      <Route path="/routes" element={<RoutesPage/>}/><Route path="/cameras" element={<Cameras/>}/>
      <Route path="/detections" element={<ANPRDetections/>}/><Route path="/analytics" element={<Analytics/>}/>
      <Route path="/alerts" element={<Alerts/>}/><Route path="/settings" element={<Settings/>}/>
      <Route path="*" element={<Navigate to="/" replace/>}/>
    </Route>
  </Routes>;
};

export function App() { return <BrowserRouter><ApplicationRoutes/></BrowserRouter>; }
export default App;
