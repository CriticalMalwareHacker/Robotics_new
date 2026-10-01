import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card'
import { ScrollArea } from '../../components/ui/scroll-area'

const dotFor = { info: 'hud-dot-info', warn: 'hud-dot-warn', error: 'hud-dot-bad' }

export default function EventLog({ events }) {
  const list = (events || []).slice(0, 100)
  return (
    <Card>
      <CardHeader>
        <CardTitle>Event log</CardTitle>
      </CardHeader>
      <CardContent>
        {list.length === 0 && (
          <p className="text-sm text-muted-foreground">Nothing happened yet. Start the monitor to watch events.</p>
        )}
        <ScrollArea className="h-44">
          <ul className="flex flex-col gap-1.5 pr-3">
            {list.map((e, i) => (
              <li key={`${e.t}-${i}`} className="flex items-baseline gap-2 text-sm">
                <span aria-hidden className={`size-1.5 shrink-0 translate-y-[-1px] rounded-full ${dotFor[e.level] || dotFor.info}`} />
                <span className="tnum shrink-0 text-muted-foreground">{e.t}</span>
                <span>{e.text}</span>
              </li>
            ))}
          </ul>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
