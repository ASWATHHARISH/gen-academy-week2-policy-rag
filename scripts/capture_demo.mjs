// Local-only captures in a fresh headless profile, never a signed-in browser.
import { createRequire } from 'node:module';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.RAG_PLAYWRIGHT_PATH || 'playwright');
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const output = path.join(root, 'artifacts', 'demo', 'captures');
await fs.mkdir(output, { recursive: true });
const browser = await chromium.launch({ channel: 'msedge', headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 });
  await page.goto('http://127.0.0.1:8501/?demo=1', { waitUntil: 'networkidle' });
  await page.getByRole('heading', { name: 'Enterprise Policy Q&A', exact: true }).waitFor();
  await page.getByRole('button', { name: 'Show saved result', exact: true }).waitFor();
  console.log((await page.locator('body').innerText()).slice(0, 12000));
  await page.screenshot({ path: path.join(output, 'overview.png') });
  await page.getByRole('button', { name: 'Show saved result', exact: true }).click();
  await page.getByText('Saved answer with validated source references', { exact: true }).waitFor();
  await page.getByRole('heading', { name: 'Sources', exact: true }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(output, 'n1.png') });
  await page.getByText(/^Inspect retrieved evidence/).click();
  await page.getByText(/Minimum Length = 12 characters/).first().scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(output, 'n1_evidence.png') });
  await page.getByRole('combobox').click();
  await page.getByRole('combobox').press('ArrowDown');
  await page.getByRole('combobox').press('Enter');
  await page.getByRole('button', { name: 'Show saved result', exact: true }).click();
  console.log((await page.locator('body').innerText()).slice(-6000));
  await page.getByText('The available evidence is insufficient for a supported answer.', {exact:true}).waitFor();
  await page.getByText('The available evidence is insufficient for a supported answer.', {exact:true}).scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(output, 'u1.png') });
  await page.goto(new URL('../docs/architecture.svg', import.meta.url).href);
  await page.locator('svg').screenshot({ path: path.join(output, 'architecture.png') });
  console.log('Saved isolated local overview, N1 answer/evidence, U1 fallback and architecture captures. No API request was submitted.');
} finally { await browser.close(); }
