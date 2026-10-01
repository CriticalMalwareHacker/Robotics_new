import { useEffect, useState } from 'react'
import { Toaster } from 'sonner'
import { estopClear, testPrint } from './api'
import { useHudState } from './useHudState'
import CameraFeed from './components/CameraFeed'
import ControlsBar from './components/ControlsBar'
import DetectionCard from './components/DetectionCard'
import EstopBanner from './components/EstopBanner'
import EventLog from './components/EventLog'
import StateCard from './components/StateCard'
import TicketCard from './components/TicketCard'
import TopBar from './components/TopBar'
import './hud.css'

function themeInitial() {
  try {
    return window.localStorage.getItem('hud-theme') || 'dark'
  } catch {
    return 'dark'
  }
}

export default function HudPage() {
  const [theme, setTheme] = useState(themeInitial)
  const { state, connection, error, refresh, fetchedAt } = useHudState(500)
  const [clearing, setClearing] = useState(false)
  const [printing, setPrinting] = useState(false)

  const toggleTheme = () => {
    setTheme((t) => {
      const next = t === 'dark' ? 'light' : 'dark'
      try { window.localStorage.setItem('hud-theme', next) } catch { /* private mode */ }
      return next
    })
  }

  const clearEstop = async () => {
    setClearing(true)
    try { await estopClear(); refresh() } catch { /* toast comes from banner action */ }
    finally { setClearing(false) }
  }

  const online = connection === 'ok'
  const robot = state?.robot
  const parking = state?.parking
  const vehicles = parking?.vehicles || []
  const driveEnabled = online && !robot?.estop && robot?.link !== 'offline'
  const hasViolation = vehicles.some((v) => v.valid === false)

  useEffect(() => { document.title = 'PrintSensei robot HUD' }, [])

  return (
    <div className={`hud-root ${theme}`}>
      <Toaster position="bottom-right" theme={theme} />
      <TopBar devices={state?.devices} theme={theme} onToggleTheme={toggleTheme} />
      <EstopBanner active={!!robot?.estop} clearing={clearing} onClear={clearEstop} />
      {!online && (
        <div role="alert" className="border-b border-border px-4 py-3 text-sm">
          Can&apos;t reach the robot backend. Check that the Pi is on and the app is running.
          {error && <span className="text-muted-foreground"> ({error})</span>}
        </div>
      )}
      <main className="grid gap-6 p-4 lg:grid-cols-[1fr_340px]">
        <CameraFeed
          frame={state?.frame}
          parking={parking}
          fetchedAt={fetchedAt}
          backendOnline={online}
          cameraOnline={state?.devices?.camera === 'ok'}
          onRetry={refresh}
        />
        <div className="flex flex-col gap-6">
          <StateCard robotState={robot?.state || 'IDLE'} hasViolation={hasViolation} hasTicket={!!state?.ticket} />
          <DetectionCard vehicles={vehicles} />
          <TicketCard ticket={state?.ticket} printing={printing} onPrint={async () => {
            setPrinting(true)
            try { await testPrint(); refresh() } catch { /* toast in controls */ }
            finally { setPrinting(false) }
          }} />
        </div>
      </main>
      <ControlsBar
        driveEnabled={driveEnabled}
        autoRunning={robot?.mode === 'auto'}
        estopActive={!!robot?.estop}
        onChanged={refresh}
      />
      <div className="p-4">
        <EventLog events={state?.events} />
      </div>
    </div>
  )
}
