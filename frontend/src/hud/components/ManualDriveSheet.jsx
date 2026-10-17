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

  const speedMode = speed < 90 ? 'Precision' : speed > 150 ? 'Rapid' : 'Cruise'

  return (
    <Sheet
      open={open}
      onOpenChange={(v) => {
        if (!v) stopAll()
        onOpenChange(v)
      }}
    >
      <SheetContent
        side="responsive"
        className="hud-glass-card border-border/80 w-full sm:max-w-md p-4 sm:p-5 flex flex-col justify-between"
      >
        <div>
          {/* Header */}
          <SheetHeader className="pb-2.5 border-b border-border/50">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                <Gamepad2 className="h-4 w-4" />
              </div>
              <div>
                <SheetTitle className="text-base font-bold tracking-tight">Manual Drive Control</SheetTitle>
                <SheetDescription className="text-xs">
                  Press and hold buttons or use WASD / Arrow keys. Release to stop.
                </SheetDescription>
              </div>
            </div>
          </SheetHeader>

          {disabled && (
            <div className="mt-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-2.5 text-xs text-amber-300">
              Steering locked: Autonomous patrol is active or communication link is offline.
            </div>
          )}

          {/* Symmetrical Diamond D-Pad */}
          <div className="my-5 flex flex-col items-center justify-center select-none touch-none">
            <div className="relative grid grid-cols-3 grid-rows-3 gap-2 sm:gap-3 p-3 sm:p-4 rounded-2xl border border-border/70 bg-black/40 backdrop-blur-md shadow-2xl">
              {/* Row 1: Forward Button (Center) */}
              <div className="col-start-2 row-start-1 flex justify-center">
                <DrivePadButton
                  cmd="F"
                  label="Forward"
                  shortcut="W / ↑"
                  active={activeCmd === 'F'}
                  disabled={disabled}
                  onHold={() => hold('F')}
                  onRelease={stopAll}
                >
                  <ArrowUp className="h-7 w-7" />
                </DrivePadButton>
              </div>

              {/* Row 2, Col 1: Turn Left */}
              <div className="col-start-1 row-start-2 flex justify-center">
                <DrivePadButton
                  cmd="L"
                  label="Left"
                  shortcut="A / ←"
                  active={activeCmd === 'L'}
                  disabled={disabled}
                  onHold={() => hold('L')}
                  onRelease={stopAll}
                >
                  <ArrowLeft className="h-7 w-7" />
                </DrivePadButton>
              </div>

              {/* Row 2, Col 2: Center STOP */}
              <div className="col-start-2 row-start-2 flex justify-center">
                <button
                  type="button"
                  aria-label="Halt Motors"
                  disabled={disabled}
                  onClick={stopAll}
                  className="flex h-16 w-16 sm:h-20 sm:w-20 flex-col items-center justify-center rounded-xl border border-red-500/40 bg-red-950/30 text-red-400 hover:bg-red-900/50 hover:text-white active:scale-95 transition-all shadow-inner font-mono text-[10px] font-bold"
                >
                  <Square className="h-5 w-5 sm:h-6 sm:w-6 fill-current mb-0.5" />
                  <span>STOP</span>
                </button>
              </div>

              {/* Row 2, Col 3: Turn Right */}
              <div className="col-start-3 row-start-2 flex justify-center">
                <DrivePadButton
                  cmd="R"
                  label="Right"
                  shortcut="D / →"
                  active={activeCmd === 'R'}
                  disabled={disabled}
                  onHold={() => hold('R')}
                  onRelease={stopAll}
                >
                  <ArrowRight className="h-7 w-7" />
                </DrivePadButton>
              </div>

              {/* Row 3: Reverse Button (Center) */}
              <div className="col-start-2 row-start-3 flex justify-center">
                <DrivePadButton
                  cmd="B"
                  label="Reverse"
                  shortcut="S / ↓"
                  active={activeCmd === 'B'}
                  disabled={disabled}
                  onHold={() => hold('B')}
                  onRelease={stopAll}
                >
                  <ArrowDown className="h-7 w-7" />
                </DrivePadButton>
              </div>
            </div>

            {/* Active Telemetry Badge */}
            <div className="mt-2.5 flex items-center gap-2">
              <span
                className={`inline-block size-2 rounded-full ${
                  activeCmd ? 'bg-cyan-400 shadow-[0_0_8px_#22d3ee]' : 'bg-muted-foreground/40'
                }`}
              />
              <span className="font-mono text-xs tracking-wider text-muted-foreground uppercase">
                {activeCmd ? `DRIVING [${activeCmd}] — ${speed} PWM` : 'MOTORS STANDBY'}
              </span>
            </div>
          </div>

          {/* Speed & Throttle Slider */}
          <div className="rounded-xl border border-border/60 bg-background/50 p-3.5 sm:p-4 space-y-2.5">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-foreground flex items-center gap-1.5">
                <Zap className="h-3.5 w-3.5 text-amber-400" /> Drive Speed (PWM)
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

            {/* Quick preset buttons */}
            <div className="flex gap-2 pt-1">
              {[80, 120, 160].map((preset) => (
                <button
                  key={preset}
                  type="button"
                  onClick={() => setSpeed(preset)}
                  className={`flex-1 rounded-md py-1 text-[11px] font-mono border transition-all ${
                    speed === preset
                      ? 'border-cyan-400 bg-cyan-950/50 text-cyan-300 font-bold'
                      : 'border-border/60 bg-background/40 text-muted-foreground hover:bg-muted/40'
                  }`}
                >
                  {preset} PWM
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Footer Actions & Shortcut Info */}
        <div className="mt-3 pt-3 border-t border-border/50 space-y-2">
          <Button
            variant="secondary"
            className="w-full h-10 text-xs sm:text-sm font-semibold bg-muted hover:bg-muted/80 text-foreground"
            disabled={disabled}
            onClick={stopAll}
          >
            <Octagon className="mr-2 h-4 w-4 text-red-400" /> Emergency Halt
          </Button>

          <p className="text-[11px] text-center text-muted-foreground">
            Desktop shortcuts: <span className="font-mono text-foreground font-semibold">W A S D</span> or arrow keys.
          </p>
        </div>
      </SheetContent>
    </Sheet>
  )
}

function DrivePadButton({ cmd, label, shortcut, active, disabled, onHold, onRelease, children }) {
  return (
    <button
      type="button"
      aria-label={`${label} (${shortcut})`}
      disabled={disabled}
      onPointerDown={(e) => {
        e.preventDefault()
        onHold()
      }}
      onPointerUp={onRelease}
      onPointerLeave={onRelease}
      onContextMenu={(e) => e.preventDefault()}
      className={`flex h-16 w-16 sm:h-20 sm:w-20 flex-col items-center justify-center rounded-xl border transition-all select-none touch-none active:scale-95 shadow-md ${
        active
          ? 'border-cyan-400 bg-cyan-500 text-black shadow-[0_0_20px_rgba(6,182,212,0.7)] scale-95'
          : 'border-border/80 bg-background/90 text-foreground hover:border-cyan-500/60 hover:bg-muted/50'
      } ${disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`}
    >
      {children}
      <span className="mt-1 font-mono text-[9px] tracking-wider uppercase opacity-75 font-semibold">
        {label}
      </span>
    </button>
  )
}
