import { useEffect, useState } from 'react'
import { AlertTriangle, Check, Printer, Play, XCircle } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card'

export default function DetectionCard({
  vehicles = [], printingId, onPrint, reviewMode, reviewVehicles = [],
  reviewConfirmed = [], reviewTicketed = [], reviewReady = false,
  onConfirm, onDismiss, onResume,
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
      toast.error('Enter the plate number before printing.')
      return
    }
    try {
      const result = await onPrint(vehicle, plate)
      if (result?.status !== 'printed') {
        toast.error(result?.message || 'Ticket was saved, but the printer did not confirm printing. Retry before continuing.')
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
    <Card className="overflow-hidden">
      <CardHeader className="space-y-1 pb-3">
        <div className="flex items-center justify-between gap-3">
          <CardTitle>Parking violations</CardTitle>
          <Badge className={violations.length ? 'hud-bad' : 'hud-ok'}>
            {violations.length} {violations.length === 1 ? 'vehicle' : 'vehicles'}
          </Badge>
        </div>
        <CardDescription>Visible cars currently outside the parking rules.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {vehicles.length === 0 && (
          <div className="rounded-md border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">
            No cars detected in the parking area.
          </div>
        )}
        {vehicles.length > 0 && violations.length === 0 && legalCount === vehicles.length && (
          <div className="flex items-center gap-3 rounded-md border border-border bg-muted/40 p-4 text-sm">
            <Check className="h-4 w-4 hud-ok" />
            <span>{vehicles.length} visible {vehicles.length === 1 ? 'car is' : 'cars are'} parked legally.</span>
          </div>
        )}
        {unknownCount > 0 && violations.length === 0 && (
          <div className="rounded-md border border-border bg-muted/40 p-4 text-sm text-muted-foreground">
            Parking analysis is updating for {unknownCount} visible {unknownCount === 1 ? 'car' : 'cars'}.
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
            <div key={vehicle.id} className="rounded-lg border border-destructive/30 bg-destructive/5 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4 text-destructive" />
                    <span className="font-medium">{vehicle.id}</span>
                    <Badge className="border-destructive/30 bg-destructive/10 text-destructive">Violation</Badge>
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {vehicle.violation?.replaceAll('_', ' ') || 'Parking violation'}
                    {vehicle.slot ? ` · ${vehicle.slot}` : ''}
                  </p>
                </div>
                {vehicle.confidence != null && (
                  <span className="text-xs text-muted-foreground">{Math.round(vehicle.confidence * 100)}% detection</span>
                )}
              </div>
              <div className="mt-4 flex flex-col gap-2 sm:flex-row">
                <input
                  aria-label={`License plate for ${vehicle.id}`}
                  autoComplete="off"
                  maxLength={16}
                  placeholder="Enter plate number"
                  value={plate}
                  onChange={(event) => setPlates((current) => ({ ...current, [vehicle.id]: event.target.value.toUpperCase() }))}
                  className="h-10 min-w-0 flex-1 rounded-md border border-border bg-background px-3 text-sm uppercase outline-none placeholder:normal-case placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-primary"
                />
                {!isConfirmed ? (
                  <Button variant="destructive" className="sm:min-w-40"
                    disabled={confirmingId === vehicle.id || (reviewMode && !isReviewVehicle)}
                    onClick={() => confirm(vehicle)}>
                    <AlertTriangle /> {confirmingId === vehicle.id ? 'Confirming…' : 'Confirm bad parking'}
                  </Button>
                ) : (
                  <Button className="sm:min-w-36" disabled={plate.trim().length < 4 || isPrinting || isPrinted || (reviewMode && !isReviewVehicle)} onClick={() => print(vehicle)}>
                    <Printer className={isPrinting ? 'animate-pulse' : ''} />
                    {isPrinting ? 'Printing…' : isPrinted ? 'Ticket printed' : 'Print ticket'}
                  </Button>
                )}
                {reviewMode && isReviewVehicle && onDismiss && (
                  <Button
                    variant="outline"
                    className="sm:min-w-28 text-muted-foreground hover:text-foreground"
                    onClick={() => onDismiss(vehicle)}
                  >
                    <XCircle className="h-4 w-4" /> Dismiss
                  </Button>
                )}
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                {vehicle.plate && vehicle.plate_conf != null
                  ? `OCR read ${Math.round(vehicle.plate_conf * 100)}% confidence · verify before printing.`
                  : 'Plate not read clearly · enter or correct it before printing.'}
              </p>
              {reviewMode && isReviewVehicle && reviewReady && (
                <Button className="mt-3 w-full" onClick={onResume}>
                  <Play /> Go ahead
                </Button>
              )}
            </div>
          )
        })}
        {legalCount > 0 && violations.length > 0 && (
          <p className="text-xs text-muted-foreground">
            {legalCount} other visible {legalCount === 1 ? 'car is' : 'cars are'} parked legally.
          </p>
        )}
      </CardContent>
    </Card>
  )
}
