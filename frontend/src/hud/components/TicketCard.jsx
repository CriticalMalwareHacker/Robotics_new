import { Download, Printer, Receipt, CheckCircle, AlertCircle } from 'lucide-react'
import { apiUrl } from '../api'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card'
import { Badge } from '../../components/ui/badge'

export default function TicketCard({ ticket, printing, onPrint }) {
  if (!ticket) return null
  const failed = ticket.status === 'failed'
  const printed = ticket.status === 'printed'

  return (
    <Card className="hud-glass-card overflow-hidden">
      <CardHeader className="p-4 pb-2 sm:p-5 sm:pb-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary border border-primary/20">
              <Receipt className="h-4 w-4" />
            </div>
            <div>
              <CardTitle className="text-base sm:text-lg font-bold tracking-tight">Active Citation</CardTitle>
              <CardDescription className="text-xs">Thermal print buffer & notice dispatch</CardDescription>
            </div>
          </div>
          <Badge
            className={`font-mono text-xs px-2.5 py-1 ${
              failed ? 'hud-bad' : printed ? 'hud-ok' : 'hud-warn'
            }`}
          >
            {failed ? 'FAILED' : printed ? 'PRINTED' : 'GENERATED'}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="p-4 pt-2 sm:p-5 sm:pt-2 flex flex-col gap-3">
        {ticket.image_url && (
          <div className="relative overflow-hidden rounded-xl border border-white/20 bg-neutral-900 p-2 shadow-xl shadow-black/40">
            <div className="rounded-lg overflow-hidden bg-white">
              <img
                src={`${apiUrl}${ticket.image_url}`}
                alt={`Ticket ${ticket.number} preview`}
                className="w-full object-contain max-h-56 filter drop-shadow"
              />
            </div>
          </div>
        )}

        <div className="rounded-xl border border-border/50 bg-background/50 p-3 space-y-2 text-xs">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground font-medium">Citation ID:</span>
            <span className="font-mono font-bold tracking-wider text-foreground">{ticket.number}</span>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-muted-foreground font-medium">Hardware Status:</span>
            <div className="flex items-center gap-1.5 font-medium">
              {failed ? (
                <>
                  <AlertCircle className="h-3.5 w-3.5 text-red-400" />
                  <span className="text-red-400">Offline / Jammed</span>
                </>
              ) : printed ? (
                <>
                  <CheckCircle className="h-3.5 w-3.5 text-emerald-400" />
                  <span className="text-emerald-400">Successfully Dispatched</span>
                </>
              ) : (
                <span className="text-amber-400">Buffered in Queue</span>
              )}
            </div>
          </div>
        </div>

        {failed && (
          <p className="text-xs text-red-400/90 bg-red-950/20 border border-red-500/20 rounded-lg p-2.5">
            Thermal printer did not respond. Ticket record is stored in memory and can be reprinted once ready.
          </p>
        )}

        <div className="flex gap-2 pt-1">
          <Button
            variant="outline"
            size="sm"
            className="flex-1 h-9 text-xs font-semibold border-border/70 hover:bg-primary hover:text-white transition-all"
            disabled={printing}
            onClick={onPrint}
          >
            <Printer className={`mr-1.5 h-3.5 w-3.5 ${printing ? 'animate-pulse' : ''}`} />
            {printing ? 'Printing…' : 'Reprint Ticket'}
          </Button>

          {ticket.image_url && (
            <Button
              variant="secondary"
              size="sm"
              className="h-9 text-xs font-medium"
              onClick={() => {
                const a = document.createElement('a')
                a.href = `${apiUrl}${ticket.image_url}`
                a.download = `ticket-${ticket.number}.png`
                a.click()
              }}
            >
              <Download className="mr-1.5 h-3.5 w-3.5" />
              Download PNG
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
