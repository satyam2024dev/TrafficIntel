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

  const card = 'bg-white rounded-2xl border border-slate-200/90 p-5 shadow-sm';

  return (
    <div className="space-y-6">
      <header>
        <h1 className="flex items-center gap-2.5 text-xl font-extrabold text-slate-900 tracking-tight">
          <AlertTriangle className="text-[#EF4444] w-6 h-6" />
          <span>Traffic & Sensor Alerts</span>
        </h1>
        <p className="mt-1 text-xs text-slate-500">
          Alerts generated from persisted inference and camera health events. Configure rules below; seeded legacy alerts are identified by their source.
        </p>
      </header>

      {error && <p role="alert" className="rounded-2xl border border-rose-300 bg-rose-50 p-4 text-sm text-rose-800 shadow-sm font-medium">{error}</p>}

      <section className={`${card} flex flex-wrap items-end gap-3`}>
        <label className="text-xs text-slate-600 font-semibold">
          State
          <select
            value={resolved}
            onChange={(e) => {
              setResolved(e.target.value);
              setOffset(0);
            }}
            className="mt-1.5 block rounded-xl border border-slate-300 bg-[#F8FAFC] px-3 py-2 text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-[#00A8C6] shadow-sm text-xs"
          >
            <option value="false">Active</option>
            <option value="true">Resolved</option>
            <option value="">All</option>
          </select>
        </label>
        <label className="text-xs text-slate-600 font-semibold">
          Severity
          <select
            value={severity}
            onChange={(e) => setSeverity(e.target.value)}
            className="mt-1.5 block rounded-xl border border-slate-300 bg-[#F8FAFC] px-3 py-2 text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-[#00A8C6] shadow-sm text-xs"
          >
            <option value="">All</option>
            {['info', 'warning', 'medium', 'high', 'critical'].map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
        </label>
        <label className="text-xs text-slate-600 font-semibold">
          Camera
          <select
            value={camera}
            onChange={(e) => setCamera(e.target.value)}
            className="mt-1.5 block rounded-xl border border-slate-300 bg-[#F8FAFC] px-3 py-2 text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-[#00A8C6] shadow-sm text-xs"
          >
            <option value="">All cameras</option>
            {cameras.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.id})
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-slate-600 font-semibold">
          Acknowledgement
          <select
            value={ack}
            onChange={(e) => setAck(e.target.value)}
            className="mt-1.5 block rounded-xl border border-slate-300 bg-[#F8FAFC] px-3 py-2 text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-[#00A8C6] shadow-sm text-xs"
          >
            <option value="">All</option>
            <option value="false">Unacknowledged</option>
            <option value="true">Acknowledged</option>
          </select>
        </label>
        <label className="text-xs text-slate-600 font-semibold">
          From
          <input
            type="date"
            value={start}
            onChange={(e) => {
              setStart(e.target.value);
              setOffset(0);
            }}
            className="mt-1.5 block rounded-xl border border-slate-300 bg-[#F8FAFC] px-3 py-2 text-slate-900 font-mono focus:outline-none focus:ring-2 focus:ring-[#00A8C6] shadow-sm text-xs"
          />
        </label>
        <label className="text-xs text-slate-600 font-semibold">
          To
          <input
            type="date"
            value={end}
            onChange={(e) => {
              setEnd(e.target.value);
              setOffset(0);
            }}
            className="mt-1.5 block rounded-xl border border-slate-300 bg-[#F8FAFC] px-3 py-2 text-slate-900 font-mono focus:outline-none focus:ring-2 focus:ring-[#00A8C6] shadow-sm text-xs"
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
          className="rounded-xl bg-[#00A8C6] hover:bg-[#0090AA] px-4 py-2 text-xs font-semibold text-white shadow-sm transition"
        >
          Export CSV
        </a>
      </section>

      <section className={card}>
        <h2 className="mb-3 font-bold text-base text-slate-900">Alert history ({page?.total ?? 0})</h2>
        <div className="space-y-2.5">
          {page?.items.map((a) => (
            <article
              key={a.id}
              className="flex flex-col gap-3 rounded-xl border border-slate-200/90 bg-[#F8FAFC] p-3.5 md:flex-row md:items-center md:justify-between shadow-sm hover:bg-white transition"
            >
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <b className="text-sm text-slate-900">{a.alert_type.replace(/_/g, ' ')}</b>
                  <span className={`rounded-md border px-2 py-0.5 text-[10px] uppercase font-mono font-bold ${
                    a.severity === 'critical' ? 'bg-rose-50 border-rose-300 text-[#EF4444]' :
                    a.severity === 'high' ? 'bg-orange-50 border-orange-300 text-orange-700' :
                    a.severity === 'warning' ? 'bg-amber-50 border-amber-300 text-[#F59E0B]' :
                    'bg-teal-50 border-teal-300 text-[#00A8C6]'
                  }`}>
                    {a.severity}
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono">
                    {a.source ?? 'legacy'} · {new Date(a.created_at).toLocaleString()}
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-700 font-medium">{a.message}</p>
                <p className="mt-1 text-[10px] text-slate-500 font-mono">
                  Camera {a.camera_id ?? '—'} · Track {a.tracking_id ?? '—'} · Plate {a.registration_number ?? '—'} · {a.acknowledged_at ? 'Acknowledged' : 'Not acknowledged'} · {a.is_resolved ? 'Resolved' : 'Active'}
                </p>
              </div>
              <div className="flex shrink-0 gap-2 font-medium">
                {!a.acknowledged_at && !a.is_resolved && (
                  <button
                    disabled={busy === a.id}
                    onClick={() => void act(a, 'acknowledge')}
                    className="inline-flex items-center gap-1 rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-xs text-[#00A8C6] hover:text-[#0090AA] hover:bg-slate-50 shadow-sm transition font-semibold"
                  >
                    <Check size={13} />
                    Acknowledge
                  </button>
                )}
                {!a.is_resolved && (
                  <button
                    disabled={busy === a.id}
                    onClick={() => void act(a, 'resolve')}
                    className="inline-flex items-center gap-1 rounded-xl border border-emerald-300 bg-emerald-50 px-3 py-1.5 text-xs text-emerald-700 hover:bg-emerald-100 shadow-sm transition font-bold"
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
            className="rounded-xl border border-slate-300 bg-white px-3.5 py-1.5 text-xs text-slate-700 hover:bg-slate-50 hover:text-[#00A8C6] shadow-sm disabled:opacity-40 transition font-semibold"
          >
            Previous
          </button>
          <button
            disabled={!page || offset + 50 >= page.total}
            onClick={() => setOffset(offset + 50)}
            className="rounded-xl border border-slate-300 bg-white px-3.5 py-1.5 text-xs text-slate-700 hover:bg-slate-50 hover:text-[#00A8C6] shadow-sm disabled:opacity-40 transition font-semibold"
          >
            Next
          </button>
        </div>
      </section>

      <section className={card}>
        <h2 className="mb-3 font-bold text-base text-slate-900">Configure alert rule</h2>
        <form onSubmit={createRule} className="flex flex-wrap items-end gap-3">
          <label className="text-xs text-slate-600 font-semibold">
            Name
            <input
              required
              maxLength={120}
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1.5 block rounded-xl border border-slate-300 bg-[#F8FAFC] px-3 py-2 text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-[#00A8C6] shadow-sm text-xs"
            />
          </label>
          <label className="text-xs text-slate-600 font-semibold">
            Type
            <select
              value={ruleType}
              onChange={(e) => setRuleType(e.target.value as AlertRuleType)}
              className="mt-1.5 block rounded-xl border border-slate-300 bg-[#F8FAFC] px-3 py-2 text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-[#00A8C6] shadow-sm text-xs"
            >
              {types.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-slate-600 font-semibold">
            Severity
            <select
              value={ruleSeverity}
              onChange={(e) => setRuleSeverity(e.target.value)}
              className="mt-1.5 block rounded-xl border border-slate-300 bg-[#F8FAFC] px-3 py-2 text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-[#00A8C6] shadow-sm text-xs"
            >
              {['info', 'warning', 'medium', 'high', 'critical'].map((x) => (
                <option key={x}>{x}</option>
              ))}
            </select>
          </label>
          {ruleType === 'registration_match' && (
            <label className="text-xs text-slate-600 font-semibold">
              Indian registration
              <input
                required
                value={registration}
                onChange={(e) => setRegistration(e.target.value)}
                placeholder="KA01AB1234"
                className="mt-1.5 block rounded-xl border border-slate-300 bg-[#F8FAFC] px-3 py-2 text-slate-900 font-mono focus:outline-none focus:ring-2 focus:ring-[#00A8C6] shadow-sm text-xs"
              />
            </label>
          )}
          {ruleType === 'low_confidence_ocr' && (
            <label className="text-xs text-slate-600 font-semibold">
              OCR threshold (0–1)
              <input
                required
                type="number"
                min="0"
                max="1"
                step="0.01"
                value={threshold}
                onChange={(e) => setThreshold(e.target.value)}
                className="mt-1.5 block rounded-xl border border-slate-300 bg-[#F8FAFC] px-3 py-2 text-slate-900 font-mono focus:outline-none focus:ring-2 focus:ring-[#00A8C6] shadow-sm text-xs"
              />
            </label>
          )}
          {ruleType === 'repeated_detection' && (
            <>
              <label className="text-xs text-slate-600 font-semibold">
                Occurrences
                <input
                  type="number"
                  min="2"
                  max="10000"
                  value={occurrences}
                  onChange={(e) => setOccurrences(e.target.value)}
                  className="mt-1.5 block rounded-xl border border-slate-300 bg-[#F8FAFC] px-3 py-2 text-slate-900 font-mono focus:outline-none focus:ring-2 focus:ring-[#00A8C6] shadow-sm text-xs"
                />
              </label>
              <label className="text-xs text-slate-600 font-semibold">
                Window seconds
                <input
                  type="number"
                  min="1"
                  max="86400"
                  value={windowSeconds}
                  onChange={(e) => setWindowSeconds(e.target.value)}
                  className="mt-1.5 block rounded-xl border border-slate-300 bg-[#F8FAFC] px-3 py-2 text-slate-900 font-mono focus:outline-none focus:ring-2 focus:ring-[#00A8C6] shadow-sm text-xs"
                />
              </label>
            </>
          )}
          <button className="inline-flex items-center gap-1.5 rounded-xl bg-[#00A8C6] hover:bg-[#0090AA] px-4 py-2 text-xs font-semibold text-white shadow-sm transition">
            <Plus size={14} />
            Add rule
          </button>
        </form>

        <div className="mt-4 space-y-2">
          {rules.map((r) => (
            <div key={r.id} className="flex items-center justify-between rounded-xl border border-slate-200/90 bg-[#F8FAFC] px-3.5 py-2.5 text-xs shadow-sm">
              <span className="text-slate-800 font-mono font-medium">
                {r.name} · {r.rule_type.replace(/_/g, ' ')} · {r.severity} · {r.enabled ? 'Enabled' : 'Disabled'}
              </span>
              <div className="flex items-center gap-3 font-semibold">
                <button
                  onClick={async () => {
                    try {
                      await api.updateAlertRule(r.id, { enabled: !r.enabled });
                      await refresh();
                    } catch (e: any) {
                      setError(e?.response?.data?.detail ?? 'Could not update rule.');
                    }
                  }}
                  className="text-[#00A8C6] hover:text-[#0090AA] transition"
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
                  className="text-rose-600 hover:text-rose-700 transition"
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
