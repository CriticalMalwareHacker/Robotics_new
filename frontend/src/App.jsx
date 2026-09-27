import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'

const exampleStudyPrompt = 'Make me a detailed labeled diagram of the IEM in the reference image including its internals as well'

const modeNames = { study: 'Study', inventory: 'Inventory', product: 'Product', qr: 'QR Code' }
const iconStroke = (color = 'var(--dim)') => ({ stroke: color, fill: 'none', strokeWidth: 1.4, strokeLinecap: 'round', strokeLinejoin: 'round' })

function WifiIcon({ on = false }) {
  const color = on ? 'var(--text)' : 'var(--dim)'
  return <svg width="15" height="15" viewBox="0 0 15 15"><path d="M1.5 5.5C3.5 3.3 5.4 2.5 7.5 2.5s4 .8 6 3" {...iconStroke(color)} /><path d="M3.5 7.8C5 6.4 6.2 5.8 7.5 5.8s2.5.6 4 2" {...iconStroke(color)} /><path d="M5.5 10C6.2 9.3 6.8 9 7.5 9s1.3.3 2 1" {...iconStroke(color)} /><circle cx="7.5" cy="12.5" r=".8" fill={color} /></svg>
}

function PrinterIcon({ on = false }) {
  const color = on ? 'var(--text)' : 'var(--dim)'
  return <svg width="15" height="15" viewBox="0 0 15 15"><path d="M4 5V3.5h7V5" {...iconStroke(color)} /><rect x="2" y="5" width="11" height="6.5" rx="1" {...iconStroke(color)} /><path d="M4 8.5h7M4 10.5h4" {...iconStroke(color)} /></svg>
}

function CameraIcon({ on = false }) {
  const color = on ? 'var(--text)' : 'var(--dim)'
  return <svg width="15" height="15" viewBox="0 0 15 15"><path d="M5.5 3h4l1 1.5H13a1 1 0 0 1 1 1V12a1 1 0 0 1-1 1H2a1 1 0 0 1-1-1V5.5a1 1 0 0 1 1-1h1.5L4.5 3z" {...iconStroke(color)} /><circle cx="7.5" cy="8.5" r="2.2" {...iconStroke(color)} /></svg>
}

function HistoryIcon() { return <svg width="15" height="15" viewBox="0 0 15 15"><circle cx="7.5" cy="7.5" r="5.5" {...iconStroke()} /><path d="M7.5 4.5v3.2l1.8 1.5" {...iconStroke()} /></svg> }
function SettingsIcon() { return <svg width="15" height="15" viewBox="0 0 15 15"><circle cx="7.5" cy="7.5" r="2" {...iconStroke()} /><path d="M7.5 1.5v2M7.5 11.5v2M1.5 7.5h2M11.5 7.5h2M3.4 3.4l1.4 1.4M10.2 10.2l1.4 1.4M11.6 3.4l-1.4 1.4M4.8 10.2l-1.4 1.4" {...iconStroke()} /></svg> }
function BackIcon() { return <svg width="14" height="14" viewBox="0 0 14 14"><path d="M9 2.5L4.5 7 9 11.5" {...iconStroke()} /></svg> }
function NextIcon() { return <svg width="12" height="12" viewBox="0 0 12 12"><path d="M4.5 2l3 4-3 4" {...iconStroke()} /></svg> }

function RetryIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none">
      <path d="M13.5 8A5.5 5.5 0 1 1 11 3.5M11 1.5v3.5h3.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function SuccessIcon() {
  return <svg width="40" height="40" viewBox="0 0 40 40"><circle cx="20" cy="20" r="18" {...iconStroke('var(--led-green)')} /><path d="M11 20l6.5 6.5 12-13" {...iconStroke('var(--led-green)')} strokeWidth="2" /></svg>
}

function VoiceIcon() {
  return <svg width="22" height="22" viewBox="0 0 22 22" fill="none"><rect x="7" y="2" width="8" height="11" rx="4" stroke="var(--sub)" strokeWidth="1.4" /><path d="M4 11c0 3.9 3.1 7 7 7s7-3.1 7-7" stroke="var(--sub)" strokeWidth="1.4" strokeLinecap="round" /><line x1="11" y1="18" x2="11" y2="21" stroke="var(--sub)" strokeWidth="1.4" strokeLinecap="round" /></svg>
}

function CameraVoiceIcon() {
  return <svg width="22" height="22" viewBox="0 0 22 22" fill="none"><rect x="1.5" y="5" width="12" height="9" rx="1.2" stroke="var(--sub)" strokeWidth="1.4" /><path d="M13.5 9l5-3v8l-5-3" stroke="var(--sub)" strokeWidth="1.4" strokeLinejoin="round" /><circle cx="7.5" cy="9.5" r="2" stroke="var(--sub)" strokeWidth="1.4" /></svg>
}

function TextIcon() {
  return <svg width="22" height="22" viewBox="0 0 22 22" fill="none"><rect x="2" y="6" width="18" height="10" rx="1.5" stroke="var(--sub)" strokeWidth="1.4" /><path d="M6 10h1M10 10h1M14 10h1M7 13h8" stroke="var(--sub)" strokeWidth="1.4" strokeLinecap="round" /></svg>
}

function StudyIcon() { return <svg width="22" height="22" viewBox="0 0 22 22"><rect x="3" y="3" width="16" height="16" rx="1.5" {...iconStroke('var(--sub)')} /><path d="M6 7.5h10M6 11h10M6 14.5h6" {...iconStroke('var(--sub)')} /></svg> }
function InventoryIcon() { return <svg width="22" height="22" viewBox="0 0 22 22"><path d="M11 3L3 7v8l8 4 8-4V7L11 3z" {...iconStroke('var(--sub)')} /><path d="M3 7l8 4 8-4M11 11v8" {...iconStroke('var(--sub)')} /></svg> }
function ProductIcon() { return <svg width="22" height="22" viewBox="0 0 22 22"><rect x="3" y="3" width="16" height="16" rx="1.5" {...iconStroke('var(--sub)')} /><path d="M6 8h10M6 11.5h6M14.5 14l2 2" {...iconStroke('var(--sub)')} /><circle cx="14" cy="13.5" r="2.5" {...iconStroke('var(--sub)')} /></svg> }

