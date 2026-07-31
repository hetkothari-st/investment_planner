import { useState } from 'react'
import { Needle } from './Needle'
import { Verdict, type VerdictSeverity } from './Verdict'

/** The dashboard signature: a machined instrument face measuring the
 * instrument. Three needles point at measured direction hit rate on an arc
 * from 30% to 80%, with the coin-flip mark engraved at 50%. SVG, not three.js
 * — vector is sharper and the depth comes from layered gradients. */

export type HorizonCalibration = {
  horizon: 'SHORT' | 'MID' | 'LONG'
  /** measured direction hit rate, percent; null when unscored */
  hitRatePct: number | null
  n: number
  netAlphaPct: number | null
  brier: number | null
  verdict: string
  severity: VerdictSeverity
}

const MIN_N = 20
const ARC_START = -120
const ARC_END = 120
const ARC_MIN = 30
const ARC_MAX = 80
const DETENT_ANGLE = ARC_START - 14

const angleFor = (pct: number) =>
  ARC_START + ((pct - ARC_MIN) / (ARC_MAX - ARC_MIN)) * (ARC_END - ARC_START)

/** angle 0 = up, positive clockwise */
const polar = (cx: number, cy: number, r: number, angleDeg: number) => {
  const rad = ((angleDeg - 90) * Math.PI) / 180
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) }
}

const arcPath = (cx: number, cy: number, r: number, a0: number, a1: number) => {
  const p0 = polar(cx, cy, r, a0)
  const p1 = polar(cx, cy, r, a1)
  const large = Math.abs(a1 - a0) > 180 ? 1 : 0
  return `M ${p0.x} ${p0.y} A ${r} ${r} 0 ${large} 1 ${p1.x} ${p1.y}`
}

const NEEDLE_LEN: Record<HorizonCalibration['horizon'], number> = {
  SHORT: 96,
  MID: 116,
  LONG: 136,
}

