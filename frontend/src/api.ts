// Every call goes through the relative `/api` path - the Vite dev server
// proxies that to the backend (see vite.config.ts), and in production
// this is served from the same origin. Never a hardcoded absolute URL.
import type {
  Alert,
  Confluence,
  LiquidityAnalysis,
  MarketSummary,
  NewsCalendar,
  SmcAnalysis,
} from './types'

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path)
  if (!response.ok) {
    throw new Error(`${path} failed: ${response.status}`)
  }
  return response.json() as Promise<T>
}

export const api = {
  markets: () => getJson<MarketSummary[]>('/api/markets'),
  candles: (symbol: string, timeframe: string, count = 300) =>
    getJson<{ timestamp: string; open: number; high: number; low: number; close: number; volume: number }[]>(
      `/api/markets/${symbol}/candles?timeframe=${timeframe}&count=${count}`,
    ),
  smc: (symbol: string, timeframe: string) => getJson<SmcAnalysis>(`/api/markets/${symbol}/smc?timeframe=${timeframe}`),
  liquidity: (symbol: string, timeframe: string) =>
    getJson<LiquidityAnalysis>(`/api/markets/${symbol}/liquidity?timeframe=${timeframe}`),
  confluence: (symbol: string, timeframe: string) =>
    getJson<Confluence>(`/api/markets/${symbol}/confluence?timeframe=${timeframe}`),
  newsCalendar: () => getJson<NewsCalendar>('/api/news/calendar'),
  recentAlerts: (limit = 50) => getJson<Alert[]>(`/api/alerts/recent?limit=${limit}`),
}
