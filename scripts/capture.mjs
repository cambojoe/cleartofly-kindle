import { chromium } from 'playwright';
import fs from 'node:fs';

function berlinDate(offsetDays = 0) {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Europe/Berlin',
    year: 'numeric', month: '2-digit', day: '2-digit'
  }).formatToParts(new Date());
  const values = {};
  for (const part of parts) values[part.type] = part.value;
  const date = new Date(Date.UTC(
    Number(values.year), Number(values.month) - 1, Number(values.day) + offsetDays, 12
  ));
  return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, '0')}-${String(date.getUTCDate()).padStart(2, '0')}`;
}

const browser = await chromium.launch({ headless: true });
const layouts = [
  { name: 'portrait', width: 600, height: 1200 },
  { name: 'landscape', width: 800, height: 1100 }
];

try {
  for (const layout of layouts) {
    const page = await browser.newPage({
      viewport: { width: layout.width, height: layout.height },
      deviceScaleFactor: 1,
      locale: 'de-DE',
      timezoneId: 'Europe/Berlin',
      colorScheme: 'light'
    });
    page.setDefaultTimeout(15000);

    for (let day = 0; day < 3; day += 1) {
      const date = berlinDate(day);
      const targetUrl = `https://cleartofly.de/airfield/DE-ALSFELD?date=${date}`;
      console.log(`Erfasse ${layout.name}, Tag ${day + 1}/3: ${targetUrl}`);

      const response = await page.goto(targetUrl, {
        waitUntil: 'domcontentloaded',
        timeout: 90000
      });
      if (!response) throw new Error(`Keine HTTP-Antwort für ${targetUrl}`);
      if (response.status() >= 400) {
        throw new Error(`ClearToFly antwortet für ${date} mit HTTP ${response.status()}.`);
      }

      await page.locator('body').waitFor({ state: 'visible' });
      // ClearToFly draws its charts client-side; allow them to finish.
      await page.waitForTimeout(12000);

      const finalUrl = page.url();
      const title = await page.title().catch(() => '');
      const bodyText = await page.locator('body').innerText().catch(() => '');
      console.log(`Seite: ${title}; Textlänge: ${bodyText.length}; URL: ${finalUrl}`);

      if (!finalUrl.includes('cleartofly.de')) {
        throw new Error(`Weiterleitung weg von ClearToFly: ${finalUrl}`);
      }
      if (bodyText.length < 80 || !/(Alsfeld|ClearToFly|Wind|Wolken|Flugwetter|Sicht)/i.test(bodyText)) {
        throw new Error(`Wetterdarstellung für ${date} wurde nicht erkannt. Kein Fehlerbild wird veröffentlicht.`);
      }

      await page.screenshot({
        path: `/tmp/cleartofly-${layout.name}-day-${day}-raw.png`,
        animations: 'disabled'
      });
      fs.writeFileSync(
        `/tmp/cleartofly-${layout.name}-day-${day}-info.txt`,
        `${targetUrl}\n${title}\n${date}\n${layout.width}x${layout.height}\n`
      );
    }
    await page.close();
  }
} finally {
  await browser.close();
}
