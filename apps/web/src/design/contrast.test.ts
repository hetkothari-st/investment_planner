/** The contrast audit from the quality floor, as a test: all text tokens
 * must clear WCAG 4.5:1 against the panel and ink surfaces, in both themes. */

import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, test } from 'vitest'

const css = readFileSync(join(__dirname, 'tokens.css'), 'utf8')

function scopeVars(scopeStart: string): Record<string, string> {
  const start = css.indexOf(scopeStart)
  const body = css.slice(start, css.indexOf('}', css.indexOf('--text-tertiary', start)))
  const vars: Record<string, string> = {}
  for (const m of body.matchAll(/--([a-z-]+):\s*(#[0-9a-fA-F]{6})/g)) vars[m[1]] = m[2]
  return vars
}

function luminance(hex: string): number {
  const lin = (c: number) => {
    const s = c / 255
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  }
  const n = parseInt(hex.slice(1), 16)
  return (
    0.2126 * lin((n >> 16) & 255) + 0.7152 * lin((n >> 8) & 255) + 0.0722 * lin(n & 255)
  )
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

const THEMES = {
  ink: scopeVars(':root {'),
  paper: scopeVars(":root[data-theme='paper']"),
}

describe.each(Object.entries(THEMES))('%s theme', (_name, vars) => {
  const surfaces = ['ink', 'panel', 'panel-raised'] as const
  const texts = ['text-primary', 'text-secondary', 'text-tertiary'] as const

  test.each(texts.flatMap((t) => surfaces.map((s) => [t, s] as const)))(
    '%s on %s ≥ 4.5:1',
    (text, surface) => {
      expect(contrast(vars[text], vars[surface])).toBeGreaterThanOrEqual(4.5)
    },
  )

  test('direction colours differ in luminance (colour-blind check)', () => {
    const dj = Math.abs(luminance(vars['jade']) - luminance(vars['madder']))
    expect(dj).toBeGreaterThan(0.03)
  })
})
