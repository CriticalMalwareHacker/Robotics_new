/* Client-side vector overlay: slots, vehicles, plate tags, robot, target.
 * Drawn on a transparent SVG exactly over the video (same aspect box). */
export default function OverlayLayer({ frame, parking, show, faded }) {
  const W = frame?.width || 1280
  const H = frame?.height || 720
  const slots = (parking?.slots || []).filter(() => show.slots)
  const vehicles = (parking?.vehicles || []).filter(() => show.vehicles)

  const poly = (pts) => (pts || []).map((p) => p.join(',')).join(' ')
  const topLeft = (pts) => {
    const xs = (pts || []).map((p) => p[0])
    const ys = (pts || []).map((p) => p[1])
    return [Math.min(...xs), Math.min(...ys)]
  }

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="xMidYMid meet"
      aria-hidden
      className="pointer-events-none absolute inset-0 h-full w-full select-none"
      style={faded ? { opacity: 0.35 } : undefined}
    >
      <defs>
        <filter id="hud-text-shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="1" stdDeviation="1.5" floodColor="#000" floodOpacity="0.8" />
        </filter>
      </defs>

      {/* Parking Slots */}
      {slots.map((s) => {
        const [x, y] = topLeft(s.polygon_px)
        return (
          <g key={s.name}>
            <polygon
              points={poly(s.polygon_px)}
              fill="rgba(56, 189, 248, 0.04)"
              stroke="rgba(56, 189, 248, 0.7)"
              strokeWidth="2"
              strokeDasharray="6 3"
              strokeLinejoin="round"
            />
            <rect
              x={x + 3}
              y={y + 3}
              width={Math.max(48, s.name.length * 8 + 10)}
              height="18"
              rx="4"
              fill="rgba(15, 23, 42, 0.75)"
              stroke="rgba(56, 189, 248, 0.4)"
              strokeWidth="1"
            />
            <text
              x={x + 8}
              y={y + 16}
              fontSize="11"
              fontFamily="monospace"
              fontWeight="bold"
              fill="#38bdf8"
            >
              {s.name}
            </text>
          </g>
        )
      })}

      {/* Detected Vehicles */}
      {vehicles.map((v) => {
        const bad = v.valid === false
        const strokeColor = bad ? '#ef4444' : '#10b981'
        const fillColor = bad ? 'rgba(239, 68, 68, 0.18)' : 'rgba(16, 185, 129, 0.12)'
        const [x, y] = topLeft(v.polygon_px)
        const label = `${v.id || ''} ${v.slot ? `· ${v.slot}` : ''} ${
          v.valid == null ? '' : v.valid ? 'LEGAL' : 'VIOLATION'
        }`.trim()

        return (
          <g key={v.id}>
            <polygon
              points={poly(v.polygon_px)}
              fill={fillColor}
              stroke={strokeColor}
              strokeWidth="2.5"
              strokeLinejoin="round"
            />
            <rect
              x={x}
              y={Math.max(4, y - 22)}
              width={Math.max(70, label.length * 7 + 12)}
              height="20"
              rx="4"
              fill={bad ? 'rgba(185, 28, 28, 0.9)' : 'rgba(15, 23, 42, 0.85)'}
              stroke={strokeColor}
              strokeWidth="1"
            />
            <text
              x={x + 6}
              y={Math.max(18, y - 8)}
              fontSize="11"
              fontFamily="monospace"
              fontWeight="bold"
              fill="#ffffff"
              filter="url(#hud-text-shadow)"
            >
              {label}
            </text>

            {show.plates && v.plate && (
              <g>
                <rect
                  x={x}
                  y={y + 26}
                  width={v.plate.length * 8 + 14}
                  height="18"
                  rx="3"
                  fill="#ffffff"
                  stroke="#000000"
                  strokeWidth="1.5"
                />
                <text
                  x={x + 6}
                  y={y + 39}
                  fontSize="11"
                  fontFamily="monospace"
                  fontWeight="900"
                  fill="#000000"
                  letterSpacing="1"
                >
                  {v.plate}
                </text>
              </g>
            )}
          </g>
        )
      })}
    </svg>
  )
}
