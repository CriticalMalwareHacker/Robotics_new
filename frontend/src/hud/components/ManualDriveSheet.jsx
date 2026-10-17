import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, Compass, Gamepad2, Octagon, Square, Zap } from 'lucide-react'
import { Button } from '../../components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '../../components/ui/sheet'
import { Slider } from '../../components/ui/slider'

const KEYS = {
  ArrowUp: 'F',
  KeyW: 'F',
  ArrowDown: 'B',
  KeyS: 'B',
  ArrowLeft: 'L',
  KeyA: 'L',
  ArrowRight: 'R',
  KeyD: 'R',
}

/* Hold-to-drive pad. Sends the command every 200 ms while pressed and always
 * sends stop on release, pointer leave, window blur, or page hide. */
export default function ManualDriveSheet({ open, onOpenChange, disabled, send }) {
  const [speed, setSpeed] = useState(120)
  const [activeCmd, setActiveCmd] = useState(null)
  const heldRef = useRef(null)
  const timerRef = useRef(null)

  const stopAll = useCallback(() => {
    heldRef.current = null
    setActiveCmd(null)
    window.clearInterval(timerRef.current)
    if (!disabled) send('S', 0, 0).catch(() => {})
  }, [disabled, send])

  const hold = useCallback(
    (cmd) => {
      if (disabled) return
      heldRef.current = cmd
      setActiveCmd(cmd)
      send(cmd, speed, 200).catch(() => {})
      window.clearInterval(timerRef.current)
      timerRef.current = window.setInterval(() => {
        if (heldRef.current) send(heldRef.current, speed, 200).catch(() => {})
      }, 200)
    },
    [disabled, send, speed]
  )

  useEffect(() => {
    const onKeyDown = (e) => {
      if (!open || e.repeat) return
      const cmd = KEYS[e.code]
      if (cmd) {
        e.preventDefault()
        hold(cmd)
      }
    }
    const onKeyUp = (e) => {
      if (KEYS[e.code]) stopAll()
    }
    const onBlur = () => stopAll()
    const onHide = () => {
      if (document.visibilityState === 'hidden') stopAll()
    }
    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)
    window.addEventListener('blur', onBlur)
    document.addEventListener('visibilitychange', onHide)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('keyup', onKeyUp)
      window.removeEventListener('blur', onBlur)
      document.removeEventListener('visibilitychange', onHide)
      window.clearInterval(timerRef.current)
    }
  }, [open, hold, stopAll])

  const speedMode = speed < 90 ? 'Creep' : speed > 150 ? 'Rapid' : 'Cruise'

  return (
    <Sheet
      open={open}
      onOpenChange={(v) => {
        if (!v) stopAll()
        onOpenChange(v)
      }}
    >
      <SheetContent className="hud-glass-card border-l border-border/80 w-full sm:max-w-md p-5 flex flex-col justify-between">
        <div>
          <SheetHeader className="pb-3 border-b border-border/50">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                <Gamepad2 className="h-4 w-4" />
              </div>
              <div>
                <SheetTitle className="text-base font-bold tracking-tight">Manual Teleoperation</SheetTitle>
                <SheetDescription className="text-xs">
                  Touch virtual D-pad or use W, A, S, D / Arrow keys
                </SheetDescription>
              </div>
            </div>
          </SheetHeader>

          {disabled && (
            <div className="mt-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-2.5 text-xs text-amber-300">
              Steering locked: Autonomous patrol is active or communication link is offline.
            </div>
          )}

          {/* D-Pad Controller */}
          <div className="my-6 flex flex-col items-center justify-center select-none touch-none">
            <div className="relative grid grid-cols-3 grid-rows-3 gap-2.5 p-3 rounded-2xl border border-border/60 bg-background/40 backdrop-blur-md shadow-2xl">
              {/* Forward */}
              <div className="col-start-2 row-start-1 flex justify-center">
                <DriveButton
                  label="Forward"
                  active={activeCmd === 'F'}
                  disabled={disabled}
                  onHold={() => hold('F')}
                  onRelease={stopAll}
                >
                  <ArrowUp className="h-6 w-6" />
                </DriveButton>
              </div>

              {/* Turn Left */}
              <div className="col-start-1 row-start-2 flex justify-center">
                <DriveButton
                  label="Turn Left"
                  active={activeCmd === 'L'}
                  disabled={disabled}
                  onHold={() => hold('L')}
                  onRelease={stopAll}
                >
                  <ArrowLeft className="h-6 w-6" />
                </DriveButton>
              </div>

              {/* Center Halt */}
              <div className="col-start-2 row-start-2 flex justify-center">
                <button
                  type="button"
                  aria-label="Stop Motors"
                  disabled={disabled}
                  onClick={stopAll}
                  className="flex h-16 w-16 items-center justify-center rounded-xl border border-border/80 bg-background/80 text-muted-foreground hover:bg-red-500/20 hover:text-red-400 active:scale-95 transition-all shadow-inner"
                >
                  <Square className="h-5 w-5 fill-current" />
                </button>
              </div>

              {/* Turn Right */}
              <div className="col-start-3 row-start-2 flex justify-center">
                <DriveButton
                  label="Turn Right"
                  active={activeCmd === 'R'}
                  disabled={disabled}
                  onHold={() => hold('R')}
                  onRelease={stopAll}
                >
                  <ArrowRight className="h-6 w-6" />
                </DriveButton>
              </div>

              {/* Reverse */}
              <div className="col-start-2 row-start-3 flex justify-center">
                <DriveButton
                  label="Reverse"
                  active={activeCmd === 'B'}
                  disabled={disabled}
                  onHold={() => hold('B')}
                  onRelease={stopAll}
                >
                  <ArrowDown className="h-6 w-6" />
                </DriveButton>
              </div>
            </div>

            <p className="mt-2 text-[11px] font-mono tracking-wider text-muted-foreground uppercase">
              {activeCmd ? `DRIVING [${activeCmd}]` : 'MOTORS IDLE'}
            </p>
          </div>

          {/* Speed & Throttle Slider */}
          <div className="rounded-xl border border-border/60 bg-background/50 p-4 space-y-3">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-foreground flex items-center gap-1.5">
                <Zap className="h-3.5 w-3.5 text-amber-400" /> Motor Throttle
              </span>
              <div className="flex items-center gap-1.5 font-mono">
                <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] uppercase font-bold text-muted-foreground">
                  {speedMode}
                </span>
                <span className="text-foreground font-bold">{speed} PWM</span>
              </div>
            </div>

            <Slider
              value={[speed]}
              min={50}
              max={200}
              step={5}
              onValueChange={([v]) => setSpeed(v)}
              aria-label="Throttle PWM"
              className="py-1"
            />

            <div className="flex justify-between text-[10px] font-mono text-muted-foreground px-1">
              <span>50 PWM</span>
              <span>120 (Standard)</span>
              <span>200 PWM</span>
            </div>
          </div>
        </div>

        {/* Footer Actions & Shortcut Info */}
        <div className="mt-4 pt-3 border-t border-border/50 space-y-2">
          <Button
            variant="secondary"
            className="w-full h-11 text-xs sm:text-sm font-semibold bg-muted hover:bg-muted/80 text-foreground"
            disabled={disabled}
            onClick={stopAll}
          >
            <Octagon className="mr-2 h-4 w-4 text-red-400" /> Stop Motors
          </Button>

          <p className="text-[11px] text-center text-muted-foreground">
            Keyboard shortcuts: <span className="font-mono text-foreground font-semibold">W A S D</span> or arrow keys.
          </p>
        </div>
      </SheetContent>
    </Sheet>
  )
}

function DriveButton({ label, active, disabled, onHold, onRelease, children }) {
  return (
    <button
      type="button"
      aria-label={label}
      disabled={disabled}
      onPointerDown={(e) => {
        e.preventDefault()
        onHold()
      }}
      onPointerUp={onRelease}
      onPointerLeave={onRelease}
      onContextMenu={(e) => e.preventDefault()}
      className={`flex h-16 w-16 items-center justify-center rounded-xl border font-bold transition-all select-none touch-none active:scale-95 shadow-md ${
        active
          ? 'border-cyan-400 bg-cyan-500 text-black shadow-[0_0_15px_rgba(6,182,212,0.6)] scale-95'
          : 'border-border/80 bg-background/90 text-foreground hover:border-cyan-500/50 hover:bg-muted/60'
      } ${disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`}
    >
      {children}
    </button>
  )
}
