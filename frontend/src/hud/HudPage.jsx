import { useEffect, useRef, useState } from 'react'
import { Toaster, toast } from 'sonner'
import { WifiOff } from 'lucide-react'
import { autoResume, confirmParkingReview, dismissParkingReview, estopClear, printViolation, testPrint } from './api'
import { useHudState } from './useHudState'
import CameraFeed from './components/CameraFeed'
import ControlsBar from './components/ControlsBar'
import DetectionCard from './components/DetectionCard'
import EstopBanner from './components/EstopBanner'
import EventLog from './components/EventLog'
import ReviewModal from './components/ReviewModal'
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
  const { state, connection, error, refresh, fetchedAt } = useHudState(750)
  const [clearing, setClearing] = useState(false)
  const [printing, setPrinting] = useState(false)
  const [printingId, setPrintingId] = useState(null)
  const [reviewModalOpen, setReviewModalOpen] = useState(false)
  const prevModeRef = useRef(null)
  const lastOpenedKeyRef = useRef('')

  const toggleTheme = () => {
    setTheme((t) => {
      const next = t === 'dark' ? 'light' : 'dark'
      try {
        window.localStorage.setItem('hud-theme', next)
      } catch {
        /* private mode */
      }
      return next
    })
  }

  const clearEstop = async () => {
    setClearing(true)
    try {
      await estopClear()
      refresh()
    } catch {
      /* toast comes from banner action */
    } finally {
      setClearing(false)
    }
  }

  const online = connection === 'ok'
  const robot = state?.robot
  const parking = state?.parking
  const vehicles = parking?.vehicles || []
  const driveEnabled = online && !robot?.estop && robot?.link !== 'offline'
  const hasViolation = vehicles.some((v) => v.valid === false)

  useEffect(() => {
    document.title = 'ParkSensei — Autonomous Robot HUD'
  }, [])

  // Auto-open Verification Gate Modal strictly on transition into review mode or when target list changes
  useEffect(() => {
    const isReview = robot?.mode === 'review'
    const vehiclesList = robot?.review_vehicles || []
    const currentKey = `${robot?.mode}:${vehiclesList.slice().sort().join(',')}`

    if (isReview && vehiclesList.length > 0) {
      if (prevModeRef.current !== 'review' || currentKey !== lastOpenedKeyRef.current) {
        setReviewModalOpen(true)
        lastOpenedKeyRef.current = currentKey
      }
    } else if (!isReview) {
      setReviewModalOpen(false)
      lastOpenedKeyRef.current = ''
    }
    prevModeRef.current = robot?.mode
  }, [robot?.mode, (robot?.review_vehicles || []).join(',')])

  // Keep body margin clean
  useEffect(() => {
    const prev = document.body.style.margin
    document.body.style.margin = '0'
    return () => {
      document.body.style.margin = prev
    }
  }, [])

  return (
    <div className={`hud-root ${theme}`}>
      <Toaster position="bottom-right" theme={theme} />
      <TopBar devices={state?.devices} theme={theme} onToggleTheme={toggleTheme} />
      <EstopBanner active={!!robot?.estop} clearing={clearing} onClear={clearEstop} />

      {!online && (
        <div
          role="alert"
          className="flex items-center gap-2.5 border-b border-amber-500/40 bg-amber-500/10 px-4 py-3 text-xs text-amber-300"
        >
          <WifiOff className="h-4 w-4 shrink-0 text-amber-400" />
          <span>
            Telemetry unreachable. Verifying connection to Pi hotspot (`10.42.0.1:8000`)…
            {error && <span className="opacity-75"> ({error})</span>}
          </span>
        </div>
      )}

      {/* Main Content Area — with extra bottom padding to clear the floating controls dock */}
      <div className="pb-28 sm:pb-32">
        <main className="mx-auto grid w-full max-w-[1600px] grid-cols-1 gap-4 p-3 sm:gap-5 sm:p-5 xl:grid-cols-[minmax(0,1fr)_390px]">
          <CameraFeed
            frame={state?.frame}
            parking={parking}
            fetchedAt={fetchedAt}
            backendOnline={online}
            cameraState={state?.devices?.camera || 'offline'}
            onRetry={refresh}
          />

          <div className="flex min-w-0 flex-col gap-4">
            <StateCard
              robotState={robot?.state || 'IDLE'}
              hasViolation={hasViolation}
              hasTicket={!!state?.ticket}
              lastError={robot?.last_error}
              distanceCm={robot?.distance_cm}
              irBlocked={robot?.ir_blocked}
              obstacle={robot?.obstacle}
              reviewReady={!!robot?.review_ready}
              reviewConfirmedCount={robot?.review_confirmed?.length || 0}
              reviewTicketedCount={robot?.review_ticketed?.length || 0}
              reviewTotal={robot?.review_vehicles?.length || 0}
            />

            <DetectionCard
              vehicles={vehicles}
              printingId={printingId}
              reviewMode={robot?.mode === 'review'}
              reviewVehicles={robot?.review_vehicles || []}
              reviewConfirmed={robot?.review_confirmed || []}
              reviewTicketed={robot?.review_ticketed || []}
              reviewReady={!!robot?.review_ready}
              onConfirm={async (vehicle) => {
                await confirmParkingReview(vehicle.id)
                await refresh()
              }}
              onDismiss={async (vehicle) => {
                try {
                  await dismissParkingReview(vehicle.id)
                  await refresh()
                  toast.info(`Vehicle ${vehicle.id} dismissed.`)
                } catch (err) {
                  toast.error(err.message || 'Could not dismiss vehicle.')
                }
              }}
              onResume={async () => {
                try {
                  await autoResume()
                  refresh()
                  toast.success('Patrol resumed.')
                } catch (error) {
                  toast.error(error.message || 'Could not resume patrol.')
                }
              }}
              onPrint={async (vehicle, plate) => {
                setPrintingId(vehicle.id)
                try {
                  const result = await printViolation(vehicle.id, plate)
                  refresh()
                  return result
                } finally {
                  setPrintingId(null)
                }
              }}
            />

            <TicketCard
              ticket={state?.ticket}
              printing={printing}
              onPrint={async () => {
                setPrinting(true)
                try {
                  await testPrint()
                  refresh()
                } catch {
                  /* toast in controls */
                } finally {
                  setPrinting(false)
                }
              }}
            />
          </div>
        </main>

        <div className="mx-auto w-full max-w-[1600px] px-3 sm:px-5">
          <EventLog events={state?.events} />
        </div>
      </div>

      {/* Floating Tactical Bottom Dock */}
      <ControlsBar
        driveEnabled={driveEnabled}
        autoRunning={robot?.mode === 'auto' || robot?.mode === 'review'}
        estopActive={!!robot?.estop}
        onChanged={refresh}
      />

      {/* Human Verification Gate Pop-up Modal */}
      <ReviewModal
        open={reviewModalOpen}
        onOpenChange={setReviewModalOpen}
        vehicles={vehicles}
        reviewVehicles={robot?.review_vehicles || []}
        reviewConfirmed={robot?.review_confirmed || []}
        reviewTicketed={robot?.review_ticketed || []}
        reviewDismissed={robot?.review_dismissed || []}
        reviewReady={!!robot?.review_ready}
        printingId={printingId}
        onConfirm={async (vehicle) => {
          await confirmParkingReview(vehicle.id)
          await refresh()
        }}
        onDismiss={async (vehicle) => {
          try {
            await dismissParkingReview(vehicle.id)
            await refresh()
            toast.info(`Vehicle ${vehicle.id} dismissed.`)
          } catch (err) {
            toast.error(err.message || 'Could not dismiss vehicle.')
          }
        }}
        onResume={async () => {
          try {
            await autoResume()
            refresh()
            toast.success('Patrol resumed.')
          } catch (error) {
            toast.error(error.message || 'Could not resume patrol.')
          }
        }}
        onPrint={async (vehicle, plate) => {
          setPrintingId(vehicle.id)
          try {
            const result = await printViolation(vehicle.id, plate)
            refresh()
            return result
          } finally {
            setPrintingId(null)
          }
        }}
      />
    </div>
  )
}
