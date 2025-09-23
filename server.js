import express from 'express';
import path from 'path';
import { promises as fs } from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const app = express();
const PORT = process.env.PORT || 3000;

const DEFAULT_MEMBERSHIP_CONTRACT = '0x495f947276749ce646f68ac8c248420045cb7b5e';

const baseAccessConfig = {
  membershipName: sanitizeEnv(process.env.IONCORE_APES_NAME) || 'Ioncore Apes',
  requiredChainId: sanitizeEnv(process.env.IONCORE_APES_CHAIN_ID) || '0x1',
  tokenType: (sanitizeEnv(process.env.IONCORE_APES_TOKEN_TYPE) || 'erc721').toLowerCase()
};

const optionalAccessConfig = {
  membershipContract: sanitizeEnv(process.env.IONCORE_APES_CONTRACT) || DEFAULT_MEMBERSHIP_CONTRACT,
  tokenId: sanitizeEnv(process.env.IONCORE_APES_TOKEN_ID),
  minBalance: sanitizeEnv(process.env.IONCORE_APES_MIN_BALANCE)
};

for (const [key, value] of Object.entries(optionalAccessConfig)) {
  if (value !== undefined) {
    baseAccessConfig[key] = value;
  }
}

const WALLET_CONFIG_TAG = `<script>window.__IONCORE_ACCESS__ = ${JSON.stringify(baseAccessConfig)};</script>`;
const WALLET_GUARD_TAG = '<script type="module" src="/wallet-guard.js"></script>';

function sanitizeEnv(value) {
  if (value === undefined || value === null) return undefined;
  if (typeof value !== 'string') return value;
  const trimmed = value.trim();
  return trimmed.length ? trimmed : undefined;
}

function injectTag(html, tag) {
  if (html.includes('</body>')) {
    return html.replace('</body>', `${tag}</body>`);
  }
  return `${html}\n${tag}`;
}

function injectWalletGuard(html) {
  if (!html || typeof html !== 'string') return html;
  let output = html;
  if (!output.includes('__IONCORE_ACCESS__')) {
    output = injectTag(output, WALLET_CONFIG_TAG);
  }
  if (!output.includes('wallet-guard.js')) {
    output = injectTag(output, WALLET_GUARD_TAG);
  }
  return output;
}

async function sendHtmlWithGuard(res, filePath) {
  try {
    let html = await fs.readFile(filePath, 'utf8');
    html = injectWalletGuard(html);
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
  if (req.path.toLowerCase().endsWith('.html') && req.path !== '/webpage.html') {
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

// Public homepage
app.get('/', async (req, res) => {
  await sendHtmlWithGuard(res, path.join(__dirname, 'webpage.html'));
});

app.get(/^\/(?!view$)[^?]*\.html$/i, async (req, res) => {
  const rel = decodeURIComponent(req.path.slice(1));
  const filePath = path.join(__dirname, rel);
  if (!filePath.startsWith(__dirname)) {
    return res.status(400).send('Invalid path');
  }
  await sendHtmlWithGuard(res, filePath);
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
    res.send(
      injectWalletGuard(`<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Brochures</title><link rel="icon" type="image/svg+xml" href="/battery.svg"><link href="https://fonts.googleapis.com/css?family=Montserrat:700,400&display=swap" rel="stylesheet"><link rel="stylesheet" href="/styles.css"></head><body><header><h1>Brochures</h1><div class="cta-buttons"><a class="btn" href="/">Home</a></div></header><div class="grid">${list}</div><footer id="contact"><h3>Ready to Energize Your Future?</h3><p>Contact Ioncore Energy today for partnership, investment, or project inquiries.</p><a href="mailto:ioncoreenergy@gmail.com" class="footer-btn">Contact Us</a><div class="copyright">&copy; <script>document.write(new Date().getFullYear())</script> Ioncore Energy. All rights reserved.</div></footer></body></html>`)
    );
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
    res.send(
      injectWalletGuard(`<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>${title}</title><link rel="icon" type="image/svg+xml" href="/battery.svg"><link href="https://fonts.googleapis.com/css?family=Montserrat:700,400&display=swap" rel="stylesheet"><link rel="stylesheet" href="/styles.css"></head><body><header><div class="cta-buttons"><a class="btn" href="/admin">Back</a></div></header>${html}<footer id="contact"><h3>Ready to Energize Your Future?</h3><p>Contact Ioncore Energy today for partnership, investment, or project inquiries.</p><a href="mailto:ioncoreenergy@gmail.com" class="footer-btn">Contact Us</a><div class="copyright">&copy; <script>document.write(new Date().getFullYear())</script> Ioncore Energy. All rights reserved.</div></footer></body></html>`)
    );
  } catch {
    res.status(404).send('Not found');
  }
});

app.listen(PORT, () => {
  console.log(`Server listening on http://localhost:${PORT}`);
});

