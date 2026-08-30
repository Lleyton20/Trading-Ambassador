import type { EconomicEvent, NewsCalendar } from '../types'

const IMPACT_COLOR: Record<string, string> = {
  high: '#ef4444',
  medium: '#f59e0b',
  low: '#64748b',
}

function EventRow({ event }: { event: EconomicEvent }) {
  const time = new Date(event.time)
  return (
    <li className="flex items-center gap-2 py-1.5 text-xs">
      <span
        className="h-2 w-2 shrink-0 rounded-full"
        style={{ backgroundColor: IMPACT_COLOR[event.impact] ?? '#64748b' }}
        title={`${event.impact} impact`}
      />
      <span className="w-12 shrink-0 text-slate-500">
        {time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
      </span>
      <span className="w-10 shrink-0 font-medium text-slate-400">{event.country}</span>
      <span className="flex-1 truncate text-slate-200">{event.event}</span>
      {event.affects_symbols.length > 0 && (
        <span className="shrink-0 truncate text-slate-500">{event.affects_symbols.join(', ')}</span>
      )}
    </li>
  )
}

export function NewsPanel({ news }: { news: NewsCalendar | null }) {
  if (!news) {
    return <div className="text-sm text-slate-500">Loading news…</div>
  }

  if (!news.available) {
    return (
      <div className="text-sm text-slate-500">
        News calendar unavailable — set <code className="text-slate-400">FINNHUB_API_KEY</code> in the backend's{' '}
        <code className="text-slate-400">.env</code> (see README).
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
          Today (high → low impact)
        </h3>
        {news.today.length === 0 ? (
          <p className="text-xs text-slate-500">No releases today.</p>
        ) : (
          <ul className="divide-y divide-white/5">
            {news.today.map((e, i) => (
              <EventRow key={i} event={e} />
            ))}
          </ul>
        )}
      </div>
      <div>
        <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Upcoming high-impact</h3>
        {news.upcoming_high_impact.length === 0 ? (
          <p className="text-xs text-slate-500">Nothing high-impact coming up.</p>
        ) : (
          <ul className="divide-y divide-white/5">
            {news.upcoming_high_impact.map((e, i) => (
              <li key={i} className="flex items-center gap-2 py-1.5 text-xs">
                <span className="w-24 shrink-0 text-slate-500">
                  {new Date(e.time).toLocaleDateString([], { month: 'short', day: 'numeric' })}
                </span>
                <span className="w-10 shrink-0 font-medium text-slate-400">{e.country}</span>
                <span className="flex-1 truncate text-slate-200">{e.event}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
