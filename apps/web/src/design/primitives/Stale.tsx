/** "As of" chip; turns madder past the staleness threshold.
 * Staleness is shown, never hidden. */
export function Stale({ asOf, stale = false }: { asOf: string; stale?: boolean }) {
  return (
    <span
      className="legend-strip"
      data-numeric
      style={{
        color: stale ? 'var(--madder)' : 'var(--text-tertiary)',
        border: `1px solid ${stale ? 'color-mix(in srgb, var(--madder) 50%, transparent)' : 'var(--rule)'}`,
        borderRadius: 'var(--radius-panel)',
        padding: '2px 8px',
      }}
    >
      as of {asOf}
      {stale ? ' · stale' : ''}
    </span>
  )
}
