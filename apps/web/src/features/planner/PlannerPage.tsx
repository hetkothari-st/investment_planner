import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, api } from '../../lib/api'
import { Empty } from '../../design'
import { IntakeForm } from './IntakeForm'
import { PlanView } from './PlanView'

export function PlannerPage() {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)

  const state = useQuery({ queryKey: ['planner-state'], queryFn: api.state })
  const plan = useQuery({
    queryKey: ['plan-latest'],
    queryFn: api.latestPlan,
    retry: (count, err) => !(err instanceof ApiError && err.status === 404) && count < 2,
  })

  const noPlanYet = plan.error instanceof ApiError && plan.error.status === 404
  const showForm = editing || noPlanYet || (plan.isError && !plan.data)

  return (
    <main style={{ maxWidth: 1440, margin: '0 auto', padding: 'var(--spacing-4)' }}>
      <header
        style={{
          display: 'flex',
          alignItems: 'baseline',
          gap: 'var(--spacing-4)',
          marginBottom: 'var(--spacing-4)',
        }}
      >
        <h1
          style={{
            font: '700 var(--t-display) var(--font-display)',
            fontStretch: '96%',
            letterSpacing: '-0.02em',
            margin: 0,
          }}
        >
          Planner
        </h1>
        <span style={{ flex: 1 }} />
        {plan.data && !showForm && (
          <button
            onClick={() => setEditing(true)}
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
            Edit profile
          </button>
        )}
      </header>

      {plan.isLoading || state.isLoading ? (
        <Empty missing="Loading plan…" fix="" />
      ) : showForm ? (
        <IntakeForm
          initial={state.data}
          onSubmitted={() => {
            setEditing(false)
            queryClient.invalidateQueries({ queryKey: ['plan-latest'] })
            queryClient.invalidateQueries({ queryKey: ['planner-state'] })
          }}
        />
      ) : plan.data ? (
        <PlanView plan={plan.data} />
      ) : (
        <Empty
          missing="The API is unreachable."
          fix="Start it with docker compose up, then reload."
        />
      )}
    </main>
  )
}
