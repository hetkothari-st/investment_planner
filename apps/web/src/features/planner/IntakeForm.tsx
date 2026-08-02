import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Panel } from '../../design'
import {
  api,
  toPaise,
  type DebtIn,
  type GoalIn,
  type ProfileIn,
  type UserState,
} from '../../lib/api'

/** Profile intake. Temperament is elicited by scenario, never a slider. */

type MoneyFields = Record<
  'monthly_inflow' | 'fixed_outflow' | 'variable_outflow' | 'liquid_balance' | 'existing_investments',
  string
>
type DebtRow = { label: string; principal: string; rate: string; emi: string }
type GoalRow = { label: string; amount: string; date: string; priority: string }

const VARIABILITY = [
  { label: 'Steady salary', value: '0.05' },
  { label: 'Some variation', value: '0.15' },
  { label: 'Highly variable', value: '0.35' },
]

export function IntakeForm({
  initial,
  onSubmitted,
}: {
  initial: UserState | undefined
  onSubmitted: () => void
}) {
  const [money, setMoney] = useState<MoneyFields>({
    monthly_inflow: '',
    fixed_outflow: '',
    variable_outflow: '',
    liquid_balance: '',
    existing_investments: '0',
  })
  const [dependants, setDependants] = useState('0')
  const [stability, setStability] = useState('MEDIUM')
  const [variability, setVariability] = useState('0.05')
  const [temperament, setTemperament] = useState('SELL_SOME')
  const [debts, setDebts] = useState<DebtRow[]>([])
  const [goals, setGoals] = useState<GoalRow[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const p = initial?.profile
    if (!p) return
    setMoney({
      monthly_inflow: String(p.monthly_inflow / 100),
      fixed_outflow: String(p.fixed_outflow / 100),
      variable_outflow: String(p.variable_outflow / 100),
      liquid_balance: String(p.liquid_balance / 100),
      existing_investments: String((p.existing_investments ?? 0) / 100),
    })
    setDependants(String(p.dependants ?? 0))
    setStability(p.job_stability ?? 'MEDIUM')
    setVariability(String(Number(p.income_variability ?? 0.05)))
    setTemperament(p.temperament_choice ?? 'SELL_SOME')
    setDebts(
      (initial?.debts ?? []).map((d) => ({
        label: d.label,
        principal: String(d.principal_outstanding / 100),
        rate: String(d.annual_rate_pct),
        emi: String((d.min_emi ?? 0) / 100),
      })),
    )
    setGoals(
      (initial?.goals ?? []).map((g) => ({
        label: g.label,
        amount: String(g.target_amount / 100),
        date: g.target_date,
        priority: g.priority ?? 'SHOULD',
      })),
    )
  }, [initial])

  const scenario = useQuery({
    queryKey: ['temperament-scenario'],
    queryFn: api.temperamentScenario,
  })

  const submit = async () => {
    setSaving(true)
    setError(null)
    try {
      const profile: ProfileIn = {
        monthly_inflow: toPaise(money.monthly_inflow),
        fixed_outflow: toPaise(money.fixed_outflow),
        variable_outflow: toPaise(money.variable_outflow),
        liquid_balance: toPaise(money.liquid_balance),
        existing_investments: toPaise(money.existing_investments || '0'),
        dependants: Number(dependants) || 0,
        job_stability: stability as ProfileIn['job_stability'],
        income_variability: variability,
        temperament_choice: temperament as ProfileIn['temperament_choice'],
      }
      await api.putProfile(profile)
      await api.putDebts(
        debts
          .filter((d) => d.label && d.principal)
          .map(
            (d): DebtIn => ({
              label: d.label,
              principal_outstanding: toPaise(d.principal),
              annual_rate_pct: d.rate,
              min_emi: toPaise(d.emi || '0'),
              tax_deductible: false,
            }),
          ),
      )
      await api.putGoals(
        goals
          .filter((g) => g.label && g.amount && g.date)
          .map(
            (g): GoalIn => ({
              label: g.label,
              target_amount: toPaise(g.amount),
              target_date: g.date,
              priority: g.priority as GoalIn['priority'],
            }),
          ),
      )
      await api.computePlan()
      onSubmitted()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ display: 'grid', gap: 'var(--spacing-4)' }}>
      <Panel legend="YOUR INPUT" title="Cashflow and balance sheet" entryIndex={0}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: 'var(--spacing-3)',
          }}
        >
          <Field label="Monthly inflow ₹" value={money.monthly_inflow} onChange={(v) => setMoney({ ...money, monthly_inflow: v })} />
          <Field label="Fixed outflow ₹ (rent, insurance, tax)" value={money.fixed_outflow} onChange={(v) => setMoney({ ...money, fixed_outflow: v })} />
          <Field label="Variable outflow ₹" value={money.variable_outflow} onChange={(v) => setMoney({ ...money, variable_outflow: v })} />
          <Field label="Liquid balance ₹" value={money.liquid_balance} onChange={(v) => setMoney({ ...money, liquid_balance: v })} />
          <Field label="Existing investments ₹" value={money.existing_investments} onChange={(v) => setMoney({ ...money, existing_investments: v })} />
          <Field label="Dependants" value={dependants} onChange={setDependants} />
        </div>
        <div style={{ display: 'flex', gap: 'var(--spacing-4)', marginTop: 'var(--spacing-4)', flexWrap: 'wrap' }}>
          <Choice
            label="Job stability (self-rated)"
            options={['LOW', 'MEDIUM', 'HIGH'].map((v) => ({ value: v, label: v.toLowerCase() }))}
            value={stability}
            onChange={setStability}
          />
          <Choice
            label="Income variability"
            options={VARIABILITY.map((v) => ({ value: v.value, label: v.label }))}
            value={variability}
            onChange={setVariability}
          />
        </div>
      </Panel>

      <Panel legend="YOUR INPUT" title="Temperament" entryIndex={1}>
        <p style={{ margin: '0 0 var(--spacing-3)', color: 'var(--text-secondary)' }}>
          {scenario.data
            ? `Your ${fmtRupees(scenario.data.before_inr)} becomes ${fmtRupees(scenario.data.after_inr)} over four months. What do you do?`
            : 'Loading scenario…'}
        </p>
        <div style={{ display: 'grid', gap: 'var(--spacing-2)' }}>
          {(scenario.data?.options ?? []).map((o) => (
            <label
              key={o.choice}
              style={{
                display: 'flex',
                gap: 'var(--spacing-3)',
                alignItems: 'baseline',
                padding: 'var(--spacing-3)',
                border: `1px solid ${temperament === o.choice ? 'var(--brass)' : 'var(--rule)'}`,
                borderRadius: 'var(--radius-panel)',
                cursor: 'pointer',
              }}
            >
              <input
                type="radio"
                name="temperament"
                checked={temperament === o.choice}
                onChange={() => setTemperament(o.choice)}
                style={{ accentColor: 'var(--brass)' }}
              />
              <span>{o.label}</span>
            </label>
          ))}
        </div>
      </Panel>

      <Panel legend="YOUR INPUT" title="Debts" entryIndex={2}>
        <RowEditor
          rows={debts}
          onChange={setDebts}
          empty={{ label: '', principal: '', rate: '', emi: '' }}
          fields={[
            { key: 'label', label: 'Label' },
            { key: 'principal', label: 'Outstanding ₹' },
            { key: 'rate', label: 'Rate %' },
            { key: 'emi', label: 'Min EMI ₹' },
          ]}
        />
      </Panel>

      <Panel legend="YOUR INPUT" title="Goals" entryIndex={3}>
        <RowEditor
          rows={goals}
          onChange={setGoals}
          empty={{ label: '', amount: '', date: '', priority: 'SHOULD' }}
          fields={[
            { key: 'label', label: 'Label' },
            { key: 'amount', label: 'Amount ₹' },
            { key: 'date', label: 'Target date (YYYY-MM-DD)' },
            { key: 'priority', label: 'MUST / SHOULD / WANT' },
          ]}
        />
      </Panel>

      {error && (
        <p role="alert" style={{ color: 'var(--madder)', margin: 0 }}>
          {error}
        </p>
      )}
      <div>
        <button
          onClick={submit}
          disabled={saving}
          style={{
            font: '600 var(--t-body) var(--font-ui)',
            background: 'var(--brass)',
            color: 'var(--ink)',
            border: 'none',
            borderRadius: 'var(--radius-panel)',
            padding: '10px 24px',
            cursor: saving ? 'wait' : 'pointer',
          }}
        >
          {saving ? 'Computing…' : 'Compute plan'}
        </button>
      </div>
    </div>
  )
}

