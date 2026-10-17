import React, { useEffect, useState } from 'react'
import { Compass, Loader2, OctagonX, Play, Printer, Square } from 'lucide-react'
import { toast } from 'sonner'
import { autoStart, autoStop, drive, estop, testPrint } from '../api'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../../components/ui/alert-dialog'
import { Button } from '../../components/ui/button'

const ManualDriveSheet = React.lazy(() => import('./ManualDriveSheet'))

export default function ControlsBar({ driveEnabled, autoRunning, estopActive, onChanged }) {
  const [busy, setBusy] = useState(null)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [driveOpen, setDriveOpen] = useState(false)
  const warnedRef = React.useRef(false)

  const run = async (key, fn, okMsg) => {
    setBusy(key)
    try {
      await fn()
      toast.success(okMsg)
      onChanged?.()
    } catch (e) {
      toast.error(e.message || 'Command failed.')
    } finally {
      setBusy(null)
    }
  }

  // Space fires E-stop anywhere on the page (except while typing).
  useEffect(() => {
    const onKey = (e) => {
      if (e.code !== 'Space') return
      const tag = (e.target?.tagName || '').toLowerCase()
      if (tag === 'input' || tag === 'textarea' || e.target?.isContentEditable) return
      e.preventDefault()
      if (!estopActive) run('estop', estop, 'Emergency stop triggered!')
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [estopActive])

  const startAuto = () => {
    if (!warnedRef.current) {
      setConfirmOpen(true)
      return
    }
    run('auto', autoStart, 'Autonomous patrol engaged.')
  }

  const spin = (key) => busy === key && <Loader2 className="animate-spin mr-1.5 h-4 w-4" aria-hidden />

  return (
    <div className="hud-dock-wrapper">
      <div className="hud-dock">
        {/* Auto Patrol / Stop Toggle */}
        {autoRunning ? (
          <Button
            variant="secondary"
            className="h-11 px-3 sm:px-4 text-xs sm:text-sm font-semibold bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 border border-amber-500/40 shadow-sm"
            disabled={!driveEnabled || busy != null}
            onClick={() => run('stop', autoStop, 'Patrol halted. Robot is idle.')}
          >
            {spin('stop') || <Square className="mr-1.5 h-4 w-4 fill-current" />}
            <span>Halt Patrol</span>
          </Button>
        ) : (
          <Button
            className={`h-11 px-3 sm:px-4 text-xs sm:text-sm font-bold tracking-wide shadow-md ${
              driveEnabled
                ? 'bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white shadow-emerald-950/40'
                : 'opacity-50'
            }`}
            disabled={!driveEnabled || busy != null}
            onClick={startAuto}
            title={!driveEnabled ? 'Controls disabled: Arduino offline or E-stop active.' : 'Start autonomous parking patrol'}
          >
            {spin('auto') || <Play className="mr-1.5 h-4 w-4 fill-current" />}
            <span>Start Patrol</span>
          </Button>
        )}

        {/* Manual Steering */}
        <Button
          variant="outline"
          className="h-11 px-3 sm:px-4 text-xs sm:text-sm font-semibold border-border/80 hover:bg-primary/20 hover:text-primary transition-all"
          disabled={!driveEnabled || autoRunning}
          onClick={() => setDriveOpen(true)}
          title={autoRunning ? 'Pause auto patrol first to enable manual steering.' : 'Open manual touch controls'}
        >
          <Compass className="mr-1.5 h-4 w-4 text-cyan-400" />
          <span className="hidden xs:inline">Manual</span> Drive
        </Button>

        {/* Test Ticket Print */}
        <Button
          variant="outline"
          className="h-11 px-2.5 sm:px-3 text-xs sm:text-sm font-medium border-border/70 hover:bg-muted/40"
          disabled={busy != null}
          onClick={() => run('print', testPrint, 'Test ticket sent to thermal printer.')}
          title="Print test calibration receipt"
        >
          {spin('print') || <Printer className="h-4 w-4 text-muted-foreground sm:mr-1.5" />}
          <span className="hidden sm:inline">Test Print</span>
        </Button>

        {/* Emergency Stop — High Visibility Thumb Target */}
        <Button
          variant="destructive"
          className={`h-11 px-3.5 sm:px-5 ml-auto text-xs sm:text-sm font-black tracking-wider uppercase transition-all shadow-lg ${
            estopActive
              ? 'bg-red-600 animate-pulse text-white'
              : 'bg-red-600/90 hover:bg-red-600 text-white shadow-red-950/60'
          }`}
          disabled={busy != null}
          onClick={() => run('estop', estop, 'Emergency stop engaged!')}
          aria-label="Emergency stop"
          title="Emergency Stop (or press SPACE)"
        >
          <OctagonX className="mr-1.5 h-4 w-4 fill-current" />
          <span>E-STOP</span>
        </Button>
      </div>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent className="hud-glass-card max-w-md mx-4">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-lg font-bold flex items-center gap-2 text-foreground">
              <Play className="h-5 w-5 text-emerald-400" /> Engage Autonomous Patrol?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-sm text-muted-foreground leading-relaxed">
              ParkSensei will scan parking spots and move autonomously. Ensure obstacles are clear and keep a hand ready on E-Stop.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="gap-2 sm:gap-0">
            <AlertDialogCancel className="h-10 text-xs sm:text-sm border-border/80">Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="h-10 text-xs sm:text-sm font-bold bg-emerald-600 hover:bg-emerald-500 text-white"
              onClick={() => {
                warnedRef.current = true
                run('auto', autoStart, 'Autonomous patrol engaged.')
              }}
            >
              Start Patrol
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <React.Suspense fallback={null}>
        {driveOpen && (
          <ManualDriveSheet
            open={driveOpen}
            onOpenChange={setDriveOpen}
            disabled={!driveEnabled || autoRunning}
            send={drive}
          />
        )}
      </React.Suspense>
    </div>
  )
}
