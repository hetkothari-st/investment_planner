/** The acceptance criterion: the 2D table matches the 3D positions exactly.
 * Both views render the same ScatterDatum array; these tests pin the mapping
 * so a change to either side breaks loudly. */

import { describe, expect, it } from 'vitest'
import {
  buildData,
  CUBE,
  EXTENT,
  position,
  radius,
  toDatum,
  type GatedVehicle,
  type VehicleScore,
} from './scatter'

const score = (over: Partial<VehicleScore> = {}): VehicleScore => ({
  vehicle_id: 'equity.index_largecap',
  label: 'Large-cap index fund',
  suitability_pct: '81.8',
  components: {},
  net_expected_return_pct: '10.28',
  volatility_annual_pct: '17.0',
  liquidity_days: 3,
  lock_in_months: 0,
  effort: 'LOW',
  knowledge_required: 'LOW',
  allocated_lumpsum: 60000000,
  allocated_monthly: 4000000,
  ...over,
})

const gated = (over: Partial<GatedVehicle> = {}): GatedVehicle => ({
  vehicle_id: 'derivatives.fno',
  label: 'Futures & options',
  gate: 'module_disabled',
  explanation: 'Gated off until the F&O module exists.',
  net_expected_return_pct: '0.0',
  volatility_annual_pct: '60.0',
  liquidity_days: 0,
  lock_in_months: 0,
  ...over,
})

describe('toDatum', () => {
  it('carries the exact numbers the table displays', () => {
    const d = toDatum(score(), 123)
    expect(d.risk).toBe(17.0)
    expect(d.ret).toBe(10.28)
    expect(d.daysToCash).toBe(3)
    expect(d.gated).toBe(false)
    expect(d.suitability).toBe('81.8')
    expect(d.allocatedPaise).toBe(123)
  })

  it('counts a hard lock into days-to-cash (matches fit_liquidity)', () => {
    const d = toDatum(score({ liquidity_days: 5, lock_in_months: 60 }))
    expect(d.daysToCash).toBeCloseTo(5 + 60 * 30.4, 10)
  })

  it('marks gated vehicles and names the gate', () => {
    const d = toDatum(gated())
    expect(d.gated).toBe(true)
    expect(d.gate).toBe('module_disabled')
    expect(d.suitability).toBeUndefined()
  })
})

describe('position — the table-to-scene mapping', () => {
  it('is the documented linear map on risk and return', () => {
    const d = toDatum(score())
    const [x, y] = position(d)
    // x: risk 17 on [0,30] -> (17/30)*2-1 scaled by CUBE
    expect(x).toBeCloseTo(((17 / 30) * 2 - 1) * CUBE, 12)
    // y: ret 10.28 on [-2,12]
    expect(y).toBeCloseTo((((10.28 - -2) / 14) * 2 - 1) * CUBE, 12)
  })

  it('is the documented log map on liquidity', () => {
    const d = toDatum(score({ liquidity_days: 5, lock_in_months: 60 }))
    const [, , z] = position(d)
    const days = 5 + 60 * 30.4
    const t = Math.log10(1 + days) / Math.log10(1 + EXTENT.days[1])
    expect(z).toBeCloseTo((t * 2 - 1) * CUBE, 12)
  })

  it('round-trips: unprojecting a position recovers the table values', () => {
    const d = toDatum(score({ volatility_annual_pct: '21.0', net_expected_return_pct: '7.44' }))
    const [x, y, z] = position(d)
    const risk = ((x / CUBE + 1) / 2) * (EXTENT.risk[1] - EXTENT.risk[0]) + EXTENT.risk[0]
    const ret = ((y / CUBE + 1) / 2) * (EXTENT.ret[1] - EXTENT.ret[0]) + EXTENT.ret[0]
    const days = Math.pow(10, ((z / CUBE + 1) / 2) * Math.log10(1 + EXTENT.days[1])) - 1
    expect(risk).toBeCloseTo(d.risk, 10)
    expect(ret).toBeCloseTo(d.ret, 10)
    expect(days).toBeCloseTo(d.daysToCash, 8)
  })

  it('clamps out-of-extent values to the cube instead of flying off', () => {
    const d = toDatum(gated({ volatility_annual_pct: '60.0' }))
    const [x] = position(d)
    expect(x).toBe(CUBE)
  })

  it('is monotonic in each axis', () => {
    const lo = position(toDatum(score({ volatility_annual_pct: '5' })))
    const hi = position(toDatum(score({ volatility_annual_pct: '25' })))
    expect(hi[0]).toBeGreaterThan(lo[0])
  })
})

describe('buildData', () => {
  it('one datum per vehicle, ranked first, ghosts after, no second pathway', () => {
    const data = buildData([score()], [gated()])
    expect(data.map((d) => d.vehicle_id)).toEqual([
      'equity.index_largecap',
      'derivatives.fno',
    ])
    // allocated year-1 rupees = lumpsum + 12 * monthly
    expect(data[0].allocatedPaise).toBe(60000000 + 12 * 4000000)
  })

  it('sizes allocated spheres by money and ghosts fixed', () => {
    const data = buildData([score()], [gated()])
    const total = data.reduce((s, d) => s + d.allocatedPaise, 0)
    expect(radius(data[0], total)).toBeGreaterThan(radius(toDatum(score(), 0), total))
    expect(radius(data[1], total)).toBe(0.09)
  })
})
