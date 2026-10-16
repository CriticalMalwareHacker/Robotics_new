import { Check } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card'
import { cn } from '../../lib/utils'

const STEPS = ['Check parking', 'Patrol', 'Avoid obstacle', 'Confirm', 'Print', 'Continue']

const STATE_COPY = {
  IDLE: { title: 'Idle', desc: 'Robot is stopped. Start the supervised tabletop patrol when the path is clear.' },
  MONITORING: { title: 'Checking parking', desc: 'Watching the mat for violations.' },
  PATROLLING: { title: 'Patrolling', desc: 'Moving forward and checking for obstacles and parking violations.' },
  PAUSED_REVIEW: { title: 'Paused for review', desc: 'Confirm the paper-card violation, print its ticket, then choose Go ahead.' },
  BLOCKED: { title: 'Patrol stopped', desc: 'The robot stopped after an obstacle, camera, sensor, or motor-link problem. Check the path and connection before restarting.' },
  ESTOP: { title: 'Emergency stop', desc: 'Robot is halted. Clear the stop to continue.' },
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

export default function StateCard({ robotState, lastError, distanceCm, irBlocked, obstacle,
  reviewReady, reviewConfirmedCount = 0, reviewTicketedCount = 0, reviewTotal = 0 }) {
  const copy = STATE_COPY[robotState] || STATE_COPY.IDLE
  const active = stepIndexFor(robotState, reviewReady, reviewConfirmedCount, reviewTicketedCount, reviewTotal)
  return (
    <Card>
      <CardHeader>
        <CardTitle>Robot state</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <p className="text-[28px] font-semibold leading-none">{copy.title}</p>
        <p className="text-sm text-muted-foreground">{copy.desc}</p>
        <dl className="grid grid-cols-3 gap-2 rounded-md border border-border bg-muted/30 p-3 text-xs">
          <div><dt className="text-muted-foreground">Ultrasonic</dt><dd className="mt-1 font-medium">{distanceCm == null ? '—' : `${distanceCm} cm`}</dd></div>
          <div><dt className="text-muted-foreground">IR sensor</dt><dd className="mt-1 font-medium">{irBlocked == null ? '—' : irBlocked ? 'Obstacle' : 'Clear'}</dd></div>
          <div><dt className="text-muted-foreground">Path</dt><dd className="mt-1 font-medium">{obstacle == null ? '—' : obstacle ? 'Blocked' : 'Clear'}</dd></div>
        </dl>
        {robotState === 'BLOCKED' && lastError && (
          <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
            {lastError}
          </p>
        )}
        <ol className="flex flex-wrap items-center gap-1.5" aria-label="Progress">
          {STEPS.map((step, i) => {
            const done = active > i
            const current = active === i
            return (
              <li key={step} className="flex items-center gap-1.5">
                <span
                  aria-current={current ? 'step' : undefined}
                  className={cn(
                    'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium',
                    done && 'text-muted-foreground',
                    current && 'border-transparent',
                    !done && !current && 'text-muted-foreground',
                  )}
                  style={current ? { backgroundColor: '#2563EB', color: '#fff', borderColor: 'transparent' } : undefined}
                >
                  {done && <Check className="size-3" aria-hidden />}
                  {step}
                </span>
              </li>
            )
          })}
        </ol>
      </CardContent>
    </Card>
  )
}
