/** Blocked/passed with the reason printed. Used all over the planner —
 * a blocked gate names why, because the block is the product working. */
export function Gate({
  label,
  passed,
  reason,
  amount,
}: {
  label: string
  passed: boolean
  reason: string
  /** pre-formatted rupee amount routed through this gate, if any */
  amount?: string
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'baseline',
        gap: 'var(--spacing-3)',
        padding: 'var(--spacing-3)',
        border: '1px solid var(--rule)',
        borderRadius: 'var(--radius-panel)',
        background: passed ? 'transparent' : 'color-mix(in srgb, var(--madder) 6%, transparent)',
      }}
    >
      <span
        className="legend-strip"
        style={{ color: passed ? 'var(--jade)' : 'var(--madder)', flexShrink: 0 }}
      >
        {passed ? 'passed' : 'blocked'}
      </span>
      <div style={{ flex: 1 }}>
        <div style={{ font: '600 var(--t-body) var(--font-ui)', color: 'var(--text-primary)' }}>
          {label}
        </div>
        <div style={{ color: 'var(--text-secondary)', fontSize: 'var(--t-data)' }}>{reason}</div>
      </div>
      {amount && (
        <span data-numeric style={{ font: '400 var(--t-data) var(--font-data)', color: 'var(--text-primary)' }}>
          {amount}
        </span>
      )}
    </div>
  )
}
