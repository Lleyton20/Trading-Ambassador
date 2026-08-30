import type { MarketSummary } from '../types'

const TIMEFRAMES = ['M15', 'M30', 'H1', 'H4', 'D1']

export function SymbolPicker({
  markets,
  symbol,
  timeframe,
  onSymbolChange,
  onTimeframeChange,
}: {
  markets: MarketSummary[]
  symbol: string
  timeframe: string
  onSymbolChange: (symbol: string) => void
  onTimeframeChange: (timeframe: string) => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <select
        value={symbol}
        onChange={(e) => onSymbolChange(e.target.value)}
        className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm"
      >
        {markets.map((m) => (
          <option key={m.symbol} value={m.symbol} className="bg-slate-900">
            {m.display_name} ({m.symbol})
          </option>
        ))}
      </select>

      <div className="flex gap-1 rounded-lg border border-white/10 bg-white/5 p-1">
        {TIMEFRAMES.map((tf) => (
          <button
            key={tf}
            onClick={() => onTimeframeChange(tf)}
            className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
              tf === timeframe ? 'bg-sky-400/20 text-sky-300' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            {tf}
          </button>
        ))}
      </div>
    </div>
  )
}