function QrIcon() {
  return <svg width="22" height="22" viewBox="0 0 22 22" fill="none"><rect x="3" y="3" width="6" height="6" rx=".5" stroke="var(--sub)" strokeWidth="1.4" /><rect x="4.5" y="4.5" width="3" height="3" fill="var(--sub)" /><rect x="13" y="3" width="6" height="6" rx=".5" stroke="var(--sub)" strokeWidth="1.4" /><rect x="14.5" y="4.5" width="3" height="3" fill="var(--sub)" /><rect x="3" y="13" width="6" height="6" rx=".5" stroke="var(--sub)" strokeWidth="1.4" /><rect x="4.5" y="14.5" width="3" height="3" fill="var(--sub)" /><rect x="13" y="13" width="2.5" height="2.5" fill="var(--sub)" /><rect x="16.5" y="13" width="2.5" height="2.5" fill="var(--sub)" /><rect x="13" y="16.5" width="2.5" height="2.5" fill="var(--sub)" /><rect x="16.5" y="16.5" width="2.5" height="2.5" fill="var(--sub)" /></svg>
}

function StatusDot({ color, pulse = false }) { return <div className={pulse ? 'status-dot pulse' : 'status-dot'} style={{ background: color ?? 'transparent' }} /> }

function Bar({ children }) { return <div className="top-bar">{children}</div> }
function IconButton({ onClick, className = '', children, label }) { return <button type="button" aria-label={label} onClick={onClick} className={`icon-button ${className}`}>{children}</button> }

function Home({ onStart, onSettings, onHistory }) {
  return <div className="screen">
    <Bar>
      <div className="status-icons"><WifiIcon on /><PrinterIcon on /><CameraIcon /></div>
      <span className="mono status-copy" />
      <div className="bar-actions"><IconButton label="History" onClick={onHistory}><HistoryIcon /></IconButton><IconButton label="Settings" onClick={onSettings}><SettingsIcon /></IconButton></div>
    </Bar>
    <div className="center-body home-body">
      <StatusDot pulse />
      <div className="ready-copy"><div className="ready-title">Ready</div><div className="ready-subtitle" /></div>
      <button className="primary-button start-button" onClick={onStart}>Tap to Start</button>
    </div>
    <div className="home-footer"><span className="mono" /></div>
  </div>
}

const modes = [
  { id: 'study', label: 'Study', Icon: StudyIcon },
  { id: 'inventory', label: 'Inventory', Icon: InventoryIcon },
  { id: 'product', label: 'Product', Icon: ProductIcon },
  { id: 'qr', label: 'QR Code', Icon: QrIcon },
]

function ModeSelect({ onSelect, onBack, onSettings }) {
  return <div className="screen"><Bar><IconButton label="Back" onClick={onBack}><BackIcon /></IconButton><span className="bar-title title-after-back">Select Mode</span></Bar>
    <div className="mode-grid">
      {modes.map(({ id, label, Icon }) => <button className="tile-button" key={id} onClick={() => onSelect(id)}><Icon /><span>{label}</span></button>)}
      <div className="empty-tile" />
      <button className="tile-button settings-tile" onClick={onSettings}><SettingsIcon /><span>Settings</span></button>
    </div>
  </div>
}

const methods = [
  { id: 'voice', label: 'Voice', sub: 'Speak your label', Icon: VoiceIcon },
  { id: 'camera+voice', label: 'Camera + Voice', sub: 'Scan then describe', Icon: CameraVoiceIcon },
  { id: 'text', label: 'Text', sub: 'Type manually', Icon: TextIcon },
]

function InputMethod({ mode, onSelect, onBack }) {
  return <div className="screen"><Bar><IconButton label="Back" onClick={onBack}><BackIcon /></IconButton><span className="bar-title title-after-back">Input Method</span><span className="bar-meta">{modeNames[mode]}</span></Bar>
    <div className="method-grid">{methods.map(({ id, label, sub, Icon }) => <button className="method-tile" key={id} onClick={() => onSelect(id)}><Icon /><span className="method-title">{label}</span><span className="method-subtitle">{sub}</span></button>)}</div>
  </div>
}

