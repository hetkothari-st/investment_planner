import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Band, Empty, Metric, Panel, Verdict } from '../../design'
import {
  inr,
  simApi,
  toPaise,
  type ManualThesisIn,
  type PositionOut,
  type ThesisOut,
} from '../../lib/api'

/** Manual theses + simulated positions. Not a game: no streaks, no badges.
 * Every thesis needs a horizon, a band and at least one falsifier — the
 * same bar machine recommendations will have to clear. */

export function SimulatorPage() {
  const qc = useQueryClient()
  const theses = useQuery({ queryKey: ['theses'], queryFn: simApi.theses })
  const positions = useQuery({ queryKey: ['positions'], queryFn: simApi.positions })
  const runDaily = useMutation({
    mutationFn: simApi.runDaily,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['positions'] })
      qc.invalidateQueries({ queryKey: ['calibration'] })
      qc.invalidateQueries({ queryKey: ['theses'] })
    },
  })
  const [showForm, setShowForm] = useState(false)

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
      <header style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--spacing-3)' }}>
        <h1
          style={{
            font: '700 var(--t-display) var(--font-display)',
            fontStretch: '96%',
            letterSpacing: '-0.02em',
            margin: 0,
          }}
        >
          Simulator
        </h1>
        <span style={{ flex: 1 }} />
        <button onClick={() => runDaily.mutate()} style={ghostBtn} disabled={runDaily.isPending}>
          {runDaily.isPending ? 'Marking…' : 'Run daily marks + scoring'}
        </button>
        <button onClick={() => setShowForm((v) => !v)} style={brassBtn}>
          {showForm ? 'Hide thesis form' : 'New thesis'}
        </button>
      </header>

      {runDaily.data && (
        <Verdict severity="neutral">
          {`Marked ${runDaily.data.marked} positions, scored ${runDaily.data.scored} expired theses.` +
            (runDaily.data.skipped.length
              ? ` Skipped: ${runDaily.data.skipped.join('; ')}`
              : '')}
        </Verdict>
      )}

      {showForm && (
        <ThesisForm
          onDone={() => {
            setShowForm(false)
            qc.invalidateQueries({ queryKey: ['theses'] })
          }}
        />
      )}

      <Panel legend="YOUR INPUT" title="Theses" entryIndex={0}>
        {!theses.data?.length ? (
          <Empty
            missing="No theses yet."
            fix="Enter your own picks with bands and falsifiers. The system starts grading you before it grades itself."
          />
        ) : (
          <div style={{ display: 'grid', gap: 'var(--spacing-4)' }}>
            {theses.data.map((t) => (
              <ThesisRow key={t.id} thesis={t} onOpened={() => qc.invalidateQueries({ queryKey: ['positions'] })} />
            ))}
          </div>
        )}
      </Panel>

      <Panel legend="COMPUTED" title="Simulated positions" entryIndex={1}>
        {!positions.data?.length ? (
          <Empty missing="No simulated positions." fix="Open one against a LIVE thesis above." />
        ) : (
          <div style={{ display: 'grid', gap: 'var(--spacing-3)' }}>
            {positions.data.map((p) => (
              <PositionRow key={p.id} position={p} onClosed={() => qc.invalidateQueries({ queryKey: ['positions'] })} />
            ))}
          </div>
        )}
      </Panel>
    </main>
  )
}

