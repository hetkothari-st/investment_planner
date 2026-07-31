import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { Empty, Gate, Panel, Verdict } from '../../design'
import { ApiError, api, inr } from '../../lib/api'

/** The allocation screen. When the plan has blocking reasons it renders
 * locked with the reason printed — the user cannot click past it into
 * research. That block is the product working (docs/03). */

export function AllocationPage() {
  const plan = useQuery({
    queryKey: ['plan-latest'],
    queryFn: api.latestPlan,
    retry: (count, err) => !(err instanceof ApiError && err.status === 404) && count < 2,
  })

  const blocked = (plan.data?.blocking_reasons.length ?? 0) > 0

  return (
    <main style={{ maxWidth: 1440, margin: '0 auto', padding: 'var(--spacing-4)' }}>
      <h1
        style={{
          font: '700 var(--t-display) var(--font-display)',
          fontStretch: '96%',
          letterSpacing: '-0.02em',
          margin: '0 0 var(--spacing-4)',
        }}
      >
        Allocation
      </h1>

      {plan.isLoading ? (
        <Empty missing="Loading plan…" fix="" />
      ) : !plan.data ? (
        <Panel legend="COMPUTED" title="No plan yet">
          <Empty
            missing="Allocation needs a plan first."
            fix="Complete the profile in the planner and compute one."
          />
          <p style={{ marginBottom: 0 }}>
            <Link to="/planner" style={{ color: 'var(--brass)' }}>
              Go to the planner
            </Link>
          </p>
        </Panel>
      ) : blocked ? (
        <Panel legend="COMPUTED" title="Locked">
          <div style={{ display: 'grid', gap: 'var(--spacing-2)' }}>
            {plan.data.blocking_reasons.map((b) => (
              <Gate key={b} label="Allocation locked" passed={false} reason={b} />
            ))}
            <Verdict severity="warning">
              The gate exists so that money that should not reach a market does not
              reach a market. Fix the reason above; this screen unlocks itself.
            </Verdict>
          </div>
        </Panel>
      ) : (
        <Panel legend="COMPUTED" title="Investable, awaiting the allocation engine">
          <Empty
            missing={`${inr(plan.data.investable_monthly)}/month and ${inr(
              plan.data.investable_lumpsum,
            )} lumpsum cleared the gates. The allocation engine ships in M7.`}
            fix="Until then the planner's horizon buckets are the allocation: liquid, debt, hybrid and equity ceilings from your goal dates and temperament."
          />
        </Panel>
      )}
    </main>
  )
}
