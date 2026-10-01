import { useEffect, useState } from 'react'
import { API_URL, monitorStart, monitorStop, parkingFrameUrl, parkingStatus } from './lib/api'

/* Parking HUD: live annotated frame + violation pills. Server draws overlays,
 * so the browser needs no coordinate mapping. Polls status ~1 Hz, frame ~2 Hz. */
export default function RoboticsPanel({ onBack }) {
  const [status, setStatus] = useState(null)
  const [frameSrc, setFrameSrc] = useState(parkingFrameUrl())
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let alive = true
    const tick = async () => {
      try {
        const s = await parkingStatus()
        if (alive) { setStatus(s); setError('') }
      } catch (e) { if (alive) setError(e.message || 'Backend unreachable') }
    }
    tick()
    const t = window.setInterval(tick, 800)
    return () => { alive = false; window.clearInterval(t) }
  }, [])

  useEffect(() => {
    const t = window.setInterval(() => setFrameSrc(parkingFrameUrl()), 500)
    return () => window.clearInterval(t)
  }, [])

  const toggle = async (fn) => {
    setBusy(true)
    try { setStatus(await fn()); setError('') }
    catch (e) { setError(e.message || 'Command failed') }
    finally { setBusy(false) }
  }

  const analysis = status?.last_analysis
  const results = analysis?.results || []
  const banner = !analysis
    ? 'NO DATA'
    : analysis.parking_valid ? 'ALL LEGAL' : `VIOLATION: ${analysis.violation || '?'}`

  return (
    <div className="screen">
      <div className="top-bar">
        <button type="button" className="icon-button" onClick={onBack} aria-label="Back">×</button>
        <span className="bar-title">Parking HUD</span>
        <span className="mono" style={{ marginLeft: 'auto', fontSize: '10px' }}>
          {status ? `monitor:${status.monitor}` : '…'}
        </span>
      </div>
      <div className="center-body" style={{ gap: '8px', padding: '8px' }}>
        {!API_URL && <span className="voice-error">VITE_API_URL not set</span>}
        {error && <span className="voice-error">{error}</span>}
        <div className="camera-frame">
          <img className="camera-video" src={frameSrc} alt="Annotated parking view" style={{ transform: 'none' }} />
          <span className={analysis && !analysis.parking_valid ? 'capture-done' : 'camera-prompt'}>{banner}</span>
        </div>
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', justifyContent: 'center' }}>
          {results.length === 0 && <small style={{ color: 'var(--dim)' }}>no vehicles</small>}
          {results.map((r) => (
            <span key={r.vehicle_id} className="mono" style={{
              fontSize: '10px', padding: '2px 8px', borderRadius: '10px',
              border: '1px solid var(--border)',
              color: r.violation === 'LEGAL' ? 'var(--led-green)' : 'var(--led-red)',
            }}>
              {r.vehicle_id} · {r.slot_id || '?'} · {r.violation}
            </span>
          ))}
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button type="button" className="primary-button" disabled={busy || status?.monitor === 'running'}
            onClick={() => toggle(monitorStart)} style={{ flex: 1 }}>
            {status?.monitor === 'running' ? 'Monitoring…' : 'Start monitor'}
          </button>
          <button type="button" className="ghost-button" disabled={busy || status?.monitor !== 'running'}
            onClick={() => toggle(monitorStop)}>
            Stop
          </button>
        </div>
      </div>
    </div>
  )
}
