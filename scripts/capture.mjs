import { chromium } from 'playwright';
import fs from 'node:fs';

function dateInBerlin() {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Europe/Berlin',
    year: 'numeric', month: '2-digit', day: '2-digit'
  }).formatToParts(new Date());
  const values = {};
  for (const part of parts) values[part.type] = part.value;
  return `${values.year}-${values.month}-${values.day}`;
}

const date = dateInBerlin();
const targetUrl = `https://cleartofly.de/airfield/DE-ALSFELD?date=${date}`;
const browser = await chromium.launch({ headless: true });

try {
  const page = await browser.newPage({
    viewport: { width: 600, height: 720 },
    deviceScaleFactor: 1,
    locale: 'de-DE',
    timezoneId: 'Europe/Berlin',
    colorScheme: 'light'
  });
  page.setDefaultTimeout(15000);
  console.log(`Rufe ClearToFly auf: ${targetUrl}`);
  const response = await page.goto(targetUrl, {
    waitUntil: 'domcontentloaded',
    timeout: 90000
  });

  if (!response) throw new Error('ClearToFly hat keine HTTP-Antwort geliefert.');
  if (response.status() >= 400) {
    throw new Error(`ClearToFly antwortet mit HTTP ${response.status()}.`);
  }

  await page.locator('body').waitFor({ state: 'visible' });
  // Give client-side weather charts a little time to draw.
  await page.waitForTimeout(12000);

  const finalUrl = page.url();
  const title = await page.title().catch(() => '');
  const bodyText = await page.locator('body').innerText().catch(() => '');
  console.log(`Seitentitel: ${title}`);
  console.log(`Endadresse: ${finalUrl}`);
  console.log(`Textlänge der Seite: ${bodyText.length}`);
  console.log(`Textanfang: ${bodyText.slice(0, 800).replace(/\s+/g, " ")}`);

  if (!finalUrl.includes('cleartofly.de')) {
    throw new Error(`Weiterleitung weg von ClearToFly: ${finalUrl}`);
  }
  if (bodyText.length < 80 || !/(Alsfeld|ClearToFly|Wind|Wolken|Flugwetter|Sicht)/i.test(bodyText)) {
    throw new Error('Die erwartete Wetterdarstellung wurde nicht erkannt. Es wird kein leeres/Fehlerbild veröffentlicht.');
  }

  fs.mkdirSync('public', { recursive: true });
  await page.screenshot({ path: '/tmp/cleartofly-raw.png', animations: 'disabled' });
  fs.writeFileSync('/tmp/cleartofly-capture-info.txt', `${targetUrl}\n${title}\n`);
} finally {
  await browser.close();
}