function fmtRupees(rupees: number): string {
  return `₹${new Intl.NumberFormat('en-IN').format(rupees)}`
}

function Field({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (v: string) => void
}) {
  return (
    <label style={{ display: 'grid', gap: 4 }}>
      <span className="legend-strip" style={{ color: 'var(--text-tertiary)' }}>
        {label}
      </span>
      <input
        value={value}
        inputMode="decimal"
        onChange={(e) => onChange(e.target.value)}
        data-numeric
        style={{
          font: '400 var(--t-data) var(--font-data)',
          background: 'var(--ink)',
          color: 'var(--text-primary)',
          border: '1px solid var(--rule)',
          borderRadius: 'var(--radius-panel)',
          padding: '8px 10px',
        }}
      />
    </label>
  )
}

function Choice({
  label,
  options,
  value,
  onChange,
}: {
  label: string
  options: { value: string; label: string }[]
  value: string
  onChange: (v: string) => void
}) {
  return (
    <div>
      <div className="legend-strip" style={{ color: 'var(--text-tertiary)', marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ display: 'flex', gap: 'var(--spacing-1)' }}>
        {options.map((o) => (
          <button
            key={o.value}
            onClick={() => onChange(o.value)}
            style={{
              font: '500 var(--t-data) var(--font-ui)',
              background: value === o.value ? 'var(--panel-raised)' : 'transparent',
              color: value === o.value ? 'var(--text-primary)' : 'var(--text-secondary)',
              border: `1px solid ${value === o.value ? 'var(--brass)' : 'var(--rule)'}`,
              borderRadius: 'var(--radius-panel)',
              padding: '6px 12px',
              cursor: 'pointer',
            }}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  )
}

function RowEditor<T extends Record<string, string>>({
  rows,
  onChange,
  empty,
  fields,
}: {
  rows: T[]
  onChange: (rows: T[]) => void
  empty: T
  fields: { key: keyof T & string; label: string }[]
}) {
  return (
    <div style={{ display: 'grid', gap: 'var(--spacing-2)' }}>
      {rows.map((row, i) => (
        <div
          key={i}
          style={{
            display: 'grid',
            gridTemplateColumns: `repeat(${fields.length}, 1fr) auto`,
            gap: 'var(--spacing-2)',
            alignItems: 'end',
          }}
        >
          {fields.map((f) => (
            <Field
              key={f.key}
              label={i === 0 ? f.label : ''}
              value={row[f.key]}
              onChange={(v) => {
                const next = [...rows]
                next[i] = { ...row, [f.key]: v }
                onChange(next)
              }}
            />
          ))}
          <button
            onClick={() => onChange(rows.filter((_, j) => j !== i))}
            title="Remove row"
            style={{
              font: '400 var(--t-data) var(--font-ui)',
              background: 'transparent',
              color: 'var(--text-tertiary)',
              border: '1px solid var(--rule)',
              borderRadius: 'var(--radius-panel)',
              padding: '8px 10px',
              cursor: 'pointer',
            }}
          >
            ✕
          </button>
        </div>
      ))}
      <div>
        <button
          onClick={() => onChange([...rows, empty])}
          style={{
            font: '500 var(--t-data) var(--font-ui)',
            background: 'transparent',
            color: 'var(--text-secondary)',
            border: '1px dashed var(--rule)',
            borderRadius: 'var(--radius-panel)',
            padding: '6px 14px',
            cursor: 'pointer',
          }}
        >
          Add row
        </button>
      </div>
    </div>
  )
}