export function CalibrationDial({
  horizons,
  size = 360,
}: {
  horizons: HorizonCalibration[]
  size?: number
}) {
  const [hovered, setHovered] = useState<HorizonCalibration | null>(null)
  const c = 180
  const faceR = 158
  const totalScored = horizons.reduce((s, h) => s + h.n, 0)

  const textAlt = horizons
    .map((h) =>
      h.n < MIN_N
        ? `${h.horizon}: uncalibrated, ${h.n} of ${MIN_N} scored calls needed`
        : `${h.horizon}: ${h.hitRatePct}% direction hit rate over ${h.n} scored calls`,
    )
    .join('. ')

  const ticks = []
  for (let v = ARC_MIN; v <= ARC_MAX; v += 2) {
    const major = v % 10 === 0
    const a = angleFor(v)
    const outer = polar(c, c, faceR - 10, a)
    const inner = polar(c, c, faceR - (major ? 22 : 16), a)
    ticks.push(
      <line
        key={v}
        x1={inner.x}
        y1={inner.y}
        x2={outer.x}
        y2={outer.y}
        stroke="var(--text-tertiary)"
        strokeWidth={major ? 2 : 1}
        opacity={major ? 1 : 0.3}
      />,
    )
  }

  return (
    <figure style={{ margin: 0, maxWidth: size }}>
      <div style={{ position: 'relative' }}>
        <svg
          viewBox="0 0 360 360"
          role="img"
          aria-label={`Calibration dial. ${textAlt}`}
          style={{ display: 'block', width: '100%' }}
        >
          <defs>
            <radialGradient id="bezel" cx="35%" cy="30%">
              <stop offset="0%" stopColor="var(--panel-raised)" />
              <stop offset="70%" stopColor="var(--rule)" />
              <stop offset="100%" stopColor="var(--ink)" />
            </radialGradient>
            <filter id="brushed">
              <feTurbulence type="fractalNoise" baseFrequency="0.9 0.02" numOctaves="2" result="n" />
              <feColorMatrix in="n" type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 0.05 0" result="grain" />
              <feComposite in="grain" in2="SourceGraphic" operator="atop" />
            </filter>
            <radialGradient id="faceShade" cx="50%" cy="50%">
              <stop offset="82%" stopColor="var(--panel)" />
              <stop offset="100%" stopColor="var(--ink)" />
            </radialGradient>
          </defs>

          {/* 1. bezel ring, brushed */}
          <circle cx={c} cy={c} r={faceR + 12} fill="url(#bezel)" filter="url(#brushed)" />
          {/* 2. face with inner shadow from bezel */}
          <circle cx={c} cy={c} r={faceR} fill="url(#faceShade)" />

          {/* 3. sub-50% sector, subtly darker */}
          <path
            d={`${arcPath(c, c, faceR - 2, ARC_START, angleFor(50))} L ${c} ${c} Z`}
            fill="var(--ink)"
            opacity={0.4}
          />

          {/* 4. ticks */}
          {ticks}

          {/* 5. engraved numerals along the arc */}
          {[30, 40, 50, 60, 70, 80].map((v) => {
            const p = polar(c, c, faceR - 34, angleFor(v))
            return (
              <text
                key={v}
                x={p.x}
                y={p.y}
                textAnchor="middle"
                dominantBaseline="middle"
                fill="var(--text-tertiary)"
                style={{ font: '400 10px var(--font-data)', fontVariantNumeric: 'tabular-nums' }}
              >
                {v}
              </text>
            )
          })}

          {/* 6. coin-flip mark */}
          {(() => {
            const a = angleFor(50)
            const p0 = polar(c, c, faceR - 24, a)
            const p1 = polar(c, c, faceR - 4, a)
            const label = polar(c, c, faceR - 52, a)
            return (
              <g>
                <line x1={p0.x} y1={p0.y} x2={p1.x} y2={p1.y} stroke="var(--madder)" strokeWidth={1} />
                <text
                  x={label.x}
                  y={label.y}
                  textAnchor="middle"
                  fill="var(--madder)"
                  opacity={0.8}
                  style={{ font: '600 7px var(--font-ui)', letterSpacing: '0.14em' }}
                >
                  COIN FLIP
                </text>
              </g>
            )
          })()}

          {/* 7. needles */}
          {horizons.map((h) => {
            const calibrated = h.n >= MIN_N && h.hitRatePct !== null
            return (
              <g
                key={h.horizon}
                onMouseEnter={() => setHovered(h)}
                onMouseLeave={() => setHovered(null)}
                style={{ cursor: 'default' }}
              >
                <Needle
                  cx={c}
                  cy={c}
                  length={NEEDLE_LEN[h.horizon]}
                  angleDeg={calibrated ? angleFor(h.hitRatePct as number) : DETENT_ANGLE}
                  color={calibrated ? 'var(--phosphor)' : 'var(--text-tertiary)'}
                  animate={calibrated}
                />
              </g>
            )
          })}

          {/* detent label when anything is uncalibrated */}
          {horizons.some((h) => h.n < MIN_N) && (
            <text
              x={polar(c, c, faceR - 44, DETENT_ANGLE).x}
              y={polar(c, c, faceR - 44, DETENT_ANGLE).y + 12}
              textAnchor="middle"
              fill="var(--text-tertiary)"
              style={{ font: '600 7px var(--font-ui)', letterSpacing: '0.14em' }}
            >
              UNCALIBRATED
            </text>
          )}

          {/* 8. hub */}
          <circle cx={c} cy={c} r={7} fill="var(--brass)" stroke="var(--ink)" strokeWidth={1} />
        </svg>

        {/* hover readout */}
        {hovered && (
          <div
            className="panel-bevel"
            data-numeric
            style={{
              position: 'absolute',
              top: 8,
              right: 8,
              padding: 'var(--spacing-2) var(--spacing-3)',
              background: 'var(--panel-raised)',
              font: '400 var(--t-data) var(--font-data)',
              color: 'var(--text-primary)',
            }}
          >
            <div className="legend-strip" style={{ color: 'var(--phosphor)' }}>
              {hovered.horizon}
            </div>
            <div>hit {hovered.hitRatePct !== null ? `${hovered.hitRatePct}%` : '—'} · n={hovered.n}</div>
            <div>
              alpha {hovered.netAlphaPct !== null ? `${hovered.netAlphaPct > 0 ? '+' : ''}${hovered.netAlphaPct}%` : '—'} · brier{' '}
              {hovered.brier ?? '—'}
            </div>
          </div>
        )}
      </div>

      <figcaption
        className="legend-strip"
        data-numeric
        style={{ textAlign: 'center', color: 'var(--text-secondary)', marginTop: 'var(--spacing-2)' }}
      >
        calibration · n={totalScored} scored calls
      </figcaption>

      {/* Accessible twin: identical data, directly beneath, never hidden. */}
      <table
        style={{ width: '100%', borderCollapse: 'collapse', marginTop: 'var(--spacing-3)' }}
      >
        <thead>
          <tr>
            {['Horizon', 'Hit rate', 'n', 'Net alpha', 'Brier'].map((h, i) => (
              <th
                key={h}
                className="legend-strip"
                style={{
                  textAlign: i === 0 ? 'left' : 'right',
                  color: 'var(--text-secondary)',
                  padding: '6px 8px',
                  borderBottom: '1px solid var(--brass)',
                }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {horizons.map((h) => {
            const gated = h.n < MIN_N
            return (
              <tr
                key={h.horizon}
                style={{ boxShadow: 'inset 0 -1px 0 color-mix(in srgb, var(--rule) 50%, transparent)' }}
              >
                <td style={{ padding: '8px', color: 'var(--text-primary)' }}>{h.horizon}</td>
                <Num v={gated ? `${h.n} / ${MIN_N} needed` : h.hitRatePct !== null ? `${h.hitRatePct}%` : '—'} dim={gated} />
                <Num v={String(h.n)} />
                <Num v={gated || h.netAlphaPct === null ? '—' : `${h.netAlphaPct > 0 ? '+' : ''}${h.netAlphaPct}%`} />
                <Num v={gated || h.brier === null ? '—' : String(h.brier)} />
              </tr>
            )
          })}
        </tbody>
      </table>

      <div style={{ display: 'grid', gap: 'var(--spacing-2)', marginTop: 'var(--spacing-3)' }}>
        {horizons.map((h) => (
          <Verdict key={h.horizon} severity={h.severity}>
            {h.verdict}
          </Verdict>
        ))}
      </div>
    </figure>
  )
}

function Num({ v, dim = false }: { v: string; dim?: boolean }) {
  return (
    <td
      data-numeric
      style={{
        padding: '8px',
        textAlign: 'right',
        font: '400 var(--t-data) var(--font-data)',
        color: dim ? 'var(--text-tertiary)' : 'var(--text-primary)',
        whiteSpace: 'nowrap',
      }}
    >
      {v}
    </td>
  )
}
