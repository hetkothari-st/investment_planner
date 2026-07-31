/** Condition + current value + distance to breach + status pip.
 * Thesis-breakage, not price movement, is what gets surfaced. */
export type FalsifierStatus = 'intact' | 'near' | 'breached'

const PIP: Record<FalsifierStatus, string> = {
  intact: 'var(--jade)',
  near: 'var(--brass)',
  breached: 'var(--madder)',
}

export function Falsifier({
  humanText,
  fieldId,
  current,
  threshold,
  distance,
  status,
}: {
  humanText: string
  fieldId: string
  /** pre-formatted current value */
  current: string
  /** pre-formatted threshold */
  threshold: string
  /** pre-formatted distance to breach, e.g. "4.2pp away" */
  distance: string
  status: FalsifierStatus
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 'var(--spacing-3)',
        padding: 'var(--spacing-3) 0',
        borderBottom: '1px solid color-mix(in srgb, var(--rule) 50%, transparent)',
      }}
    >
      <span
        aria-label={status}
        style={{
          width: 7,
          height: 7,
          borderRadius: '50%',
          background: PIP[status],
          marginTop: 6,
          flexShrink: 0,
        }}
      />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ color: 'var(--text-primary)' }}>{humanText}</div>
        <div className="legend-strip" style={{ color: 'var(--text-tertiary)', marginTop: 2 }}>
          {fieldId}
        </div>
      </div>
      <div data-numeric style={{ textAlign: 'right', font: '400 var(--t-data) var(--font-data)' }}>
        <div style={{ color: status === 'breached' ? 'var(--madder)' : 'var(--text-primary)' }}>
          {current} <span style={{ color: 'var(--text-tertiary)' }}>/ {threshold}</span>
        </div>
        <div style={{ color: 'var(--text-secondary)' }}>{distance}</div>
      </div>
    </div>
  )
}
