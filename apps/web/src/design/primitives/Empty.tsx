/** Never "no data" — always names what's missing and what would fix it.
 * Empty states are instructions, not apologies. */
export function Empty({ missing, fix }: { missing: string; fix: string }) {
  return (
    <div
      style={{
        padding: 'var(--spacing-4)',
        border: '1px dashed var(--rule)',
        borderRadius: 'var(--radius-panel)',
        color: 'var(--text-secondary)',
      }}
    >
      <div style={{ color: 'var(--text-primary)' }}>{missing}</div>
      <div style={{ marginTop: 'var(--spacing-1)', fontSize: 'var(--t-data)' }}>{fix}</div>
    </div>
  )
}
