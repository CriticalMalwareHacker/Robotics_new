import { useState } from 'react'
import { AlertTriangle, Check, Printer } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card'

export default function DetectionCard({ vehicles = [], printingId, onPrint }) {
  const [plates, setPlates] = useState({})
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
      await onPrint(vehicle, plate)
      toast.success(`Ticket sent for ${plate}.`)
    } catch (error) {
      toast.error(error.message || 'Could not print the ticket.')
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
                <Button className="sm:min-w-36" disabled={plate.trim().length < 4 || isPrinting} onClick={() => print(vehicle)}>
                  <Printer className={isPrinting ? 'animate-pulse' : ''} />
                  {isPrinting ? 'Printing…' : 'Print ticket'}
                </Button>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                {vehicle.plate && vehicle.plate_conf != null
                  ? `OCR read ${Math.round(vehicle.plate_conf * 100)}% confidence · verify before printing.`
                  : 'Plate not read clearly · enter or correct it before printing.'}
              </p>
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
