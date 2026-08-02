import { useQuery } from '@tanstack/react-query'
import { CalibrationDial, Empty, Panel, type HorizonCalibration } from '../../design'
import { simApi, type HorizonSummary } from '../../lib/api'

/** The dashboard signature, wired to real scored calls. When a horizon has
 * fewer than 20, the dial says UNCALIBRATED rather than lying with a rate. */

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

export function CalibrationPage() {
  const summary = useQuery({ queryKey: ['calibration'], queryFn: simApi.calibration })

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
        Calibration
      </h1>
      {summary.isLoading ? (
        <Empty missing="Loading calibration…" fix="" />
      ) : !summary.data ? (
        <Empty
          missing="The API is unreachable."
          fix="Start it with docker compose up, then reload."
        />
      ) : (
        <Panel legend="COMPUTED" title="Measured direction hit rate by horizon">
          <div style={{ display: 'grid', placeItems: 'center' }}>
            <CalibrationDial horizons={summary.data.map(toDial)} />
          </div>
        </Panel>
      )}
    </main>
  )
}
