import { useMemo, useState } from 'react'

/** Sortable, sticky header, virtualised beyond 100 rows.
 * Numeric columns right-aligned in the data face, tabular.
 * Sort indicator is a 1px underline on the header, not a caret. */
export type Column<T> = {
  key: string
  label: string
  numeric?: boolean
  render: (row: T) => string | null
  sortValue?: (row: T) => number | string
}

const ROW_H = 38
const VIRTUAL_THRESHOLD = 100
const OVERSCAN = 6

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  maxHeight = 420,
}: {
  columns: Column<T>[]
  rows: T[]
  rowKey: (row: T) => string
  maxHeight?: number
}) {
  const [sortKey, setSortKey] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<1 | -1>(1)
  const [scrollTop, setScrollTop] = useState(0)

  const sorted = useMemo(() => {
    if (!sortKey) return rows
    const col = columns.find((c) => c.key === sortKey)
    if (!col) return rows
    const val = col.sortValue ?? ((r: T) => col.render(r) ?? '')
    return [...rows].sort((a, b) => {
      const va = val(a)
      const vb = val(b)
      return (va < vb ? -1 : va > vb ? 1 : 0) * sortDir
    })
  }, [rows, columns, sortKey, sortDir])

  const virtual = rows.length > VIRTUAL_THRESHOLD
  const first = virtual ? Math.max(0, Math.floor(scrollTop / ROW_H) - OVERSCAN) : 0
  const visible = virtual
    ? sorted.slice(first, first + Math.ceil(maxHeight / ROW_H) + OVERSCAN * 2)
    : sorted

  const toggleSort = (key: string) => {
    if (sortKey === key) setSortDir((d) => (d === 1 ? -1 : 1))
    else {
      setSortKey(key)
      setSortDir(1)
    }
  }

  return (
    <div
      style={{ overflowY: 'auto', maxHeight, position: 'relative' }}
      onScroll={virtual ? (e) => setScrollTop(e.currentTarget.scrollTop) : undefined}
    >
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr
            style={{
              position: 'sticky',
              top: 0,
              background: 'var(--panel)',
              boxShadow: 'inset 0 -1px 0 var(--brass)',
              zIndex: 1,
            }}
          >
            {columns.map((c) => (
              <th key={c.key} style={{ padding: 0, textAlign: c.numeric ? 'right' : 'left' }}>
                <button
                  onClick={() => toggleSort(c.key)}
                  className="legend-strip"
                  style={{
                    all: 'unset',
                    cursor: 'pointer',
                    display: 'block',
                    width: '100%',
                    boxSizing: 'border-box',
                    padding: '10px 12px',
                    textAlign: c.numeric ? 'right' : 'left',
                    color: 'var(--text-secondary)',
                    font: '600 var(--t-label) var(--font-ui)',
                    letterSpacing: '0.14em',
                    textTransform: 'uppercase',
                    textDecoration: sortKey === c.key ? 'underline' : 'none',
                    textUnderlineOffset: 4,
                    textDecorationThickness: 1,
                  }}
                  aria-sort={
                    sortKey === c.key ? (sortDir === 1 ? 'ascending' : 'descending') : undefined
                  }
                >
                  {c.label}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {virtual && first > 0 && (
            <tr aria-hidden style={{ height: first * ROW_H }}>
              <td colSpan={columns.length} />
            </tr>
          )}
          {visible.map((row) => (
            <tr
              key={rowKey(row)}
              style={{
                height: ROW_H,
                boxShadow: 'inset 0 -1px 0 color-mix(in srgb, var(--rule) 50%, transparent)',
                transition: 'background var(--d-instant) var(--ease-quick)',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--panel-raised)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              {columns.map((c) => {
                const v = c.render(row)
                return (
                  <td
                    key={c.key}
                    data-numeric={c.numeric || undefined}
                    style={{
                      padding: '0 12px',
                      textAlign: c.numeric ? 'right' : 'left',
                      font: c.numeric
                        ? '400 var(--t-data) var(--font-data)'
                        : '400 var(--t-body) var(--font-ui)',
                      color: v === null ? 'var(--text-tertiary)' : 'var(--text-primary)',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {v ?? '—'}
                  </td>
                )
              })}
            </tr>
          ))}
          {virtual && first + visible.length < sorted.length && (
            <tr aria-hidden style={{ height: (sorted.length - first - visible.length) * ROW_H }}>
              <td colSpan={columns.length} />
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
