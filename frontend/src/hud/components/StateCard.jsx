import { Check, ShieldAlert, Activity, AlertTriangle, Radio, Navigation, PauseCircle } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card'
import { cn } from '../../lib/utils'

const STEPS = ['Detect', 'Patrol', 'Avoid', 'Review', 'Ticket', 'Resume']

const STATE_CONFIG = {
  IDLE: {
    title: 'System Idle',
    desc: 'Robot stationary. Path ready for patrol.',
    badgeClass: 'bg-slate-500/10 text-slate-400 border-slate-500/20',
    icon: Activity,
  },
  MONITORING: {
    title: 'Monitoring Lot',
    desc: 'Overhead camera actively tracking bay boundaries.',
    badgeClass: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
    icon: Radio,
  },
  PATROLLING: {
    title: 'Autonomous Patrol',
    desc: 'Navigating forward with active obstacle and violation detection.',
    badgeClass: 'bg-blue-500/10 text-blue-400 border-blue-500/20 hud-pulse-live',
    icon: Navigation,
  },
  PAUSED_REVIEW: {
    title: 'Operator Review',
    desc: 'Violation spotted. Verify plate & print citation to resume.',
    badgeClass: 'bg-amber-500/10 text-amber-400 border-amber-500/30 animate-pulse',
    icon: PauseCircle,
  },
  BLOCKED: {
    title: 'Patrol Blocked',
    desc: 'Robot halted after obstacle or link fault. Clear path to continue.',
    badgeClass: 'bg-red-500/10 text-red-400 border-red-500/30',
    icon: AlertTriangle,
  },
  ESTOP: {
    title: 'Emergency Halted',
    desc: 'Hardware safety lock active. Release E-stop to resume motion.',
    badgeClass: 'bg-red-600/20 text-red-500 border-red-500/40 hud-pulse-danger',
    icon: ShieldAlert,
  },
}

function stepIndexFor(state, reviewReady, reviewConfirmedCount, reviewTicketedCount, reviewTotal) {
  if (state === 'MONITORING') return 0
  if (state === 'PATROLLING') return 1
  if (state === 'PAUSED_REVIEW') {
    if (reviewReady) return 5
    if (reviewTicketedCount > 0 || (reviewTotal > 0 && reviewConfirmedCount >= reviewTotal)) return 4
    return 3
  }
  return -1
}

export default function StateCard({
  robotState, lastError, distanceCm, irBlocked, obstacle,
  reviewReady, reviewConfirmedCount = 0, reviewTicketedCount = 0, reviewTotal = 0,
}) {
  const cfg = STATE_CONFIG[robotState] || STATE_CONFIG.IDLE
  const StateIcon = cfg.icon
  const activeStep = stepIndexFor(robotState, reviewReady, reviewConfirmedCount, reviewTicketedCount, reviewTotal)

  return (
    <Card className="overflow-hidden border border-border/80 bg-card/90 backdrop-blur-md shadow-xl transition-all">
      <CardHeader className="p-4 pb-2">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Vehicle Telemetry
          </CardTitle>
          <div className={cn('flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border', cfg.badgeClass)}>
            <StateIcon className="w-3.5 h-3.5" />
            <span>{cfg.title}</span>
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-4 pt-1 flex flex-col gap-3.5">
        <div>
          <p className="text-xs text-muted-foreground leading-relaxed">
            {cfg.desc}
          </p>
        </div>

        {/* 3-Column Metric Dials */}
        <div className="grid grid-cols-3 gap-2">
          {/* Ultrasonic Sensor */}
          <div className="flex flex-col justify-between p-2.5 rounded-xl border border-border/60 bg-muted/20">
            <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Sonar Range</span>
            <div className="my-1">
              <span className="text-lg font-bold tnum text-foreground">
                {distanceCm == null ? '—' : `${distanceCm}`}
              </span>
              <span className="text-[11px] text-muted-foreground ml-1">cm</span>
            </div>
            <div className="w-full bg-border/40 h-1 rounded-full overflow-hidden">
              <div
                className={cn('h-full transition-all', distanceCm && distanceCm <= 18 ? 'bg-red-500' : 'bg-emerald-500')}
                style={{ width: `${Math.min(100, Math.max(10, ((distanceCm || 50) / 60) * 100))}%` }}
              />
            </div>
          </div>

          {/* IR Proximity */}
          <div className="flex flex-col justify-between p-2.5 rounded-xl border border-border/60 bg-muted/20">
            <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">IR Beam</span>
            <div className="my-1 flex items-center gap-1.5">
              <span className={cn('w-2 h-2 rounded-full', irBlocked ? 'bg-red-500' : 'bg-emerald-500')} />
              <span className={cn('text-sm font-bold', irBlocked ? 'text-red-400' : 'text-emerald-400')}>
                {irBlocked == null ? '—' : irBlocked ? 'Blocked' : 'Clear'}
              </span>
            </div>
            <span className="text-[10px] text-muted-foreground">GPIO22</span>
          </div>

          {/* Combined Path */}
          <div className="flex flex-col justify-between p-2.5 rounded-xl border border-border/60 bg-muted/20">
            <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Front Path</span>
            <div className="my-1 flex items-center gap-1.5">
              <span className={cn('text-sm font-bold', obstacle ? 'text-red-400' : 'text-emerald-400')}>
                {obstacle == null ? '—' : obstacle ? 'Obstacle' : 'Safe'}
              </span>
            </div>
            <span className="text-[10px] text-muted-foreground">Dual Sensor</span>
          </div>
        </div>

        {/* Error Alert Box */}
        {robotState === 'BLOCKED' && lastError && (
          <div role="alert" className="flex items-start gap-2.5 rounded-xl border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <p className="leading-relaxed">{lastError}</p>
          </div>
        )}

        {/* Progress Step Pipeline */}
        <div className="pt-1 border-t border-border/40">
          <div className="flex items-center justify-between gap-1 overflow-x-auto no-scrollbar py-1">
            {STEPS.map((step, i) => {
              const done = activeStep > i
              const current = activeStep === i
              return (
                <div key={step} className="flex items-center gap-1 shrink-0">
                  <div
                    className={cn(
                      'flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium transition-all',
                      done && 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20',
                      current && 'bg-primary text-white shadow-md shadow-primary/30 font-bold',
                      !done && !current && 'text-muted-foreground/60 border border-transparent'
                    )}
                  >
                    {done && <Check className="w-2.5 h-2.5" />}
                    <span>{step}</span>
                  </div>
                  {i < STEPS.length - 1 && (
                    <span className="w-2 h-0.5 bg-border/50 rounded-full shrink-0" />
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
