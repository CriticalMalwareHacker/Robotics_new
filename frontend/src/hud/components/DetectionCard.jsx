import { useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2, Printer, Play, XCircle, ShieldAlert, Sparkles, Car } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card'

export default function DetectionCard({
  vehicles = [],
  printingId,
  onPrint,
  reviewMode,
  reviewVehicles = [],
  reviewConfirmed = [],
  reviewTicketed = [],
  reviewReady = false,
  onConfirm,
  onDismiss,
  onResume,
}) {
  const [plates, setPlates] = useState({})
  const [confirmed, setConfirmed] = useState({})
  const [printed, setPrinted] = useState({})
  const [confirmingId, setConfirmingId] = useState(null)
  const reviewKey = reviewVehicles.join('|')

  useEffect(() => {
    setConfirmed({})
    setPrinted({})
  }, [reviewMode, reviewKey])

  const violations = vehicles.filter((vehicle) => vehicle.valid === false)
  const legalCount = vehicles.filter((vehicle) => vehicle.valid === true).length
  const unknownCount = vehicles.filter((vehicle) => vehicle.valid == null).length

  const print = async (vehicle) => {
    const plate = (plates[vehicle.id] ?? vehicle.plate ?? '').trim().toUpperCase()
    if (plate.length < 4) {
      toast.error('Enter valid license plate (min 4 characters) before printing.')
      return
    }
    try {
      const result = await onPrint(vehicle, plate)
      if (result?.status !== 'printed') {
        toast.error(result?.message || 'Ticket saved, but printer did not confirm. Retry before continuing.')
        return
      }
      setPrinted((current) => ({ ...current, [vehicle.id]: true }))
      toast.success(`Ticket printed for ${plate}.`)
    } catch (error) {
      toast.error(error.message || 'Could not print the ticket.')
    }
  }

  const confirm = async (vehicle) => {
    if (!reviewMode) {
      setConfirmed((current) => ({ ...current, [vehicle.id]: true }))
      return
    }
    setConfirmingId(vehicle.id)
    try {
      await onConfirm?.(vehicle)
      setConfirmed((current) => ({ ...current, [vehicle.id]: true }))
    } catch (error) {
      toast.error(error.message || 'Could not confirm this review.')
    } finally {
      setConfirmingId(null)
    }
  }

  return (
    <Card className="hud-glass-card overflow-hidden">
      <CardHeader className="p-4 pb-2 sm:p-5 sm:pb-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-red-500/10 text-red-400 border border-red-500/20">
              <ShieldAlert className="h-4 w-4" />
            </div>
            <div>
              <CardTitle className="text-base sm:text-lg font-bold tracking-tight">Violation Review</CardTitle>
              <CardDescription className="text-xs">Live parking rule enforcement queue</CardDescription>
            </div>
          </div>
          <Badge className={violations.length ? 'hud-bad font-mono text-xs px-2.5 py-1' : 'hud-ok font-mono text-xs px-2.5 py-1'}>
            {violations.length} {violations.length === 1 ? 'VIOLATION' : 'VIOLATIONS'}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="p-4 pt-2 sm:p-5 sm:pt-2 space-y-3">
        {/* Verification Gate Prompt */}
        {reviewMode && (
          <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 sm:p-3.5 backdrop-blur-md">
            <div className="flex items-center gap-2.5">
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-amber-500"></span>
              </span>
              <span className="text-xs font-semibold uppercase tracking-wider text-amber-300">
                Patrol Paused — Verification Required
              </span>
            </div>
            <p className="mt-1 text-xs text-amber-200/80 leading-relaxed">
              Robot stopped in front of potential violation. Confirm plate, issue or dismiss notice, then resume.
            </p>
          </div>
        )}

        {vehicles.length === 0 && (
          <div className="rounded-xl border border-dashed border-border/60 bg-muted/10 px-4 py-8 text-center text-sm text-muted-foreground flex flex-col items-center justify-center gap-2">
            <Car className="h-6 w-6 opacity-40" />
            <span>No vehicles detected in active camera zone.</span>
          </div>
        )}

        {vehicles.length > 0 && violations.length === 0 && legalCount === vehicles.length && (
          <div className="flex items-center gap-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3.5 text-sm text-emerald-300">
            <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-400" />
            <span>All {vehicles.length} visible {vehicles.length === 1 ? 'vehicle is' : 'vehicles are'} parked legally within marked slots.</span>
          </div>
        )}

        {unknownCount > 0 && violations.length === 0 && (
          <div className="rounded-xl border border-border/50 bg-muted/20 p-3 text-xs text-muted-foreground flex items-center gap-2">
            <Sparkles className="h-4 w-4 shrink-0 text-blue-400 animate-pulse" />
            <span>Analyzing parking alignment for {unknownCount} visible {unknownCount === 1 ? 'car' : 'cars'}…</span>
          </div>
        )}

        {violations.map((vehicle) => {
          const plate = plates[vehicle.id] ?? vehicle.plate ?? ''
          const isPrinting = printingId === vehicle.id
          const isReviewVehicle = reviewVehicles.includes(vehicle.id)
          const isConfirmed = reviewMode
            ? reviewConfirmed.includes(vehicle.id) || confirmed[vehicle.id]
            : confirmed[vehicle.id]
          const isPrinted = reviewTicketed.includes(vehicle.id) || printed[vehicle.id]

          return (
            <div
              key={vehicle.id}
              className={`rounded-xl border p-3.5 sm:p-4 transition-all duration-200 ${
                isReviewVehicle
                  ? 'border-red-500/50 bg-red-950/30 shadow-[0_0_15px_rgba(239,68,68,0.15)]'
                  : 'border-red-500/25 bg-red-950/15'
              }`}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="flex h-7 w-7 items-center justify-center rounded-md bg-red-500/20 text-red-400 font-mono font-bold text-xs shrink-0">
                    {vehicle.id.slice(-2)}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="font-semibold text-sm tracking-tight text-foreground">{vehicle.id}</span>
                      {vehicle.slot && (
                        <span className="rounded bg-muted/60 px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground border border-border/40">
                          {vehicle.slot}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-red-400/90 font-medium capitalize truncate">
                      {vehicle.violation?.replaceAll('_', ' ').toLowerCase() || 'Parking violation'}
                    </p>
                  </div>
                </div>

                {vehicle.confidence != null && (
                  <span className="font-mono text-[11px] text-muted-foreground bg-background/50 px-2 py-0.5 rounded border border-border/40">
                    {Math.round(vehicle.confidence * 100)}% conf
                  </span>
                )}
              </div>

              {/* License Plate Input and Actions */}
              <div className="mt-3 space-y-2">
                <div className="relative">
                  <input
                    aria-label={`License plate for ${vehicle.id}`}
                    autoComplete="off"
                    maxLength={16}
                    placeholder="ENTER VEHICLE PLATE"
                    value={plate}
                    onChange={(event) =>
                      setPlates((current) => ({ ...current, [vehicle.id]: event.target.value.toUpperCase() }))
                    }
                    className="h-10 w-full rounded-lg border border-border/80 bg-background/90 px-3 font-mono text-sm tracking-wider uppercase text-foreground outline-none placeholder:text-xs placeholder:font-sans placeholder:tracking-normal placeholder:text-muted-foreground focus:border-primary focus:ring-1 focus:ring-primary shadow-inner"
                  />
                  {plate.length >= 4 && (
                    <span className="absolute right-2.5 top-2.5 text-[10px] font-mono font-semibold text-emerald-400 bg-emerald-950/60 px-1.5 py-0.5 rounded border border-emerald-500/30">
                      READY
                    </span>
                  )}
                </div>

                <div className="flex flex-wrap gap-2">
                  {!isConfirmed ? (
                    <Button
                      variant="destructive"
                      className="flex-1 min-w-[140px] h-10 text-xs sm:text-sm font-semibold tracking-wide"
                      disabled={confirmingId === vehicle.id || (reviewMode && !isReviewVehicle)}
                      onClick={() => confirm(vehicle)}
                    >
                      <AlertTriangle className="mr-1.5 h-3.5 w-3.5" />
                      {confirmingId === vehicle.id ? 'Confirming…' : 'Confirm Violation'}
                    </Button>
                  ) : (
                    <Button
                      className={`flex-1 min-w-[140px] h-10 text-xs sm:text-sm font-semibold tracking-wide ${
                        isPrinted ? 'bg-emerald-600 hover:bg-emerald-700 text-white' : 'bg-primary hover:bg-primary/90'
                      }`}
                      disabled={plate.trim().length < 4 || isPrinting || isPrinted || (reviewMode && !isReviewVehicle)}
                      onClick={() => print(vehicle)}
                    >
                      <Printer className={`mr-1.5 h-3.5 w-3.5 ${isPrinting ? 'animate-pulse' : ''}`} />
                      {isPrinting ? 'Printing Citation…' : isPrinted ? 'Ticket Printed' : 'Print Citation'}
                    </Button>
                  )}

                  {reviewMode && isReviewVehicle && onDismiss && (
                    <Button
                      variant="outline"
                      className="h-10 text-xs sm:text-sm text-muted-foreground hover:text-foreground hover:bg-muted/40 border-border/60"
                      onClick={() => onDismiss(vehicle)}
                    >
                      <XCircle className="mr-1.5 h-3.5 w-3.5 text-muted-foreground" /> Dismiss
                    </Button>
                  )}
                </div>
              </div>

              <p className="mt-2 text-[11px] text-muted-foreground/80 flex items-center justify-between">
                <span>
                  {vehicle.plate && vehicle.plate_conf != null
                    ? `OCR scanned (${Math.round(vehicle.plate_conf * 100)}% match) — verify above.`
                    : 'Plate not recognized — enter manually before citation.'}
                </span>
              </p>

              {/* Resume Patrol when review is ready */}
              {reviewMode && isReviewVehicle && reviewReady && (
                <Button
                  className="mt-3 w-full h-11 bg-emerald-600 hover:bg-emerald-500 text-white font-bold tracking-wide shadow-lg shadow-emerald-950/50"
                  onClick={onResume}
                >
                  <Play className="mr-2 h-4 w-4 fill-current" /> Continue Patrol
                </Button>
              )}
            </div>
          )
        })}

        {legalCount > 0 && violations.length > 0 && (
          <p className="text-[11px] text-muted-foreground pt-1 text-center">
            {legalCount} other {legalCount === 1 ? 'vehicle' : 'vehicles'} verified legally parked.
          </p>
        )}
      </CardContent>
    </Card>
  )
}
