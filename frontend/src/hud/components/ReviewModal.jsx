import { useEffect, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  Play,
  Printer,
  ShieldAlert,
  XCircle,
  Car,
} from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog'

export default function ReviewModal({
  open,
  onOpenChange,
  vehicles = [],
  reviewVehicles = [],
  reviewConfirmed = [],
  reviewTicketed = [],
  reviewDismissed = [],
  reviewReady = false,
  printingId,
  onConfirm,
  onPrint,
  onDismiss,
  onResume,
}) {
  const [plates, setPlates] = useState({})
  const [confirmingId, setConfirmingId] = useState(null)

  // Vehicles currently flagged for review
  const reviewTargets = vehicles.filter((v) => reviewVehicles.includes(v.id))
  const displayVehicles = reviewTargets.length > 0 ? reviewTargets : vehicles.slice(0, 1)

  const handlePrint = async (vehicle) => {
    const plate = (plates[vehicle.id] ?? vehicle.plate ?? '').trim().toUpperCase()
    if (plate.length < 4) {
      toast.error('Enter valid license plate (min 4 characters) before printing.')
      return
    }
    try {
      const result = await onPrint(vehicle, plate)
      if (result?.status !== 'printed') {
        toast.error(
          result?.message || 'Ticket saved, but printer did not confirm. Retry before continuing.'
        )
        return
      }
      toast.success(`Citation printed for ${plate}.`)
    } catch (error) {
      toast.error(error.message || 'Could not print the ticket.')
    }
  }

  const handleConfirm = async (vehicle) => {
    setConfirmingId(vehicle.id)
    try {
      await onConfirm?.(vehicle)
      toast.success(`Violation confirmed for ${vehicle.id}.`)
    } catch (error) {
      toast.error(error.message || 'Could not confirm this review.')
    } finally {
      setConfirmingId(null)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="hud-glass-card max-w-lg border border-amber-500/40 bg-neutral-950/95 p-5 sm:p-6 text-foreground shadow-[0_0_50px_rgba(245,158,11,0.25)]">
        <DialogHeader className="space-y-1.5 border-b border-border/50 pb-3">
          <div className="flex items-center gap-2">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-amber-500"></span>
            </span>
            <span className="font-mono text-xs font-bold tracking-wider uppercase text-amber-400">
              Human Verification Gate
            </span>
          </div>
          <DialogTitle className="text-lg sm:text-xl font-bold tracking-tight text-white flex items-center gap-2">
            <ShieldAlert className="h-5 w-5 text-amber-400 shrink-0" />
            Parking Enforcement Approval
          </DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground leading-relaxed">
            Autonomous patrol has halted at this vehicle. Verify the violation, correct the plate if needed, and choose to cite or dismiss.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 my-2 max-h-[60vh] overflow-y-auto pr-1">
          {displayVehicles.map((vehicle) => {
            const plate = plates[vehicle.id] ?? vehicle.plate ?? ''
            const isConfirmed = reviewConfirmed.includes(vehicle.id)
            const isPrinted = reviewTicketed.includes(vehicle.id)
            const isDismissed = reviewDismissed.includes(vehicle.id)
            const isPrinting = printingId === vehicle.id

            return (
              <div
                key={vehicle.id}
                className="rounded-xl border border-red-500/30 bg-red-950/20 p-4 space-y-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-red-500/20 text-red-400 font-mono font-bold text-xs shrink-0">
                      <Car className="h-4 w-4" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-sm tracking-tight text-white">
                          {vehicle.id}
                        </span>
                        {vehicle.slot && (
                          <Badge variant="outline" className="font-mono text-[10px] text-cyan-400 border-cyan-500/30 bg-cyan-950/40">
                            {vehicle.slot}
                          </Badge>
                        )}
                      </div>
                      <p className="text-xs font-semibold text-red-400 capitalize">
                        {vehicle.violation?.replaceAll('_', ' ').toLowerCase() || 'Parking Violation'}
                      </p>
                    </div>
                  </div>

                  <Badge
                    className={`font-mono text-[10px] px-2 py-0.5 ${
                      isDismissed
                        ? 'bg-neutral-800 text-neutral-400'
                        : isPrinted
                        ? 'bg-emerald-950 text-emerald-400 border border-emerald-500/30'
                        : isConfirmed
                        ? 'bg-amber-950 text-amber-400 border border-amber-500/30'
                        : 'bg-red-950 text-red-400 border border-red-500/30'
                    }`}
                  >
                    {isDismissed
                      ? 'DISMISSED'
                      : isPrinted
                      ? 'TICKET PRINTED'
                      : isConfirmed
                      ? 'CONFIRMED'
                      : 'NEEDS APPROVAL'}
                  </Badge>
                </div>

                {/* License Plate Input */}
                <div className="space-y-1.5">
                  <label className="text-[11px] font-semibold tracking-wider text-muted-foreground uppercase flex items-center justify-between">
                    <span>License Plate Number</span>
                    {vehicle.plate && (
                      <span className="text-[10px] text-emerald-400 font-mono">
                        OCR {Math.round((vehicle.plate_conf || 0.9) * 100)}% match
                      </span>
                    )}
                  </label>
                  <div className="relative">
                    <input
                      aria-label={`License plate for ${vehicle.id}`}
                      autoComplete="off"
                      maxLength={16}
                      placeholder="ENTER VEHICLE PLATE"
                      value={plate}
                      onChange={(e) =>
                        setPlates((prev) => ({ ...prev, [vehicle.id]: e.target.value.toUpperCase() }))
                      }
                      className="h-11 w-full rounded-lg border border-border/80 bg-black/60 px-3.5 font-mono text-sm tracking-widest uppercase text-emerald-400 outline-none placeholder:text-xs placeholder:font-sans placeholder:tracking-normal placeholder:text-muted-foreground focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400 shadow-inner"
                    />
                    {plate.length >= 4 && (
                      <span className="absolute right-3 top-3 text-[10px] font-mono font-bold text-emerald-400 bg-emerald-950/80 px-1.5 py-0.5 rounded border border-emerald-500/40">
                        VALID
                      </span>
                    )}
                  </div>
                </div>

                {/* Enforcement Action Buttons */}
                <div className="flex flex-wrap gap-2 pt-1">
                  {!isConfirmed && !isDismissed ? (
                    <Button
                      variant="destructive"
                      className="flex-1 min-w-[140px] h-10 text-xs sm:text-sm font-semibold tracking-wide bg-red-600 hover:bg-red-500 text-white"
                      disabled={confirmingId === vehicle.id}
                      onClick={() => handleConfirm(vehicle)}
                    >
                      <AlertTriangle className="mr-1.5 h-3.5 w-3.5" />
                      {confirmingId === vehicle.id ? 'Confirming…' : 'Confirm Violation'}
                    </Button>
                  ) : !isPrinted && !isDismissed ? (
                    <Button
                      className="flex-1 min-w-[140px] h-10 text-xs sm:text-sm font-semibold tracking-wide bg-cyan-600 hover:bg-cyan-500 text-white shadow-lg shadow-cyan-950/40"
                      disabled={plate.trim().length < 4 || isPrinting}
                      onClick={() => handlePrint(vehicle)}
                    >
                      <Printer className={`mr-1.5 h-3.5 w-3.5 ${isPrinting ? 'animate-pulse' : ''}`} />
                      {isPrinting ? 'Printing Citation…' : 'Print Citation Ticket'}
                    </Button>
                  ) : null}

                  {!isDismissed && (
                    <Button
                      variant="outline"
                      className="h-10 text-xs sm:text-sm text-muted-foreground hover:text-white border-border/60 hover:bg-muted/40"
                      onClick={() => onDismiss(vehicle)}
                    >
                      <XCircle className="mr-1.5 h-3.5 w-3.5 text-muted-foreground" />
                      Dismiss
                    </Button>
                  )}
                </div>
              </div>
            )
          })}
        </div>

        {/* Resume Patrol Button */}
        <div className="pt-2 border-t border-border/50">
          <Button
            className={`w-full h-11 text-xs sm:text-sm font-bold tracking-wide transition-all ${
              reviewReady
                ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-950/60'
                : 'bg-muted/60 text-muted-foreground hover:bg-muted'
            }`}
            onClick={() => {
              onResume?.()
              onOpenChange(false)
            }}
          >
            <Play className="mr-2 h-4 w-4 fill-current" />
            {reviewReady ? 'Resume Autonomous Patrol' : 'Bypass & Continue Patrol'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
