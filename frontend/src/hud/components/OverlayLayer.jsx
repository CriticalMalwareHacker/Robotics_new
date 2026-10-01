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
      preserveAspectRatio="none"
      aria-hidden
      className="pointer-events-none absolute inset-0 h-full w-full"
      style={faded ? { opacity: 0.4 } : undefined}
    >
      {slots.map((s) => {
        const [x, y] = topLeft(s.polygon_px)
        return (
          <g key={s.name}>
            <polygon points={poly(s.polygon_px)} fill="none" stroke="#fff" strokeOpacity="0.6" strokeWidth="1.5" />
            <text x={x + 4} y={y + 16} fontSize="12" fill="#fff" fillOpacity="0.9">{s.name}</text>
          </g>
        )
      })}
      {vehicles.map((v) => {
        const bad = v.valid === false
        const color = bad ? '#EF4444' : '#22C55E'
        const [x, y] = topLeft(v.polygon_px)
        const label = `${v.id || ''}  ${v.slot || ''}  ${v.valid == null ? '' : v.valid ? 'Legal' : 'Violation'}`.trim()
        return (
          <g key={v.id}>
            <polygon points={poly(v.polygon_px)} fill="none" stroke={color} strokeWidth="2" />
            <text x={x} y={Math.max(14, y - 6)} fontSize="12" fill={color}>{label}</text>
            {show.plates && v.plate && (
              <text x={x} y={y + 30} fontSize="12" fill="#fff">{v.plate}</text>
            )}
          </g>
        )
      })}
      {/* Robot pose, target and home render here once tracking lands. */}
    </svg>
  )
}
