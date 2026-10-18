import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  AlertTriangle,
  ArrowLeft,
  ArrowUpRight,
  Camera,
  CarFront,
  CheckCircle2,
  CircleParking,
  Clock3,
  ExternalLink,
  Eye,
  FileText,
  RefreshCw,
  Search,
  ShieldCheck,
  Ticket,
  X,
} from 'lucide-react'
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
                <strong>Photo Evidence & Citations</strong>
                <small>Review logged parking infractions, optical photo evidence, and thermal tickets</small>
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

function EvidenceModal({ ticket, onClose }) {
  const [activeTab, setActiveTab] = useState('evidence')

  if (!ticket) return null

  const evidenceUrl = ticket.evidence_url
    ? (ticket.evidence_url.startsWith('http') ? ticket.evidence_url : `${apiUrl}${ticket.evidence_url}`)
    : null

  const ticketImageUrl = ticket.image_url
    ? (ticket.image_url.startsWith('http') ? ticket.image_url : `${apiUrl}${ticket.image_url}`)
    : null

  return (
    <div className="evidence-modal-backdrop" onClick={onClose}>
      <div className="evidence-modal-dialog" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="evidence-modal-header">
          <div className="evidence-modal-title-group">
            <span className="evidence-badge-verified">
              <ShieldCheck size={14} /> OFFICIAL RECORD
            </span>
            <h2>Citation {ticket.number}</h2>
            <p className="evidence-modal-meta">
              <Clock3 size={13} /> {formatDate(ticket.time)} · Autonomous Unit #1
            </p>
          </div>
          <button className="evidence-modal-close" onClick={onClose} aria-label="Close dialog">
            <X size={20} />
          </button>
        </div>

        {/* View Switcher Tabs */}
        <div className="evidence-tab-bar">
          <button
            className={`evidence-tab-btn ${activeTab === 'evidence' ? 'active' : ''}`}
            onClick={() => setActiveTab('evidence')}
          >
            <Camera size={15} /> Optical Photo Evidence
          </button>
          <button
            className={`evidence-tab-btn ${activeTab === 'receipt' ? 'active' : ''}`}
            onClick={() => setActiveTab('receipt')}
          >
            <FileText size={15} /> Thermal Receipt Printout
          </button>
        </div>

        {/* Media Display Area */}
        <div className="evidence-modal-body">
          {activeTab === 'evidence' ? (
            <div className="evidence-photo-viewer">
              {evidenceUrl ? (
                <div className="evidence-img-wrap">
                  <img src={evidenceUrl} alt={`Evidence for ${ticket.number}`} className="evidence-main-img" />
                  <div className="evidence-img-overlay-tag">
                    <CheckCircle2 size={13} /> AI Annotated Bay & Vehicle Quad
                  </div>
                </div>
              ) : (
                <div className="evidence-placeholder">
                  <Camera size={38} />
                  <p>Optical evidence snapshot archived for citation {ticket.number}</p>
                  {ticketImageUrl && (
                    <Button variant="outline" size="sm" onClick={() => setActiveTab('receipt')}>
                      View Thermal Receipt
                    </Button>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="evidence-receipt-viewer">
              {ticketImageUrl ? (
                <div className="receipt-scroll-wrap">
                  <img src={ticketImageUrl} alt={`Thermal ticket for ${ticket.number}`} className="receipt-main-img" />
                </div>
              ) : (
                <div className="evidence-placeholder">
                  <FileText size={38} />
                  <p>Thermal ticket label image unavailable</p>
                </div>
              )}
            </div>
          )}

          {/* Details Grid */}
          <div className="evidence-details-grid">
            <div className="evidence-detail-cell">
              <span className="detail-label">REGISTRATION PLATE</span>
              <div className="license-plate-badge">
                <span className="plate-ind">IND</span>
                <span className="plate-num">{ticket.plate || 'UNREAD'}</span>
              </div>
            </div>

            <div className="evidence-detail-cell">
              <span className="detail-label">INFRACTION OBSERVED</span>
              <span className="violation-tag-pill">
                <AlertTriangle size={13} /> {ticket.violation?.replace(/_/g, ' ') || 'PARKING INFRACTION'}
              </span>
            </div>

            <div className="evidence-detail-cell">
              <span className="detail-label">LOCATION ASSIGNMENT</span>
              <span className="detail-val-highlight">BAY {ticket.slot || 'UNKNOWN'}</span>
            </div>

            <div className="evidence-detail-cell">
              <span className="detail-label">DISPATCH STATUS</span>
              <span className={`ticket-status status-${ticket.status || 'saved'}`}>
                {ticket.status || 'SAVED'}
              </span>
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="evidence-modal-footer">
          {evidenceUrl && (
            <a href={evidenceUrl} target="_blank" rel="noreferrer" className="evidence-footer-link">
              <ExternalLink size={14} /> Full Resolution Photo
            </a>
          )}
          {ticketImageUrl && (
            <a href={ticketImageUrl} target="_blank" rel="noreferrer" className="evidence-footer-link">
              <Ticket size={14} /> Open Thermal PNG
            </a>
          )}
          <Button variant="outline" onClick={onClose} className="evidence-footer-btn">
            Done
          </Button>
        </div>
      </div>
    </div>
  )
}

function TicketHistory() {
  const [tickets, setTickets] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedTicket, setSelectedTicket] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterType, setFilterType] = useState('ALL')

  const location = useLocation()

  const refresh = useCallback(async () => {
    setError('')
    try {
      const data = await getTicketHistory()
      const list = Array.isArray(data) ? data : data.tickets || []
      setTickets(list)

      // Auto-open modal if ?ticket=T-xxx is in URL query parameters
      const params = new URLSearchParams(location.search)
      const ticketParam = params.get('ticket')
      if (ticketParam) {
        const found = list.find((t) => t.number?.toUpperCase() === ticketParam.toUpperCase())
        if (found) {
          setSelectedTicket(found)
        }
      }
    } catch (err) {
      setError(err.message || 'Could not load ticket history.')
    } finally {
      setLoading(false)
    }
  }, [location.search])

  useEffect(() => {
    document.title = 'Photo Evidence Gallery — ParkSensei'
    refresh()
  }, [refresh])

  // Filter and search
  const filteredTickets = useMemo(() => {
    return tickets.filter((t) => {
      // Violation filter
      if (filterType !== 'ALL') {
        if (!t.violation || !t.violation.toUpperCase().includes(filterType)) {
          return false
        }
      }
      // Text search
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim()
        const matchNum = t.number?.toLowerCase().includes(q)
        const matchPlate = t.plate?.toLowerCase().includes(q)
        const matchSlot = t.slot?.toLowerCase().includes(q)
        const matchVio = t.violation?.toLowerCase().includes(q)
        return matchNum || matchPlate || matchSlot || matchVio
      }
      return true
    })
  }, [tickets, filterType, searchQuery])

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
          <ArrowLeft size={16} /> Back to Console
        </Link>
      </header>

      <section className="history-page">
        <div className="history-heading">
          <div>
            <p className="portal-eyebrow">ENFORCEMENT AUDIT & EVIDENCE</p>
            <h1>Photo Evidence Gallery</h1>
            <p className="portal-subtitle">
              Inspect annotated camera snapshots, bay geometry, and issued citations recorded by ParkSensei.
            </p>
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
            <RefreshCw className={loading ? 'animate-spin' : ''} /> Refresh Gallery
          </Button>
        </div>

        {/* Filter and Search Bar */}
        <div className="gallery-toolbar">
          <div className="gallery-search-wrap">
            <Search size={16} className="gallery-search-icon" />
            <input
              type="text"
              placeholder="Search by license plate, citation number, bay..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="gallery-search-input"
            />
            {searchQuery && (
              <button className="gallery-search-clear" onClick={() => setSearchQuery('')}>
                <X size={14} />
              </button>
            )}
          </div>

          <div className="gallery-filter-pills">
            <button
              className={`filter-pill ${filterType === 'ALL' ? 'active' : ''}`}
              onClick={() => setFilterType('ALL')}
            >
              All Records ({tickets.length})
            </button>
            <button
              className={`filter-pill ${filterType === 'STRADDLING' ? 'active' : ''}`}
              onClick={() => setFilterType('STRADDLING')}
            >
              Straddling
            </button>
            <button
              className={`filter-pill ${filterType === 'OUTSIDE' ? 'active' : ''}`}
              onClick={() => setFilterType('OUTSIDE')}
            >
              Outside Bay
            </button>
          </div>
        </div>

        {/* Main Content Area */}
        {loading ? (
          <Card className="ticket-list-card">
            <div className="history-empty">
              <RefreshCw className="animate-spin" size={28} />
              <p>Loading digital evidence records…</p>
            </div>
          </Card>
        ) : error ? (
          <Card className="ticket-list-card">
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
          </Card>
        ) : tickets.length === 0 ? (
          <Card className="ticket-list-card">
            <div className="history-empty">
              <span className="empty-ticket-icon">
                <ShieldCheck />
              </span>
              <strong>No Citations Recorded</strong>
              <p>Photo evidence and tickets will appear here automatically when ParkSensei detects a violation.</p>
            </div>
          </Card>
        ) : filteredTickets.length === 0 ? (
          <Card className="ticket-list-card">
            <div className="history-empty">
              <Search size={28} />
              <strong>No matching records found</strong>
              <p>Try clearing your search query or filter tags.</p>
              <Button variant="outline" size="sm" onClick={() => { setSearchQuery(''); setFilterType('ALL'); }}>
                Reset Filters
              </Button>
            </div>
          </Card>
        ) : (
          <div className="evidence-grid">
            {filteredTickets.map((ticket) => {
              const evidenceThumb = ticket.evidence_url
                ? (ticket.evidence_url.startsWith('http') ? ticket.evidence_url : `${apiUrl}${ticket.evidence_url}`)
                : null
              const receiptThumb = ticket.image_url
                ? (ticket.image_url.startsWith('http') ? ticket.image_url : `${apiUrl}${ticket.image_url}`)
                : null

              return (
                <article
                  className="evidence-card"
                  key={ticket.number}
                  onClick={() => setSelectedTicket(ticket)}
                >
                  {/* Thumbnail Banner */}
                  <div className="evidence-card-thumb">
                    {evidenceThumb ? (
                      <img src={evidenceThumb} alt={`Evidence for ${ticket.number}`} loading="lazy" />
                    ) : receiptThumb ? (
                      <div className="receipt-thumb-preview">
                        <img src={receiptThumb} alt={`Receipt for ${ticket.number}`} loading="lazy" />
                      </div>
                    ) : (
                      <div className="evidence-thumb-fallback">
                        <Camera size={32} />
                        <span>PHOTO EVIDENCE</span>
                      </div>
                    )}
                    <div className="evidence-card-badge">
                      <Camera size={12} /> PHOTO EVIDENCE
                    </div>
                    <div className="evidence-card-hover-overlay">
                      <Eye size={20} />
                      <span>Inspect Evidence</span>
                    </div>
                  </div>

                  {/* Card Body */}
                  <div className="evidence-card-body">
                    <div className="evidence-card-header">
                      <span className="evidence-card-id">{ticket.number}</span>
                      <span className={`ticket-status status-${ticket.status || 'saved'}`}>
                        {ticket.status || 'SAVED'}
                      </span>
                    </div>

                    {/* License Plate Display */}
                    <div className="card-plate-box">
                      <span className="card-plate-tag">IND</span>
                      <strong className="card-plate-text">{ticket.plate || 'UNREAD'}</strong>
                    </div>

                    {/* Violation & Location */}
                    <div className="evidence-card-meta">
                      <span className="card-violation-pill">
                        <AlertTriangle size={12} /> {ticket.violation?.replace(/_/g, ' ') || 'INFRACTION'}
                      </span>
                      <span className="card-slot-tag">BAY {ticket.slot || 'N/A'}</span>
                    </div>

                    <div className="evidence-card-time">
                      <Clock3 size={12} /> {formatDate(ticket.time)}
                    </div>
                  </div>

                  {/* Footer Action */}
                  <div className="evidence-card-footer">
                    <button
                      className="evidence-inspect-btn"
                      onClick={(e) => {
                        e.stopPropagation()
                        setSelectedTicket(ticket)
                      }}
                    >
                      <Eye size={14} /> View Evidence Record
                    </button>
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </section>

      {/* Modal Dialog */}
      {selectedTicket && (
        <EvidenceModal ticket={selectedTicket} onClose={() => setSelectedTicket(null)} />
      )}
    </main>
  )
}

export default function App() {
  const { pathname } = useLocation()
  return pathname === '/history' ? <TicketHistory /> : <Home />
}
