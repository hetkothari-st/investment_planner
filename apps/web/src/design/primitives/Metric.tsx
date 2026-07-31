import type { Provenance } from './Legend'

const DOT: Record<Provenance, string> = {
  MEASURED: 'var(--phosphor)',
  COMPUTED: 'var(--phosphor)',
  INFERRED: 'var(--brass)',
  SOURCE: 'var(--text-secondary)',
  'YOUR INPUT': 'var(--brass)',
}

/** Label + value + unit + delta + provenance dot. Tabular, never wraps.
 * A missing value renders as an em dash — never zero, never imputed. */
export function Metric({
  label,
  value,
  unit,
  delta,
  provenance = 'MEASURED',
  large = false,
}: {
  label: string
  /** pre-formatted by the caller; null = missing */
  value: string | null
  unit?: string
  /** signed pre-formatted delta, e.g. "+1.2" */
  delta?: string | null
  provenance?: Provenance
  large?: boolean
}) {
  const deltaUp = delta != null && !delta.startsWith('-')
  return (
    <div style={{ whiteSpace: 'nowrap' }}>
      <div
        className="legend-strip"
        style={{ color: 'var(--text-tertiary)', display: 'flex', alignItems: 'center', gap: 6 }}
      >
        <span
          aria-hidden
          style={{
            width: 5,
            height: 5,
            borderRadius: '50%',
            background: DOT[provenance],
            display: 'inline-block',
          }}
        />
        {label}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--spacing-2)' }}>
        <span
          data-numeric
          style={{
            font: `${large ? '500 var(--t-data-lg)' : '400 var(--t-data)'} var(--font-data)`,
            fontVariantNumeric: 'tabular-nums',
            color: value === null ? 'var(--text-tertiary)' : 'var(--text-primary)',
          }}
        >
          {value ?? '—'}
        </span>
        {unit && value !== null && (
          <span style={{ font: '400 var(--t-label) var(--font-ui)', color: 'var(--text-tertiary)' }}>
            {unit}
          </span>
        )}
        {delta != null && (
          <span
            data-numeric
            style={{
              font: '400 var(--t-data) var(--font-data)',
              color: deltaUp ? 'var(--jade)' : 'var(--madder)',
            }}
          >
            {deltaUp ? '▲' : '▼'} {delta}
          </span>
        )}
      </div>
    </div>
  )
}
