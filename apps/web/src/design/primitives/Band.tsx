/** Bear/base/bull horizontal range with base marker and n= readout.
 * The band is an empirical quantile, not an opinion — show the honest bear. */
export function Band({
  bearPct,
  basePct,
  bullPct,
  nAnalogues,
}: {
  bearPct: number
  basePct: number
  bullPct: number
  nAnalogues: number
}) {
  const lo = Math.min(bearPct, 0)
  const hi = Math.max(bullPct, 0)
  const span = hi - lo || 1
  const x = (v: number) => ((v - lo) / span) * 100
  const fmt = (v: number) => `${v > 0 ? '+' : ''}${v.toFixed(1)}%`

  return (
    <div>
      <div
        style={{ position: 'relative', height: 22, marginBlock: 'var(--spacing-2)' }}
        role="img"
        aria-label={`Scenario band: bear ${fmt(bearPct)}, base ${fmt(basePct)}, bull ${fmt(
          bullPct,
        )}, from ${nAnalogues} analogues`}
      >
        {/* zero line */}
        <div
          style={{
            position: 'absolute',
            left: `${x(0)}%`,
            top: 0,
            bottom: 0,
            width: 1,
            background: 'var(--rule)',
          }}
        />
        {/* range */}
        <div
          style={{
            position: 'absolute',
            left: `${x(bearPct)}%`,
            width: `${x(bullPct) - x(bearPct)}%`,
            top: 8,
            height: 6,
            borderRadius: 1,
            background:
              'linear-gradient(90deg, color-mix(in srgb, var(--madder) 55%, transparent), color-mix(in srgb, var(--phosphor) 45%, transparent), color-mix(in srgb, var(--jade) 55%, transparent))',
          }}
        />
        {/* base marker */}
        <div
          style={{
            position: 'absolute',
            left: `${x(basePct)}%`,
            top: 4,
            height: 14,
            width: 2,
            background: 'var(--phosphor)',
          }}
        />
      </div>
      <div
        data-numeric
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          font: '400 var(--t-data) var(--font-data)',
          color: 'var(--text-secondary)',
        }}
      >
        <span style={{ color: 'var(--madder)' }}>{fmt(bearPct)}</span>
        <span style={{ color: 'var(--text-primary)' }}>{fmt(basePct)}</span>
        <span style={{ color: 'var(--jade)' }}>{fmt(bullPct)}</span>
      </div>
      <div className="legend-strip" data-numeric style={{ color: 'var(--text-tertiary)', marginTop: 4 }}>
        n={nAnalogues} analogues
      </div>
    </div>
  )
}
