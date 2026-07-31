import { chromium } from '@playwright/test'

const OUT = process.argv[2] ?? 'shots'
const BASE = 'http://127.0.0.1:5173'

const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' })
for (const { path, name, width } of [
  { path: '/planner', name: 'planner-blocked-1440.png', width: 1440 },
  { path: '/allocation', name: 'allocation-locked-1440.png', width: 1440 },
  { path: '/planner', name: 'planner-blocked-390.png', width: 390 },
]) {
  const page = await browser.newPage({ viewport: { width, height: 1050 } })
  await page.goto(`${BASE}${path}`)
  await page.waitForTimeout(1800)
  await page.screenshot({ path: `${OUT}/${name}`, fullPage: true })
  console.log(name)
  await page.close()
}
await browser.close()
