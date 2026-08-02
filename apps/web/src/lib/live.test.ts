/** The browser half of the M9 acceptance: the reconnect ladder matches the
 * server's, and — mechanically checked — no Kite credential material exists
 * anywhere in the web bundle's source. The browser talks only to /api. */

import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { describe, expect, it } from 'vitest'
import { BACKOFF_MS, backoffMs } from './live'

describe('backoff ladder', () => {
  it('matches the server ladder, capped at 30s', () => {
    expect([...BACKOFF_MS]).toEqual([1000, 2000, 4000, 8000, 15000, 30000])
    expect(backoffMs(0)).toBe(1000)
    expect(backoffMs(5)).toBe(30000)
    expect(backoffMs(99)).toBe(30000)
  })
})

const SRC = join(__dirname, '..')
const CREDENTIAL_MARKERS = /KITE_API|access_token|api_secret|kiteconnect/i

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name)
    return statSync(p).isDirectory() ? walk(p) : [p]
  })
}

describe('no credentials reach the browser', () => {
  it('web source never references Kite credential material', () => {
    const offenders = walk(SRC)
      .filter((f) => /\.(ts|tsx|css)$/.test(f) && !f.endsWith('live.test.ts'))
      .filter((f) => CREDENTIAL_MARKERS.test(readFileSync(f, 'utf8')))
      .map((f) => relative(SRC, f))
    expect(offenders).toEqual([])
  })

  it('the live socket only ever targets our own /api origin', () => {
    const src = readFileSync(join(__dirname, 'live.ts'), 'utf8')
    expect(src).toContain('/api/live/ws')
    expect(src).not.toMatch(/wss?:\/\/(?!\$\{)/) // no hard-coded external ws host
  })
})
