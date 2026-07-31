// @vitest-environment jsdom
import { renderToString } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { expect, test } from 'vitest'
import { App } from './App'

test('kitchen sink route renders every primitive section', () => {
  const html = renderToString(
    <MemoryRouter initialEntries={['/kitchen-sink']}>
      <App />
    </MemoryRouter>,
  )
  for (const expected of [
    'Kitchen sink',
    'Scenario band',
    'Falsifiers',
    'Calibration dial',
    'COIN FLIP',
    'UNCALIBRATED',
  ]) {
    expect(html).toContain(expected)
  }
  // A missing metric renders as an em dash, never zero.
  expect(html).toContain('—')
})
