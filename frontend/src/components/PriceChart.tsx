import { useEffect, useRef } from 'react'
import {
  CandlestickSeries,
  LineStyle,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type SeriesMarker,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts'
import { BEARISH_COLOR, BULLISH_COLOR, CANDLE_DOWN_COLOR, CANDLE_UP_COLOR } from '../colors'
import type { Candle, LiquidityAnalysis, SmcAnalysis } from '../types'

function toUnixSeconds(iso: string): UTCTimestamp {
  return Math.floor(new Date(iso).getTime() / 1000) as UTCTimestamp
}

export function PriceChart({
  candles,
  smc,
  liquidity,
}: {
  candles: Candle[]
  smc: SmcAnalysis | null
  liquidity: LiquidityAnalysis | null
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null)
  const priceLinesRef = useRef<IPriceLine[]>([])

  // Chart lifecycle: created once, torn down on unmount.
  useEffect(() => {
    if (!containerRef.current) return

    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: { background: { color: 'transparent' }, textColor: '#94a3b8' },
      grid: {
        vertLines: { color: 'rgba(148, 163, 184, 0.08)' },
        horzLines: { color: 'rgba(148, 163, 184, 0.08)' },
      },
      timeScale: { timeVisible: true, secondsVisible: false },
    })
    const series = chart.addSeries(CandlestickSeries, {
      upColor: CANDLE_UP_COLOR,
      downColor: CANDLE_DOWN_COLOR,
      borderVisible: false,
      wickUpColor: CANDLE_UP_COLOR,
      wickDownColor: CANDLE_DOWN_COLOR,
    })
    const markers = createSeriesMarkers(series, [])

    chartRef.current = chart
    seriesRef.current = series
    markersRef.current = markers

    return () => {
      chart.remove()
      chartRef.current = null
      seriesRef.current = null
      markersRef.current = null
    }
  }, [])

  // Candles.
  useEffect(() => {
    if (!seriesRef.current || candles.length === 0) return
    seriesRef.current.setData(
      candles.map((c) => ({
        time: toUnixSeconds(c.timestamp),
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })),
    )
    chartRef.current?.timeScale().fitContent()
  }, [candles])

  // Swings + BOS/CHoCH as markers, bias-colored (bullish = light blue,
  // bearish = red - same convention as everywhere else on the dashboard).
  // Capped to the most recent handful - the backend already truncates to
  // 20 each, but that's still too dense to read on a chart (see the same
  // lesson learned in scripts/plot_analysis.py).
  useEffect(() => {
    if (!markersRef.current || !smc) return

    const markers: SeriesMarker<Time>[] = []
    for (const s of smc.swing_points.slice(-8)) {
      const bullishStructure = s.label === 'HH' || s.label === 'HL'
      markers.push({
        time: toUnixSeconds(s.timestamp),
        position: s.kind === 'high' ? 'aboveBar' : 'belowBar',
        color: bullishStructure ? BULLISH_COLOR : BEARISH_COLOR,
        shape: s.kind === 'high' ? 'arrowDown' : 'arrowUp',
        text: s.label,
        size: 0.6,
      })
    }
    for (const e of smc.structure_events.slice(-6)) {
      markers.push({
        time: toUnixSeconds(e.timestamp),
        position: e.direction === 'bullish' ? 'belowBar' : 'aboveBar',
        color: e.direction === 'bullish' ? BULLISH_COLOR : BEARISH_COLOR,
        shape: e.direction === 'bullish' ? 'arrowUp' : 'arrowDown',
        text: e.event_type,
      })
    }
    markers.sort((a, b) => (a.time as number) - (b.time as number))
    markersRef.current.setMarkers(markers)
  }, [smc])

  // Zones (order blocks, FVGs, liquidity levels, premium/discount) as
  // price lines - recreated on every update since createPriceLine has no
  // built-in "update" for an existing line's price/color. Only *active*
  // zones are drawn: a mitigated order block or a fully-filled FVG is
  // history, not a zone still worth watching, and including them anyway
  // was making the chart unreadable (the same zones app/alerts/watcher.py
  // treats as "of high interest" are exactly the ones shown here).
  useEffect(() => {
    const series = seriesRef.current
    if (!series) return

    for (const line of priceLinesRef.current) series.removePriceLine(line)
    priceLinesRef.current = []

    const addLine = (price: number, color: string, title: string, style: LineStyle = LineStyle.Dotted) => {
      priceLinesRef.current.push(
        series.createPriceLine({ price, color, lineWidth: 1, lineStyle: style, axisLabelVisible: true, title }),
      )
    }

    if (smc) {
      const activeOrderBlocks = smc.order_blocks.filter((ob) => !ob.mitigated).slice(-4)
      for (const ob of activeOrderBlocks) {
        const color = ob.direction === 'bullish' ? BULLISH_COLOR : BEARISH_COLOR
        addLine(ob.zone_high, color, `OB ${ob.direction}`, LineStyle.Dashed)
        addLine(ob.zone_low, color, '', LineStyle.Dashed)
      }
      const activeGaps = smc.fair_value_gaps.filter((g) => g.mitigated_pct < 100).slice(-4)
      for (const g of activeGaps) {
        const color = g.direction === 'bullish' ? BULLISH_COLOR : BEARISH_COLOR
        addLine(g.upper, color, `FVG ${g.direction} ${g.mitigated_pct.toFixed(0)}%`)
        addLine(g.lower, color, '')
      }
      if (smc.premium_discount) {
        const { range_high, range_low, equilibrium } = smc.premium_discount
        addLine(range_high, BEARISH_COLOR, 'premium', LineStyle.LargeDashed)
        addLine(equilibrium, '#64748b', 'equilibrium', LineStyle.Solid)
        addLine(range_low, BULLISH_COLOR, 'discount', LineStyle.LargeDashed)
      }
    }

    if (liquidity) {
      const recentLevels = liquidity.levels.slice(-5)
      for (const level of recentLevels) {
        addLine(level.price, level.swept ? '#e879f9' : '#64748b', `${level.label}${level.swept ? ' (swept)' : ''}`)
      }
    }
  }, [smc, liquidity])

  return <div ref={containerRef} className="h-full w-full" />
}
