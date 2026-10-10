import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { ArrowLeft, ArrowUpRight, CarFront, CircleParking, Clock3, RefreshCw, Ticket } from 'lucide-react'
import { Button } from './components/ui/button'
import { Card } from './components/ui/card'
import { apiUrl, getTicketHistory } from './hud/api'
import './portal.css'

function Home() {
  useEffect(() => { document.title = 'ParkSensei' }, [])

  return (
    <main className="portal-shell">
      <header className="portal-header">
        <Link to="/" className="portal-brand"><span className="portal-brand-icon"><CircleParking /></span>ParkSensei</Link>
        <span className="portal-header-note">Parking monitor</span>
      </header>
      <section className="portal-home">
        <p className="portal-eyebrow">LOCAL ROBOT CONSOLE</p>
        <h1>Good to see you.</h1>
        <p className="portal-subtitle">Choose where you want to go.</p>
        <div className="portal-options">
          <Link to="/hud" className="portal-option-link">
            <Card className="portal-option">
              <span className="portal-option-icon"><CarFront /></span>
              <span className="portal-option-copy"><strong>Open live HUD</strong><small>Camera, parking detection, and robot controls</small></span>
              <ArrowUpRight className="portal-option-arrow" />
            </Card>
          </Link>
          <Link to="/history" className="portal-option-link">
            <Card className="portal-option">
              <span className="portal-option-icon"><Ticket /></span>
              <span className="portal-option-copy"><strong>Ticket history</strong><small>Review parking notices created by the system</small></span>
              <ArrowUpRight className="portal-option-arrow" />
            </Card>
          </Link>
        </div>
        <p className="portal-footnote"><span className="portal-live-dot" />Self-hosted on your local network</p>
      </section>
    </main>
  )
}

function formatDate(value) {
  if (!value) return 'Time unavailable'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

function TicketHistory() {
  const [tickets, setTickets] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    setError('')
    try {
      const data = await getTicketHistory()
      setTickets(Array.isArray(data) ? data : data.tickets || [])
    } catch (err) {
      setError(err.message || 'Could not load ticket history.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { document.title = 'Ticket history - ParkSensei'; refresh() }, [refresh])

  return (
    <main className="portal-shell">
      <header className="portal-header">
        <Link to="/" className="portal-brand"><span className="portal-brand-icon"><CircleParking /></span>ParkSensei</Link>
        <Link to="/" className="portal-back-link"><ArrowLeft /> Menu</Link>
      </header>
      <section className="history-page">
        <div className="history-heading">
          <div><p className="portal-eyebrow">RECORDS</p><h1>Ticket history</h1><p className="portal-subtitle">Parking notices recorded by this system.</p></div>
          <Button variant="outline" className="portal-refresh" onClick={() => { setLoading(true); refresh() }} disabled={loading}><RefreshCw /> Refresh</Button>
        </div>
        <Card className="ticket-list-card">
          {loading ? <div className="history-empty">Loading tickets...</div> : error ? (
            <div className="history-empty"><p>{error}</p><Button variant="outline" onClick={() => { setLoading(true); refresh() }}>Try again</Button></div>
          ) : tickets.length === 0 ? (
            <div className="history-empty"><span className="empty-ticket-icon"><Ticket /></span><strong>No tickets yet</strong><p>Tickets will appear here when the system records a parking violation.</p></div>
          ) : (
            <div className="ticket-list">
              {tickets.map((ticket) => (
                <article className="ticket-row" key={ticket.number}>
                  <span className="ticket-row-icon"><Ticket /></span>
                  <div className="ticket-row-main"><div className="ticket-row-title"><strong>{ticket.number || 'Parking ticket'}</strong><span className={`ticket-status status-${ticket.status || 'saved'}`}>{ticket.status || 'saved'}</span></div>
                    <p>{[ticket.plate, ticket.vehicle, ticket.slot, ticket.violation].filter(Boolean).join(' | ') || ticket.message || 'Parking notice'}</p>
                    <small><Clock3 /> {formatDate(ticket.time)}</small>
                  </div>
                  {ticket.image_url && <a className="ticket-image-link" href={`${apiUrl}${ticket.image_url}`} target="_blank" rel="noreferrer">View ticket <ArrowUpRight /></a>}
                </article>
              ))}
            </div>
          )}
        </Card>
      </section>
    </main>
  )
}

export default function App() {
  const { pathname } = useLocation()
  return pathname === '/history' ? <TicketHistory /> : <Home />
}
