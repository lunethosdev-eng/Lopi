#!/usr/bin/env node
'use strict';
// Render a publicly accessible page with its normal JavaScript runtime.
// This does not solve CAPTCHAs, defeat access controls, or extract DRM keys.
const { chromium } = require('playwright');

(async () => {
  const target = process.argv[2];
  if (!target || !/^https?:\/\//i.test(target)) throw new Error('URL http(s) requerida');
  const browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || undefined, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  try {
    const page = await browser.newPage({
      userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36',
      locale: 'es-419',
      javaScriptEnabled: true,
      serviceWorkers: 'allow'
    });
    await page.goto(target, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForTimeout(1200);
    const result = await page.evaluate(() => ({
      url: location.href,
      title: document.title,
      html: document.documentElement.outerHTML,
      json: Array.from(document.scripts).map(x => (x.textContent || '').slice(0, 180000)).filter(x => x && x.length),
      media: Array.from(document.querySelectorAll('video[src],video source[src],source[src]')).map(x => x.src || x.getAttribute('src')).filter(Boolean).concat(performance.getEntriesByType('resource').map(x => x.name).filter(x => /\.(m3u8|mp4|mpd)(?:$|[?#])/i.test(x))),
      text: document.body ? document.body.innerText.slice(0, 50000) : ''
    }));
    process.stdout.write(JSON.stringify(result));
  } finally {
    await browser.close();
  }
})().catch(err => { console.error(String(err && err.message || err)); process.exit(2); });