function CameraCapture({ onCaptured, onBack, source = 'usb', onSourceChange }) {
  const [captured, setCaptured] = useState(false)
  const [capturedPhoto, setCapturedPhoto] = useState(null)
  const [capturing, setCapturing] = useState(false)
  const [cameraError, setCameraError] = useState('')
  const [frameSrc, setFrameSrc] = useState('/api/camera/frame')
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const isMountedRef = useRef(true)

  const stopPhoneCamera = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
  }

  const releaseUsbCamera = () => {
    fetch('/api/camera/release', { method: 'POST' }).catch(() => {})
  }

  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
      stopPhoneCamera()
      releaseUsbCamera()
    }
  }, [])

  // USB Camera live frame updater loop
  useEffect(() => {
    if (source !== 'usb' || captured) return undefined
    let timer = null
    let active = true

    const loadNextFrame = () => {
      if (!active || captured) return
      setFrameSrc(`/api/camera/frame?t=${Date.now()}`)
    }

    timer = window.setInterval(loadNextFrame, 120) // ~8-10 FPS live feed
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [source, captured])

  useEffect(() => {
    if (source === 'phone') {
      releaseUsbCamera()
      let active = true
      setCameraError('')
      navigator.mediaDevices?.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false })
        .then((stream) => {
          if (!active) { stream.getTracks().forEach((track) => track.stop()); return }
          streamRef.current = stream
          if (videoRef.current) videoRef.current.srcObject = stream
        })
        .catch(() => setCameraError('Phone camera access was denied or is unavailable.'))
      return () => { active = false; stopPhoneCamera() }
    } else {
      stopPhoneCamera()
      setCameraError('')
    }
  }, [source])

  const handleClose = () => {
    stopPhoneCamera()
    releaseUsbCamera()
    onBack()
  }

  const takePhoto = async () => {
    if (captured || capturing) return
    setCapturing(true)
    setCameraError('')

    if (source === 'usb') {
      try {
        const res = await fetch('/api/camera/capture', { method: 'POST' })
        const data = await res.json()
        if (!res.ok || !data.image) {
          throw new Error(data.detail || 'Failed to capture frame from USB webcam.')
        }
        setCaptured(true)
        setCapturedPhoto(data.image)
        window.setTimeout(() => {
          releaseUsbCamera()
          onCaptured(data.image)
        }, 800)
      } catch (err) {
        setCameraError(err.message || 'USB camera capture failed.')
        setCapturing(false)
      }
    } else {
      const video = videoRef.current
      if (!video?.videoWidth) {
        setCapturing(false)
        return
      }
      const canvas = document.createElement('canvas')
      canvas.width = video.videoWidth
      canvas.height = video.videoHeight
      canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height)
      const image = canvas.toDataURL('image/jpeg', 0.92)
      setCaptured(true)
      setCapturedPhoto(image)
      stopPhoneCamera()
      window.setTimeout(() => onCaptured(image), 800)
    }
  }

  return (
    <div className="screen">
      <Bar>
        <StatusDot color="var(--led-blue)" pulse />
        <span className="bar-title status-title">Camera</span>
        <div className="camera-source-tabs" style={{ marginLeft: 'auto', marginRight: '6px' }}>
          <button
            type="button"
            className={`camera-source-btn ${source === 'usb' ? 'active' : ''}`}
            onClick={() => { onSourceChange?.('usb'); setCameraError('') }}
          >
            USB Cam
          </button>
          <button
            type="button"
            className={`camera-source-btn ${source === 'phone' ? 'active' : ''}`}
            onClick={() => { onSourceChange?.('phone'); setCameraError('') }}
          >
            Phone
          </button>
        </div>
        <IconButton label="Close" className="close-button" onClick={handleClose}>×</IconButton>
      </Bar>
      <div className="center-body camera-body">
        <div className="camera-frame">
          {captured && capturedPhoto ? (
            <img className="camera-video" src={capturedPhoto} alt="Captured photo" style={{ transform: 'none' }} />
          ) : source === 'usb' ? (
            <img
              className="camera-video"
              src={frameSrc}
              alt="Hikvision Live Viewfinder"
              style={{ transform: 'none' }}
              onError={() => setCameraError('Initializing USB Camera…')}
              onLoad={() => setCameraError('')}
            />
          ) : (
            <video ref={videoRef} className="camera-video" autoPlay playsInline muted />
          )}
          <i className="corner top left" />
          <i className="corner top right" />
          <i className="corner bottom left" />
          <i className="corner bottom right" />
          <span className={captured ? 'capture-done' : 'camera-prompt'}>
            {cameraError || (captured ? 'Captured ✓' : source === 'usb' ? 'Hikvision USB Live' : 'Aim at subject')}
          </span>
        </div>
        <button
          type="button"
          className={`primary-button capture-button ${captured ? 'is-captured' : ''}`}
          disabled={captured || capturing}
          onClick={takePhoto}
        >
          {captured ? 'Captured ✓' : capturing ? 'Capturing…' : 'Capture Photo'}
        </button>
      </div>
    </div>
  )
}

