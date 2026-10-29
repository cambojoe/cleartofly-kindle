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

// Capture each requested panel separately. This prevents ClearToFly's site
// navigation, compass rose, Significant Weather, and any unrelated panel from
// entering the Kindle image.
const SECTIONS = [
  { key: 'temperature', label: 'Temperature', aliases: ['Temperature', 'Temp'] },
  { key: 'wind', label: 'Wind', aliases: ['Wind'] },
  { key: 'crosswind', label: 'Crosswind', aliases: ['Crosswind component', 'Crosswind', 'Cross wind', 'Cross-wind'] },
  { key: 'visibility', label: 'Visibility', aliases: ['Visibility', 'Visibility range'] },
  { key: 'runway-wind', label: 'Runway wind', aliases: ['Runway wind', 'Wind component to runway', 'Wind components to runway', 'Runway component', 'Headwind / tailwind', 'Headwind', 'Tailwind'] },
  { key: 'cloud-cover', label: 'Cloud cover', aliases: ['Cloud cover', 'Cloud coverage', 'Clouds by altitude', 'Cloudiness', 'Clouds'] },
  { key: 'pressure', label: 'Pressure', aliases: ['Pressure', 'Air pressure', 'Atmospheric pressure', 'Sea-level pressure', 'Sea level pressure', 'MSLP', 'QNH'] },
  { key: 'sun-elevation', label: 'Sun elevation', aliases: ['Sun elevation', 'Solar elevation', 'Sun altitude', 'Solar altitude'] }
];

const PAGE_SECTIONS = [
  ['temperature', 'wind', 'crosswind', 'visibility'],
  ['runway-wind', 'cloud-cover', 'pressure', 'sun-elevation']
];

function rawPath(day, key) {
  return `/tmp/cleartofly-day-${day}-section-${key}.png`;
}

async function hideSiteNavigation(page) {
  const hidden = await page.evaluate(() => {
    const norm = (s) => String(s || '').replace(/\s+/g, ' ').trim().toLowerCase();
    const candidates = [];
    for (const node of document.querySelectorAll('body *')) {
      if (node.closest('svg,canvas')) continue;
      const text = norm(node.innerText || node.textContent);
      if (!text || text.length > 140) continue;
      if (!text.includes('maps') || !text.includes('meteograms') || !text.includes('route')) continue;
      let el = node;
      for (let depth = 0; el && depth < 5; depth += 1, el = el.parentElement) {
        const r = el.getBoundingClientRect();
        if (r.width >= Math.min(400, window.innerWidth * 0.7) && r.height >= 15 && r.height <= 130 && r.top < 220) {
          candidates.push({ el, area: r.width * r.height });
          break;
        }
      }
    }
    candidates.sort((a, b) => a.area - b.area);
    if (candidates.length) {
      candidates[0].el.setAttribute('data-kindle-hide', 'true');
      return true;
    }
    return false;
  });
  if (hidden) {
    await page.addStyleTag({ content: '[data-kindle-hide="true"] { display:none !important; visibility:hidden !important; }' });
    console.log('ClearToFly-Navigationsleiste ausgeblendet.');
  } else {
    console.log('Navigationsleiste nicht eindeutig erkannt; sie wird nicht mit aufgenommen, weil ausschließlich einzelne Diagrammbereiche fotografiert werden.');
  }
}

