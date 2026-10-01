import { useEffect, useRef, useState } from 'react'
import { Layers } from 'lucide-react'
import { frameUrl, streamUrl } from '../api'
import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { Skeleton } from '../../components/ui/skeleton'
import { Switch } from '../../components/ui/switch'
import OverlayLayer from './OverlayLayer'

/* Live feed: MJPEG stream <img>, falling back to polled frames on error.
 * Overlay is client-side SVG synced by poll age (fades past 1 s). */
export default function CameraFeed({ frame, parking, fetchedAt, backendOnline, cameraOnline, onRetry }) {
  const [useStream, setUseStream] = useState(true)
  const [streamOk, setStreamOk] = useState(true)
  const [pollSrc, setPollSrc] = useState(frameUrl())
  const [showPanel, setShowPanel] = useState(false)
  const [show, setShow] = useState({ slots: true, vehicles: true, plates: true })
  const [streamSrc, setStreamSrc] = useState(streamUrl())
  const pollRef = useRef(null)

  const live = useStream && streamOk

  useEffect(() => {
    if (live) return undefined
    pollRef.current = window.setInterval(() => setPollSrc(frameUrl()), 250)
    return () => window.clearInterval(pollRef.current)
  }, [live])

  const retry = () => {
    setStreamOk(true)
    setUseStream(true)
    setStreamSrc(streamUrl())
    setPollSrc(frameUrl())
    onRetry?.()
  }

  const delayed = Date.now() - fetchedAt > 1000
  const aspect = frame?.width && frame?.height ? `${frame.width} / ${frame.height}` : '16 / 9'

  return (
    <div className="flex flex-col gap-2">
      <div className="relative overflow-hidden rounded-lg border border-border bg-black" style={{ aspectRatio: aspect }}>
        {!backendOnline && <Skeleton className="absolute inset-0 h-full w-full rounded-none" />}
        {backendOnline && !cameraOnline && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 p-6 text-center">
            <p className="text-sm text-muted-foreground">Camera not found. Check the cable, then press Retry.</p>
            <Button variant="outline" size="sm" onClick={retry}>Retry</Button>
          </div>
        )}
        {backendOnline && cameraOnline && (
          <>
            {live ? (
              <img
                src={streamSrc}
                alt="Live camera feed"
                className="absolute inset-0 h-full w-full"
                onError={() => setStreamOk(false)}
              />
            ) : (
              <img src={pollSrc} alt="Live camera feed" className="absolute inset-0 h-full w-full" onError={() => setStreamOk(false)} />
            )}
            <OverlayLayer frame={frame} parking={parking} show={show} faded={delayed} />
            {delayed && (
              <div className="absolute left-2 top-2">
                <Badge>Overlay delayed</Badge>
              </div>
            )}
            <div className="absolute right-2 top-2">
              <Button variant="outline" size="icon" aria-label="Overlay layers" onClick={() => setShowPanel((v) => !v)}>
                <Layers />
              </Button>
              {showPanel && (
                <div className="mt-1 flex flex-col gap-2 rounded-md border border-border bg-card p-3 text-sm">
                  {[['slots', 'Slots'], ['vehicles', 'Vehicles'], ['plates', 'Plates']].map(([key, label]) => (
                    <label key={key} className="flex items-center gap-2">
                      <Switch checked={show[key]} onCheckedChange={(v) => setShow((s) => ({ ...s, [key]: v }))} aria-label={`${label} layer`} />
                      {label}
                    </label>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </div>
      <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
        <span className="tnum">
          {frame?.width ? `${frame.width}×${frame.height}` : '–'}
        </span>
        <span>Checking parking</span>
      </div>
    </div>
  )
}
