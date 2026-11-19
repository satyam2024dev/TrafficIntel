import React, { useState } from 'react';
import { Settings as SettingsIcon, Shield, Sliders, Terminal, Check } from 'lucide-react';

export const Settings: React.FC = () => {
  const [simInterval, setSimInterval] = useState('2.0');
  const [ocrThreshold, setOcrThreshold] = useState('85');
  const [autoEnhance, setAutoEnhance] = useState(true);
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-white flex items-center gap-2 tracking-tight">
          <SettingsIcon className="w-5 h-5 text-blue-500" />
          <span>System & Demonstration Settings</span>
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Configure AI pipeline parameters, simulation cadence, and view data privacy compliance.
        </p>
      </div>

      {/* 1. Simulation Engine Configuration */}
      <div className="glass-panel p-6 rounded-xl border border-[#222634] space-y-4 shadow-sm">
        <h2 className="text-sm font-bold text-white flex items-center gap-2">
          <Sliders className="w-4 h-4 text-blue-500" />
          <span>Simulation Engine & ANPR Thresholds</span>
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2 text-xs">
          <div className="space-y-2">
            <label className="text-slate-300 font-medium block">
              Simulation Tick Cadence: <span className="font-mono text-blue-400 tabular-nums">{simInterval}s</span>
            </label>
            <input
              type="range"
              min="1.0"
              max="5.0"
              step="0.5"
              value={simInterval}
              onChange={(e) => setSimInterval(e.target.value)}
              className="w-full accent-blue-600 cursor-pointer"
            />
            <p className="text-[11px] text-slate-400">
              Interval at which vehicles transit between camera nodes in Demo Mode.
            </p>
          </div>

          <div className="space-y-2">
            <label className="text-slate-300 font-medium block">
              OCR Alert Confidence Threshold: <span className="font-mono text-blue-400 tabular-nums">{ocrThreshold}%</span>
            </label>
            <input
              type="range"
              min="70"
              max="95"
              step="1"
              value={ocrThreshold}
              onChange={(e) => setOcrThreshold(e.target.value)}
              className="w-full accent-blue-600 cursor-pointer"
            />
            <p className="text-[11px] text-slate-400">
              Triggers low confidence warning when adverse weather degrades recognition.
            </p>
          </div>

          <div className="flex items-center justify-between p-3 rounded-lg bg-[#171A24] border border-[#2B3040]">
            <div>
              <span className="text-slate-200 font-medium block">Autonomous OpenCV Enhancement</span>
              <span className="text-[11px] text-slate-400">Engage CLAHE, Dehaze, and Gamma filters dynamically</span>
            </div>
            <input
              type="checkbox"
              checked={autoEnhance}
              onChange={(e) => setAutoEnhance(e.target.checked)}
              className="w-4 h-4 accent-blue-600 rounded cursor-pointer"
            />
          </div>

          <div className="flex items-center justify-between p-3 rounded-lg bg-[#171A24] border border-[#2B3040]">
            <div>
              <span className="text-slate-200 font-medium block">Active AI Model Provider</span>
              <span className="text-[11px] text-slate-400">Modular provider architecture</span>
            </div>
            <span className="font-mono text-[11px] px-2.5 py-0.5 rounded bg-[#11131A] text-blue-400 border border-[#2B3040] font-bold">
              YOLOv8 + ByteTrack
            </span>
          </div>
        </div>

        <div className="pt-2 flex justify-end">
          <button
            onClick={handleSave}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs font-mono transition shadow-sm"
          >
            {saved ? (
              <>
                <Check className="w-3.5 h-3.5" />
                <span>Settings Saved!</span>
              </>
            ) : (
              <span>Save Configuration</span>
            )}
          </button>
        </div>
      </div>

      {/* 2. Security & Privacy Statement */}
      <div className="glass-panel p-6 rounded-xl border border-[#222634] space-y-4 shadow-sm">
        <h2 className="text-sm font-bold text-white flex items-center gap-2">
          <Shield className="w-4 h-4 text-emerald-400" />
          <span>Security, Academic Integrity & Data Privacy Compliance</span>
        </h2>

        <div className="p-4 rounded-lg bg-[#171A24] border border-[#2B3040] space-y-2 text-xs leading-relaxed text-slate-300">
          <p className="font-semibold text-white">
            Privacy Policy & Authorized Footage Compliance Notice:
          </p>
          <p>
            This system is an academic engineering prototype designed for demonstration and research into multi-camera vehicle tracking and adverse-weather Optical Character Recognition.
          </p>
          <ul className="list-disc pl-5 space-y-1 text-slate-400 font-mono text-[11px]">
            <li>All vehicle numbers (e.g., <span className="text-blue-400">KA01AB1234, KA05XY9988</span>) are generated synthetically in demo mode.</li>
            <li>Synthetic owner identities and trajectories do not correspond to living individuals or registered private vehicles.</li>
            <li>Real-world field deployment requires compliance with statutory motor vehicles data governance and authorized municipal CCTV feeds.</li>
            <li>Role-Based Access Control (Admin, Operator, Analyst) and token authorization are structured within backend security middleware.</li>
          </ul>
        </div>
      </div>

      {/* 3. System Environment Info */}
      <div className="glass-panel p-6 rounded-xl border border-[#222634] space-y-3 text-xs shadow-sm">
        <h2 className="text-sm font-bold text-white flex items-center gap-2">
          <Terminal className="w-4 h-4 text-indigo-400" />
          <span>Runtime Environment & Architecture</span>
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 font-mono text-[11px]">
          <div className="p-3 rounded-lg bg-[#171A24] border border-[#2B3040]">
            <span className="text-slate-400 block">Frontend</span>
            <span className="text-blue-400 font-bold">React 18 + Vite + TS</span>
          </div>
          <div className="p-3 rounded-lg bg-[#171A24] border border-[#2B3040]">
            <span className="text-slate-400 block">Backend</span>
            <span className="text-emerald-400 font-bold">FastAPI + Asyncio</span>
          </div>
          <div className="p-3 rounded-lg bg-[#171A24] border border-[#2B3040]">
            <span className="text-slate-400 block">Database</span>
            <span className="text-amber-400 font-bold">PostgreSQL / SQLite</span>
          </div>
          <div className="p-3 rounded-lg bg-[#171A24] border border-[#2B3040]">
            <span className="text-slate-400 block">Computer Vision</span>
            <span className="text-purple-400 font-bold">OpenCV + NumPy</span>
          </div>
        </div>
      </div>
    </div>
  );
};
