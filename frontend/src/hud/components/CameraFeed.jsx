import { useEffect, useRef, useState } from 'react'
import { Layers, RefreshCw, Video, VideoOff, Eye, EyeOff } from 'lucide-react'
import { frameUrl, streamUrl } from '../api'
import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { Skeleton } from '../../components/ui/skeleton'
import { Switch } from '../../components/ui/switch'
import OverlayLayer from './OverlayLayer'

export default function CameraFeed({ frame, parking, fetchedAt, backendOnline, cameraState, onRetry }) {
  const cameraOnline = cameraState === 'ok'
  const cameraDegraded = cameraState === 'degraded'
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
  const maxWidth = frame?.width && frame?.height
    ? `${60 * frame.width / frame.height}vh`
    : undefined

  return (
    <div className="flex flex-col gap-2">
      <div
        className="relative mx-auto w-full overflow-hidden rounded-2xl border border-border/80 bg-black shadow-2xl shadow-black/60 transition-all"
        style={{
          aspectRatio: aspect,
          maxHeight: '44vh',
          ...(maxWidth ? { maxWidth } : {}),
        }}
      >
        {!backendOnline && <Skeleton className="absolute inset-0 h-full w-full rounded-none bg-muted/20" />}

        {backendOnline && !cameraOnline && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 p-6 text-center bg-gradient-to-b from-card/80 to-background/90 backdrop-blur-md">
            <div className="w-12 h-12 rounded-2xl bg-destructive/10 border border-destructive/20 flex items-center justify-center text-destructive">
              <VideoOff className="w-6 h-6" />
            </div>
            <p className="max-w-md text-sm text-muted-foreground leading-relaxed">
              {cameraDegraded
                ? 'Camera stream is active but black. Check lens cover or background apps.'
                : 'Camera feed unavailable. Connect USB camera and retry.'}
            </p>
            <Button variant="outline" size="sm" onClick={retry} className="gap-2 rounded-lg border-border/80 hover:bg-primary hover:text-white transition-colors">
              <RefreshCw className="w-3.5 h-3.5" /> Reconnect Camera
            </Button>
          </div>
        )}

        {backendOnline && cameraOnline && (
          <>
            {live ? (
              <img
                src={streamSrc}
                alt="Live camera feed"
                className="absolute inset-0 h-full w-full object-contain"
                onError={() => setStreamOk(false)}
              />
            ) : (
              <img
                src={pollSrc}
                alt="Polled camera feed"
                className="absolute inset-0 h-full w-full object-contain"
                onError={() => setStreamOk(false)}
              />
            )}

            <OverlayLayer frame={frame} parking={parking} show={show} faded={delayed} />

            {/* Tactical Cyber Corner Reticles */}
            <div className="pointer-events-none absolute inset-2 border border-white/5 rounded-xl">
              <div className="absolute top-0 left-0 w-3 h-3 border-t-2 border-l-2 border-primary/60 rounded-tl-sm" />
              <div className="absolute top-0 right-0 w-3 h-3 border-t-2 border-r-2 border-primary/60 rounded-tr-sm" />
              <div className="absolute bottom-0 left-0 w-3 h-3 border-b-2 border-l-2 border-primary/60 rounded-bl-sm" />
              <div className="absolute bottom-0 right-0 w-3 h-3 border-b-2 border-r-2 border-primary/60 rounded-br-sm" />
            </div>

            {/* Top Left Status Overlay */}
            <div className="absolute left-3 top-3 flex items-center gap-2">
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-black/60 backdrop-blur-md border border-white/10 text-[10px] font-bold text-white uppercase tracking-wider">
                <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                <span>LIVE</span>
                <span className="text-white/40">|</span>
                <span className="text-white/80 tnum">{frame?.width ? `${frame.width}p` : 'HD'}</span>
              </div>
              {delayed && (
                <span className="px-2 py-0.5 rounded-full bg-amber-500/20 border border-amber-500/40 text-[10px] font-semibold text-amber-400">
                  Syncing…
                </span>
              )}
            </div>

            {/* Top Right Layers Dropdown */}
            <div className="absolute right-3 top-3">
              <Button
                variant="outline"
                size="icon"
                aria-label="Toggle camera overlay layers"
                className="h-8 w-8 rounded-lg bg-black/60 backdrop-blur-md border-white/10 text-white hover:bg-black/80 hover:text-white shadow-lg"
                onClick={() => setShowPanel((v) => !v)}
              >
                <Layers className="w-4 h-4" />
              </Button>

              {showPanel && (
                <div className="absolute right-0 mt-2 w-40 flex flex-col gap-2 rounded-xl border border-white/10 bg-card/95 backdrop-blur-xl p-3 text-xs shadow-2xl z-20">
                  <span className="font-semibold text-foreground/80 text-[11px] uppercase tracking-wider">Overlays</span>
                  {[['slots', 'Parking Bays'], ['vehicles', 'Vehicles'], ['plates', 'Plates']].map(([key, label]) => (
                    <label key={key} className="flex items-center justify-between gap-2 cursor-pointer py-0.5">
                      <span className="text-muted-foreground">{label}</span>
                      <Switch
                        checked={show[key]}
                        onCheckedChange={(v) => setShow((s) => ({ ...s, [key]: v }))}
                        aria-label={`${label} layer`}
                      />
                    </label>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* Sub-bar Information */}
      <div className="flex items-center justify-between px-1 text-[11px] text-muted-foreground">
        <span className="tnum font-medium flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
          {frame?.width ? `${frame.width}×${frame.height}px` : 'Camera Ready'}
        </span>
        <span className="font-medium">Vision Monitor Active</span>
      </div>
    </div>
  )
}
