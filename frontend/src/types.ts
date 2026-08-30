// Mirrors backend/app/schemas/*.py exactly - field names and shapes are
// kept in lockstep with the Pydantic models, not redefined independently.

export type Bias = 'bullish' | 'bearish' | 'neutral'

export interface MarketSummary {
  symbol: string
  display_name: string
  asset_class: string
  current_price: number
}

export interface Candle {
  timestamp: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface SwingPoint {
  timestamp: string
  price: number
  kind: 'high' | 'low'
  label: 'HH' | 'HL' | 'LH' | 'LL'
}

export interface StructureEvent {
  timestamp: string
  event_type: 'BOS' | 'CHOCH'
  direction: 'bullish' | 'bearish'
  price: number
  broken_level: number
}

export interface OrderBlock {
  direction: 'bullish' | 'bearish'
  zone_low: number
  zone_high: number
  created_at: string
  structure_event_type: 'BOS' | 'CHOCH'
  mitigated: boolean
  mitigated_at: string | null
  retest_count: number
}

export interface FairValueGap {
  direction: 'bullish' | 'bearish'
  upper: number
  lower: number
  created_at: string
  mitigated_pct: number
}

export interface LiquidityLevel {
  label: string
  kind: 'high' | 'low'
  price: number
  formed_at: string
  swept: boolean
  swept_at: string | null
}

export interface PremiumDiscount {
  range_high: number
  range_low: number
  equilibrium: number
  status: 'premium' | 'discount' | 'equilibrium'
}

export interface SmcAnalysis {
  symbol: string
  timeframe: string
  bias: Bias
  swing_points: SwingPoint[]
  structure_events: StructureEvent[]
  order_blocks: OrderBlock[]
  fair_value_gaps: FairValueGap[]
  premium_discount: PremiumDiscount | null
}

export interface LiquidityAnalysis {
  symbol: string
  timeframe: string
  levels: LiquidityLevel[]
}

export interface ConfluenceFactor {
  name: string
  weight: number
  met: boolean
}

export interface Confluence {
  symbol: string
  timeframe: string
  htf_timeframe: string
  bias: Bias
  htf_bias: Bias
  score: number
  max_score: number
  score_pct: number
  factors: ConfluenceFactor[]
}

export interface EconomicEvent {
  event: string
  country: string
  impact: 'low' | 'medium' | 'high'
  time: string
  actual: number | null
  estimate: number | null
  prev: number | null
  unit: string | null
  affects_symbols: string[]
}

export interface NewsCalendar {
  available: boolean
  today: EconomicEvent[]
  upcoming_high_impact: EconomicEvent[]
}

export interface Alert {
  id: number
  symbol: string
  timeframe: string
  zone_type: 'order_block' | 'fair_value_gap'
  direction: 'bullish' | 'bearish'
  zone_low: number
  zone_high: number
  price_at_trigger: number
  triggered_at: string
  message: string
  telegram_sent: boolean
}
