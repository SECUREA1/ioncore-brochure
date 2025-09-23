import express from 'express';
import path from 'path';
import { promises as fs } from 'fs';
import { fileURLToPath } from 'url';
import unzipper from 'unzipper';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const app = express();
const PORT = process.env.PORT || 3000;

const TIMEPIECES_ZIP = 'ioncore_ready_to_sell_brochure_mint_5_with_solana_desc.html.zip';
const TIMEPIECES_HTML = 'ioncore_ready_to_sell_brochure_mint_5_with_solana_desc.html';

const sseClients = new Set();
let totalVisits = 0;

function getMetricsPayload() {
  return {
    activeUsers: sseClients.size,
    totalVisits
  };
}

function broadcastMetrics() {
  const data = `data: ${JSON.stringify(getMetricsPayload())}\n\n`;
  for (const res of sseClients) {
    if (res.writableEnded) {
      sseClients.delete(res);
      continue;
    }
    res.write(data);
  }
}

const ACCESS_GUARD_CONFIG = {
  membershipName: 'Ioncore Apes',
  requiredChainId: '0x1',
  membershipContract: '0xaef8b6346ca4dadaa71783dddf4a3d00633b679d',
  tokenType: 'erc721',
  tokenId: null,
  minBalance: '1'
};

const ACCESS_GUARD_SNIPPET = (() => {
  const serialized = JSON.stringify(ACCESS_GUARD_CONFIG);
  return (
    `<script>window.__IONCORE_ACCESS__ = ${serialized};</script>` +
    '<script src="/wallet-guard.js" defer></script>'
  );
})();

function injectAccessGuard(html) {
  if (typeof html !== 'string' || !html) return html;
  if (html.includes('/wallet-guard.js')) return html;
  const closingBody = html.match(/<\/body>/i);
  if (closingBody) {
    return html.replace(/<\/body>/i, `${ACCESS_GUARD_SNIPPET}\n</body>`);
  }
  return `${html}\n${ACCESS_GUARD_SNIPPET}`;
}

async function sendHtml(res, filePath) {
  try {
    let html = await fs.readFile(filePath, 'utf8');
    html = injectAccessGuard(html);
    res.type('html').send(html);
  } catch {
    res.status(404).send('Not found');
  }
}

function auth(req, res, next) {
  const header = req.headers.authorization || '';
  const [scheme, encoded] = header.split(' ');
  if (scheme !== 'Basic' || !encoded) {
    res.set('WWW-Authenticate', 'Basic realm="Ioncore"');
    return res.status(401).send('Authentication required');
  }
  const [user, pass] = Buffer.from(encoded, 'base64').toString().split(':');
  if (user === 'admin' && pass === '1234') {
    return next();
  }
  res.set('WWW-Authenticate', 'Basic realm="Ioncore"');
  res.status(401).send('Authentication required');
}

// Require authentication for direct HTML requests
app.use((req, res, next) => {
  const lowerPath = req.path.toLowerCase();
  if (lowerPath.endsWith('.html') && !['/webpage.html', '/index.html'].includes(lowerPath)) {
    return auth(req, res, next);
  }
  next();
});

async function getHtmlFiles(dir) {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  let files = [];
  for (const entry of entries) {
    if (entry.name.startsWith('.')) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (['node_modules', 'scripts'].includes(entry.name)) continue;
      files = files.concat(await getHtmlFiles(full));
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith('.html')) {
      files.push(full);
    }
  }
  return files;
}

async function getTitle(filePath) {
  const content = await fs.readFile(filePath, 'utf8');
  const match = content.match(/<title>([^<]*)<\/title>/i);
  return match ? match[1].trim() : path.basename(filePath);
}

// Public homepage with visit counter
app.get('/', async (req, res) => {
  totalVisits += 1;
  broadcastMetrics();
  await sendHtml(res, path.join(__dirname, 'webpage.html'));
});

// Server-sent events stream for live metrics
app.get('/metrics-stream', (req, res) => {
  res.set({
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    Connection: 'keep-alive'
  });

  if (typeof res.flushHeaders === 'function') {
    res.flushHeaders();
  }

  sseClients.add(res);
  broadcastMetrics();

  req.on('close', () => {
    sseClients.delete(res);
    broadcastMetrics();
  });
});

