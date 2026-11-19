import React, { useEffect, useState } from 'react';
import { AlertTriangle, Check, CheckCircle2, Plus, Trash2 } from 'lucide-react';
import { api } from '../services/api';
import type { AlertItem, AlertPage, AlertRule, AlertRuleType, Camera } from '../types';

const types: { value: AlertRuleType; label: string }[] = [
  { value: 'vehicle_detection', label: 'Vehicle detection' },
  { value: 'registration_match', label: 'Registration match' },
  { value: 'repeated_detection', label: 'Repeated detection' },
  { value: 'low_confidence_ocr', label: 'Low OCR confidence' },
  { value: 'camera_disconnected', label: 'Camera disconnected' },
  { value: 'camera_reconnected', label: 'Camera reconnected' },
];

export const Alerts: React.FC = () => {
  const [page, setPage] = useState<AlertPage | null>(null);
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [resolved, setResolved] = useState('false');
  const [severity, setSeverity] = useState('');
  const [camera, setCamera] = useState('');
  const [ack, setAck] = useState('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState<number | null>(null);
  const [name, setName] = useState('');
  const [ruleType, setRuleType] = useState<AlertRuleType>('vehicle_detection');
  const [ruleSeverity, setRuleSeverity] = useState('warning');
  const [registration, setRegistration] = useState('');
  const [threshold, setThreshold] = useState('0.6');
  const [occurrences, setOccurrences] = useState('3');
  const [windowSeconds, setWindowSeconds] = useState('300');

  const refresh = async () => {
    try {
      const [p, r] = await Promise.all([
        api.getAlertsPage({
          resolved: resolved === '' ? undefined : resolved === 'true',
          severity: severity || undefined,
          camera_id: camera || undefined,
          acknowledged: ack === '' ? undefined : ack === 'true',
          start_at: start ? `${start}T00:00:00Z` : undefined,
          end_at: end ? `${end}T23:59:59Z` : undefined,
          limit: 50,
          offset,
        }),
        api.getAlertRules(),
      ]);
      setPage(p);
      setRules(r);
      setError('');
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? 'Could not load alert records.');
    }
  };

  useEffect(() => {
    api.getCameras().then(setCameras).catch(() => setCameras([]));
  }, []);

  useEffect(() => {
    void refresh();
  }, [resolved, severity, camera, ack, start, end, offset]);

  const act = async (item: AlertItem, action: 'acknowledge' | 'resolve') => {
    setBusy(item.id);
    try {
      if (action === 'acknowledge') await api.acknowledgeAlert(item.id);
      else await api.resolveAlert(item.id);
      await refresh();
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? `Could not ${action} alert.`);
    } finally {
      setBusy(null);
    }
  };

  const createRule = async (e: React.FormEvent) => {
    e.preventDefault();
    let configuration: Record<string, string | number | boolean> = {};
    if (ruleType === 'registration_match') configuration.registration_number = registration.toUpperCase().replace(/\s|-/g, '');
    if (ruleType === 'low_confidence_ocr') configuration.threshold = Number(threshold);
    if (ruleType === 'repeated_detection') {
      configuration.occurrences = Number(occurrences);
      configuration.window_seconds = Number(windowSeconds);
    }
    try {
      await api.createAlertRule({ name, rule_type: ruleType, severity: ruleSeverity, configuration, enabled: true });
      setName('');
      await refresh();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Could not save alert rule.');
    }
  };

  const card = 'glass-panel rounded-xl border border-[#222634] p-5 shadow-sm';

  return (
    <div className="space-y-6">
      <header>
        <h1 className="flex items-center gap-2 text-xl font-bold text-white tracking-tight">
          <AlertTriangle className="text-rose-400" />
          <span>Traffic alerts</span>
        </h1>
        <p className="mt-1 text-xs text-slate-400">
          Alerts generated from persisted inference and camera health events. Configure rules below; seeded legacy alerts are identified by their source.
        </p>
      </header>

      {error && <p role="alert" className="rounded-lg border border-rose-800 bg-rose-950/30 p-3 text-sm text-rose-200">{error}</p>}

      <section className={`${card} flex flex-wrap items-end gap-3`}>
        <label className="text-xs text-slate-400">
          State
          <select
            value={resolved}
            onChange={(e) => {
              setResolved(e.target.value);
              setOffset(0);
            }}
            className="mt-1 block rounded-lg border border-[#2B3040] bg-[#171A24] p-2 text-white font-medium"
          >
            <option value="false">Active</option>
            <option value="true">Resolved</option>
            <option value="">All</option>
          </select>
        </label>
        <label className="text-xs text-slate-400">
          Severity
          <select
            value={severity}
            onChange={(e) => setSeverity(e.target.value)}
            className="mt-1 block rounded-lg border border-[#2B3040] bg-[#171A24] p-2 text-white font-medium"
          >
            <option value="">All</option>
            {['info', 'warning', 'medium', 'high', 'critical'].map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
        </label>
        <label className="text-xs text-slate-400">
          Camera
          <select
            value={camera}
            onChange={(e) => setCamera(e.target.value)}
            className="mt-1 block rounded-lg border border-[#2B3040] bg-[#171A24] p-2 text-white font-medium"
          >
            <option value="">All cameras</option>
            {cameras.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.id})
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-slate-400">
          Acknowledgement
          <select
            value={ack}
            onChange={(e) => setAck(e.target.value)}
            className="mt-1 block rounded-lg border border-[#2B3040] bg-[#171A24] p-2 text-white font-medium"
          >
            <option value="">All</option>
            <option value="false">Unacknowledged</option>
            <option value="true">Acknowledged</option>
          </select>
        </label>
        <label className="text-xs text-slate-400">
          From
          <input
            type="date"
            value={start}
            onChange={(e) => {
              setStart(e.target.value);
              setOffset(0);
            }}
            className="mt-1 block rounded-lg border border-[#2B3040] bg-[#171A24] p-2 text-white font-mono"
          />
        </label>
        <label className="text-xs text-slate-400">
          To
          <input
            type="date"
            value={end}
            onChange={(e) => {
              setEnd(e.target.value);
              setOffset(0);
            }}
            className="mt-1 block rounded-lg border border-[#2B3040] bg-[#171A24] p-2 text-white font-mono"
          />
        </label>
        <a
          href={api.getAnalyticsExportUrl('alert_history', {
            ...(camera ? { camera_id: camera } : {}),
            ...(start ? { start_at: `${start}T00:00:00Z` } : {}),
            ...(end ? { end_at: `${end}T23:59:59Z` } : {}),
            ...(severity ? { severity } : {}),
            ...(resolved !== '' ? { resolved: resolved === 'true' } : {}),
            ...(ack !== '' ? { acknowledged: ack === 'true' } : {}),
          })}
          className="rounded-lg border border-[#2B3040] bg-[#171A24] px-3.5 py-2 text-xs font-semibold text-blue-400 hover:text-blue-300 hover:border-blue-500/50 transition"
        >
          Export CSV
        </a>
      </section>

      <section className={card}>
        <h2 className="mb-3 font-semibold text-white">Alert history ({page?.total ?? 0})</h2>
        <div className="space-y-2">
          {page?.items.map((a) => (
            <article
              key={a.id}
              className="flex flex-col gap-3 rounded-lg border border-[#222634] bg-[#171A24]/60 p-3 md:flex-row md:items-center md:justify-between"
            >
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <b className="text-sm text-white">{a.alert_type.replace(/_/g, ' ')}</b>
                  <span className="rounded bg-[#171A24] border border-[#2B3040] px-2 py-0.5 text-[10px] uppercase font-mono text-amber-400">
                    {a.severity}
                  </span>
                  <span className="text-[10px] text-slate-400 font-mono">
                    {a.source ?? 'legacy'} · {new Date(a.created_at).toLocaleString()}
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-200">{a.message}</p>
                <p className="mt-1 text-[10px] text-slate-400 font-mono">
                  Camera {a.camera_id ?? '—'} · Track {a.tracking_id ?? '—'} · Plate {a.registration_number ?? '—'} · {a.acknowledged_at ? 'Acknowledged' : 'Not acknowledged'} · {a.is_resolved ? 'Resolved' : 'Active'}
                </p>
              </div>
              <div className="flex shrink-0 gap-2 font-medium">
                {!a.acknowledged_at && !a.is_resolved && (
                  <button
                    disabled={busy === a.id}
                    onClick={() => void act(a, 'acknowledge')}
                    className="inline-flex items-center gap-1 rounded-lg border border-[#2B3040] bg-[#171A24] px-2.5 py-1.5 text-xs text-blue-400 hover:text-blue-300 transition"
                  >
                    <Check size={13} />
                    Acknowledge
                  </button>
                )}
                {!a.is_resolved && (
                  <button
                    disabled={busy === a.id}
                    onClick={() => void act(a, 'resolve')}
                    className="inline-flex items-center gap-1 rounded-lg border border-emerald-800 bg-emerald-950/40 px-2.5 py-1.5 text-xs text-emerald-400 hover:bg-emerald-900/50 transition"
                  >
                    <CheckCircle2 size={13} />
                    Resolve
                  </button>
                )}
              </div>
            </article>
          ))}
          {page?.items.length === 0 && <p className="p-6 text-center text-xs text-slate-500">No alerts match these filters.</p>}
        </div>
        <div className="mt-4 flex items-center justify-end gap-3">
          <button
            disabled={!page || offset === 0}
            onClick={() => setOffset(Math.max(0, offset - 50))}
            className="rounded-lg border border-[#2B3040] bg-[#171A24] px-3 py-1.5 text-xs text-slate-300 hover:text-white disabled:opacity-40 transition"
          >
            Previous
          </button>
          <button
            disabled={!page || offset + 50 >= page.total}
            onClick={() => setOffset(offset + 50)}
            className="rounded-lg border border-[#2B3040] bg-[#171A24] px-3 py-1.5 text-xs text-slate-300 hover:text-white disabled:opacity-40 transition"
          >
            Next
          </button>
        </div>
      </section>

      <section className={card}>
        <h2 className="mb-3 font-semibold text-white">Configure alert rule</h2>
        <form onSubmit={createRule} className="flex flex-wrap items-end gap-3">
          <label className="text-xs text-slate-400">
            Name
            <input
              required
              maxLength={120}
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 block rounded-lg border border-[#2B3040] bg-[#171A24] p-2 text-white font-medium"
            />
          </label>
          <label className="text-xs text-slate-400">
            Type
            <select
              value={ruleType}
              onChange={(e) => setRuleType(e.target.value as AlertRuleType)}
              className="mt-1 block rounded-lg border border-[#2B3040] bg-[#171A24] p-2 text-white font-medium"
            >
              {types.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-slate-400">
            Severity
            <select
              value={ruleSeverity}
              onChange={(e) => setRuleSeverity(e.target.value)}
              className="mt-1 block rounded-lg border border-[#2B3040] bg-[#171A24] p-2 text-white font-medium"
            >
              {['info', 'warning', 'medium', 'high', 'critical'].map((x) => (
                <option key={x}>{x}</option>
              ))}
            </select>
          </label>
          {ruleType === 'registration_match' && (
            <label className="text-xs text-slate-400">
              Indian registration
              <input
                required
                value={registration}
                onChange={(e) => setRegistration(e.target.value)}
                placeholder="KA01AB1234"
                className="mt-1 block rounded-lg border border-[#2B3040] bg-[#171A24] p-2 text-white font-mono"
              />
            </label>
          )}
          {ruleType === 'low_confidence_ocr' && (
            <label className="text-xs text-slate-400">
              OCR threshold (0–1)
              <input
                required
                type="number"
                min="0"
                max="1"
                step="0.01"
                value={threshold}
                onChange={(e) => setThreshold(e.target.value)}
                className="mt-1 block rounded-lg border border-[#2B3040] bg-[#171A24] p-2 text-white font-mono"
              />
            </label>
          )}
          {ruleType === 'repeated_detection' && (
            <>
              <label className="text-xs text-slate-400">
                Occurrences
                <input
                  type="number"
                  min="2"
                  max="10000"
                  value={occurrences}
                  onChange={(e) => setOccurrences(e.target.value)}
                  className="mt-1 block rounded-lg border border-[#2B3040] bg-[#171A24] p-2 text-white font-mono"
                />
              </label>
              <label className="text-xs text-slate-400">
                Window seconds
                <input
                  type="number"
                  min="1"
                  max="86400"
                  value={windowSeconds}
                  onChange={(e) => setWindowSeconds(e.target.value)}
                  className="mt-1 block rounded-lg border border-[#2B3040] bg-[#171A24] p-2 text-white font-mono"
                />
              </label>
            </>
          )}
          <button className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 px-3.5 py-2 text-xs font-semibold text-white shadow-sm transition">
            <Plus size={14} />
            Add rule
          </button>
        </form>

        <div className="mt-4 space-y-2">
          {rules.map((r) => (
            <div key={r.id} className="flex items-center justify-between rounded-lg border border-[#222634] bg-[#171A24]/60 px-3 py-2 text-xs">
              <span className="text-slate-200 font-mono">
                {r.name} · {r.rule_type.replace(/_/g, ' ')} · {r.severity} · {r.enabled ? 'Enabled' : 'Disabled'}
              </span>
              <div className="flex items-center gap-3 font-medium">
                <button
                  onClick={async () => {
                    try {
                      await api.updateAlertRule(r.id, { enabled: !r.enabled });
                      await refresh();
                    } catch (e: any) {
                      setError(e?.response?.data?.detail ?? 'Could not update rule.');
                    }
                  }}
                  className="text-blue-400 hover:text-blue-300 transition"
                >
                  {r.enabled ? 'Disable' : 'Enable'}
                </button>
                <button
                  onClick={async () => {
                    try {
                      await api.deleteAlertRule(r.id);
                      await refresh();
                    } catch (e: any) {
                      setError(e?.response?.data?.detail ?? 'Could not delete rule.');
                    }
                  }}
                  className="text-rose-400 hover:text-rose-300 transition"
                  aria-label={`Delete ${r.name}`}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
          {rules.length === 0 && <p className="text-xs text-slate-500">No configured alert rules.</p>}
        </div>
      </section>
    </div>
  );
};
