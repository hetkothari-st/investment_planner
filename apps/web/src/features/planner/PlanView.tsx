import { type Column, DataTable, Gate, Metric, Panel, Verdict } from '../../design'
import { inr, type PlanResult } from '../../lib/api'

/** Rendered plan: the gate waterfall, amounts, buckets, and the sensitivity
 * table that teaches the plan is a function of assumptions. */

const BUCKET_LABELS: Record<string, string> = {
  LIQUID_0_12: 'Liquid (< 12 months)',
  DEBT_12_36: 'Debt (12–36 months)',
  HYBRID_36_60: 'Hybrid (36–60 months)',
  EQUITY_60_PLUS: 'Equity (> 60 months)',
}

type SensRow = PlanResult['sensitivity'][number]

const SENS_COLUMNS: Column<SensRow>[] = [
  {
    key: 'real',
    label: 'Equity real return',
    numeric: true,
    render: (r) => `${r.equity_real_return_pct}%`,
    sortValue: (r) => Number(r.equity_real_return_pct),
  },
  {
    key: 'hurdle',
    label: 'Prepay hurdle',
    numeric: true,
    render: (r) => `${r.hurdle_pct}%`,
    sortValue: (r) => Number(r.hurdle_pct),
  },
  {
    key: 'investable',
    label: 'Investable / mo',
    numeric: true,
    render: (r) => inr(r.investable_monthly),
    sortValue: (r) => r.investable_monthly,
  },
  { key: 'note', label: 'Meaning', render: (r) => r.note },
]

export function PlanView({ plan }: { plan: PlanResult }) {
  const blocked = plan.blocking_reasons.length > 0
  return (
    <div style={{ display: 'grid', gap: 'var(--spacing-4)' }}>
      {blocked && (
        <Panel legend="COMPUTED" title="Why nothing invests yet" entryIndex={0}>
          <div style={{ display: 'grid', gap: 'var(--spacing-2)' }}>
            {plan.blocking_reasons.map((b) => (
              <Verdict key={b} severity="warning">
                {b}
              </Verdict>
            ))}
            {plan.spending_recommendations.map((s) => (
              <Verdict key={s} severity="failure">
                {s}
              </Verdict>
            ))}
          </div>
        </Panel>
      )}

      <Panel legend="COMPUTED" title="The waterfall" entryIndex={1}>
        <div style={{ display: 'grid', gap: 'var(--spacing-2)' }}>
          {plan.gates.map((g) => (
            <Gate
              key={g.gate}
              label={`${g.gate} · ${g.label}`}
              passed={g.status !== 'BLOCKED'}
              reason={g.reason}
              amount={g.amount > 0 ? inr(g.amount) : undefined}
            />
          ))}
        </div>
      </Panel>

      <Panel legend="COMPUTED" title="Investable" entryIndex={2}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: 'var(--spacing-4)',
          }}
        >
          <Metric label="Monthly" value={inr(plan.investable_monthly)} large provenance="COMPUTED" />
          <Metric label="Lumpsum" value={inr(plan.investable_lumpsum)} large provenance="COMPUTED" />
          <Metric
            label="Buffer"
            value={`${inr(plan.buffer_current)} / ${inr(plan.buffer_target)}`}
            provenance="COMPUTED"
          />
          <Metric
            label="Buffer full in"
            value={plan.buffer_eta_months != null ? `${plan.buffer_eta_months} mo` : null}
            provenance="COMPUTED"
          />
          <Metric
            label="Max equity fraction"
            value={`${Math.round(Number(plan.max_equity_fraction) * 100)}%`}
            provenance="COMPUTED"
          />
        </div>
        {!blocked && (
          <div style={{ marginTop: 'var(--spacing-4)' }}>
            <div className="legend-strip" style={{ color: 'var(--text-tertiary)', marginBottom: 6 }}>
              Horizon buckets (lumpsum)
            </div>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                gap: 'var(--spacing-3)',
              }}
            >
              {Object.entries(plan.horizon_buckets).map(([bucket, paise]) => (
                <Metric
                  key={bucket}
                  label={BUCKET_LABELS[bucket] ?? bucket}
                  value={inr(paise)}
                  provenance="COMPUTED"
                />
              ))}
            </div>
          </div>
        )}
      </Panel>

      <Panel legend="COMPUTED" title="If the assumptions are wrong" entryIndex={3}>
        <p style={{ margin: '0 0 var(--spacing-3)', color: 'var(--text-secondary)' }}>
          These are assumptions, not forecasts. The plan moves with them.
        </p>
        <DataTable
          columns={SENS_COLUMNS}
          rows={plan.sensitivity}
          rowKey={(r) => String(r.equity_real_return_pct)}
        />
        <p className="legend-strip" style={{ color: 'var(--text-tertiary)', marginTop: 'var(--spacing-3)', marginBottom: 0 }}>
          assumptions {plan.assumptions_version}
        </p>
      </Panel>
    </div>
  )
}
