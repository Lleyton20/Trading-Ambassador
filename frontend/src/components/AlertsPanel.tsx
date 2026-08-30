import { biasColor } from '../colors'
import type { Alert } from '../types'

export function AlertsPanel({ alerts }: { alerts: Alert[] | null }) {
  if (!alerts) {
    return <div className="text-sm text-slate-500">Loading alerts…</div>
  }

  if (alerts.length === 0) {
    return (
      <p className="text-xs text-slate-500">
        No price-in-zone alerts yet. Enable them with <code className="text-slate-400">ALERTS_ENABLED=true</code> in
        the backend's <code className="text-slate-400">.env</code> (see README).
      </p>
    )
  }

  return (
    <ul className="max-h-64 space-y-1.5 overflow-y-auto pr-1">
      {alerts.map((a) => (
        <li key={a.id} className="rounded-md border border-white/5 bg-white/5 px-2.5 py-1.5 text-xs">
          <div className="flex items-center justify-between">
            <span className="font-medium" style={{ color: biasColor(a.direction) }}>
              {a.symbol} · {a.zone_type.replace('_', ' ')}
            </span>
            <span className="text-slate-500">{new Date(a.triggered_at).toLocaleTimeString()}</span>
          </div>
          <p className="mt-0.5 text-slate-400">{a.message}</p>
          {a.telegram_sent && <span className="mt-0.5 inline-block text-[10px] text-sky-400">sent to Telegram</span>}
        </li>
      ))}
    </ul>
  )
}
