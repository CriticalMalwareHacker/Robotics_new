/* Typed HUD API client. Components never call fetch directly.
 * Empty VITE_API_URL means same-origin relative calls (local dev via the
 * vite proxy); a set value means absolute calls (Vercel -> tunnel/Pi).
 * No hardcoded hosts, no credentials in source. */
import { API_URL, API_KEY } from '../lib/api'

function headers(extra = {}) {
  return API_KEY
    ? { ...extra, Authorization: `Bearer ${API_KEY}` }
    : { ...extra }
}

async function request(path, options = {}, timeoutMs = 8000) {
  const ctrl = new AbortController()
  const timer = window.setTimeout(() => {
    ctrl.abort(new Error(`Request timed out after ${Math.round(timeoutMs / 1000)}s.`))
  }, timeoutMs)
  try {
    const res = await fetch(`${API_URL}${path}`, {
      ...options,
      signal: ctrl.signal,
      headers: headers({ 'Content-Type': 'application/json', ...(options.headers || {}) }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data.detail || `Backend error ${res.status}.`)
    return data
  } catch (err) {
    if (ctrl.signal.aborted || err.name === 'AbortError') {
      const msg = ctrl.signal.reason?.message || err.message || `Request timed out after ${Math.round(timeoutMs / 1000)}s.`
      throw new Error(msg)
    }
    throw err
  } finally {
    window.clearTimeout(timer)
  }
}

export const apiUrl = API_URL
export const getHudState = () => request('/api/hud/state')
export const streamUrl = (t = Date.now()) => `${API_URL}/api/parking/stream?t=${t}`
export const frameUrl = (t = Date.now()) => `${API_URL}/api/parking/frame?t=${t}`

export const autoStart = () => request('/api/robot/auto/start', { method: 'POST' }, 20000)
export const autoStop = () => request('/api/robot/auto/stop', { method: 'POST' }, 10000)
export const autoResume = () => request('/api/robot/auto/resume', { method: 'POST' }, 10000)
export const confirmParkingReview = (vehicleId) => request('/api/robot/review/confirm', {
  method: 'POST',
  body: JSON.stringify({ vehicle_id: vehicleId }),
})
export const dismissParkingReview = (vehicleId) => request('/api/robot/review/dismiss', {
  method: 'POST',
  body: JSON.stringify({ vehicle_id: vehicleId }),
})
export const estop = () => request('/api/robot/estop', { method: 'POST' })
export const estopClear = () => request('/api/robot/estop/clear', { method: 'POST' })
export const drive = (command, speed, durationMs) =>
  request('/api/robot/command', {
    method: 'POST',
    body: JSON.stringify({ command, speed, duration_ms: durationMs }),
  })
// Bluetooth connect can take up to 10s on the backend; allow the print job to
// finish before the browser gives up. An aborted browser request does not stop
// a ticket that the backend has already started printing.
export const testPrint = () => request('/api/ticket/test-print', { method: 'POST' }, 30000)
export const printViolation = (vehicleId, plate) => request('/api/ticket/violation', {
  method: 'POST',
  body: JSON.stringify({ vehicle_id: vehicleId, plate }),
}, 30000)
export const getTicketHistory = () => request('/api/ticket/history')
