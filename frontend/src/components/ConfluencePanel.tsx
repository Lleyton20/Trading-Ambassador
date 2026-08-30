import { biasColor } from '../colors'
import type { Confluence } from '../types'

export function ConfluencePanel({ confluence }: { confluence: Confluence | null }) {
  if (!confluence) {
    return <div className="text-sm text-slate-500">Loading confluence…</div>
  }

  const pct = Math.round(confluence.score_pct)

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-slate-300">
          Confluence ({confluence.timeframe} vs {confluence.htf_timeframe})
        </span>
        <span className="text-lg font-bold" style={{ color: biasColor(confluence.bias) }}>
          {confluence.score}/{confluence.max_score} ({pct}%)
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-white/10">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, backgroundColor: biasColor(confluence.bias) }}
        />
      </div>
      <ul className="grid grid-cols-2 gap-1.5 text-xs">
        {confluence.factors.map((f) => (
          <li
            key={f.name}
            className={`flex items-center justify-between rounded-md px-2 py-1 ${
              f.met ? 'bg-white/10 text-slate-200' : 'text-slate-500'
            }`}
          >
            <span className="capitalize">{f.name.replace(/_/g, ' ')}</span>
            <span>{f.met ? `+${f.weight}` : '—'}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