async function findAndMarkHeading(page, section) {
  const found = await page.evaluate(({ key, aliases }) => {
    const norm = (value) => String(value || '')
      .replace(/\s+/g, ' ')
      .replace(/[：:]$/, '')
      .trim()
      .toLowerCase();
    const wanted = aliases.map(norm);
    const candidates = [];
    for (const el of document.querySelectorAll('body *')) {
      if (el.closest('svg,canvas')) continue;
      const raw = String(el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
      if (!raw || raw.length > 85) continue;
      const text = norm(raw);
      let matchRank = 999;
      for (let i = 0; i < wanted.length; i += 1) {
        const term = wanted[i];
        if (text === term) matchRank = Math.min(matchRank, i);
        else if (text.startsWith(term + ' ') || text.startsWith(term + ':') || text.startsWith(term + ' ·') || text.startsWith(term + ' (')) {
          matchRank = Math.min(matchRank, 100 + i);
        }
      }
      if (matchRank === 999) continue;
      const rect = el.getBoundingClientRect();
      if (rect.width < 8 || rect.height < 5 || rect.height > 110) continue;
      if (el.children.length > 6) continue;
      const headingTag = /^H[1-6]$/.test(el.tagName) || el.tagName === 'SUMMARY' || el.tagName === 'BUTTON';
      const rank = matchRank * 100 + (headingTag ? 0 : 4) + (el.children.length === 0 ? 0 : 2) + Math.min(raw.length, 80) / 100;
      candidates.push({ el, raw, rank, y: Math.round(rect.top + window.scrollY), tag: el.tagName });
    }
    candidates.sort((a, b) => a.rank - b.rank || a.y - b.y);
    if (!candidates.length) return null;
    const chosen = candidates[0];
    chosen.el.setAttribute('data-kindle-heading', key);
    return { text: chosen.raw, y: chosen.y, tag: chosen.tag };
  }, { key: section.key, aliases: section.aliases });

  if (!found) {
    throw new Error(`ClearToFly-Bereich „${section.label}“ nicht gefunden. Gesucht: ${section.aliases.join(', ')}. Es wird kein unvollständiges Bild veröffentlicht.`);
  }
  console.log(`Bereich „${section.label}“ gefunden: ${found.text} bei Y=${found.y}px (${found.tag}).`);
}

async function expandDetailsForSection(page, section) {
  const changed = await page.evaluate((key) => {
    const heading = document.querySelector(`[data-kindle-heading="${key}"]`);
    const details = heading && heading.closest('details');
    if (details && !details.open) {
      details.open = true;
      return true;
    }
    return false;
  }, section.key);
  if (changed) {
    await page.waitForTimeout(900);
    console.log(`Aufklappbereich für „${section.label}“ geöffnet.`);
  }
}

async function findPanelForSection(page, section) {
  const result = await page.evaluate((key) => {
    const heading = document.querySelector(`[data-kindle-heading="${key}"]`);
    if (!heading) return { error: 'Markierte Überschrift nicht mehr vorhanden.' };
    let el = heading;
    let fallback = null;
    for (let depth = 0; el && depth < 14; depth += 1, el = el.parentElement) {
      const rect = el.getBoundingClientRect();
      const markerCount = (el.matches('[data-kindle-heading]') ? 1 : 0) + el.querySelectorAll('[data-kindle-heading]').length;
      const widthOk = rect.width >= Math.min(380, window.innerWidth * 0.7);
      const heightOk = rect.height >= 80 && rect.height <= 1100;
      if (!widthOk || !heightOk || markerCount !== 1) continue;
      const graphics = Array.from(el.querySelectorAll('svg, canvas, table, [role="img"], img')).map((graphic) => {
        const r = graphic.getBoundingClientRect();
        return { width: r.width, height: r.height };
      });
      const hasPlot = graphics.some((g) => g.width >= Math.min(260, window.innerWidth * 0.45) && g.height >= 35);
      if (hasPlot) {
        el.setAttribute('data-kindle-panel', key);
        return { tag: el.tagName, width: Math.round(rect.width), height: Math.round(rect.height), depth, graphicCount: graphics.length };
      }
      // Fallback for simple forecast panels that show values without an SVG.
      const textLength = String(el.innerText || el.textContent || '').trim().length;
      if (!fallback && textLength > 18) fallback = { el, width: rect.width, height: rect.height, depth, graphics };
    }
    if (fallback && fallback.width >= Math.min(380, window.innerWidth * 0.7) && fallback.height >= 80 && fallback.height <= 1100) {
      fallback.el.setAttribute('data-kindle-panel', key);
      return { tag: fallback.el.tagName, width: Math.round(fallback.width), height: Math.round(fallback.height), depth: fallback.depth, graphicCount: fallback.graphics.length, note: 'text/value fallback' };
    }
    return { error: 'Der einzelne Diagrammbereich konnte nicht sicher erkannt werden; es wird absichtlich kein vollständiger Seitenbereich aufgenommen.' };
  }, section.key);

  if (result.error) throw new Error(`${section.label}: ${result.error}`);
  console.log(`Isolierter Bereich „${section.label}“: ${result.width}x${result.height}px (${result.tag}, Ebene ${result.depth}${result.note ? `, ${result.note}` : ''}).`);
  return page.locator(`[data-kindle-panel="${section.key}"]`);
}

async function capturePanel(page, section, day) {
  const panel = await findPanelForSection(page, section);
  await panel.scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  const path = rawPath(day, section.key);
  await panel.screenshot({ path, animations: 'disabled', timeout: 30000 });
  const dimensions = await page.evaluate((key) => {
    const el = document.querySelector(`[data-kindle-panel="${key}"]`);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { width: Math.round(r.width), height: Math.round(r.height) };
  }, section.key);
  if (!dimensions || dimensions.width < 250 || dimensions.height < 65) {
    throw new Error(`Screenshot von „${section.label}“ ist unerwartet klein (${JSON.stringify(dimensions)}).`);
  }
  console.log(`Einzelbereich gespeichert: ${path} (${dimensions.width}x${dimensions.height}px).`);
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
  page.setDefaultTimeout(20000);

  for (let day = 0; day < 3; day += 1) {
    const date = berlinDate(day);
    const targetUrl = `https://cleartofly.de/airfield/DE-ALSFELD?date=${date}`;
    console.log(`\nErfasse ClearToFly für Tag ${day + 1}/3: ${targetUrl}`);
    const response = await page.goto(targetUrl, { waitUntil: 'domcontentloaded', timeout: 90000 });
    if (!response) throw new Error(`Keine HTTP-Antwort für ${targetUrl}`);
    if (response.status() >= 400) throw new Error(`ClearToFly antwortet für ${date} mit HTTP ${response.status()}.`);
    await page.locator('body').waitFor({ state: 'visible' });
    await page.waitForTimeout(12000);

    const finalUrl = page.url();
    const bodyText = await page.locator('body').innerText().catch(() => '');
    console.log(`Endadresse: ${finalUrl}; Textlänge: ${bodyText.length}`);
    if (!finalUrl.includes('cleartofly.de')) throw new Error(`Unerwartete Weiterleitung: ${finalUrl}`);
    if (bodyText.length < 100 || !/(Alsfeld|Wind|Cloud|Wolken|Visibility|Sicht)/i.test(bodyText)) {
      throw new Error('Die Wetterdarstellung wurde nicht erkannt. Es wird kein leeres/Fehlerbild veröffentlicht.');
    }

    await hideSiteNavigation(page);
    for (const section of SECTIONS) await findAndMarkHeading(page, section);
    for (const section of SECTIONS) await expandDetailsForSection(page, section);
    await page.waitForTimeout(600);

    // Four and only four panels are composed per page, in the requested order.
    for (const pageSections of PAGE_SECTIONS) {
      for (const key of pageSections) {
        const section = SECTIONS.find((item) => item.key === key);
        await capturePanel(page, section, day);
      }
    }

    fs.writeFileSync(`/tmp/cleartofly-day-${day}-info.txt`, `${targetUrl}\n${date}\n`);
  }
  await page.close();
} finally {
  await browser.close();
}
