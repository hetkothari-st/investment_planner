import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import { CalibrationDial, Empty, Panel, type HorizonCalibration } from '../../design'
import { liveApi, simApi, type HorizonSummary } from '../../lib/api'
import { connectLive, type LiveMsg, type StateMsg, type TickMsg } from '../../lib/live'

/** The dashboard — docs/09: the calibration dial is the hero, the market
 * overview is context. Live numbers tick in place (tabular numerals, no
 * reflow); the connection state is always stated, never implied. */

const INDEX_NAMES: Record<number, string> = {
  256265: 'NIFTY 50',
  260105: 'NIFTY BANK',
  257801: 'NIFTY MIDCAP 100',
}

const STOCK_NAMES: Record<number, string> = {
  408065: 'INFY',
  738561: 'RELIANCE',
  2953217: 'TCS',
  341249: 'HDFCBANK',
  1270529: 'ONGC',
}

function toDial(s: HorizonSummary): HorizonCalibration {
  return {
    horizon: s.horizon as HorizonCalibration['horizon'],
    hitRatePct: s.hit_rate_pct !== null ? Number(s.hit_rate_pct) : null,
    n: s.n,
    netAlphaPct: s.net_alpha_pct !== null ? Number(s.net_alpha_pct) : null,
    brier: s.mean_brier !== null ? Number(s.mean_brier) : null,
    verdict: s.verdict,
    severity: s.severity as HorizonCalibration['severity'],
  }
}

function useLiveTicks() {
  const [ticks, setTicks] = useState<Record<number, TickMsg>>({})
  const [upstream, setUpstream] = useState<StateMsg | null>(null)
  const [link, setLink] = useState<'open' | 'reconnecting'>('reconnecting')
  const [offDetail, setOffDetail] = useState<string | null>(null)
  useEffect(() => {
    const socket = connectLive((msg: LiveMsg) => {
      if (msg.type === 'tick') {
        setTicks((t) => ({ ...t, [msg.instrument_token]: msg }))
      } else if (msg.type === 'snapshot') {
        setUpstream(msg.state)
        setOffDetail(null)
        setTicks(Object.fromEntries(msg.ticks.map((t) => [t.instrument_token, t])))
      } else if (msg.type === 'state') {
        setUpstream(msg)
        if (msg.status === 'OFF') setOffDetail(msg.detail ?? 'Live feed is off.')
      }
    }, setLink)
    return socket.close
  }, [])
  return { ticks, upstream, link, offDetail }
}

function ConnectionChip({
  link,
  upstream,
}: {
  link: 'open' | 'reconnecting'
  upstream: StateMsg | null
}) {
  const state = link !== 'open' ? 'LINK LOST' : (upstream?.status ?? 'CONNECTING')
  const color =
    state === 'CONNECTED'
      ? 'var(--phosphor)'
      : state === 'OFF' || state === 'LINK LOST'
        ? 'var(--text-tertiary)'
        : 'var(--brass)'
  return (
    <span
      className="legend-strip"
      data-numeric
      style={{ display: 'inline-flex', alignItems: 'center', gap: 8, color: 'var(--text-tertiary)' }}
    >
      <span style={{ width: 7, height: 7, borderRadius: '50%', background: color }} />
      {state}
      {upstream != null && upstream.reconnects > 0 && ` · ${upstream.reconnects} reconnects`}
    </span>
  )
}

function Quote({ name, tick }: { name: string; tick: TickMsg | undefined }) {
  const prev = useRef<string | null>(null)
  const [pulse, setPulse] = useState(false)
  useEffect(() => {
    if (tick && prev.current !== null && prev.current !== tick.last_price) {
      setPulse(true)
      const t = setTimeout(() => setPulse(false), 350)
      return () => clearTimeout(t)
    }
    prev.current = tick?.last_price ?? null
  }, [tick])
  useEffect(() => {
    prev.current = tick?.last_price ?? null
  }, [tick])
  const change = tick?.change_pct != null ? Number(tick.change_pct) : null
  return (
    <div style={{ minWidth: 168 }}>
      <div className="legend-strip" style={{ color: 'var(--text-tertiary)' }}>
        {name}
      </div>
      <div
        data-numeric
        style={{
          font: '500 var(--t-data-lg) var(--font-data)',
          color: pulse ? 'var(--phosphor)' : 'var(--text-primary)',
          transition: 'color 300ms',
        }}
      >
        {tick ? Number(tick.last_price).toLocaleString('en-IN') : '—'}
      </div>
      <div
        data-numeric
        style={{
          font: '400 var(--t-data) var(--font-data)',
          color:
            change == null
              ? 'var(--text-tertiary)'
              : change < 0
                ? 'var(--madder)'
                : 'var(--jade)',
        }}
      >
        {change == null ? '—' : `${change > 0 ? '+' : ''}${change.toFixed(2)}%`}
      </div>
    </div>
  )
}

