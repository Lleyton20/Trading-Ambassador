export function Toast({ message, onDismiss }: { message: string; onDismiss: () => void }) {
  return (
    <div className="fixed right-4 top-4 z-50 max-w-sm rounded-lg border border-sky-400/30 bg-slate-900 px-4 py-3 shadow-lg shadow-black/40">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 h-2 w-2 shrink-0 rounded-full bg-sky-400" />
        <p className="text-sm text-slate-200">{message}</p>
        <button onClick={onDismiss} className="ml-auto text-slate-500 hover:text-slate-300">
          ✕
        </button>
      </div>
    </div>
  )
}