app.get('/timepieces', async (req, res) => {
  try {
    const zipPath = path.join(__dirname, TIMEPIECES_ZIP);
    const directory = await unzipper.Open.file(zipPath);
    const file = directory.files.find((f) => f.path === TIMEPIECES_HTML);
    if (!file) {
      return res.status(404).send('Timepieces brochure not found');
    }
    const buffer = await file.buffer();
    const html = injectAccessGuard(buffer.toString('utf8'));
    res.type('html').send(html);
  } catch (err) {
    console.error('Failed to load timepieces brochure', err);
    res.status(500).send('Failed to load timepieces brochure');
  }
});

app.get(/^\/(?!view$)[^?]*\.html$/i, async (req, res) => {
  const rel = decodeURIComponent(req.path.slice(1));
  const filePath = path.join(__dirname, rel);
  if (!filePath.startsWith(__dirname)) {
    return res.status(400).send('Invalid path');
  }
  await sendHtml(res, filePath);
});

// Serve static assets but disable automatic index fallback
app.use(express.static(__dirname, { index: false }));

// Password-protected HTML file listing
app.get('/admin', auth, async (req, res) => {
  try {
    const files = await getHtmlFiles(__dirname);
    const items = await Promise.all(
      files.map(async (f) => ({
        rel: path.relative(__dirname, f),
        title: await getTitle(f)
      }))
    );
    items.sort((a, b) => a.title.localeCompare(b.title));
    const list = items
      .map((i) => `<div class="card"><h2>${i.title}</h2><a class="btn" href="/view?f=${encodeURIComponent(i.rel)}">View</a></div>`)
      .join('');
    const html = `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Brochures</title><link rel="icon" type="image/svg+xml" href="/battery.svg"><link href="https://fonts.googleapis.com/css?family=Montserrat:700,400&display=swap" rel="stylesheet"><link rel="stylesheet" href="/styles.css"></head><body><header><h1>Brochures</h1><div class="cta-buttons"><a class="btn" href="/">Home</a></div></header><div class="grid">${list}</div><footer id="contact"><h3>Ready to Energize Your Future?</h3><p>Contact Ioncore Energy today for partnership, investment, or project inquiries.</p><a href="mailto:ioncoreenergy@gmail.com" class="footer-btn">Contact Us</a><div class="copyright">&copy; <script>document.write(new Date().getFullYear())</script> Ioncore Energy. All rights reserved.</div></footer></body></html>`;
    res.send(injectAccessGuard(html));
  } catch (err) {
    res.status(500).send('Failed to load index');
  }
});

app.get('/view', auth, async (req, res) => {
  const rel = req.query.f;
  if (!rel) return res.status(400).send('Missing file');
  const filePath = path.join(__dirname, rel);
  if (!filePath.startsWith(__dirname)) return res.status(400).send('Invalid path');
  try {
    const html = await fs.readFile(filePath, 'utf8');
    const title = await getTitle(filePath);
    const wrapped = `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>${title}</title><link rel="icon" type="image/svg+xml" href="/battery.svg"><link href="https://fonts.googleapis.com/css?family=Montserrat:700,400&display=swap" rel="stylesheet"><link rel="stylesheet" href="/styles.css"></head><body><header><div class="cta-buttons"><a class="btn" href="/admin">Back</a><a class="btn" href="/index.html">Index Page</a></div></header>${html}<footer id="contact"><h3>Ready to Energize Your Future?</h3><p>Contact Ioncore Energy today for partnership, investment, or project inquiries.</p><a href="mailto:ioncoreenergy@gmail.com" class="footer-btn">Contact Us</a><div class="copyright">&copy; <script>document.write(new Date().getFullYear())</script> Ioncore Energy. All rights reserved.</div></footer></body></html>`;
    res.send(injectAccessGuard(wrapped));
  } catch {
    res.status(404).send('Not found');
  }
});

app.listen(PORT, () => {
  console.log(`Server listening on http://localhost:${PORT}`);
});

