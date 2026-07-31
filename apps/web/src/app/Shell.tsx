import type { ReactNode } from 'react'
import { NavLink } from 'react-router'

/** 68px icon rail, no labels, tooltip on hover. Active item: 2px brass bar
 * on the left edge — a physical switch indicator, not a filled pill. */

const NAV = [
  { to: '/planner', title: 'Planner', glyph: 'P' },
  { to: '/allocation', title: 'Allocation', glyph: 'A' },
  { to: '/equity', title: 'Equity research', glyph: 'E' },
  { to: '/simulator', title: 'Simulator', glyph: 'S' },
  { to: '/alerts', title: 'Alerts', glyph: '!' },
  { to: '/calibration', title: 'Calibration', glyph: 'C' },
  { to: '/kitchen-sink', title: 'Kitchen sink', glyph: 'K' },
]

export function Shell({ children }: { children: ReactNode }) {
  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <nav
        aria-label="Primary"
        style={{
          width: 68,
          flexShrink: 0,
          borderRight: '1px solid var(--rule)',
          background: 'var(--panel)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'stretch',
          paddingTop: 'var(--spacing-4)',
          gap: 'var(--spacing-1)',
        }}
      >
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            title={item.title}
            style={({ isActive }) => ({
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              height: 44,
              textDecoration: 'none',
              borderLeft: `2px solid ${isActive ? 'var(--brass)' : 'transparent'}`,
              color: isActive ? 'var(--text-primary)' : 'var(--text-tertiary)',
              font: '600 var(--t-section) var(--font-ui)',
              transition: 'color var(--d-instant) var(--ease-quick)',
            })}
          >
            {item.glyph}
          </NavLink>
        ))}
      </nav>
      <div style={{ flex: 1, minWidth: 0 }}>{children}</div>
    </div>
  )
}
