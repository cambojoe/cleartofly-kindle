import { chromium } from 'playwright';
import fs from 'node:fs';

const WIDTH = 600;
const VIEWPORT_HEIGHT = 1200;

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

// Find the visible chart heading by its short text. ClearToFly currently labels
// its panels in English; the alternate names make the workflow more tolerant
// of small wording changes.
async function findHeadingY(page, label, aliases, required = true) {
  const result = await page.evaluate((requestedAliases) => {
    const norm = (value) => String(value || '')
      .replace(/\s+/g, ' ')
      .replace(/[：:]$/, '')
      .trim()
      .toLowerCase();
    const wanted = requestedAliases.map(norm);
    const candidates = [];
    for (const el of document.querySelectorAll('body *')) {
      const raw = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
      if (!raw || raw.length > 42) continue;
      const text = norm(raw);
      let matchRank = 999;
      for (let i = 0; i < wanted.length; i += 1) {
        const term = wanted[i];
        if (text === term) matchRank = Math.min(matchRank, i);
        else if (text.startsWith(term + ' ') || text.startsWith(term + ':')) {
          matchRank = Math.min(matchRank, 100 + i);
        }
      }
      if (matchRank === 999) continue;
      const rect = el.getBoundingClientRect();
      const documentY = rect.top + window.scrollY;
      if (rect.width < 8 || rect.height < 5 || rect.height > 100 || documentY < 130) continue;
      if (el.children.length > 5) continue;
      const headingTag = /^H[1-6]$/.test(el.tagName) || el.tagName === 'SUMMARY' || el.tagName === 'BUTTON';
      const rank = matchRank * 100 + (headingTag ? 0 : 4) + (el.children.length === 0 ? 0 : 2) + Math.min(raw.length, 40) / 100;
      candidates.push({ text: raw, y: documentY, rank, tag: el.tagName });
    }
    candidates.sort((a, b) => a.rank - b.rank || a.y - b.y);
    return candidates.length ? candidates[0] : null;
  }, aliases);

  if (!result) {
    const message = `ClearToFly-Überschrift für „${label}“ nicht gefunden (gesucht: ${aliases.join(', ')}).`;
    if (required) throw new Error(message);
    console.warn(message);
    return null;
  }
  console.log(`Diagramm „${label}“ gefunden: ${result.text} bei Y=${Math.round(result.y)} px (${result.tag}).`);
  return result.y;
}

async function scrollToChart(page, documentY) {
  const targetScrollY = Math.max(0, Math.round(documentY - 45));
  await page.evaluate((y) => window.scrollTo(0, y), targetScrollY);
  await page.waitForTimeout(500);
  return await page.evaluate(() => window.scrollY);
}

