import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const origin = 'https://swhan0329.github.io/';

// Run only into a new directory, preserving earlier downloads and local edits.
export async function capture(destination = packageRoot) {
  const site = path.join(destination, 'assets/site');
  const archive = path.join(destination, 'references/original');
  try { await fs.access(site); throw new Error(`Destination already exists: ${site}`); }
  catch (error) { if (error.code !== 'ENOENT') throw error; }
  await fs.mkdir(site, { recursive: true });
  const manifest = { source: origin, capturedAt: new Date().toISOString(), files: [], modifications: [], externalNavigation: 'Preserved; same-origin subpages point to the original website.' };
  const visited = new Map();
  async function download(url, relative) {
    if (visited.has(url)) return visited.get(url);
    visited.set(url, relative);
    const response = await fetch(url, { signal: AbortSignal.timeout(45000) });
    if (!response.ok) throw new Error(`${response.status}: ${url}`);
    const bytes = Buffer.from(await response.arrayBuffer());
    for (const root of [site, archive]) {
      await fs.mkdir(path.dirname(path.join(root, relative)), { recursive: true });
      await fs.writeFile(path.join(root, relative), bytes);
    }
    manifest.files.push({ url, path: relative, bytes: bytes.length, sha256: crypto.createHash('sha256').update(bytes).digest('hex') });
    if (relative.endsWith('.css')) {
      let css = bytes.toString('utf8');
      for (const match of [...css.matchAll(/url\(\s*['"]?([^'"\s)]+)['"]?\s*\)/g)]) {
        if (match[1].startsWith('data:')) continue;
        const assetUrl = new URL(match[1], url).href;
        const local = `vendor/${crypto.createHash('sha256').update(assetUrl).digest('hex').slice(0, 12)}${path.posix.extname(new URL(assetUrl).pathname) || '.bin'}`;
        await download(assetUrl, local);
        css = css.replaceAll(match[1], path.posix.relative(path.posix.dirname(relative), local));
      }
      await fs.writeFile(path.join(site, relative), css);
    }
    return relative;
  }
  await download(origin, 'index.html');
  let html = await fs.readFile(path.join(site, 'index.html'), 'utf8');
  for (const tag of [...html.matchAll(/<(?:link|script|img)\b[^>]*>/gi)].map(m => m[0])) {
    const attr = tag.match(/\b(src|href)="([^"]+)"/i);
    if (!attr || !(/<(img|script)\b/i.test(tag) || /rel="(?:stylesheet|icon|apple-touch-icon)"/.test(tag))) continue;
    const url = new URL(attr[2].replaceAll('&amp;', '&'), origin);
    const relative = url.origin === new URL(origin).origin ? decodeURIComponent(url.pathname.slice(1)) : `vendor/${crypto.createHash('sha256').update(url.href).digest('hex').slice(0,12)}${url.hostname === 'fonts.googleapis.com' ? '.css' : path.posix.extname(url.pathname) || '.bin'}`;
    await download(url.href, relative);
    html = html.replace(tag, tag.replace(attr[2], relative));
  }
  html = html.replace(/(<a\b[^>]*\bhref=")([^"#]+)(")/gi, (all, before, href, after) => {
    if (/^(?:https?:|mailto:|tel:)/.test(href)) return all;
    return before + new URL(href, origin).href + after;
  });
  html = html.replace(/<meta name="robots"[^>]*>/, '<meta name="robots" content="noindex, nofollow">');
  html = html.replace('</head>', '    <link rel="stylesheet" href="css/custom.css">\n</head>');
  await fs.writeFile(path.join(site, 'index.html'), html);
  const jsPath = path.join(site, 'js/main.js');
  let js = await fs.readFile(jsPath, 'utf8');
  // Keep counter UI, but never send a request to the original counter service.
  js = js.replaceAll('fetch(', 'offlineCounterFetch(');
  js = 'function offlineCounterFetch() { return Promise.resolve({ ok: true, json: async () => ({ value: 0 }) }); }\n' + js;
  await fs.writeFile(jsPath, js);
  await fs.writeFile(path.join(site, 'css/custom.css'), '/* Reusable overrides: edit these tokens without changing the downloaded CSS. */\n:root {\n  --accent: #3b82f6;\n  --accent-hover: #2563eb;\n  --container-max: 1100px;\n  --section-padding: 4rem;\n}\n[data-theme="dark"] {\n  --accent: #60a5fa;\n  --accent-hover: #3b82f6;\n}\n');
  manifest.modifications = ['Localized stylesheet, scripts, images, and CSS font URLs.', 'Remote counter fetches replaced with a local zero-value response.', 'Relative subpage navigation points to original website; subpages are outside this capture.', 'Added noindex and custom.css override entrypoint.'];
  for (const file of manifest.files) file.localSha256 = crypto.createHash('sha256').update(await fs.readFile(path.join(site, file.path))).digest('hex');
  await fs.writeFile(path.join(destination, 'references/source-manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
  return { destination, downloaded: manifest.files.length };
}

if (globalThis.process?.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  console.log(await capture(process.argv[2] ? path.resolve(process.argv[2]) : packageRoot));
}
