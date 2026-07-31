/** 56×18, single stroke, no axes, no fill. */
export function Sparkline({
  points,
  stroke = 'var(--phosphor)',
}: {
  points: number[]
  stroke?: string
}) {
  if (points.length < 2) return null
  const w = 56
  const h = 18
  const min = Math.min(...points)
  const max = Math.max(...points)
  const span = max - min || 1
  const d = points
    .map((p, i) => {
      const x = (i / (points.length - 1)) * (w - 2) + 1
      const y = h - 2 - ((p - min) / span) * (h - 4)
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
  return (
    <svg width={w} height={h} aria-hidden style={{ display: 'block' }}>
      <path d={d} fill="none" stroke={stroke} strokeWidth={1.25} />
    </svg>
  )
}
