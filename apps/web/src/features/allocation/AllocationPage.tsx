import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Suspense, lazy, useState } from 'react'
import { Link } from 'react-router'
import { type Column, DataTable, Empty, Gate, Legend, Panel, Verdict } from '../../design'
import { ApiError, allocationApi, inr } from '../../lib/api'
import type { AllocationOut } from '../../lib/api'
import { buildData, position, type ScatterDatum } from './scatter'

// three.js only loads when this route renders with data
const Scatter3D = lazy(() =>
  import('./Scatter3D').then((m) => ({ default: m.Scatter3D })),
)

/** The allocation screen — docs/04. The ranking is a UI affordance; the
 * allocation is the recommendation. Gated-out vehicles stay visible, greyed,
 * with the gate that killed them named. */

type Line = AllocationOut['lines'][number]

const LINE_COLUMNS: Column<Line>[] = [
  { key: 'bucket', label: 'Bucket', render: (l) => l.bucket },
  { key: 'vehicle', label: 'Vehicle', render: (l) => l.label },
  {
    key: 'lumpsum',
    label: 'Lumpsum',
    numeric: true,
    render: (l) => (l.lumpsum_inr > 0 ? inr(l.lumpsum_inr) : '—'),
    sortValue: (l) => l.lumpsum_inr,
  },
  {
    key: 'sip',
    label: 'Monthly SIP',
    numeric: true,
    render: (l) => (l.monthly_inr > 0 ? inr(l.monthly_inr) : '—'),
    sortValue: (l) => l.monthly_inr,
  },
  { key: 'rationale', label: 'Rationale', render: (l) => l.rationale },
]

// The 2D source of truth beneath the scatter: exactly the ScatterDatum array
// the 3D scene renders — raw values plus the derived world position.
const SCATTER_COLUMNS: Column<ScatterDatum>[] = [
  { key: 'vehicle', label: 'Vehicle', render: (d) => d.label },
  {
    key: 'risk',
    label: 'Risk σ%',
    numeric: true,
    render: (d) => d.risk.toFixed(1),
    sortValue: (d) => d.risk,
  },
  {
    key: 'ret',
    label: 'Net %/yr',
    numeric: true,
    render: (d) => d.ret.toFixed(2),
    sortValue: (d) => d.ret,
  },
  {
    key: 'days',
    label: 'Days to cash',
    numeric: true,
    render: (d) => String(Math.round(d.daysToCash)),
    sortValue: (d) => d.daysToCash,
  },
  {
    key: 'suit',
    label: 'Suitability',
    numeric: true,
    render: (d) => (d.gated ? `GATED: ${d.gate}` : `${d.suitability}%`),
    sortValue: (d) => (d.gated ? -1 : Number(d.suitability)),
  },
  {
    key: 'alloc',
    label: 'Allocated (yr 1)',
    numeric: true,
    render: (d) => (d.allocatedPaise > 0 ? inr(d.allocatedPaise) : '—'),
    sortValue: (d) => d.allocatedPaise,
  },
  {
    key: 'pos',
    label: 'Position [x y z]',
    render: (d) =>
      position(d)
        .map((v) => v.toFixed(2))
        .join(' '),
  },
]

const KNOWLEDGE = ['LOW', 'MEDIUM', 'HIGH'] as const

function Preferences() {
  const qc = useQueryClient()
  const prefs = useQuery({
    queryKey: ['allocation-prefs'],
    queryFn: allocationApi.preferences,
  })
  const [lockDraft, setLockDraft] = useState<string | null>(null)
  const save = useMutation({
    mutationFn: allocationApi.putPreferences,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['allocation-prefs'] })
      qc.invalidateQueries({ queryKey: ['allocation'] })
    },
  })
  if (!prefs.data) return null
  const p = prefs.data
  return (
    <Panel legend="YOUR INPUT" title="Allocation preferences" entryIndex={1}>
      <div
        style={{
          display: 'flex',
          gap: 'var(--spacing-3)',
          alignItems: 'center',
          flexWrap: 'wrap',
        }}
      >
        <label style={{ font: '500 var(--t-body) var(--font-ui)', color: 'var(--text-secondary)' }}>
          Self-rated knowledge
        </label>
        <div style={{ display: 'flex', gap: 'var(--spacing-1)' }}>
          {KNOWLEDGE.map((k) => (
            <button
              key={k}
              onClick={() => save.mutate({ ...p, self_rated_knowledge: k })}
              style={{
                font: '600 var(--t-data) var(--font-ui)',
                background: p.self_rated_knowledge === k ? 'var(--panel-raised)' : 'transparent',
                color: p.self_rated_knowledge === k ? 'var(--text-primary)' : 'var(--text-secondary)',
                border: `1px solid ${p.self_rated_knowledge === k ? 'var(--brass)' : 'var(--rule)'}`,
                borderRadius: 'var(--radius-panel)',
                padding: '6px 14px',
                cursor: 'pointer',
              }}
            >
              {k}
            </button>
          ))}
        </div>
        <label style={{ font: '500 var(--t-body) var(--font-ui)', color: 'var(--text-secondary)' }}>
          Max lock-in (months)
        </label>
        <input
          data-numeric
          value={lockDraft ?? (p.max_lock_in_months == null ? '' : String(p.max_lock_in_months))}
          placeholder="no constraint"
          onChange={(e) => setLockDraft(e.target.value)}
          onBlur={() => {
            if (lockDraft === null) return
            const v = lockDraft.trim()
            save.mutate({
              ...p,
              max_lock_in_months: v === '' ? null : Math.max(0, Math.round(Number(v))),
            })
            setLockDraft(null)
          }}
          style={{
            font: '400 var(--t-data) var(--font-data)',
            background: 'var(--ink)',
            color: 'var(--text-primary)',
            border: '1px solid var(--rule)',
            borderRadius: 'var(--radius-panel)',
            padding: '6px 10px',
            width: 140,
          }}
        />
        <span style={{ font: '400 var(--t-body) var(--font-ui)', color: 'var(--text-tertiary)' }}>
          LOW keeps HIGH-knowledge vehicles gated. Empty lock-in means no constraint stated.
        </span>
      </div>
    </Panel>
  )
}

