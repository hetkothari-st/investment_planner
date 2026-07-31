import { renderToString } from 'react-dom/server'
import { expect, test } from 'vitest'
import { App } from './App'

test('App renders the product name', () => {
  const html = renderToString(<App />)
  expect(html).toContain('CORPUS')
})
