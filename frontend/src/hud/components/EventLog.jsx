import { Terminal, Activity } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card'
import { ScrollArea } from '../../components/ui/scroll-area'

const dotFor = {
  info: 'hud-dot-info',
  warn: 'hud-dot-warn',
  error: 'hud-dot-bad',
}

const badgeFor = {
  info: 'text-cyan-400 bg-cyan-950/40 border-cyan-500/30',
  warn: 'text-amber-400 bg-amber-950/40 border-amber-500/30',
  error: 'text-red-400 bg-red-950/40 border-red-500/30',
}

export default function EventLog({ events }) {
  const list = (events || []).slice(0, 100)

  return (
    <Card className="hud-glass-card overflow-hidden">
      <CardHeader className="p-4 pb-2 sm:p-5 sm:pb-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
              <Terminal className="h-4 w-4" />
            </div>
            <div>
              <CardTitle className="text-base sm:text-lg font-bold tracking-tight">System Telemetry Log</CardTitle>
              <CardDescription className="text-xs">Subsystem diagnostics and hardware event stream</CardDescription>
            </div>
          </div>
          <span className="font-mono text-xs text-muted-foreground bg-background/50 px-2 py-0.5 rounded border border-border/40">
            {list.length} EVENTS
          </span>
        </div>
      </CardHeader>

      <CardContent className="p-4 pt-2 sm:p-5 sm:pt-2">
        {list.length === 0 ? (
          <div className="flex items-center justify-center gap-2 py-8 text-xs text-muted-foreground">
            <Activity className="h-4 w-4 opacity-40 animate-pulse" />
            <span>Telemetry stream awaiting new system messages…</span>
          </div>
        ) : (
          <ScrollArea className="h-44 rounded-xl border border-border/40 bg-black/40 p-3 font-mono text-xs">
            <ul className="flex flex-col gap-2 pr-2">
              {list.map((e, i) => (
                <li
                  key={`${e.t}-${i}`}
                  className="flex items-start gap-2.5 text-xs leading-relaxed border-b border-white/[0.03] pb-1.5 last:border-b-0 last:pb-0"
                >
                  <span
                    aria-hidden
                    className={`mt-1.5 size-2 shrink-0 rounded-full ${dotFor[e.level] || dotFor.info}`}
                  />
                  <span className="shrink-0 text-[11px] text-muted-foreground font-semibold">
                    {e.t}
                  </span>
                  <span className="break-words text-foreground/90 font-sans sm:font-mono">
                    {e.text}
                  </span>
                </li>
              ))}
            </ul>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  )
}
