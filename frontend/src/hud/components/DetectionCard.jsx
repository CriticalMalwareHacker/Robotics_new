import { Badge } from '../../components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card'
import { Progress } from '../../components/ui/progress'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs'

function Row({ label, children }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1 text-sm">
      <span className="font-medium text-muted-foreground">{label}</span>
      <span className="text-right">{children}</span>
    </div>
  )
}

const dash = <span className="text-muted-foreground">–</span>

export default function DetectionCard({ vehicles }) {
  const list = vehicles || []
  const v = list[0]
  return (
    <Card>
      <CardHeader>
        <CardTitle>Latest detection</CardTitle>
      </CardHeader>
      <CardContent>
        {!v && <p className="text-sm text-muted-foreground">No vehicle in view. Place a test car on the mat.</p>}
        {v && (
          <Tabs defaultValue="details">
            <TabsList aria-label="Detection views">
              <TabsTrigger value="details">Details</TabsTrigger>
              <TabsTrigger value="crops">Crops</TabsTrigger>
            </TabsList>
            <TabsContent value="details">
              <Row label="Vehicle">{v.id || dash}</Row>
              <Row label="Slot">{v.slot || dash}</Row>
              <Row label="Status">
                {v.valid == null ? dash : v.valid
                  ? <Badge dotClassName="hud-dot-ok" className="hud-ok">Legal</Badge>
                  : <Badge dotClassName="hud-dot-bad" className="hud-bad">Violation</Badge>}
              </Row>
              <Row label="Plate">{v.plate || dash}</Row>
              <Row label="Confidence">
                {v.confidence == null
                  ? dash
                  : <span className="tnum">{Math.round(v.confidence * 100)}%</span>}
              </Row>
              <Row label="Violation type">{v.violation || dash}</Row>
              {v.confidence != null && <Progress className="mt-2" value={Math.round(v.confidence * 100)} aria-label="Confidence" />}
              {list.length > 1 && (
                <p className="mt-2 text-xs text-muted-foreground">+{list.length - 1} more vehicle{list.length > 2 ? 's' : ''} in view.</p>
              )}
            </TabsContent>
            <TabsContent value="crops">
              <p className="text-sm text-muted-foreground">Car and plate crops appear here once the plate reader lands.</p>
            </TabsContent>
          </Tabs>
        )}
      </CardContent>
    </Card>
  )
}