function Movers({ ticks }: { ticks: Record<number, TickMsg> }) {
  const rows = useMemo(() => {
    return Object.values(ticks)
      .filter((t) => !(t.instrument_token in INDEX_NAMES) && t.change_pct != null)
      .sort((a, b) => Number(b.change_pct) - Number(a.change_pct))
  }, [ticks])
  if (rows.length === 0)
    return (
      <Empty
        missing="No movers yet."
        fix="Movers come from the live snapshot; they appear when the feed delivers stock ticks."
      />
    )
  return (
    <div style={{ display: 'grid', gap: 'var(--spacing-1)' }}>
      {rows.map((t) => {
        const change = Number(t.change_pct)
        return (
          <div
            key={t.instrument_token}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              padding: '6px 0',
              borderBottom: '1px solid color-mix(in srgb, var(--rule) 50%, transparent)',
            }}
          >
            <span style={{ font: '500 var(--t-body) var(--font-ui)' }}>
              {STOCK_NAMES[t.instrument_token] ?? t.instrument_token}
            </span>
            <span data-numeric style={{ font: '400 var(--t-data) var(--font-data)' }}>
              {Number(t.last_price).toLocaleString('en-IN')}{' '}
              <span style={{ color: change < 0 ? 'var(--madder)' : 'var(--jade)' }}>
                {change > 0 ? '+' : ''}
                {change.toFixed(2)}%
              </span>
            </span>
          </div>
        )
      })}
    </div>
  )
}

export function DashboardPage() {
  const { ticks, upstream, link, offDetail } = useLiveTicks()
  const status = useQuery({
    queryKey: ['live-status'],
    queryFn: liveApi.status,
    refetchInterval: 30_000,
  })
  const calibration = useQuery({ queryKey: ['calibration'], queryFn: simApi.calibration })

  return (
    <main
      style={{
        maxWidth: 1100,
        margin: '0 auto',
        padding: 'var(--spacing-4)',
        display: 'grid',
        gap: 'var(--spacing-4)',
      }}
    >
      <header style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--spacing-4)', flexWrap: 'wrap' }}>
        <h1
          style={{
            font: '700 var(--t-display) var(--font-display)',
            fontStretch: '96%',
            letterSpacing: '-0.02em',
            margin: 0,
          }}
        >
          Corpus
        </h1>
        <ConnectionChip link={link} upstream={upstream} />
        {status.data && (
          <span className="legend-strip" style={{ color: 'var(--text-tertiary)' }}>
            {status.data.detail}
          </span>
        )}
      </header>

      <Panel legend="MEASURED" title="Market" entryIndex={0}>
        {offDetail ? (
          <Empty missing="The live feed is off." fix={offDetail} />
        ) : (
          <div style={{ display: 'flex', gap: 'var(--spacing-5)', flexWrap: 'wrap' }}>
            {Object.entries(INDEX_NAMES).map(([token, name]) => (
              <Quote key={token} name={name} tick={ticks[Number(token)]} />
            ))}
          </div>
        )}
      </Panel>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
          gap: 'var(--spacing-4)',
        }}
      >
        <Panel legend="COMPUTED" title="Calibration — the instrument measures itself" entryIndex={1}>
          {calibration.data && calibration.data.some((h) => h.n > 0) ? (
            <CalibrationDial horizons={calibration.data.map(toDial)} />
          ) : (
            <Empty
              missing="No scored calls yet."
              fix="The dial engages as recommendations expire and get scored. Until then it stays honest and blank."
            />
          )}
        </Panel>

        <Panel legend="MEASURED" title="Movers" entryIndex={2}>
          <Movers ticks={ticks} />
        </Panel>
      </div>
    </main>
  )
}