function VoiceRecorder({ mode, onCapture, onBack, source = 'usb', onSourceChange }) {
  const [state, setState] = useState('idle')
  const [error, setError] = useState('')
  const [transcript, setTranscript] = useState('')
  const [duration, setDuration] = useState(0)
  const recorderRef = useRef(null)
  const streamRef = useRef(null)
  const chunksRef = useRef([])
  const timerRef = useRef(null)
  const pressStartTimeRef = useRef(0)
  const isHoldingRef = useRef(false)

  const stopStream = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
  }

  const cancelRecording = useCallback(async () => {
    if (timerRef.current) clearInterval(timerRef.current)
    stopStream()
    if (source === 'usb') {
      try {
        await fetch('/api/voice/cancel_record', { method: 'POST' })
      } catch {}
    }
  }, [source])

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
      stopStream()
      fetch('/api/voice/cancel_record', { method: 'POST' }).catch(() => {})
    }
  }, [])

  useEffect(() => {
    if (state === 'recording') {
      setDuration(0)
      timerRef.current = setInterval(() => {
        setDuration((d) => d + 1)
      }, 1000)
    } else {
      if (timerRef.current) clearInterval(timerRef.current)
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [state])

  const startUsbRecording = async () => {
    setError('')
    setState('recording')
    try {
      const res = await fetch('/api/voice/start_record', { method: 'POST' })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || 'Could not start USB microphone.')
      }
    } catch (err) {
      setError(err.message || 'USB Mic failed to start.')
      setState('idle')
    }
  }

  const stopUsbRecording = async () => {
    setState('transcribing')
    try {
      const res = await fetch('/api/voice/stop_record', { method: 'POST' })
      const data = await res.json()
      if (!res.ok || !data.text) {
        throw new Error(data.detail || 'No speech was detected. Please try speaking closer to the webcam.')
      }
      setTranscript(data.text)
      onCapture(data.text)
    } catch (err) {
      setError(err.message || 'USB Mic transcription failed.')
      setState('idle')
    }
  }

  const startPhoneRecording = async () => {
    setError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      streamRef.current = stream
      chunksRef.current = []
      recorder.ondataavailable = (event) => {
        if (event.data.size) chunksRef.current.push(event.data)
      }
      recorder.onstop = async () => {
        stopStream()
        setState('transcribing')
        try {
          const audio = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
          const form = new FormData()
          form.append('audio', audio, 'recording.webm')
          const response = await fetch('/voice/transcribe', { method: 'POST', body: form })
          const data = await response.json()
          if (!response.ok) throw new Error(data.detail || 'Transcription failed.')
          setTranscript(data.text)
          if (data.text) onCapture(data.text)
          else {
            setError('No speech was detected. Please try again.')
            setState('idle')
          }
        } catch (exc) {
          setError(exc.message || 'Transcription failed.')
          setState('idle')
        }
      }
      recorderRef.current = recorder
      recorder.start(500)
      setState('recording')
    } catch {
      setError('Phone microphone access was denied or is unavailable.')
      setState('idle')
    }
  }

  const stopPhoneRecording = () => {
    if (recorderRef.current?.state === 'recording') {
      recorderRef.current.stop()
    }
  }

  const handlePointerDown = (e) => {
    if (state === 'transcribing') return
    if (state === 'recording') {
      // Tap while recording to stop
      if (source === 'usb') stopUsbRecording()
      else stopPhoneRecording()
      return
    }
    pressStartTimeRef.current = Date.now()
    isHoldingRef.current = true
    if (source === 'usb') startUsbRecording()
    else startPhoneRecording()
  }

  const handlePointerUp = () => {
    if (state !== 'recording' || !isHoldingRef.current) return
    const holdDuration = Date.now() - pressStartTimeRef.current
    isHoldingRef.current = false
    // If held for more than 400ms, treat as push-to-talk release
    if (holdDuration > 400) {
      if (source === 'usb') stopUsbRecording()
      else stopPhoneRecording()
    }
    // If tapped (<400ms), remain recording until tapped again
  }

  const handleManualStop = () => {
    if (state !== 'recording') return
    isHoldingRef.current = false
    if (source === 'usb') stopUsbRecording()
    else stopPhoneRecording()
  }

  const formatTimer = (secs) => {
    const m = Math.floor(secs / 60)
    const s = secs % 60
    return `${m}:${s < 10 ? '0' : ''}${s}`
  }

  const label = state === 'recording'
    ? `Stop (${formatTimer(duration)})`
    : state === 'transcribing'
    ? 'Transcribing…'
    : 'Tap or Hold to Record'

  return (
    <div className="screen">
      <Bar>
        <StatusDot color={state === 'recording' ? 'var(--led-red)' : 'var(--led-blue)'} pulse />
        <span className="bar-title status-title">{modeNames[mode]}</span>
        <div className="camera-source-tabs" style={{ marginLeft: 'auto', marginRight: '6px' }}>
          <button
            type="button"
            className={`camera-source-btn ${source === 'usb' ? 'active' : ''}`}
            disabled={state === 'recording' || state === 'transcribing'}
            onClick={() => { onSourceChange?.('usb'); setError('') }}
          >
            USB Mic
          </button>
          <button
            type="button"
            className={`camera-source-btn ${source === 'phone' ? 'active' : ''}`}
            disabled={state === 'recording' || state === 'transcribing'}
            onClick={() => { onSourceChange?.('phone'); setError('') }}
          >
            Phone
          </button>
        </div>
        <IconButton label="Close" className="close-button" onClick={() => { cancelRecording(); onBack() }}>Close</IconButton>
      </Bar>
      <div className="center-body voice-body">
        <div className="voice-visual">
          <VoiceIcon />
          <div className={state === 'recording' ? 'wave waveform' : 'waveform'}>
            {[6, 12, 20, 26, 20, 12, 6].map((height, index) => (
              <span
                key={index}
                style={{
                  height: state === 'recording' ? height : 4,
                  backgroundColor: state === 'recording' ? 'var(--led-red)' : 'var(--border)',
                }}
              />
            ))}
          </div>
        </div>
        <div className="live-transcript" style={{ textAlign: 'center' }}>
          {transcript || (state === 'recording'
            ? (source === 'usb' ? `🔴 Recording USB Mic (${formatTimer(duration)})... Tap to stop` : `🔴 Recording Phone Mic (${formatTimer(duration)})... Tap to stop`)
            : state === 'transcribing'
            ? '⏳ Transcribing with Whisper...'
            : (source === 'usb' ? 'Hikvision USB Mic ready · Tap or hold to speak' : 'Phone Mic ready · Tap or hold to speak'))}
        </div>
        {error && <span className="voice-error">{error}</span>}
        <div style={{ display: 'flex', gap: '8px', width: '100%', maxWidth: '240px' }}>
          <button
            type="button"
            className={`primary-button record-button ${state === 'recording' ? 'holding' : ''}`}
            disabled={state === 'transcribing'}
            onPointerDown={handlePointerDown}
            onPointerUp={handlePointerUp}
            style={{
              flex: 1,
              backgroundColor: state === 'recording' ? '#ef4444' : undefined,
              borderColor: state === 'recording' ? '#dc2626' : undefined,
            }}
          >
            {label}
          </button>
          {state === 'recording' && (
            <button
              type="button"
              className="ghost-button"
              onClick={handleManualStop}
              style={{ padding: '0 12px', fontSize: 'var(--fs-xs)' }}
            >
              Done ✓
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

function VoiceResult({ transcript, onBack, onGenerate, hasReferenceImage }) {
  return <div className="screen"><Bar><span className="bar-title">Voice recognized</span></Bar><div className="center-body voice-result-body"><div className="transcript-card">{transcript}</div><span className="voice-result-note">English output · faster-whisper tiny{hasReferenceImage ? ' · camera image attached' : ''}</span><div className="voice-result-actions"><button className="ghost-button" onClick={onBack}>Discard</button><button className="primary-button" onClick={onGenerate}>Generate image</button></div></div></div>
}

function Capture({ mode, inputMethod, onCapture, onBack, source = 'usb', onSourceChange }) {
  const [recordState, setRecordState] = useState('idle')
  const [text, setText] = useState('')
  const isText = inputMethod === 'text'
  if (!isText) return <VoiceRecorder mode={mode} onCapture={onCapture} onBack={onBack} source={source} onSourceChange={onSourceChange} />
  const finishRecording = () => { if (recordState !== 'holding') return; setRecordState('done'); window.setTimeout(() => onCapture(exampleStudyPrompt), 600) }
  return <div className="screen"><Bar><StatusDot color="var(--led-blue)" pulse /><span className="bar-title status-title">{modeNames[mode]}</span>{inputMethod === 'camera+voice' && <span className="step-copy">· step 2 of 2</span>}<IconButton label="Close" className="close-button" onClick={onBack}>×</IconButton></Bar>
    {isText ? <div className="center-body text-body"><textarea value={text} onChange={(event) => setText(event.target.value)} placeholder={mode === 'inventory' ? "Line 1: Item Name (Bold Big)\nLine 2: Description / Qty (Small)" : mode === 'product' ? "Line 1: Product Name\nLine 2: Price (e.g. 499)\nLine 3: Details / Description" : mode === 'qr' ? "Enter URL or text for QR code..." : "Describe what to label…"} /><button className="primary-button continue-button" disabled={!text.trim()} onClick={() => onCapture(text.trim())}>Continue</button></div>
      : <div className="center-body voice-body"><div className="voice-visual"><svg width="26" height="30" viewBox="0 0 26 30" fill="none"><rect x="7" y="2" width="12" height="16" rx="6" stroke={recordState === 'holding' ? 'var(--led-blue)' : 'var(--dim)'} strokeWidth="1.4" /><path d="M3 15c0 5.5 4.5 9 10 9s10-3.5 10-9" stroke={recordState === 'holding' ? 'var(--led-blue)' : 'var(--dim)'} strokeWidth="1.4" strokeLinecap="round" /><line x1="13" y1="24" x2="13" y2="29" stroke={recordState === 'holding' ? 'var(--led-blue)' : 'var(--dim)'} strokeWidth="1.4" strokeLinecap="round" /></svg>
          <div className={recordState === 'holding' ? 'wave waveform' : 'waveform'}>{[6, 12, 20, 26, 20, 12, 6].map((height, index) => <span key={index} style={{ height: recordState === 'holding' ? height : 4 }} />)}</div></div>
        <button className={`primary-button record-button ${recordState}`} onPointerDown={() => setRecordState('holding')} onPointerUp={finishRecording} onPointerCancel={finishRecording} onPointerLeave={finishRecording}>{recordState === 'done' ? 'Captured' : recordState === 'holding' ? 'Recording…' : 'Hold to Record'}</button>
      </div>}
  </div>
}

function Processing({ onCancel, error }) {
  if (error) return <div className="screen"><Bar><span className="bar-title">Generation failed</span></Bar><div className="center-body processing-body"><div className="processing-copy"><div>{error}</div><span>Check the AI image provider configuration and try again.</span></div><button className="ghost-button" onClick={onCancel}>Back</button></div></div>
  return <div className="screen"><Bar><StatusDot color="var(--led-purple)" pulse /><span className="bar-title status-title">Processing</span></Bar><div className="center-body processing-body"><svg width="36" height="36" viewBox="0 0 36 36" fill="none" className="spin"><circle cx="18" cy="18" r="14" stroke="var(--border)" strokeWidth="3" /><path d="M18 4a14 14 0 0 1 14 14" stroke="var(--led-purple)" strokeWidth="3" strokeLinecap="round" /></svg><div className="processing-copy"><div>Generating label</div><span>AI is creating content…</span></div><div className="progress-track processing-progress"><div className="fill-anim" /></div><button className="ghost-button" onClick={onCancel}>Cancel</button></div></div>
}

const previews = {
  study: { title: 'Study Diagram', desc: 'Educational diagram' },
  inventory: { title: 'Inventory Item', desc: '' },
  product: { title: 'Product Label', desc: '' },
  qr: { title: 'QR Code', desc: '' },
}

function Preview({ mode, onEdit, onPrint, generatedImage, isPrinting, printError, transcript }) {
  const previewItem = previews[mode] || { title: 'PrintSensei Label', desc: '' }
  const transcriptLines = (transcript || '').split('\n').map((l) => l.trim()).filter(Boolean)
  const title = transcriptLines.length > 0 ? transcriptLines[0] : previewItem.title
  
  let priceStr = null
  let bodyLines = []
  if (mode === 'product') {
    for (let i = 1; i < transcriptLines.length; i++) {
      const line = transcriptLines[i]
      const priceMatch = line.match(/^(?:price\s*[:=]?\s*|rs\.?\s*|₹\s*|\$\s*)?(\d+(?:\.\d+)?)$/i)
      if (priceMatch && priceStr === null) {
        priceStr = priceMatch[1]
      } else {
        bodyLines.push(line)
      }
    }
  } else {
    bodyLines = transcriptLines.length > 1 ? transcriptLines.slice(1) : []
  }
  const desc = bodyLines.join(' · ')
  const date = new Date().toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' }).toUpperCase()
  if (generatedImage) return <div className="screen"><Bar><span className="bar-title">Study image</span><span className="bar-meta">Ready</span></Bar><div className="center-body preview-body"><img className="generated-image" src={generatedImage} alt="Generated study diagram" /><div className="preview-actions"><button className="ghost-button" disabled={isPrinting} onClick={onEdit}>Edit</button><button className="primary-button" disabled={isPrinting} onClick={onPrint}>{isPrinting ? 'Sending…' : 'Print'}</button></div>{printError && <span className="voice-error">{printError}</span>}</div></div>
  return <div className="screen"><Bar><span className="bar-title">Preview</span><span className="bar-meta">{modeNames[mode]}</span></Bar><div className="center-body preview-body"><div className="label-preview"><div className="label-main"><div className="label-copy"><div className="label-title">{title}</div>{priceStr && <div className="label-price" style={{ color: 'var(--accent)', fontWeight: 600, fontSize: '12px', marginTop: '2px' }}>Rs {priceStr}</div>}{desc && <div className="label-desc">{desc}</div>}</div><div className="qr-box"><QrIcon /></div></div><div className="label-footer mono">PRINTSENSEI · {date} · 58MM</div></div><div className="preview-actions"><button className="ghost-button" disabled={isPrinting} onClick={onEdit}>Edit</button><button className="primary-button" disabled={isPrinting} onClick={onPrint}>{isPrinting ? 'Sending…' : 'Print'}</button></div>{printError && <span className="voice-error">{printError}</span>}</div></div>
}

function Printing({ onDone }) {
  useEffect(() => { const timer = window.setTimeout(onDone, 3200); return () => window.clearTimeout(timer) }, [onDone])
  return <div className="screen"><Bar><StatusDot color="var(--led-green)" pulse /><span className="bar-title status-title">Printing</span></Bar><div className="center-body printing-body"><SuccessIcon /><div className="printed-copy"><div>Label printed</div><span>Returning to home…</span></div><div className="progress-track print-progress"><div className="drain-anim" /></div></div></div>
}

function Settings({ onBack, brightness = 85, onBrightnessChange }) {
  const [systemInfo, setSystemInfo] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    fetch('/api/system/status')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (active && data) {
          setSystemInfo(data)
          setLoading(false)
        }
      })
      .catch(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [])

  const wifiVal = systemInfo?.wifi?.name || 'Online'
  const printerVal = systemInfo?.printer?.status || 'POSIFLOW 58D (USB)'
  const cameraVal = systemInfo?.camera?.name || 'Camera Ready'
  const osVal = systemInfo?.system?.os || 'Linux'
  const appVer = systemInfo?.system?.version || 'v1.0.0'

  const rows = [
    { icon: <WifiIcon on={Boolean(systemInfo?.wifi?.status)} />, label: 'Wi-Fi / LAN', value: wifiVal },
    { icon: <PrinterIcon on />, label: 'Printer', value: printerVal },
    { icon: <CameraIcon on />, label: 'Camera', value: cameraVal },
  ]

  return (
    <div className="screen">
      <Bar>
        <IconButton label="Back" onClick={onBack}><BackIcon /></IconButton>
        <span className="bar-title title-after-back">Settings</span>
        {loading && <span className="mono" style={{ fontSize: '9px', color: 'var(--dim)', marginLeft: 'auto' }}>Syncing...</span>}
      </Bar>
      <div className="settings-list scroll-hidden">
        {rows.map((row) => (
          <div className="settings-row" key={row.label}>
            {row.icon}
            <span>{row.label}</span>
            <small>{row.value}</small>
          </div>
        ))}
        <div className="brightness">
          <div>
            <span>Brightness</span>
            <small>{brightness}%</small>
          </div>
          <div
            className="brightness-track"
            onClick={(e) => {
              const rect = e.currentTarget.getBoundingClientRect()
              const pct = Math.max(30, Math.min(100, Math.round(((e.clientX - rect.left) / rect.width) * 100)))
              onBrightnessChange?.(pct)
            }}
            style={{ cursor: 'pointer' }}
          >
            <div className="brightness-fill" style={{ width: `${brightness}%` }} />
            <i style={{ left: `${brightness}%` }} />
          </div>
        </div>
        <div className="settings-row about-row">
          <span>System</span>
          <small className="mono">{appVer} · {osVal}</small>
        </div>
        <div className="settings-row">
          <span>AI Engines</span>
          <small className="mono">Whisper + Gemini</small>
        </div>
      </div>
    </div>
  )
}

const historyFilterTabs = [
  { id: 'all', label: 'All' },
  { id: 'study', label: 'Study' },
  { id: 'inventory', label: 'Inventory' },
  { id: 'product', label: 'Product' },
  { id: 'qr', label: 'QR Code' },
]

function History({ onBack, onReprint, items = [], isPrinting = false }) {
  const [selectedGroup, setSelectedGroup] = useState('all')

  const filteredItems = useMemo(() => {
    if (selectedGroup === 'all') return items
    return items.filter((item) => (item.mode || 'study').toLowerCase() === selectedGroup)
  }, [items, selectedGroup])

  return (
    <div className="screen">
      <Bar>
        <IconButton label="Back" onClick={onBack}><BackIcon /></IconButton>
        <span className="bar-title title-after-back">History</span>
        <span className="history-count">{filteredItems.length} {filteredItems.length === 1 ? 'item' : 'items'}</span>
      </Bar>

      <div className="history-filter-bar scroll-hidden">
        {historyFilterTabs.map((tab) => {
          const count = tab.id === 'all'
            ? items.length
            : items.filter((it) => (it.mode || 'study').toLowerCase() === tab.id).length
          return (
            <button
              key={tab.id}
              className={`history-filter-btn ${selectedGroup === tab.id ? 'active' : ''}`}
              onClick={() => setSelectedGroup(tab.id)}
            >
              <span>{tab.label}</span>
              <span className="history-filter-badge">{count}</span>
            </button>
          )
        })}
      </div>

      <div className="history-list scroll-hidden">
        {filteredItems.length === 0 ? (
          <div className="center-body" style={{ color: 'var(--dim)', fontSize: 'var(--fs-xs)', height: '110px' }}>
            No {selectedGroup === 'all' ? 'print' : selectedGroup} history yet
          </div>
        ) : (
          filteredItems.map((item) => {
            const itemMode = (item.mode || 'study').toUpperCase()
            return (
              <div className="history-row" key={item.id}>
                <div className="history-copy">
                  <div className="history-title-row">
                    <span className="history-title-text">{item.title}</span>
                    <span className={`history-mode-pill mode-${(item.mode || 'study').toLowerCase()}`}>{itemMode}</span>
                  </div>
                  <span>{item.desc}</span>
                </div>
                <span className="mono history-time">{item.time}</span>
                <IconButton
                  label={`Reprint ${item.title}`}
                  disabled={isPrinting}
                  onClick={() => onReprint(item)}
                >
                  <RetryIcon />
                </IconButton>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}

function useDisplayScale() {
  const [scale, setScale] = useState(1)
  useLayoutEffect(() => {
    const update = () => setScale(Math.min(window.innerWidth / 320, window.innerHeight / 240))
    update()
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
  }, [])
  return scale
}

export default function App() {
  const [screen, setScreen] = useState('home')
  const [mode, setMode] = useState('study')
  const [inputMethod, setInputMethod] = useState('voice')
  const [referenceImage, setReferenceImage] = useState(null)
  const [generatedImage, setGeneratedImage] = useState(null)
  const [generationError, setGenerationError] = useState('')
  const [printError, setPrintError] = useState('')
  const [isPrinting, setIsPrinting] = useState(false)
  const [voiceTranscript, setVoiceTranscript] = useState('')
  const [historyItems, setHistoryItems] = useState([])
  const [brightness, setBrightness] = useState(85)
  const [deviceSource, setDeviceSource] = useState('usb')
  const scale = useDisplayScale()
  const go = useCallback((next) => setScreen(next), [])

  const fetchHistory = useCallback(async () => {
    try {
      const response = await fetch('/api/history')
      if (response.ok) {
        const data = await response.json()
        if (Array.isArray(data)) {
          setHistoryItems(data)
        }
      }
    } catch {
      // Fallback silently if offline
    }
  }, [])

  useEffect(() => {
    fetchHistory()
  }, [fetchHistory])

  const openHistory = () => {
    fetchHistory()
    go('history')
  }

  const generateStudyImage = async (prompt = exampleStudyPrompt) => {
    setGenerationError('')
    go('processing')
    try {
      const response = await fetch('/study/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: prompt || exampleStudyPrompt, image_data: referenceImage }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Unable to generate the image.')
      setGeneratedImage(data.image_url)
      fetchHistory()
      go('preview')
    } catch (error) {
      setGenerationError(error.message || 'Unable to generate the image.')
    }
  }

  const extractErrorMessage = (data, fallback = 'Operation failed.') => {
    if (!data) return fallback
    if (typeof data.detail === 'string') return data.detail
    if (Array.isArray(data.detail) && data.detail.length > 0) {
      return data.detail[0]?.msg || fallback
    }
    if (data.message) return data.message
    return fallback
  }

  const printCurrentLabel = async (reprintItem = null) => {
    setPrintError('')
    setIsPrinting(true)
    try {
      let base64Image = ''
      let itemTitle = ''
      let itemDesc = ''
      let itemMode = mode
      let targetImageUrl = null

      if (reprintItem) {
        itemTitle = reprintItem.title
        itemDesc = reprintItem.desc
        itemMode = reprintItem.mode || mode
        targetImageUrl = reprintItem.image_url || reprintItem.imageUrl

        if (reprintItem.imageBase64) {
          base64Image = reprintItem.imageBase64
        } else if (targetImageUrl) {
          const imageResponse = await fetch(targetImageUrl)
          if (!imageResponse.ok) throw new Error('Could not read the history diagram image.')
          const imageBlob = await imageResponse.blob()
          base64Image = await new Promise((resolve, reject) => {
            const reader = new FileReader()
            reader.onload = () => resolve(reader.result)
            reader.onerror = () => reject(new Error('Could not prepare the image for printing.'))
            reader.readAsDataURL(imageBlob)
          })
        } else {
          const currentMode = reprintItem.mode || mode
          const previewItem = previews[currentMode] || { title: 'PrintSensei Label', desc: '' }
          const title = reprintItem.title || previewItem.title
          const desc = reprintItem.desc || ''
          const qrPayload = currentMode === 'qr' ? title : (title || 'https://printsensei.local')
          
          const renderRes = await fetch('/render', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              title: title,
              subtitle: modeNames[currentMode] || 'PrintSensei',
              body: desc,
              date: new Date().toISOString().split('T')[0],
              qr_data: qrPayload,
              template: currentMode,
              label_type: currentMode,
            }),
          })
          const renderData = await renderRes.json()
          if (!renderRes.ok) throw new Error(extractErrorMessage(renderData, 'Could not render label.'))
          targetImageUrl = `/${renderData.file}`
          const imageResponse = await fetch(targetImageUrl)
          if (!imageResponse.ok) throw new Error('Could not read the rendered label image.')
          const imageBlob = await imageResponse.blob()
          base64Image = await new Promise((resolve, reject) => {
            const reader = new FileReader()
            reader.onload = () => resolve(reader.result)
            reader.onerror = () => reject(new Error('Could not prepare the image for printing.'))
            reader.readAsDataURL(imageBlob)
          })
        }
      } else if (generatedImage) {
        itemTitle = voiceTranscript || 'BMW Engine Overview'
        itemDesc = 'AI generated diagram'
        itemMode = 'study'
        targetImageUrl = generatedImage
        const imageResponse = await fetch(generatedImage)
        if (!imageResponse.ok) throw new Error('Could not read the generated image.')
        const imageBlob = await imageResponse.blob()
        base64Image = await new Promise((resolve, reject) => {
          const reader = new FileReader()
          reader.onload = () => resolve(reader.result)
          reader.onerror = () => reject(new Error('Could not prepare the image for printing.'))
          reader.readAsDataURL(imageBlob)
        })
      } else {
        const currentMode = mode
        const previewItem = previews[currentMode] || { title: 'PrintSensei Label', desc: '' }
        const transcriptLines = (voiceTranscript || '').split('\n').map((l) => l.trim()).filter(Boolean)
        const title = transcriptLines.length > 0 ? transcriptLines[0] : (voiceTranscript || previewItem.title)
        
        let price = null
        let bodyLines = []
        if (currentMode === 'product') {
          for (let i = 1; i < transcriptLines.length; i++) {
            const line = transcriptLines[i]
            const priceMatch = line.match(/^(?:price\s*[:=]?\s*|rs\.?\s*|₹\s*|\$\s*)?(\d+(?:\.\d+)?)$/i)
            if (priceMatch && price === null) {
              price = parseFloat(priceMatch[1])
            } else {
              bodyLines.push(line)
            }
          }
        } else {
          bodyLines = transcriptLines.length > 1 ? transcriptLines.slice(1) : []
        }
        
        const desc = bodyLines.join('\n')
        itemTitle = title
        itemDesc = desc
        itemMode = currentMode
        const qrPayload = currentMode === 'qr' ? title : (title || 'https://printsensei.local')
        
        const renderRes = await fetch('/render', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: title,
            subtitle: modeNames[currentMode] || 'PrintSensei',
            body: desc,
            price: price,
            date: new Date().toISOString().split('T')[0],
            qr_data: qrPayload,
            template: currentMode,
            label_type: currentMode,
          }),
        })
        const renderData = await renderRes.json()
        if (!renderRes.ok) throw new Error(extractErrorMessage(renderData, 'Could not render label.'))
        targetImageUrl = `/${renderData.file}`
        const imageResponse = await fetch(targetImageUrl)
        if (!imageResponse.ok) throw new Error('Could not read the rendered label image.')
        const imageBlob = await imageResponse.blob()
        base64Image = await new Promise((resolve, reject) => {
          const reader = new FileReader()
          reader.onload = () => resolve(reader.result)
          reader.onerror = () => reject(new Error('Could not prepare the image for printing.'))
          reader.readAsDataURL(imageBlob)
        })
      }

      const response = await fetch('/api/print', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_base64: base64Image,
          label_width_mm: 50,
          label_height_mm: 50,
          gap_mm: 2,
          title: itemTitle,
          desc: itemDesc,
          mode: itemMode,
          image_url: targetImageUrl,
        }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(extractErrorMessage(data, 'The printer rejected the print job.'))

      fetchHistory()
      go('printing')
    } catch (error) {
      setPrintError(error.message || 'Could not send the print job.')
    } finally {
      setIsPrinting(false)
    }
  }

  useEffect(() => {
    if (screen !== 'processing' || mode === 'study' || generationError) return undefined
    const timer = window.setTimeout(() => go('preview'), 2000)
    return () => window.clearTimeout(timer)
  }, [screen, mode, generationError, go])

  const selectMethod = (method) => { setInputMethod(method); setGeneratedImage(null); if (method !== 'camera+voice') setReferenceImage(null); go(method === 'camera+voice' ? 'camera-capture' : 'capture') }
  const renderScreen = () => {
    switch (screen) {
      case 'mode-select': return <ModeSelect onSelect={(value) => { setMode(value); go('input-method') }} onBack={() => go('home')} onSettings={() => go('settings')} />
      case 'input-method': return <InputMethod mode={mode} onSelect={selectMethod} onBack={() => go('mode-select')} />
      case 'camera-capture': return <CameraCapture source={deviceSource} onSourceChange={setDeviceSource} onCaptured={(image) => { setReferenceImage(image); go('capture') }} onBack={() => go('input-method')} />
      case 'capture': return <Capture mode={mode} inputMethod={inputMethod} source={deviceSource} onSourceChange={setDeviceSource} onCapture={(text) => { setVoiceTranscript(text || ''); go('voice-result') }} onBack={() => go('input-method')} />
      case 'voice-result': return <VoiceResult transcript={voiceTranscript} hasReferenceImage={Boolean(referenceImage)} onBack={() => go('home')} onGenerate={() => mode === 'study' ? generateStudyImage(voiceTranscript) : go('preview')} />
      case 'processing': return <Processing onCancel={() => go('home')} error={generationError} />
      case 'preview': return <Preview mode={mode} transcript={voiceTranscript} generatedImage={generatedImage} isPrinting={isPrinting} printError={printError} onEdit={() => go('capture')} onPrint={() => printCurrentLabel()} />
      case 'printing': return <Printing onDone={() => go('home')} />
      case 'settings': return <Settings onBack={() => go('home')} brightness={brightness} onBrightnessChange={setBrightness} />
      case 'history': return <History items={historyItems} isPrinting={isPrinting} onBack={() => go('home')} onReprint={(item) => printCurrentLabel(item)} />
      default: return <Home onStart={() => go('mode-select')} onSettings={() => go('settings')} onHistory={openHistory} />
    }
  }

  return <main className="lcd-viewport"><div className="lcd-screen" style={{ transform: `scale(${scale})`, filter: `brightness(${brightness}%)` }}>{renderScreen()}</div></main>
}