async function captureGroup(page, { path, startY, stopY, fallbackHeight, title }) {
  const scrollY = await scrollToChart(page, startY);
  // Stop just before the next chart, so that the bottom of one page does not
  // show a clipped fragment of the next page's first chart.
  let clipHeight = stopY ? Math.floor(stopY - scrollY - 8) : fallbackHeight;
  // Some ClearToFly panels are taller than the Kindle's available content
  // area. Capture up to 900 px here; make_kindle_image.py scales the full
  // stack down to the 740 px content height instead of cropping a chart.
  clipHeight = Math.min(900, Math.max(420, clipHeight || fallbackHeight));
  if (clipHeight > VIEWPORT_HEIGHT) clipHeight = VIEWPORT_HEIGHT;
  console.log(`${title}: Bildausschnitt 600x${clipHeight}, Scrollposition ${Math.round(scrollY)} px.`);
  await page.screenshot({
    path,
    clip: { x: 0, y: 0, width: WIDTH, height: clipHeight },
    animations: 'disabled'
  });
}

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({
    viewport: { width: WIDTH, height: VIEWPORT_HEIGHT },
    deviceScaleFactor: 1,
    locale: 'de-DE',
    timezoneId: 'Europe/Berlin',
    colorScheme: 'light'
  });
  page.setDefaultTimeout(15000);

  for (let day = 0; day < 3; day += 1) {
    const date = berlinDate(day);
    const targetUrl = `https://cleartofly.de/airfield/DE-ALSFELD?date=${date}`;
    console.log(`\nErfasse ClearToFly für Tag ${day + 1}/3: ${targetUrl}`);
    const response = await page.goto(targetUrl, { waitUntil: 'domcontentloaded', timeout: 90000 });
    if (!response) throw new Error(`Keine HTTP-Antwort für ${targetUrl}`);
    if (response.status() >= 400) throw new Error(`ClearToFly antwortet für ${date} mit HTTP ${response.status()}.`);
    await page.locator('body').waitFor({ state: 'visible' });
    // Give the client-side charts time to finish drawing.
    await page.waitForTimeout(12000);

    const finalUrl = page.url();
    const bodyText = await page.locator('body').innerText().catch(() => '');
    console.log(`Endadresse: ${finalUrl}; Textlänge: ${bodyText.length}`);
    if (!finalUrl.includes('cleartofly.de')) throw new Error(`Unerwartete Weiterleitung: ${finalUrl}`);
    if (bodyText.length < 80 || !/(Alsfeld|Wind|Cloud|Wolken|Visibility|Sicht)/i.test(bodyText)) {
      throw new Error('Die Wetterdarstellung wurde nicht erkannt. Es wird kein leeres/Fehlerbild veröffentlicht.');
    }

    const temperatureY = await findHeadingY(page, 'Temperatur', ['Temperature', 'Temp']);
    const windY = await findHeadingY(page, 'Wind', ['Wind']);
    const crosswindY = await findHeadingY(page, 'Querwind', ['Crosswind component', 'Crosswind', 'Cross wind', 'Cross-wind']);
    const cloudsY = await findHeadingY(page, 'Wolkenbedeckung', ['Cloud cover', 'Cloud coverage', 'Clouds by altitude', 'Cloudiness', 'Clouds']);
    const visibilityY = await findHeadingY(page, 'Sichtweite', ['Visibility']);
    const runwayY = await findHeadingY(page, 'Pistenwind', [
      'Runway wind', 'Wind component to runway', 'Wind components to runway',
      'Runway component', 'Headwind / tailwind', 'Headwind', 'Tailwind'
    ]);

    // ClearToFly's actual order can place the runway-wind accordion before
    // Cloud Cover and Visibility. Validate the order within each page, rather
    // than incorrectly expecting all six panels in a single fixed sequence.
    if (!(temperatureY < windY && windY < crosswindY && runwayY < cloudsY && cloudsY < visibilityY)) {
      throw new Error('Die Reihenfolge der ClearToFly-Diagramme passt nicht zu den zwei vorgesehenen Seiten. Die Bilder wurden nicht veröffentlicht, damit keine falschen Bereiche angezeigt werden.');
    }

    fs.mkdirSync('public', { recursive: true });
    await captureGroup(page, {
      path: `/tmp/cleartofly-day-${day}-page-0-raw.png`,
      startY: temperatureY,
      stopY: cloudsY,
      fallbackHeight: 700,
      title: `Tag ${day + 1}, Seite 1 (Temperatur/Wind/Querwind)`
    });
    await captureGroup(page, {
      path: `/tmp/cleartofly-day-${day}-page-1-raw.png`,
      // In the live Alsfeld layout the Runway wind panel appears before
      // Cloud Cover and Visibility, so begin at the earliest of those three.
      // Include the full Visibility plot and let the image step scale the
      // complete vertical stack to the Kindle content height.
      startY: runwayY,
      stopY: visibilityY + 225,
      fallbackHeight: 800,
      title: `Tag ${day + 1}, Seite 2 (Wolken/Sicht/Pistenwind)`
    });
    fs.writeFileSync(`/tmp/cleartofly-day-${day}-info.txt`, `${targetUrl}\n${date}\n`);
  }
  await page.close();
} finally {
  await browser.close();
}
