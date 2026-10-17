import { Link } from 'react-router-dom'
import { CircleParking, Moon, Sun, Ticket, ArrowLeft, ShieldCheck, Activity } from 'lucide-react'
import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../../components/ui/tooltip'

const toneDot = {
  ok: 'hud-dot-ok',
  degraded: 'hud-dot-warn',
  offline: 'hud-dot-bad',
  simulated: 'hud-dot-info',
}

const toneWord = { ok: 'Online', degraded: 'Degraded', offline: 'Offline', simulated: 'Simulated' }

function DeviceBadge({ name, status, icon: Icon }) {
  const s = toneDot[status] ? status : 'offline'
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-border/60 bg-muted/40 text-[11px] font-medium transition-all hover:bg-muted/70 cursor-default select-none shrink-0">
          <span className={`w-2 h-2 rounded-full ${toneDot[s]} ${s === 'ok' ? 'hud-pulse-live' : ''}`} />
          <span className="text-foreground/90 font-semibold">{name}</span>
          <span className="text-muted-foreground hidden sm:inline">· {toneWord[s]}</span>
        </div>
      </TooltipTrigger>
      <TooltipContent side="bottom" className="text-xs">
        <p className="font-semibold">{name}</p>
        <p className="text-muted-foreground">{toneWord[s]}</p>
      </TooltipContent>
    </Tooltip>
  )
}

export default function TopBar({ devices, theme, onToggleTheme }) {
  const d = devices || {}
  const allConnected = d.camera === 'ok' && d.arduino === 'ok' && d.backend === 'ok'

  return (
    <header className="sticky top-0 z-40 w-full border-b border-border/50 bg-background/80 backdrop-blur-xl px-3 sm:px-6 py-2.5 transition-colors">
      <div className="mx-auto flex max-w-[1600px] items-center justify-between gap-3">
        {/* Brand & Navigation */}
        <div className="flex items-center gap-3 shrink-0">
          <Link
            to="/"
            className="flex items-center gap-2 group transition-transform active:scale-95"
            title="Return to ParkSensei Menu"
          >
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-cyan-500 flex items-center justify-center text-white shadow-md shadow-blue-500/20 group-hover:shadow-blue-500/40 transition-all">
              <CircleParking className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="font-extrabold text-base tracking-tight font-['Outfit'] bg-gradient-to-r from-foreground via-foreground/90 to-foreground/70 bg-clip-text">
                  ParkSensei
                </span>
                <span className="hidden xs:inline-flex items-center px-1.5 py-0.2 text-[9px] font-bold uppercase tracking-wider rounded bg-primary/10 text-primary border border-primary/20">
                  HUD
                </span>
              </div>
            </div>
          </Link>

          {/* Quick Navigation Links */}
          <nav className="hidden md:flex items-center gap-1 ml-2 pl-3 border-l border-border/60">
            <Link
              to="/history"
              className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-muted-foreground hover:text-foreground rounded-md hover:bg-muted/50 transition-colors"
            >
              <Ticket className="w-3.5 h-3.5" />
              <span>Tickets</span>
            </Link>
            <Link
              to="/"
              className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-muted-foreground hover:text-foreground rounded-md hover:bg-muted/50 transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Portal</span>
            </Link>
          </nav>
        </div>

        {/* Device Telemetry Badges - Horizontally Scrollable on Mobile */}
        <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar py-0.5 px-1 max-w-full">
          <TooltipProvider delayDuration={150}>
            <DeviceBadge name="Camera" status={d.camera} />
            <DeviceBadge name="Uno" status={d.arduino} />
            <DeviceBadge name="Sonar" status={d.ultrasonic} />
            <DeviceBadge name="IR" status={d.ir} />
            <DeviceBadge name="Printer" status={d.printer} />
          </TooltipProvider>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-1.5 shrink-0">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 rounded-lg hover:bg-muted/60"
            aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
            onClick={onToggleTheme}
          >
            {theme === 'dark' ? (
              <Sun className="w-4 h-4 text-amber-400 transition-transform hover:rotate-45" />
            ) : (
              <Moon className="w-4 h-4 text-slate-700 transition-transform hover:-rotate-12" />
            )}
          </Button>
        </div>
      </div>
    </header>
  )
}
