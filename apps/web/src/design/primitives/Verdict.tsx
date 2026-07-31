/** Plain-text system judgement. Deterministic templated text — the system
 * grading itself must not be able to spin. */
export type VerdictSeverity = 'neutral' | 'warning' | 'failure'

const BAR: Record<VerdictSeverity, string> = {
  neutral: 'var(--phosphor)',
  warning: 'var(--brass)',
  failure: 'var(--madder)',
}

export function Verdict({
  severity,
  children,
}: {
  severity: VerdictSeverity
  children: string
}) {
  return (
    <p
      style={{
        borderLeft: `2px solid ${BAR[severity]}`,
        paddingLeft: 'var(--spacing-3)',
        margin: 0,
        font: '400 var(--t-body) var(--font-ui)',
        color: 'var(--text-primary)',
      }}
    >
      {children}
    </p>
  )
}
