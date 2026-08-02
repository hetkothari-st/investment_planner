import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { type Column, DataTable, Empty, Legend, Panel, Verdict } from '../../design'
import { researchApi, type CandidatesOut, type ReportOut } from '../../lib/api'

/** Equity research: horizon selector, deterministic candidate list, and the
 * on-demand report with provenance labels. Lists never wait on an LLM. */

type Candidate = CandidatesOut['candidates'][number]

const HORIZONS = ['SHORT', 'MID', 'LONG'] as const

const COLUMNS: Column<Candidate>[] = [
  { key: 'symbol', label: 'Symbol', render: (c) => c.tradingsymbol ?? c.isin },
  { key: 'isin', label: 'ISIN', render: (c) => c.isin },
  {
    key: 'pctl',
    label: 'Composite pctl',
    numeric: true,
    render: (c) => c.composite_pctl.toFixed(1),
    sortValue: (c) => c.composite_pctl,
  },
  {
    key: 'coverage',
    label: 'Coverage',
    numeric: true,
    render: (c) => `${Math.round(c.coverage * 100)}%`,
    sortValue: (c) => c.coverage,
  },
  { key: 'conviction', label: 'Conviction', render: (c) => c.conviction },
]

export function EquityPage() {
  const [horizon, setHorizon] = useState<(typeof HORIZONS)[number]>('MID')
  const [report, setReport] = useState<ReportOut | null>(null)
  const candidates = useQuery({
    queryKey: ['candidates', horizon],
    queryFn: () => researchApi.candidates(horizon),
  })
  const generate = useMutation({
    mutationFn: (isin: string) => researchApi.generateReport(isin, horizon),
    onSuccess: setReport,
  })

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
          Equity
        </h1>
        <div style={{ display: 'flex', gap: 'var(--spacing-1)' }}>
          {HORIZONS.map((h) => (
            <button
              key={h}
              onClick={() => setHorizon(h)}
              style={{
                font: '600 var(--t-data) var(--font-ui)',
                background: horizon === h ? 'var(--panel-raised)' : 'transparent',
                color: horizon === h ? 'var(--text-primary)' : 'var(--text-secondary)',
                border: `1px solid ${horizon === h ? 'var(--brass)' : 'var(--rule)'}`,
                borderRadius: 'var(--radius-panel)',
                padding: '6px 14px',
                cursor: 'pointer',
              }}
            >
              {h}
            </button>
          ))}
        </div>
        {candidates.data?.as_of && (
          <span className="legend-strip" data-numeric style={{ color: 'var(--text-tertiary)' }}>
            data as of {candidates.data.as_of}
          </span>
        )}
      </header>

      <Panel legend="COMPUTED" title={`${horizon} candidates`} entryIndex={0}>
        {candidates.isLoading ? (
          <Empty missing="Loading candidates…" fix="" />
        ) : candidates.data?.message ? (
          <Empty
            missing={candidates.data.message}
            fix="That's the expected outcome until the data spine is populated — and for SHORT, on most days even after."
          />
        ) : (
          <>
            <DataTable
              columns={COLUMNS}
              rows={candidates.data?.candidates ?? []}
              rowKey={(c) => c.isin}
            />
            <div style={{ display: 'flex', gap: 'var(--spacing-2)', marginTop: 'var(--spacing-3)', flexWrap: 'wrap' }}>
              {(candidates.data?.candidates ?? []).slice(0, 5).map((c) => (
                <button
                  key={c.isin}
                  onClick={() => generate.mutate(c.isin)}
                  disabled={generate.isPending}
                  style={{
                    font: '600 var(--t-data) var(--font-ui)',
                    background: 'transparent',
                    color: 'var(--brass)',
                    border: '1px solid var(--brass)',
                    borderRadius: 'var(--radius-panel)',
                    padding: '6px 14px',
                    cursor: 'pointer',
                  }}
                >
                  {generate.isPending ? 'Composing…' : `Report: ${c.tradingsymbol ?? c.isin}`}
                </button>
              ))}
            </div>
          </>
        )}
      </Panel>

      {generate.error && (
        <Verdict severity="warning">{generate.error.message}</Verdict>
      )}

      {report && (
        <Panel
          legend={report.narrative_included ? 'INFERRED' : 'MEASURED'}
          title={`${report.isin} · ${report.horizon}`}
          coverage={report.coverage}
          entryIndex={1}
        >
          {!report.narrative_included && (
            <Verdict severity="warning">
              The narrative failed the report contract twice and was withheld.
              The measured blocks below are unaffected — a report with no prose
              is fine; a report with invented prose is not.
            </Verdict>
          )}
          <div style={{ display: 'grid', gap: 'var(--spacing-4)', marginTop: 'var(--spacing-3)' }}>
            {report.blocks.map((b, i) => (
              <section key={i}>
                <Legend provenance={b.provenance as 'MEASURED'} />
                <pre
                  style={{
                    font: b.kind === 'metrics' ? '400 var(--t-data) var(--font-data)' : '400 var(--t-body) var(--font-ui)',
                    whiteSpace: 'pre-wrap',
                    color: 'var(--text-primary)',
                    background: b.provenance === 'SOURCE' ? 'var(--ink)' : 'transparent',
                    border: b.provenance === 'SOURCE' ? '1px solid var(--rule)' : 'none',
                    borderRadius: 'var(--radius-panel)',
                    padding: b.provenance === 'SOURCE' ? 'var(--spacing-3)' : 0,
                    margin: 'var(--spacing-1) 0 0',
                  }}
                >
                  {b.content}
                </pre>
              </section>
            ))}
          </div>
        </Panel>
      )}
    </main>
  )
}
