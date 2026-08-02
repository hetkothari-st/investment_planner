import type { ReactNode } from 'react'
import { motion, useReducedMotion } from 'motion/react'
import { Legend, type Provenance } from './Legend'

/** The workhorse container. Legend is required — every panel declares the
 * epistemic status of its contents. */
export function Panel({
  legend,
  title,
  actions,
  coverage,
  entryIndex = 0,
  children,
}: {
  legend: Provenance
  title?: string
  actions?: ReactNode
  /** 0..1 fraction of metrics computable; renders as a badge when provided */
  coverage?: number
  /** stagger position for the once-on-mount entry (40ms steps) */
  entryIndex?: number
  children: ReactNode
}) {
  const reduced = useReducedMotion()
  return (
    <motion.section
      className="panel-bevel"
      initial={reduced ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1], delay: entryIndex * 0.04 }}
      style={{ padding: 'var(--spacing-4)' }}
    >
      <header
        style={{
          display: 'flex',
          alignItems: 'baseline',
          gap: 'var(--spacing-3)',
          marginBottom: title || coverage !== undefined ? 'var(--spacing-3)' : 0,
        }}
      >
        <Legend provenance={legend} />
        {coverage !== undefined && (
          <span
            className="legend-strip"
            data-numeric
            style={{ color: 'var(--phosphor)', opacity: 0.75 }}
          >
            coverage {Math.round(coverage * 100)}%
          </span>
        )}
        <span style={{ flex: 1 }} />
        {actions}
      </header>
      {title && (
        <h2
          style={{
            font: '600 var(--t-section) var(--font-ui)',
            color: 'var(--text-primary)',
            margin: '0 0 var(--spacing-3)',
          }}
        >
          {title}
        </h2>
      )}
      {children}
    </motion.section>
  )
}
