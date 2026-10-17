import { AlertOctagon, RotateCcw } from 'lucide-react'
import { Button } from '../../components/ui/button'

export default function EstopBanner({ active, clearing, onClear }) {
  if (!active) return null

  return (
    <div
      role="alert"
      className="relative z-30 flex flex-wrap items-center justify-between gap-3 border-b border-red-500/50 bg-gradient-to-r from-red-950 via-red-900 to-red-950 px-4 py-3 text-white shadow-lg shadow-red-950/60"
    >
      <div className="flex items-center gap-2.5 min-w-0">
        <span className="relative flex h-3 w-3 shrink-0">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
        </span>
        <div className="flex items-center gap-2 flex-wrap">
          <AlertOctagon className="h-5 w-5 text-red-300 shrink-0" />
          <span className="font-bold text-sm tracking-wide">EMERGENCY STOP ENGAGED</span>
          <span className="text-xs text-red-200/90 hidden sm:inline">
            — Hardware motion locked until cleared.
          </span>
        </div>
      </div>

      <Button
        variant="outline"
        size="sm"
        className="ml-auto h-9 bg-white/10 hover:bg-white/20 text-white border-white/30 text-xs font-bold tracking-wide"
        disabled={clearing}
        onClick={onClear}
      >
        <RotateCcw className={`mr-1.5 h-3.5 w-3.5 ${clearing ? 'animate-spin' : ''}`} />
        {clearing ? 'Clearing Motors…' : 'Clear & Reset E-Stop'}
      </Button>
    </div>
  )
}
