/** The engraved provenance strip. Its text is always a provenance class —
 * it carries information the reader needs, never decoration. */

export type Provenance = 'MEASURED' | 'COMPUTED' | 'INFERRED' | 'SOURCE' | 'YOUR INPUT'

const COLOR: Record<Provenance, string> = {
  MEASURED: 'var(--phosphor)',
  COMPUTED: 'var(--phosphor)',
  INFERRED: 'color-mix(in srgb, var(--brass) 70%, transparent)',
  SOURCE: 'var(--text-secondary)',
  'YOUR INPUT': 'var(--brass)',
}

export function Legend({ provenance }: { provenance: Provenance }) {
  return (
    <span className="legend-strip" style={{ color: COLOR[provenance], opacity: 0.9 }}>
      {provenance}
    </span>
  )
}
