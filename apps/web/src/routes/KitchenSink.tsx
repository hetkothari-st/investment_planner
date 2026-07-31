import { useEffect, useState } from 'react'
import {
  Band,
  CalibrationDial,
  type Column,
  CostBreakdown,
  DataTable,
  Empty,
  Falsifier,
  Gate,
  Metric,
  Panel,
  Sparkline,
  Stale,
  Verdict,
} from '../design'

/** Every primitive in every state, driven by mock data. M2's acceptance
 * surface — screenshot at 1440/768/390, both themes, both motion settings. */

type Row = { symbol: string; close: string | null; rs3m: number | null; sector: string }

const TABLE_ROWS: Row[] = Array.from({ length: 120 }, (_, i) => ({
  symbol: `SYM${String(i + 1).padStart(3, '0')}`,
  close: i % 17 === 0 ? null : (500 + i * 7.25).toFixed(2),
  rs3m: i % 13 === 0 ? null : +((i % 40) - 12.4).toFixed(1),
  sector: ['Financials', 'IT', 'Energy', 'Pharma', 'Auto'][i % 5],
}))

const COLUMNS: Column<Row>[] = [
  { key: 'symbol', label: 'Symbol', render: (r) => r.symbol },
  { key: 'sector', label: 'Sector', render: (r) => r.sector },
  {
    key: 'close',
    label: 'Close ₹',
    numeric: true,
    render: (r) => r.close,
    sortValue: (r) => (r.close === null ? -Infinity : parseFloat(r.close)),
  },
  {
    key: 'rs3m',
    label: 'RS 3m %',
    numeric: true,
    render: (r) => (r.rs3m === null ? null : `${r.rs3m > 0 ? '+' : ''}${r.rs3m.toFixed(1)}`),
    sortValue: (r) => r.rs3m ?? -Infinity,
  },
]

