/** Waterfall from gross to net, always expandable. Cost and tax are
 * modelled, not mentioned — this is where the model shows its work. */
export type CostLine = { label: string; amount: string }

export function CostBreakdown({
  grossLabel,
  gross,
  lines,
  netLabel,
  net,
  defaultOpen = false,
}: {
  grossLabel: string
  gross: string
  lines: CostLine[]
  netLabel: string
  net: string
  defaultOpen?: boolean
}) {
  return (
    <details open={defaultOpen}>
      <summary
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          cursor: 'pointer',
          listStyle: 'none',
          font: '400 var(--t-body) var(--font-ui)',
          color: 'var(--text-primary)',
        }}
      >
        <span>{netLabel}</span>
        <span data-numeric style={{ font: '500 var(--t-data) var(--font-data)' }}>{net}</span>
      </summary>
      <div
        style={{
          marginTop: 'var(--spacing-2)',
          paddingLeft: 'var(--spacing-3)',
          borderLeft: '1px solid var(--rule)',
        }}
      >
        <Row label={grossLabel} amount={gross} strong />
        {lines.map((l) => (
          <Row key={l.label} label={l.label} amount={l.amount} negative />
        ))}
      </div>
    </details>
  )
}

function Row({
  label,
  amount,
  strong = false,
  negative = false,
}: {
  label: string
  amount: string
  strong?: boolean
  negative?: boolean
}) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        padding: '3px 0',
        color: strong ? 'var(--text-primary)' : 'var(--text-secondary)',
        fontSize: 'var(--t-data)',
      }}
    >
      <span>{label}</span>
      <span
        data-numeric
        style={{
          font: '400 var(--t-data) var(--font-data)',
          color: negative ? 'var(--madder)' : undefined,
        }}
      >
        {amount}
      </span>
    </div>
  )
}
