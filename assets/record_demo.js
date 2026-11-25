// Drives the Streamlit UI with Playwright and saves PNG frames; make_gif.py stitches them.
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const out = process.argv[2];
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1280, height: 900 } });
  let n = 0;
  const snap = async () => p.screenshot({ path: `${out}/f${String(n++).padStart(3, '0')}.png` });
  await p.goto('http://localhost:8501'); await p.waitForSelector('text=Upload a receipt');
  await p.waitForTimeout(1000); await snap(); await snap();
  await p.setInputFiles('input[type=file]', 'assets/sample_receipt.png');
  for (let i = 0; i < 4; i++) { await p.waitForTimeout(500); await snap(); }
  await p.waitForSelector('text=Needs review', { timeout: 90000 });
  await p.waitForTimeout(800);
  for (let i = 0; i < 5; i++) { await snap(); await p.waitForTimeout(300); }
  await p.mouse.wheel(0, 500); await p.waitForTimeout(600);
  for (let i = 0; i < 3; i++) { await snap(); await p.waitForTimeout(300); }
  const dl = p.waitForEvent('download');
  await p.click('text=Download CSV'); await dl; await p.waitForTimeout(500);
  for (let i = 0; i < 4; i++) { await snap(); await p.waitForTimeout(300); }
  await b.close();
})();