export function KitchenSink() {
  const [theme, setTheme] = useState<'ink' | 'paper'>(() =>
    new URLSearchParams(window.location.search).get('theme') === 'paper' ? 'paper' : 'ink',
  )
  useEffect(() => {
    if (theme === 'paper') document.documentElement.dataset.theme = 'paper'
    else delete document.documentElement.dataset.theme
  }, [theme])

  let panelIndex = 0
  const next = () => panelIndex++

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
          Kitchen sink
        </h1>
        <span style={{ flex: 1 }} />
        <Stale asOf="30 Jul 2026" />
        <button
          onClick={() => setTheme(theme === 'ink' ? 'paper' : 'ink')}
          style={{
            font: '600 var(--t-data) var(--font-ui)',
            background: 'var(--brass)',
            color: 'var(--ink)',
            border: 'none',
            borderRadius: 'var(--radius-panel)',
            padding: '6px 14px',
            cursor: 'pointer',
          }}
        >
          {theme === 'ink' ? 'Paper mode' : 'Ink mode'}
        </button>
      </header>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: 'var(--spacing-4)',
        }}
      >
        <Panel legend="MEASURED" title="Metric — all states" coverage={0.82} entryIndex={next()}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-4)' }}>
            <Metric label="ROCE median 5y" value="19.4" unit="%" large />
            <Metric label="P/E percentile 5y" value="31" unit="pctl" delta="-4.0" large />
            <Metric label="Promoter pledge" value={null} unit="%" />
            <Metric label="Cash conversion" value="0.87" unit="ratio" delta="+0.05" />
            <Metric label="Est. revision 3m" value="-2.1" unit="%" delta="-1.2" provenance="COMPUTED" />
            <Metric label="Guidance direction" value="raised" provenance="INFERRED" />
          </div>
        </Panel>

        <Panel legend="COMPUTED" title="Scenario band" entryIndex={next()}>
          <Band bearPct={-18.2} basePct={7.5} bullPct={22.1} nAnalogues={142} />
          <div style={{ marginTop: 'var(--spacing-4)' }}>
            <Band bearPct={-6.1} basePct={2.2} bullPct={9.8} nAnalogues={34} />
          </div>
        </Panel>

        <Panel legend="COMPUTED" title="Sparkline + stale states" entryIndex={next()}>
          <div style={{ display: 'flex', gap: 'var(--spacing-4)', alignItems: 'center' }}>
            <Sparkline points={[3, 4, 3.5, 5, 6, 5.5, 7, 8]} stroke="var(--jade)" />
            <Sparkline points={[8, 7, 7.5, 6, 5, 5.5, 4, 3]} stroke="var(--madder)" />
            <Sparkline points={[5, 5.2, 4.9, 5.1, 5, 5.05, 4.95, 5]} />
          </div>
          <div style={{ display: 'flex', gap: 'var(--spacing-2)', marginTop: 'var(--spacing-4)' }}>
            <Stale asOf="30 Jul 2026" />
            <Stale asOf="12 Apr 2026" stale />
          </div>
        </Panel>
      </div>

      <Panel legend="MEASURED" title="DataTable — 120 rows, virtualised, sortable" entryIndex={next()}>
        <DataTable columns={COLUMNS} rows={TABLE_ROWS} rowKey={(r) => r.symbol} maxHeight={320} />
      </Panel>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: 'var(--spacing-4)',
        }}
      >
        <Panel legend="COMPUTED" title="Falsifiers" entryIndex={next()}>
          <Falsifier
            humanText="TTM EBITDA margin falls 2pp from entry"
            fieldId="fin.ebitda_margin_ttm"
            current="16.8%"
            threshold="14.2%"
            distance="2.6pp away"
            status="intact"
          />
          <Falsifier
            humanText="Promoter pledge rises 5pp above entry level"
            fieldId="gov.pledge_pct"
            current="11.9%"
            threshold="13.0%"
            distance="1.1pp away"
            status="near"
          />
          <Falsifier
            humanText="Price breaches the bear-case level"
            fieldId="price.close"
            current="₹482.10"
            threshold="₹495.00"
            distance="breached 12 Jun"
            status="breached"
          />
        </Panel>

        <Panel legend="YOUR INPUT" title="Gates" entryIndex={next()}>
          <div style={{ display: 'grid', gap: 'var(--spacing-2)' }}>
            <Gate
              label="G3 · Emergency buffer"
              passed={false}
              reason="Buffer at 3.2 of 6.0 months. Nothing invests before this."
              amount="₹18,400/mo"
            />
            <Gate
              label="G4 · High-cost debt"
              passed
              reason="No debt above the 12.4% hurdle."
            />
          </div>
        </Panel>

        <Panel legend="COMPUTED" title="Cost breakdown + verdicts" entryIndex={next()}>
          <CostBreakdown
            grossLabel="Gross expected (base case)"
            gross="₹4,120"
            lines={[
              { label: 'Brokerage + STT + charges', amount: '−₹214' },
              { label: 'Slippage estimate', amount: '−₹96' },
              { label: 'STCG 20%', amount: '−₹762' },
            ]}
            netLabel="Net expected"
            net="₹3,048"
            defaultOpen
          />
          <div style={{ display: 'grid', gap: 'var(--spacing-2)', marginTop: 'var(--spacing-4)' }}>
            <Verdict severity="neutral">MID horizon is performing above the coin-flip mark.</Verdict>
            <Verdict severity="warning">Band coverage 87% — bands may be too wide to be useful.</Verdict>
            <Verdict severity="failure">This system is not good at short-horizon calls.</Verdict>
          </div>
        </Panel>

        <Panel legend="SOURCE" title="Empty state" entryIndex={next()}>
          <Empty
            missing="No short-horizon candidates cleared the cost hurdle today."
            fix="That's the expected outcome most days. The hurdle protects you from paying ₹340 round-trip to chase +1.8%."
          />
        </Panel>
      </div>

      <Panel legend="COMPUTED" title="Calibration dial" entryIndex={next()}>
        <div style={{ display: 'grid', placeItems: 'center' }}>
          <CalibrationDial
            horizons={[
              {
                horizon: 'SHORT',
                hitRatePct: null,
                n: 7,
                netAlphaPct: null,
                brier: null,
                verdict: 'SHORT — 7 of 20 scored calls needed. Uncalibrated.',
                severity: 'neutral',
              },
              {
                horizon: 'MID',
                hitRatePct: 61,
                n: 63,
                netAlphaPct: 3.2,
                brier: 0.21,
                verdict: 'MID — direction correct 61% of 63 calls, +3.2% net alpha.',
                severity: 'neutral',
              },
              {
                horizon: 'LONG',
                hitRatePct: 44,
                n: 41,
                netAlphaPct: -2.3,
                brier: 0.29,
                verdict:
                  'LONG — direction correct 44% of the time. Net of costs −2.3% against +6.1% index. This horizon is underperforming a coin flip.',
                severity: 'failure',
              },
            ]}
          />
        </div>
      </Panel>
    </main>
  )
}
