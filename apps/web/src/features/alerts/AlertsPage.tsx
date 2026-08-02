import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router'
import { Empty, Falsifier, Panel, Verdict } from '../../design'
import { alertsApi, type AlertOut, type LiveFalsifierOut } from '../../lib/api'

/** The alert centre — docs/05: thesis-breakage alerts, not price alerts.
 * A stock down 8% with an intact thesis is noise. A stock flat with a
 * broken thesis is urgent. Every alert quotes the original thesis line
 * the breach contradicts, verbatim from the frozen report. */

const OP: Record<string, string> = {
  LT: '<',
  LTE: '≤',
  GT: '>',
  GTE: '≥',
  CROSSES_BELOW: 'crossed below',
  CROSSES_ABOVE: 'crossed above',
}

function AlertCard({ alert }: { alert: AlertOut }) {
  const qc = useQueryClient()
  const ack = useMutation({
    mutationFn: () => alertsApi.ack(alert.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts'] }),
  })
  return (
    <div
      style={{
        border: '1px solid var(--rule)',
        borderLeft: '3px solid var(--madder)',
        borderRadius: 'var(--radius-panel)',
        padding: 'var(--spacing-3)',
        display: 'grid',
        gap: 'var(--spacing-2)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--spacing-3)', flexWrap: 'wrap' }}>
        <span style={{ font: '600 var(--t-section) var(--font-ui)' }}>
          {alert.tradingsymbol ?? alert.isin} · {alert.horizon} thesis invalidated
        </span>
        <span className="legend-strip" data-numeric style={{ color: 'var(--text-tertiary)' }}>
          {alert.field_id} {OP[alert.operator] ?? alert.operator} {alert.threshold} · observed{' '}
          {alert.observed_value} on {alert.observed_as_of}
        </span>
      </div>
      <blockquote
        style={{
          margin: 0,
          padding: 'var(--spacing-2) var(--spacing-3)',
          borderLeft: '2px solid var(--rule)',
          background: 'var(--ink)',
          borderRadius: 'var(--radius-panel)',
          font: '400 var(--t-body) var(--font-ui)',
          color: 'var(--text-primary)',
        }}
      >
        {alert.thesis_line}
        <footer className="legend-strip" style={{ color: 'var(--text-tertiary)', marginTop: 4 }}>
          {alert.thesis_line_found
            ? 'FROM THE FROZEN THESIS, VERBATIM'
            : 'FALSIFIER TEXT — THE FROZEN THESIS NEVER SPELLED THIS LINE OUT'}
        </footer>
      </blockquote>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 'var(--spacing-3)', flexWrap: 'wrap' }}>
        <span style={{ font: '400 var(--t-body) var(--font-ui)', color: 'var(--text-secondary)' }}>
          Linked paper positions are flagged, not auto-closed —{' '}
          <Link to="/simulator" style={{ color: 'var(--brass)' }}>
            decide in the simulator
          </Link>{' '}
          and journal why. That decision gets scored.
        </span>
        {!alert.acknowledged_at && (
          <button
            onClick={() => ack.mutate()}
            disabled={ack.isPending}
            style={{
              font: '600 var(--t-data) var(--font-ui)',
              background: 'transparent',
              color: 'var(--text-secondary)',
              border: '1px solid var(--rule)',
              borderRadius: 'var(--radius-panel)',
              padding: '6px 14px',
              cursor: 'pointer',
            }}
          >
            Acknowledge
          </button>
        )}
      </div>
    </div>
  )
}

function distance(f: LiveFalsifierOut): string {
  if (f.current_value == null) return 'no reading'
  const gap = Number(f.threshold) - Number(f.current_value)
  const away = Math.abs(gap).toFixed(2)
  if (f.operator.startsWith('LT') || f.operator === 'CROSSES_BELOW')
    return gap < 0 ? `${away} above breach line` : `${away} to breach`
  return gap > 0 ? `${away} below breach line` : `${away} past breach`
}

function falsifierStatus(f: LiveFalsifierOut): 'intact' | 'near' | 'breached' {
  if (f.breached) return 'breached'
  if (f.current_value == null) return 'intact'
  const rel = Math.abs(Number(f.threshold) - Number(f.current_value))
  const scale = Math.max(Math.abs(Number(f.threshold)), 1)
  return rel / scale < 0.1 ? 'near' : 'intact'
}

export function AlertsPage() {
  const qc = useQueryClient()
  const alerts = useQuery({ queryKey: ['alerts'], queryFn: () => alertsApi.list(false) })
  const live = useQuery({ queryKey: ['live-falsifiers'], queryFn: alertsApi.liveFalsifiers })
  const check = useMutation({
    mutationFn: alertsApi.check,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alerts'] })
      qc.invalidateQueries({ queryKey: ['live-falsifiers'] })
    },
  })

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
          Alerts
        </h1>
        <button
          onClick={() => check.mutate()}
          disabled={check.isPending}
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
          {check.isPending ? 'Checking…' : 'Run falsifier check'}
        </button>
        {check.data && (
          <span className="legend-strip" data-numeric style={{ color: 'var(--text-tertiary)' }}>
            {check.data.checked} checked · {check.data.breached} breached ·{' '}
            {check.data.skipped.length} without a reading
          </span>
        )}
      </header>

      {check.data && check.data.skipped.length > 0 && (
        <Verdict severity="warning">
          {`Unresolvable falsifiers are gaps, not passes: ${check.data.skipped.join('; ')}`}
        </Verdict>
      )}

      <Panel legend="COMPUTED" title="Thesis breaches" entryIndex={0}>
        {alerts.data && alerts.data.length > 0 ? (
          <div style={{ display: 'grid', gap: 'var(--spacing-3)' }}>
            {alerts.data.map((a) => (
              <AlertCard key={a.id} alert={a} />
            ))}
          </div>
        ) : (
          <Empty
            missing="No open alerts."
            fix="This is the good state. Breaches appear here with the thesis line they contradict; the nightly check (or the button above) raises them."
          />
        )}
      </Panel>

      <Panel legend="MEASURED" title="Live falsifiers — the watch list" entryIndex={1}>
        {live.data && live.data.length > 0 ? (
          <div>
            {live.data.map((f) => (
              <Falsifier
                key={f.falsifier_id}
                humanText={`${f.tradingsymbol ?? f.isin} · ${f.human_text}`}
                fieldId={`${f.field_id} · breach when ${OP[f.operator] ?? f.operator} ${f.threshold}`}
                current={f.current_value == null ? '—' : String(f.current_value)}
                threshold={String(f.threshold)}
                distance={distance(f)}
                status={falsifierStatus(f)}
              />
            ))}
          </div>
        ) : (
          <Empty
            missing="No falsifiers on live theses."
            fix="Every thesis carries at least one; once a thesis is live its falsifiers appear here with distance to breach."
          />
        )}
      </Panel>
    </main>
  )
}
