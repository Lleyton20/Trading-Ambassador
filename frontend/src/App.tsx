import { useEffect, useRef, useState } from 'react'
import { api } from './api'
import { AlertsPanel } from './components/AlertsPanel'
import { BiasBadge } from './components/BiasBadge'
import { ConfluencePanel } from './components/ConfluencePanel'
import { NewsPanel } from './components/NewsPanel'
import { PriceChart } from './components/PriceChart'
import { SymbolPicker } from './components/SymbolPicker'
import { Toast } from './components/Toast'
import { usePolling } from './hooks/usePolling'

const CANDLE_POLL_MS = 20_000
const NEWS_POLL_MS = 60_000
const ALERTS_POLL_MS = 10_000

function App() {
  const [symbol, setSymbol] = useState('EURUSD')
  const [timeframe, setTimeframe] = useState('H1')

  const markets = usePolling(() => api.markets(), 60_000, [])
  const candles = usePolling(() => api.candles(symbol, timeframe), CANDLE_POLL_MS, [symbol, timeframe])
  const smc = usePolling(() => api.smc(symbol, timeframe), CANDLE_POLL_MS, [symbol, timeframe])
  const liquidity = usePolling(() => api.liquidity(symbol, timeframe), CANDLE_POLL_MS, [symbol, timeframe])
  const confluence = usePolling(() => api.confluence(symbol, timeframe), CANDLE_POLL_MS, [symbol, timeframe])
  const news = usePolling(() => api.newsCalendar(), NEWS_POLL_MS, [])
  const alerts = usePolling(() => api.recentAlerts(), ALERTS_POLL_MS, [])

  const [toast, setToast] = useState<string | null>(null)
  const lastSeenAlertId = useRef<number | null>(null)

  useEffect(() => {
    if (!alerts.data || alerts.data.length === 0) return
    const newestId = alerts.data[0].id
    if (lastSeenAlertId.current !== null && newestId > lastSeenAlertId.current) {
      setToast(alerts.data[0].message)
    }
    lastSeenAlertId.current = newestId
  }, [alerts.data])

  useEffect(() => {
    if (!toast) return
    const id = setTimeout(() => setToast(null), 8000)
    return () => clearTimeout(id)
  }, [toast])

  return (
    <div className="mx-auto flex min-h-screen max-w-7xl flex-col gap-4 p-4">
      {toast && <Toast message={toast} onDismiss={() => setToast(null)} />}

      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-100">Trading Ambassador</h1>
          <p className="text-xs text-slate-500">
            Evidence, not signals — structure, liquidity, and risk math for Forex &amp; Deriv synthetic indices.
          </p>
        </div>
        <SymbolPicker
          markets={markets.data ?? []}
          symbol={symbol}
          timeframe={timeframe}
          onSymbolChange={setSymbol}
          onTimeframeChange={setTimeframe}
        />
      </header>

      <div className="flex flex-wrap gap-3">
        <BiasBadge label={`${timeframe} bias`} bias={smc.data?.bias ?? 'neutral'} />
        {smc.data?.premium_discount && (
          <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-400">
            price is <span className="font-medium text-slate-200">{smc.data.premium_discount.status}</span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[2fr_1fr]">
        <div className="h-[640px] rounded-xl border border-white/10 bg-white/5 p-2">
          {candles.error ? (
            <div className="flex h-full items-center justify-center text-sm text-red-400">
              Failed to load candles: {candles.error}
            </div>
          ) : (
            <PriceChart candles={candles.data ?? []} smc={smc.data} liquidity={liquidity.data} />
          )}
        </div>

        <div className="flex flex-col gap-4">
          <section className="rounded-xl border border-white/10 bg-white/5 p-4">
            <ConfluencePanel confluence={confluence.data} />
          </section>
          <section className="rounded-xl border border-white/10 bg-white/5 p-4">
            <h2 className="mb-2 text-sm font-semibold text-slate-300">Alerts</h2>
            <AlertsPanel alerts={alerts.data} />
          </section>
        </div>
      </div>

      <section className="rounded-xl border border-white/10 bg-white/5 p-4">
        <h2 className="mb-2 text-sm font-semibold text-slate-300">Economic calendar</h2>
        <NewsPanel news={news.data} />
      </section>
    </div>
  )
}

export default App
