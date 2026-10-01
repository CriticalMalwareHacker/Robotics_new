import React, { useEffect, useState } from 'react'
import { Loader2, OctagonX } from 'lucide-react'
import { toast } from 'sonner'
import { autoStart, autoStop, drive, estop, testPrint } from '../api'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
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
      if (!estopActive) run('estop', estop, 'Emergency stop active.')
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [estopActive])

  const startAuto = () => {
    if (!warnedRef.current) {
      setConfirmOpen(true)
      return
    }
    run('auto', autoStart, 'Started auto mode.')
  }

  const spin = (key) => busy === key && <Loader2 className="animate-spin" aria-hidden />

  return (
    <div className="sticky bottom-0 z-40 flex flex-wrap items-center gap-2 border-t border-border bg-background px-4 py-3">
      {driveEnabled ? (
        <Button disabled={busy != null || autoRunning} onClick={startAuto}>
          {spin('auto')} Start auto
        </Button>
      ) : (
        <Button disabled title="Controls are disabled while the Arduino is offline.">Start auto</Button>
      )}
      <Button variant="secondary" disabled={!driveEnabled || busy != null} onClick={() => run('stop', autoStop, 'Stopped. Robot is idle.')}>
        {spin('stop')} Stop
      </Button>
      <Button variant="outline" disabled={!driveEnabled || autoRunning} onClick={() => setDriveOpen(true)}>
        Manual drive
      </Button>
      <Button variant="outline" disabled={busy != null} onClick={() => run('print', testPrint, 'Ticket sent to printer.')}>
        {spin('print')} Print test
      </Button>
      <Button
        variant="destructive"
        size="lg"
        className="ml-auto"
        disabled={busy != null}
        onClick={() => run('estop', estop, 'Emergency stop active.')}
        aria-label="Emergency stop"
      >
        <OctagonX /> E-stop
      </Button>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Start auto mode?</AlertDialogTitle>
            <AlertDialogDescription>
              The robot will move on its own. Clear the table and keep a hand near the power switch.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                warnedRef.current = true
                run('auto', autoStart, 'Started auto mode.')
              }}
            >
              Start
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
