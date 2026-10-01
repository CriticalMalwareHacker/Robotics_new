import { Button } from '../../components/ui/button'

export default function EstopBanner({ active, clearing, onClear }) {
  if (!active) return null
  return (
    <div role="alert" className="flex flex-wrap items-center gap-3 border-b border-border bg-card px-4 py-3">
      <span aria-hidden className="size-2.5 rounded-full hud-dot-bad" />
      <p className="text-sm font-medium">Emergency stop active. All drive controls are disabled until cleared.</p>
      <Button variant="outline" size="sm" className="ml-auto" disabled={clearing} onClick={onClear}>
        {clearing ? 'Clearing…' : 'Clear and reset'}
      </Button>
    </div>
  )
}
