/* Typed HUD API client. Components never call fetch directly.
 * Base URL + key come from build-time env (VITE_API_URL, VITE_API_KEY);
 * no hardcoded hosts, no credentials in source. */
import { API_URL, API_KEY } from '../lib/api'

function headers(extra = {}) {
  return API_KEY
    ? { ...extra, Authorization: `Bearer ${API_KEY}` }
    : { ...extra }
}

async function request(path, options = {}) {
  if (!API_URL) throw new Error('Backend address is not set.')
  const ctrl = new AbortController()
  const timer = window.setTimeout(() => ctrl.abort(), 8000)
  try {
    const res = await fetch(`${API_URL}${path}`, {
      ...options,
      signal: ctrl.signal,
      headers: headers({ 'Content-Type': 'application/json', ...(options.headers || {}) }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data.detail || `Backend error ${res.status}.`)
    return data
  } finally {
    window.clearTimeout(timer)
  }
}

export const apiUrl = API_URL
export const getHudState = () => request('/api/hud/state')
export const streamUrl = (t = Date.now()) => `${API_URL}/api/parking/stream?t=${t}`
export const frameUrl = (t = Date.now()) => `${API_URL}/api/parking/frame?t=${t}`

export const autoStart = () => request('/api/robot/auto/start', { method: 'POST' })
export const autoStop = () => request('/api/robot/auto/stop', { method: 'POST' })
export const estop = () => request('/api/robot/estop', { method: 'POST' })
export const estopClear = () => request('/api/robot/estop/clear', { method: 'POST' })
export const drive = (command, speed, durationMs) =>
  request('/api/robot/command', {
    method: 'POST',
    body: JSON.stringify({ command, speed, duration_ms: durationMs }),
  })
export const testPrint = () => request('/api/ticket/test-print', { method: 'POST' })