export function AllocationPage() {
  const allocation = useQuery({
    queryKey: ['allocation'],
    queryFn: allocationApi.get,
    retry: (count, err) => !(err instanceof ApiError) && count < 2,
  })

  const err = allocation.error instanceof ApiError ? allocation.error : null
  const data = allocation.data
  const scatterData = data ? buildData(data.ranked_vehicles, data.gated_out) : []

  return (
    <main
      style={{
        maxWidth: 1440,
        margin: '0 auto',
        padding: 'var(--spacing-4)',
        display: 'grid',
        gap: 'var(--spacing-4)',
      }}
    >
      <header style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--spacing-4)' }}>
        <h1
          style={{
            font: '700 var(--t-display) var(--font-display)',
            fontStretch: '96%',
            letterSpacing: '-0.02em',
            margin: 0,
          }}
        >
          Allocation
        </h1>
        {data && (
          <span className="legend-strip" data-numeric style={{ color: 'var(--text-tertiary)' }}>
            vehicles {data.vehicles_version} · assumptions {data.assumptions_version} · ranked
            at {data.horizon_months} months
          </span>
        )}
      </header>

      {allocation.isLoading ? (
        <Empty missing="Loading allocation…" fix="" />
      ) : err?.status === 404 ? (
        <Panel legend="COMPUTED" title="No plan yet">
          <Empty missing={err.message} fix="Allocation is a function of the plan." />
          <p style={{ marginBottom: 0 }}>
            <Link to="/planner" style={{ color: 'var(--brass)' }}>
              Go to the planner
            </Link>
          </p>
        </Panel>
      ) : err?.status === 409 ? (
        <Panel legend="COMPUTED" title="Locked">
          <div style={{ display: 'grid', gap: 'var(--spacing-2)' }}>
            <Gate label="Allocation locked" passed={false} reason={err.message} />
            <Verdict severity="warning">
              The gate exists so that money that should not reach a market does not reach a
              market. Fix the reason above; this screen unlocks itself.
            </Verdict>
          </div>
        </Panel>
      ) : err ? (
        <Verdict severity="warning">{err.message}</Verdict>
      ) : data ? (
        <>
          <Preferences />

          <Panel legend="COMPUTED" title="Recommended allocation" entryIndex={0}>
            <DataTable
              columns={LINE_COLUMNS}
              rows={data.lines}
              rowKey={(l) => `${l.bucket}:${l.vehicle_id}`}
            />
            {data.diversification_notes.length > 0 && (
              <div style={{ display: 'grid', gap: 'var(--spacing-1)', marginTop: 'var(--spacing-3)' }}>
                {data.diversification_notes.map((n) => (
                  <Verdict key={n} severity="neutral">
                    {n}
                  </Verdict>
                ))}
              </div>
            )}
          </Panel>

          <Panel legend="COMPUTED" title="Suitability — risk × return × liquidity" entryIndex={2}>
            <Suspense fallback={<div style={{ height: 420 }} />}>
              <Scatter3D data={scatterData} />
            </Suspense>
            <div style={{ marginTop: 'var(--spacing-3)' }}>
              <Legend provenance="COMPUTED" />
              <p
                style={{
                  font: '400 var(--t-body) var(--font-ui)',
                  color: 'var(--text-secondary)',
                  margin: 'var(--spacing-1) 0 var(--spacing-2)',
                }}
              >
                The table is the source of truth; the scatter renders exactly these rows.
                Filled spheres are allocated (sized by first-year rupees), small dots are
                eligible, wireframe ghosts are gated out — the gate is named per row.
              </p>
              <DataTable columns={SCATTER_COLUMNS} rows={scatterData} rowKey={(d) => d.vehicle_id} />
            </div>
          </Panel>
        </>
      ) : null}
    </main>
  )
}
