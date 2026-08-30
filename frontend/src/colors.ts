// Explicit bias color convention used everywhere bias shows up on the
// dashboard (zones, badges, dealing-range shading): bearish = red,
// bullish = light blue. Not the "green up / red down" convention candles
// themselves use - this is specifically about *bias*, not candle direction.
export const BEARISH_COLOR = '#ef4444' // red-500
export const BULLISH_COLOR = '#7dd3fc' // sky-300 ("light blue")
export const NEUTRAL_COLOR = '#94a3b8' // slate-400

export function biasColor(bias: string): string {
  if (bias === 'bearish') return BEARISH_COLOR
  if (bias === 'bullish') return BULLISH_COLOR
  return NEUTRAL_COLOR
}

// Candle body colors keep the conventional green/red up/down look -
// distinct from the bias palette above by design.
export const CANDLE_UP_COLOR = '#22c55e'
export const CANDLE_DOWN_COLOR = '#ef4444'
