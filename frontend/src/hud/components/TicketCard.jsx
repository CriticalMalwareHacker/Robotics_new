import { Download, Printer } from 'lucide-react'
import { apiUrl } from '../api'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card'

export default function TicketCard({ ticket, printing, onPrint }) {
  if (!ticket) return null
  const failed = ticket.status === 'failed'
  return (
    <Card>
      <CardHeader>
        <CardTitle>Ticket</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {ticket.image_url && (
          <img
            src={`${apiUrl}${ticket.image_url}`}
            alt={`Ticket ${ticket.number} preview`}
            className="w-full rounded-md border border-border bg-white"
          />
        )}
        <div className="flex items-baseline justify-between gap-3 text-sm">
          <span className="font-medium text-muted-foreground">Number</span>
          <span className="tnum">{ticket.number}</span>
        </div>
        <div className="flex items-baseline justify-between gap-3 text-sm">
          <span className="font-medium text-muted-foreground">Status</span>
          <span className={failed ? 'hud-bad' : 'hud-ok'}>
            {failed ? 'Failed' : ticket.status === 'printed' ? 'Printed' : 'Generated'}
          </span>
        </div>
        {failed && (
          <p className="text-sm text-muted-foreground">Printer not available. The ticket was saved and can be reprinted.</p>
        )}
        <div className="flex gap-2">
          <Button variant="outline" size="sm" disabled={printing} onClick={onPrint}>
            <Printer /> {printing ? 'Printing…' : 'Reprint'}
          </Button>
          {ticket.image_url && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                const a = document.createElement('a')
                a.href = `${apiUrl}${ticket.image_url}`
                a.download = `ticket-${ticket.number}.png`
                a.click()
              }}
            >
              <Download /> Download PNG
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
