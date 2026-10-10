import { useCallback, useEffect, useRef, useState } from 'react'
import { getHudState } from './api'

/* Owns HUD polling. Exposes {state, connection, error, refresh}.
 * Pauses when the tab is hidden, fetches immediately when visible again. */
export function useHudState(intervalMs = 1500) {
  const [state, setState] = useState(null)
  const [connection, setConnection] = useState('connecting') // connecting | ok | offline
  const [error, setError] = useState('')
  const [fetchedAt, setFetchedAt] = useState(0)
  const timerRef = useRef(null)
  const requestInFlight = useRef(false)

  const refresh = useCallback(async () => {
    if (requestInFlight.current) return
    requestInFlight.current = true
    try {
      const s = await getHudState()
      setState(s)
      setFetchedAt(Date.now())
      setConnection('ok')
      setError('')
    } catch (e) {
      setConnection('offline')
      setError(e.name === 'AbortError' ? 'Request timed out.' : (e.message || 'Backend unreachable.'))
    } finally {
      requestInFlight.current = false
    }
  }, [])

  useEffect(() => {
    let alive = true
    const tick = () => { if (alive && document.visibilityState === 'visible') refresh() }
    tick()
    timerRef.current = window.setInterval(tick, intervalMs)
    const onVisible = () => { if (document.visibilityState === 'visible') refresh() }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      alive = false
      window.clearInterval(timerRef.current)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [intervalMs, refresh])

  return { state, connection, error, refresh, fetchedAt }
}
