import { biasColor } from '../colors'

export function BiasBadge({ label, bias }: { label: string; bias: string }) {
  const color = biasColor(bias)
  return (
    <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2">
      <span className="text-xs uppercase tracking-wide text-slate-400">{label}</span>
      <span
        className="rounded px-2 py-0.5 text-sm font-semibold capitalize"
        style={{ backgroundColor: `${color}33`, color }}
      >
        {bias}
      </span>
    </div>
  )
}