function ThesisRow({ thesis, onOpened }: { thesis: ThesisOut; onOpened: () => void }) {
  const [amount, setAmount] = useState('')
  const [price, setPrice] = useState('')
  const [error, setError] = useState<string | null>(null)
  const open = useMutation({
    mutationFn: () =>
      simApi.openPosition(thesis.id, toPaise(amount), price || undefined),
    onSuccess: onOpened,
    onError: (e) => setError(e.message),
  })
  const statusColor =
    thesis.status === 'LIVE'
      ? 'var(--phosphor)'
      : thesis.status === 'INVALIDATED'
        ? 'var(--madder)'
        : 'var(--text-tertiary)'
  return (
    <div
      style={{
        border: '1px solid var(--rule)',
        borderRadius: 'var(--radius-panel)',
        padding: 'var(--spacing-3)',
        display: 'grid',
        gap: 'var(--spacing-3)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--spacing-3)', flexWrap: 'wrap' }}>
        <strong style={{ font: '600 var(--t-section) var(--font-ui)' }}>
          {thesis.tradingsymbol ?? thesis.isin}
        </strong>
        <span className="legend-strip" style={{ color: statusColor }}>
          {thesis.status} · {thesis.horizon} · {thesis.conviction}
        </span>
        <span style={{ flex: 1 }} />
        <span
          className="legend-strip"
          data-numeric
          style={{
            color: 'var(--text-tertiary)',
            border: '1px solid var(--rule)',
            borderRadius: 'var(--radius-panel)',
            padding: '2px 8px',
          }}
        >
          expires {thesis.expires_on}
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(220px, 1fr) 2fr', gap: 'var(--spacing-4)' }}>
        <div>
          <Metric label="Ref price" value={String(thesis.ref_price)} unit="₹" provenance="YOUR INPUT" />
          <div style={{ marginTop: 'var(--spacing-2)' }}>
            <Band
              bearPct={Number(thesis.band_bear_pct)}
              basePct={Number(thesis.band_base_pct)}
              bullPct={Number(thesis.band_bull_pct)}
            />
          </div>
        </div>
        <div>
          <p style={{ margin: 0, color: 'var(--text-secondary)', whiteSpace: 'pre-wrap' }}>
            {thesis.report_md}
          </p>
          <ul style={{ margin: 'var(--spacing-2) 0 0', paddingLeft: 18, color: 'var(--text-tertiary)', fontSize: 'var(--t-data)' }}>
            {thesis.falsifiers.map((f, i) => (
              <li key={i}>
                {String(f.human_text)}{' '}
                <span className="legend-strip">({String(f.field_id)})</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      {thesis.status === 'LIVE' && (
        <div style={{ display: 'flex', gap: 'var(--spacing-2)', alignItems: 'center', flexWrap: 'wrap' }}>
          <input placeholder="Amount ₹" value={amount} onChange={(e) => setAmount(e.target.value)} style={inputStyle} inputMode="decimal" />
          <input placeholder="Price ₹ (blank = last close)" value={price} onChange={(e) => setPrice(e.target.value)} style={inputStyle} inputMode="decimal" />
          <button style={brassBtn} disabled={!amount || open.isPending} onClick={() => open.mutate()}>
            Simulate
          </button>
          {error && <span style={{ color: 'var(--madder)', fontSize: 'var(--t-data)' }}>{error}</span>}
        </div>
      )}
    </div>
  )
}

function PositionRow({ position: p, onClosed }: { position: PositionOut; onClosed: () => void }) {
  const [journal, setJournal] = useState('')
  const [error, setError] = useState<string | null>(null)
  const close = useMutation({
    mutationFn: () => simApi.closePosition(p.id, 'MANUAL', journal),
    onSuccess: onClosed,
    onError: (e) => setError(e.message),
  })
  const mark = p.latest_mark as {
    trade_date: string
    mtm_inr: number
    unrealised_pct: string
    drawdown_from_peak_pct: string
  } | null
  return (
    <div
      style={{
        border: '1px solid var(--rule)',
        borderRadius: 'var(--radius-panel)',
        padding: 'var(--spacing-3)',
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
        gap: 'var(--spacing-3)',
        alignItems: 'end',
      }}
    >
      {p.flagged_at && !p.closed_on && (
        <div
          style={{
            gridColumn: '1 / -1',
            borderLeft: '2px solid var(--madder)',
            padding: '2px var(--spacing-2)',
            font: '400 var(--t-body) var(--font-ui)',
            color: 'var(--text-primary)',
          }}
        >
          <span style={{ color: 'var(--madder)', fontWeight: 600 }}>FLAGGED</span>{' '}
          — {p.flag_reason} · Not auto-closed: closing is your call, and the call
          gets scored.
        </div>
      )}
      <Metric label={p.isin} value={`${p.qty} sh @ ${p.entry_price}`} provenance="COMPUTED" />
      <Metric label="Entry costs" value={inr(p.entry_costs_inr)} provenance="COMPUTED" />
      <Metric
        label={mark ? `MTM (${mark.trade_date})` : 'MTM'}
        value={mark ? inr(mark.mtm_inr) : null}
        delta={mark ? `${mark.unrealised_pct}%` : null}
        provenance="COMPUTED"
      />
      <Metric
        label="Drawdown from peak"
        value={mark ? `${mark.drawdown_from_peak_pct}%` : null}
        provenance="COMPUTED"
      />
      {p.closed_on ? (
        <Metric
          label={`Closed ${p.closed_on} (${p.close_reason})`}
          value={p.realised_pnl_inr !== null ? inr(p.realised_pnl_inr) : null}
          delta={p.holding_xirr_pct != null ? `${p.holding_xirr_pct}% xirr` : null}
          provenance="COMPUTED"
        />
      ) : (
        <div style={{ display: 'grid', gap: 'var(--spacing-1)' }}>
          <input
            placeholder="Why close now? (required)"
            value={journal}
            onChange={(e) => setJournal(e.target.value)}
            style={inputStyle}
          />
          <button style={ghostBtn} disabled={!journal || close.isPending} onClick={() => close.mutate()}>
            Close position
          </button>
          {error && <span style={{ color: 'var(--madder)', fontSize: 'var(--t-data)' }}>{error}</span>}
        </div>
      )}
    </div>
  )
}

function ThesisForm({ onDone }: { onDone: () => void }) {
  const [f, setF] = useState({
    symbol: '', isin: '', token: '', horizon: 'MID', expires: '', ref: '',
    bear: '', base: '', bull: '', conviction: 'MODERATE', size: '',
    thesis: '', falsifierField: 'price.close', falsifierOp: 'LT',
    falsifierThreshold: '', falsifierText: '',
  })
  const [error, setError] = useState<string | null>(null)
  const save = useMutation({
    mutationFn: () => {
      const body: ManualThesisIn = {
        isin: f.isin,
        tradingsymbol: f.symbol || null,
        instrument_token: f.token ? Number(f.token) : null,
        horizon: f.horizon,
        expires_on: f.expires,
        ref_price: f.ref,
        band_bear_pct: f.bear,
        band_base_pct: f.base,
        band_bull_pct: f.bull,
        conviction: f.conviction,
        suggested_size_inr: toPaise(f.size),
        thesis_md: f.thesis,
        falsifiers: [
          {
            field_id: f.falsifierField,
            operator: f.falsifierOp,
            threshold: f.falsifierThreshold,
            human_text: f.falsifierText,
          },
        ],
      }
      return simApi.postThesis(body)
    },
    onSuccess: onDone,
    onError: (e) => setError(e.message),
  })
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setF({ ...f, [k]: e.target.value })
  return (
    <Panel legend="YOUR INPUT" title="New thesis — falsifiable or nothing">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 'var(--spacing-2)' }}>
        <input placeholder="Symbol" value={f.symbol} onChange={set('symbol')} style={inputStyle} />
        <input placeholder="ISIN (required)" value={f.isin} onChange={set('isin')} style={inputStyle} />
        <input placeholder="Kite token (optional)" value={f.token} onChange={set('token')} style={inputStyle} />
        <select value={f.horizon} onChange={set('horizon')} style={inputStyle}>
          <option>SHORT</option><option>MID</option><option>LONG</option>
        </select>
        <input placeholder="Expires (YYYY-MM-DD)" value={f.expires} onChange={set('expires')} style={inputStyle} />
        <input placeholder="Ref price ₹" value={f.ref} onChange={set('ref')} style={inputStyle} inputMode="decimal" />
        <input placeholder="Bear %" value={f.bear} onChange={set('bear')} style={inputStyle} inputMode="decimal" />
        <input placeholder="Base %" value={f.base} onChange={set('base')} style={inputStyle} inputMode="decimal" />
        <input placeholder="Bull %" value={f.bull} onChange={set('bull')} style={inputStyle} inputMode="decimal" />
        <select value={f.conviction} onChange={set('conviction')} style={inputStyle}>
          <option>LOW</option><option>MODERATE</option><option>HIGH</option>
        </select>
        <input placeholder="Size ₹" value={f.size} onChange={set('size')} style={inputStyle} inputMode="decimal" />
      </div>
      <textarea
        placeholder="The thesis. What has to be true, and why the market disagrees."
        value={f.thesis}
        onChange={(e) => setF({ ...f, thesis: e.target.value })}
        rows={3}
        style={{ ...inputStyle, width: '100%', marginTop: 'var(--spacing-2)', resize: 'vertical' }}
      />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 'var(--spacing-2)', marginTop: 'var(--spacing-2)' }}>
        <input placeholder="Falsifier field_id" value={f.falsifierField} onChange={set('falsifierField')} style={inputStyle} />
        <select value={f.falsifierOp} onChange={set('falsifierOp')} style={inputStyle}>
          <option>LT</option><option>LTE</option><option>GT</option><option>GTE</option>
          <option>CROSSES_BELOW</option><option>CROSSES_ABOVE</option>
        </select>
        <input placeholder="Threshold" value={f.falsifierThreshold} onChange={set('falsifierThreshold')} style={inputStyle} inputMode="decimal" />
        <input placeholder="Kill condition in plain words" value={f.falsifierText} onChange={set('falsifierText')} style={inputStyle} />
      </div>
      {error && <p role="alert" style={{ color: 'var(--madder)' }}>{error}</p>}
      <div style={{ marginTop: 'var(--spacing-3)' }}>
        <button style={brassBtn} disabled={save.isPending} onClick={() => save.mutate()}>
          Record thesis
        </button>
      </div>
    </Panel>
  )
}

const inputStyle: React.CSSProperties = {
  font: '400 var(--t-data) var(--font-data)',
  background: 'var(--ink)',
  color: 'var(--text-primary)',
  border: '1px solid var(--rule)',
  borderRadius: 'var(--radius-panel)',
  padding: '8px 10px',
}

const brassBtn: React.CSSProperties = {
  font: '600 var(--t-data) var(--font-ui)',
  background: 'var(--brass)',
  color: 'var(--ink)',
  border: 'none',
  borderRadius: 'var(--radius-panel)',
  padding: '8px 16px',
  cursor: 'pointer',
}

const ghostBtn: React.CSSProperties = {
  font: '600 var(--t-data) var(--font-ui)',
  background: 'transparent',
  color: 'var(--brass)',
  border: '1px solid var(--brass)',
  borderRadius: 'var(--radius-panel)',
  padding: '8px 16px',
  cursor: 'pointer',
}
