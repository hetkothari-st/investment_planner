/** The risk × return × liquidity layout — docs/04.
 *
 * One pure function produces the data for BOTH the 3D scene and the 2D
 * fallback table. The acceptance criterion "the scatter's 2D table matches
 * the 3D positions exactly" is met by construction: there is no second
 * pathway, and the vitest suite checks the mapping round-trips.
 */

import type { components } from '@corpus/contracts/api'

export type VehicleScore = components['schemas']['VehicleScore']
export type GatedVehicle = components['schemas']['GatedVehicle']

export interface ScatterDatum {
  vehicle_id: string
  label: string
  /** volatility_annual_pct, as displayed in the table */
  risk: number
  /** net_expected_return_pct at the ranking horizon, as displayed */
  ret: number
  /** worst-case days to cash: settlement + hard lock (matches fit_liquidity) */
  daysToCash: number
  gated: boolean
  gate?: string
  explanation?: string
  suitability?: string
  allocatedPaise: number
}

const DAYS_PER_MONTH = 30.4

/** Fixed axis extents (declared, not data-fitted, so positions are stable
 * across reloads and comparable across profiles). */
export const EXTENT = {
  risk: [0, 30] as const, // σ% — direct mid/small sits at 26
  ret: [-2, 12] as const, // net %/yr — savings is negative-real, honest
  days: [0, 2000] as const, // SGB's 60-month lock ≈ 1829 days
}

/** Half-extent of the scene cube in world units. */
export const CUBE = 2

export function toDatum(
  v: VehicleScore | GatedVehicle,
  allocatedPaise = 0,
): ScatterDatum {
  const gated = 'gate' in v
  return {
    vehicle_id: v.vehicle_id,
    label: v.label,
    risk: Number(v.volatility_annual_pct),
    ret: Number(v.net_expected_return_pct),
    daysToCash: v.liquidity_days + v.lock_in_months * DAYS_PER_MONTH,
    gated,
    gate: gated ? v.gate : undefined,
    explanation: gated ? v.explanation : undefined,
    suitability: gated ? undefined : v.suitability_pct,
    allocatedPaise,
  }
}

function lin(value: number, lo: number, hi: number): number {
  const t = (value - lo) / (hi - lo)
  return (Math.min(1, Math.max(0, t)) * 2 - 1) * CUBE
}

/** Liquidity uses a declared log10 axis (labelled in the scene): days-to-cash
 * spans 0 to ~1800 and a linear axis would collapse everything tradable into
 * one point. The table shows the raw number; this is presentation only. */
function liqScale(days: number): number {
  const t =
    Math.log10(1 + Math.min(days, EXTENT.days[1])) / Math.log10(1 + EXTENT.days[1])
  return (t * 2 - 1) * CUBE
}

/** World position [x, y, z] = [risk, return, liquidity]. */
export function position(d: ScatterDatum): [number, number, number] {
  return [
    lin(d.risk, EXTENT.risk[0], EXTENT.risk[1]),
    lin(d.ret, EXTENT.ret[0], EXTENT.ret[1]),
    liqScale(d.daysToCash),
  ]
}

/** Sphere radius: allocated vehicles sized by rupee amount (area ∝ money),
 * eligible-but-unallocated small, ghosts fixed. */
export function radius(d: ScatterDatum, totalAllocatedPaise: number): number {
  if (d.gated) return 0.09
  if (d.allocatedPaise <= 0 || totalAllocatedPaise <= 0) return 0.055
  return 0.09 + 0.28 * Math.sqrt(d.allocatedPaise / totalAllocatedPaise)
}

export function buildData(
  ranked: VehicleScore[],
  gated: GatedVehicle[],
): ScatterDatum[] {
  return [
    ...ranked.map((v) =>
      toDatum(v, v.allocated_lumpsum + 12 * v.allocated_monthly),
    ),
    ...gated.map((v) => toDatum(v)),
  ]
}
