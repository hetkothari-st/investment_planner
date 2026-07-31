/** The design fence: src/design/ is the only place a colour is defined.
 * A hex code anywhere else in src/ is a bug (docs/01, docs/09). */

import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { expect, test } from 'vitest'

const SRC = join(__dirname)
const HEX = /#[0-9a-fA-F]{3,8}\b/

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name)
    if (statSync(p).isDirectory()) return name === 'design' ? [] : walk(p)
    return /\.(tsx?|css)$/.test(name) ? [p] : []
  })
}

test('no hex colour outside src/design', () => {
  const offenders = walk(SRC)
    .filter((f) => HEX.test(readFileSync(f, 'utf8')))
    .map((f) => relative(SRC, f))
  expect(offenders).toEqual([])
})
