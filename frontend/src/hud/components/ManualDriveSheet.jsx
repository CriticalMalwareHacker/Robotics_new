import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, Square } from 'lucide-react'
import { Button } from '../../components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '../../components/ui/sheet'
import { Slider } from '../../components/ui/slider'

const KEYS = { ArrowUp: 'F', KeyW: 'F', ArrowDown: 'B', KeyS: 'B', ArrowLeft: 'L', KeyA: 'L', ArrowRight: 'R', KeyD: 'R' }

/* Hold-to-drive pad. Sends the command every 200 ms while pressed and always
 * sends stop on release, pointer leave, window blur, or page hide. */
export default function ManualDriveSheet({ open, onOpenChange, disabled, send }) {
  const [speed, setSpeed] = useState(120)
  const heldRef = useRef(null)
  const timerRef = useRef(null)

  const stopAll = useCallback(() => {
    heldRef.current = null
    window.clearInterval(timerRef.current)
    if (!disabled) send('S', 0, 0).catch(() => {})
  }, [disabled, send])

  const hold = useCallback((cmd) => {
    if (disabled) return
    heldRef.current = cmd
    send(cmd, speed, 200).catch(() => {})
    window.clearInterval(timerRef.current)
    timerRef.current = window.setInterval(() => {
      if (heldRef.current) send(heldRef.current, speed, 200).catch(() => {})
    }, 200)
  }, [disabled, send, speed])

  useEffect(() => {
    const onKeyDown = (e) => {
      if (!open || e.repeat) return
      const cmd = KEYS[e.code]
      if (cmd) { e.preventDefault(); hold(cmd) }
    }
    const onKeyUp = (e) => { if (KEYS[e.code]) stopAll() }
    const onBlur = () => stopAll()
    const onHide = () => { if (document.visibilityState === 'hidden') stopAll() }
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

  const pad = [
    { cmd: 'F', Icon: ArrowUp, label: 'Forward' },
    { cmd: 'L', Icon: ArrowLeft, label: 'Turn left' },
    { cmd: 'R', Icon: ArrowRight, label: 'Turn right' },
    { cmd: 'B', Icon: ArrowDown, label: 'Reverse' },
  ]

  return (
    <Sheet open={open} onOpenChange={(v) => { if (!v) stopAll(); onOpenChange(v) }}>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>Manual drive</SheetTitle>
          <SheetDescription>Hold a button or use arrow keys / WASD. Release to stop.</SheetDescription>
        </SheetHeader>
        {disabled && <p className="text-sm text-muted-foreground">Disabled while auto mode is running or the link is down.</p>}
        <div className="grid grid-cols-3 gap-2">
          <span />
          {pad.slice(0, 1).map(({ cmd, Icon, label }) => (
            <DriveButton key={cmd} label={label} disabled={disabled} onHold={() => hold(cmd)} onRelease={stopAll}><Icon /></DriveButton>
          ))}
          <span />
          {pad.slice(1, 3).map(({ cmd, Icon, label }) => (
            <DriveButton key={cmd} label={label} disabled={disabled} onHold={() => hold(cmd)} onRelease={stopAll}><Icon /></DriveButton>
          ))}
          <span />
          <span />
          {pad.slice(3).map(({ cmd, Icon, label }) => (
            <DriveButton key={cmd} label={label} disabled={disabled} onHold={() => hold(cmd)} onRelease={stopAll}><Icon /></DriveButton>
          ))}
          <span />
        </div>
        <div className="flex flex-col gap-2">
          <div className="flex items-baseline justify-between text-sm">
            <span className="font-medium">Speed</span>
            <span className="tnum text-muted-foreground">{speed} PWM</span>
          </div>
          <Slider value={[speed]} min={50} max={200} step={5} onValueChange={([v]) => setSpeed(v)} aria-label="Speed" />
        </div>
        <Button variant="secondary" disabled={disabled} onClick={stopAll}>
          <Square /> Stop
        </Button>
      </SheetContent>
    </Sheet>
  )
}

function DriveButton({ label, disabled, onHold, onRelease, children }) {
  return (
    <Button
      variant="outline"
      size="lg"
      aria-label={label}
      disabled={disabled}
      onPointerDown={(e) => { e.preventDefault(); onHold() }}
      onPointerUp={onRelease}
      onPointerLeave={onRelease}
      onContextMenu={(e) => e.preventDefault()}
    >
      {children}
    </Button>
  )
}
