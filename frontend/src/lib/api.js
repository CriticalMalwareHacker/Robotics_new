/* Remote-backend client for the deployed frontend.
 * Build-time config (Vite bakes VITE_* vars at `npm run build`, so rebuild
 * after changing them on your host):
 *   VITE_API_URL  e.g. https://printsensei.<tunnel>.trycloudflare.com
 *   VITE_API_KEY  same token as the Pi's API_KEY (empty = open dev backend)
 */

export const API_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
export const API_KEY = import.meta.env.VITE_API_KEY || ''

function authHeaders(extra = {}) {
  return API_KEY
    ? { ...extra, Authorization: `Bearer ${API_KEY}` }
    : { ...extra }
}

async function request(path, options = {}) {
  if (!API_URL) throw new Error('VITE_API_URL is not set — point it at the Pi backend.')
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
