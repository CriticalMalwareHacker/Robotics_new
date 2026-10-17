import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { ArrowLeft, ArrowUpRight, CarFront, CircleParking, Clock3, RefreshCw, Ticket, ShieldCheck } from 'lucide-react'
import { Button } from './components/ui/button'
import { Card } from './components/ui/card'
import { apiUrl, getTicketHistory } from './hud/api'
import './portal.css'

function Home() {
  useEffect(() => {
    document.title = 'ParkSensei — Autonomous Robot Console'
  }, [])

  return (
    <main className="portal-shell">
      <header className="portal-header">
        <Link to="/" className="portal-brand">
          <span className="portal-brand-icon">
            <CircleParking />
          </span>
          ParkSensei
        </Link>
        <span className="portal-header-note">Autonomous Sentinel</span>
      </header>

      <section className="portal-home">
        <p className="portal-eyebrow">TACTICAL ROBOT CONSOLE</p>
        <h1>ParkSensei Sentinel</h1>
        <p className="portal-subtitle">
          Autonomous parking space surveillance, AI violation detection, and on-spot thermal citation system.
        </p>

        <div className="portal-options">
          <Link to="/hud" className="portal-option-link">
            <Card className="portal-option">
              <span className="portal-option-icon">
                <CarFront />
              </span>
              <span className="portal-option-copy">
                <strong>Launch Robot HUD</strong>
                <small>Live camera stream, telemetry sensors, AI parking detector & manual steering</small>
              </span>
              <ArrowUpRight className="portal-option-arrow" />
            </Card>
          </Link>

          <Link to="/history" className="portal-option-link">
            <Card className="portal-option">
              <span className="portal-option-icon">
                <Ticket />
              </span>
              <span className="portal-option-copy">
                <strong>Citation Archive</strong>
                <small>Review logged parking tickets, license plate records, and print dispatch status</small>
              </span>
              <ArrowUpRight className="portal-option-arrow" />
            </Card>
          </Link>
        </div>

        <p className="portal-footnote">
          <span className="portal-live-dot" /> Connected to Raspberry Pi 5 node (10.42.0.1:8000)
        </p>
      </section>
    </main>
  )
}

function formatDate(value) {
  if (!value) return 'Time unavailable'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
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

  useEffect(() => {
    document.title = 'Citation Archive — ParkSensei'
    refresh()
  }, [refresh])

  return (
    <main className="portal-shell">
      <header className="portal-header">
        <Link to="/" className="portal-brand">
          <span className="portal-brand-icon">
            <CircleParking />
          </span>
          ParkSensei
        </Link>
        <Link to="/" className="portal-back-link">
          <ArrowLeft /> Back to Console
        </Link>
      </header>

      <section className="history-page">
        <div className="history-heading">
          <div>
            <p className="portal-eyebrow">ENFORCEMENT AUDIT</p>
            <h1>Citation Archive</h1>
            <p className="portal-subtitle">Historical log of violations recorded by ParkSensei.</p>
          </div>
          <Button
            variant="outline"
            className="portal-refresh"
            onClick={() => {
              setLoading(true)
              refresh()
            }}
            disabled={loading}
          >
            <RefreshCw className={loading ? 'animate-spin' : ''} /> Refresh Records
          </Button>
        </div>

        <Card className="ticket-list-card">
          {loading ? (
            <div className="history-empty">Loading enforcement records…</div>
          ) : error ? (
            <div className="history-empty">
              <p>{error}</p>
              <Button
                variant="outline"
                onClick={() => {
                  setLoading(true)
                  refresh()
                }}
              >
                Retry
              </Button>
            </div>
          ) : tickets.length === 0 ? (
            <div className="history-empty">
              <span className="empty-ticket-icon">
                <ShieldCheck />
              </span>
              <strong>No Violations Recorded</strong>
              <p>Tickets will appear here when ParkSensei detects and tickets an unauthorized vehicle.</p>
            </div>
          ) : (
            <div className="ticket-list">
              {tickets.map((ticket) => (
                <article className="ticket-row" key={ticket.number}>
                  <span className="ticket-row-icon">
                    <Ticket />
                  </span>
                  <div className="ticket-row-main">
                    <div className="ticket-row-title">
                      <strong>{ticket.number || 'PARK-NOTICE'}</strong>
                      <span className={`ticket-status status-${ticket.status || 'saved'}`}>
                        {ticket.status || 'saved'}
                      </span>
                    </div>
                    <p>
                      {[ticket.plate, ticket.vehicle, ticket.slot, ticket.violation]
                        .filter(Boolean)
                        .join(' · ') || ticket.message || 'Parking violation'}
                    </p>
                    <small>
                      <Clock3 /> {formatDate(ticket.time)}
                    </small>
                  </div>
                  {ticket.image_url && (
                    <a
                      className="ticket-image-link"
                      href={`${apiUrl}${ticket.image_url}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      View Notice <ArrowUpRight />
                    </a>
                  )}
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
