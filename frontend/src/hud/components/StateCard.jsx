import { Check } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card'
import { cn } from '../../lib/utils'

const STEPS = ['Scan', 'Check', 'Read plate', 'Ticket', 'Drive', 'Print', 'Return']

const STATE_COPY = {
  IDLE: { title: 'Idle', desc: 'Robot is parked. Start auto mode to begin checking.' },
  MONITORING: { title: 'Checking parking', desc: 'Watching the mat for violations.' },
  PATROLLING: { title: 'Driving to vehicle', desc: 'Moving toward the violating vehicle.' },
  ESTOP: { title: 'Emergency stop', desc: 'Robot is halted. Clear the stop to continue.' },
}

function stepIndexFor(state, hasViolation, hasTicket) {
  if (state === 'ESTOP' || state === 'IDLE') return -1
  if (hasTicket) return 4
  if (hasViolation) return 2
  return 1
}

export default function StateCard({ robotState, hasViolation, hasTicket }) {
  const copy = STATE_COPY[robotState] || STATE_COPY.IDLE
  const active = stepIndexFor(robotState, hasViolation, hasTicket)
  return (
    <Card>
      <CardHeader>
        <CardTitle>Robot state</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <p className="text-[28px] font-semibold leading-none">{copy.title}</p>
        <p className="text-sm text-muted-foreground">{copy.desc}</p>
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
