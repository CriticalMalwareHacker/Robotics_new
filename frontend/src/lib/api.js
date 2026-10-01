/* Backend client.
 * VITE_API_URL set    -> absolute calls (Vercel -> tunnel/Pi).
 * VITE_API_URL empty  -> same-origin relative calls (local `npm run dev`,
 *   forwarded by the vite proxy). Relative is also what defeats mixed-content
 *   blocking when the dev page is served over https.
 */

export const API_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
export const API_KEY = import.meta.env.VITE_API_KEY || ''

function authHeaders(extra = {}) {
  return API_KEY
    ? { ...extra, Authorization: `Bearer ${API_KEY}` }
    : { ...extra }
}

async function request(path, options = {}) {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: authHeaders({ 'Content-Type': 'application/json', ...(options.headers || {}) }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || `Backend error ${res.status}`)
  return data
}

/** POST detections (table coords, cm) -> ParkingAnalysis. */
export const parkingAnalyze = (detections) =>
  request('/api/parking/analyze', { method: 'POST', body: JSON.stringify({ detections }) })

/** Latest analysis + monitor state (poll every 500–1000 ms for the HUD). */
export const parkingStatus = () => request('/api/parking/status')

/** Live annotated-frame URL for <img> (Phase 5 wires the annotator). */
export const parkingFrameUrl = (t = Date.now()) => `${API_URL}/api/parking/frame?t=${t}`

/** Monitor loop control (1 Hz detect -> analyze -> debounce on the Pi). */
export const monitorStart = () =>
  request('/api/parking/monitor/start', { method: 'POST' })

export const monitorStop = () =>
  request('/api/parking/monitor/stop', { method: 'POST' })
