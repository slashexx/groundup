import { useCallback, useRef } from 'react'

interface GaugeProps {
  min: number
  max: number
  /** Distinct floor base heights (display metres) — drawn as tick dashes. */
  floors: number[]
  value: number
  cutEnabled: boolean
  showUnderground: boolean
  onValue: (v: number) => void
  onCutToggle: (on: boolean) => void
  onUndergroundToggle: (on: boolean) => void
}

/**
 * Elevation gauge: a graduated height scale in metres (ground line at ±0,
 * hatched below-grade zone, floor marks from the data) that doubles as the
 * section-cut control — drag the red handle to slice the scene at that
 * elevation. The signature control of the viewer: vertical property, made
 * into a vertical instrument.
 */
export function Gauge({
  min,
  max,
  floors,
  value,
  cutEnabled,
  showUnderground,
  onValue,
  onCutToggle,
  onUndergroundToggle,
}: GaugeProps) {
  const trackRef = useRef<HTMLDivElement>(null)
  const span = max - min
  const topPct = (v: number) => ((max - v) / span) * 100

  const valueFromPointer = useCallback(
    (clientY: number) => {
      const rect = trackRef.current!.getBoundingClientRect()
      const frac = Math.min(1, Math.max(0, (clientY - rect.top) / rect.height))
      return Math.round((max - frac * span) * 5) / 5
    },
    [max, span],
  )

  const startDrag = (e: React.PointerEvent) => {
    e.preventDefault()
    if (!cutEnabled) onCutToggle(true)
    onValue(valueFromPointer(e.clientY))
    const move = (ev: PointerEvent) => onValue(valueFromPointer(ev.clientY))
    const up = () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
  }

  const onKey = (e: React.KeyboardEvent) => {
    const step = e.key === 'PageUp' ? 3 : e.key === 'PageDown' ? -3 : e.key === 'ArrowUp' ? 0.5 : e.key === 'ArrowDown' ? -0.5 : null
    if (step == null) return
    e.preventDefault()
    if (!cutEnabled) onCutToggle(true)
    onValue(Math.min(max, Math.max(min, value + step)))
  }

  const majors: number[] = []
  for (let m = Math.ceil(min / 5) * 5; m <= max; m += 5) majors.push(m)

  return (
    <div className="gauge" aria-label="Elevation gauge">
      <button
        type="button"
        className={`gauge-btn ${cutEnabled ? 'on' : ''}`}
        aria-pressed={cutEnabled}
        onClick={() => onCutToggle(!cutEnabled)}
        title="Section cut: hide everything above the handle"
      >
        cut
      </button>

      <div
        ref={trackRef}
        className={`gauge-track ${cutEnabled ? 'cutting' : ''}`}
        onPointerDown={startDrag}
        role="slider"
        tabIndex={0}
        aria-label="Section cut elevation, metres above ground"
        aria-valuemin={min}
        aria-valuemax={max}
        aria-valuenow={cutEnabled ? value : max}
        aria-disabled={!cutEnabled}
        onKeyDown={onKey}
      >
        {/* below-grade zone */}
        <div className="gauge-below" style={{ top: `${topPct(0)}%` }} />

        {majors.map((m) => (
          <div key={m} className={`gauge-tick ${m === 0 ? 'zero' : ''}`} style={{ top: `${topPct(m)}%` }}>
            <span>{m === 0 ? 'GL ±0' : `${m > 0 ? '+' : ''}${m}`}</span>
          </div>
        ))}

        {floors.map((f) => (
          <div key={f} className="gauge-floor" style={{ top: `${topPct(f)}%` }} />
        ))}

        {cutEnabled && (
          <div className="gauge-handle" style={{ top: `${topPct(value)}%` }}>
            <span className="gauge-value">{value.toFixed(1)} m</span>
          </div>
        )}
      </div>

      <button
        type="button"
        className={`gauge-btn ${showUnderground ? 'on' : ''}`}
        aria-pressed={showUnderground}
        onClick={() => onUndergroundToggle(!showUnderground)}
        title="Below grade: fade the ground, reveal underground volumes"
      >
        b.g.
      </button>
    </div>
  )
}
