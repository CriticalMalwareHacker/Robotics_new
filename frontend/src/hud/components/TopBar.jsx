import { Moon, Sun } from 'lucide-react'
import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../../components/ui/tooltip'

const toneDot = {
  ok: 'hud-dot-ok',
  degraded: 'hud-dot-warn',
  offline: 'hud-dot-bad',
  simulated: 'hud-dot-info',
}

const toneWord = { ok: 'Ok', degraded: 'Degraded', offline: 'Offline', simulated: 'Simulated' }

function DeviceBadge({ name, status }) {
  const s = toneDot[status] ? status : 'offline'
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span>
          <Badge dotClassName={toneDot[s]}>{name} · {toneWord[s]}</Badge>
        </span>
      </TooltipTrigger>
      <TooltipContent>{name}: {toneWord[s]}.</TooltipContent>
    </Tooltip>
  )
}

export default function TopBar({ devices, theme, onToggleTheme }) {
  const d = devices || {}
  return (
    <header className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-3">
      <h1 className="text-xl font-semibold">PrintSensei robot</h1>
      <div className="ml-2 flex flex-wrap items-center gap-2">
        <TooltipProvider>
          <DeviceBadge name="Camera" status={d.camera} />
          <DeviceBadge name="Arduino" status={d.arduino} />
          <DeviceBadge name="Ultrasonic" status={d.ultrasonic} />
          <DeviceBadge name="Printer" status={d.printer} />
          <DeviceBadge name="Backend" status={d.backend} />
        </TooltipProvider>
      </div>
      <div className="ml-auto">
        <Button variant="outline" size="icon" aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'} onClick={onToggleTheme}>
          {theme === 'dark' ? <Sun /> : <Moon />}
        </Button>
      </div>
    </header>
  )
}
