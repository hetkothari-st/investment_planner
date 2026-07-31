import { chromium } from '@playwright/test'

const OUT = '/tmp/claude-0/-home-user-investment-planner/9f6bb46d-8f58-5b34-84cd-c125851965b4/scratchpad/shots'
const BASE = 'http://127.0.0.1:4173/kitchen-sink'

const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' })
const matrix = []
for (const width of [1440, 768, 390])
  for (const theme of ['ink', 'paper']) matrix.push({ width, theme, motion: 'no-preference' })
matrix.push({ width: 1440, theme: 'ink', motion: 'reduce' })
matrix.push({ width: 1440, theme: 'paper', motion: 'reduce' })

for (const { width, theme, motion } of matrix) {
  const page = await browser.newPage({
    viewport: { width, height: 1000 },
    reducedMotion: motion,
  })
  await page.goto(`${BASE}?theme=${theme}`)
  await page.waitForTimeout(1600) // let entries and needles settle
  const name = `${width}-${theme}${motion === 'reduce' ? '-reduced' : ''}.png`
  await page.screenshot({ path: `${OUT}/${name}`, fullPage: true })
  console.log(name)
  await page.close()
}
await browser.close()
