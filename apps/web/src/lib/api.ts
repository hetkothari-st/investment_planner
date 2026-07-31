/** Typed fetch over the generated contracts. Types are never hand-written —
 * regenerate with `pnpm --filter @corpus/contracts generate` after API changes. */

import type { components } from '@corpus/contracts/api'

// Money fields differ by direction: requests accept paise ints, responses
// emit them. Use the Input variants for writes; UserState carries Outputs.
export type ProfileIn = components['schemas']['ProfileIn-Input']
export type DebtIn = components['schemas']['DebtIn-Input']
export type GoalIn = components['schemas']['GoalIn-Input']
export type PlanResult = components['schemas']['PlanResult']
export type GateResult = components['schemas']['GateResult']
export type UserState = components['schemas']['UserState']
export type TemperamentScenario = components['schemas']['TemperamentScenario']

export class ApiError extends Error {
  constructor(
    public status: number,
    detail: string,
  ) {
    super(detail)
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!resp.ok) {
    let detail = resp.statusText
    try {
      detail = (await resp.json()).detail ?? detail
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(resp.status, detail)
  }
  return resp.json() as Promise<T>
}

export const api = {
  state: () => request<UserState>('/planner/state'),
  putProfile: (p: ProfileIn) =>
    request<ProfileIn>('/planner/profile', { method: 'PUT', body: JSON.stringify(p) }),
  putDebts: (d: DebtIn[]) =>
    request<DebtIn[]>('/planner/debts', { method: 'PUT', body: JSON.stringify(d) }),
  putGoals: (g: GoalIn[]) =>
    request<GoalIn[]>('/planner/goals', { method: 'PUT', body: JSON.stringify(g) }),
  computePlan: () => request<PlanResult>('/planner/plan', { method: 'POST' }),
  latestPlan: () => request<PlanResult>('/planner/plan/latest'),
  temperamentScenario: () => request<TemperamentScenario>('/planner/temperament-scenario'),
}

/** Integer paise (JSON transport) -> display rupees, Indian grouping. */
export function inr(paise: number): string {
  return `₹${new Intl.NumberFormat('en-IN').format(Math.round(paise / 100))}`
}

/** Display rupees string -> integer paise for transport. */
export function toPaise(rupees: string | number): number {
  return Math.round(Number(rupees) * 100)
}
