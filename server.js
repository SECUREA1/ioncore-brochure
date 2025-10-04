import express from 'express';
import path from 'path';
import { promises as fs } from 'fs';
import { fileURLToPath } from 'url';
import unzipper from 'unzipper';
import { randomUUID } from 'crypto';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const app = express();
const PORT = process.env.PORT || 3000;

const TIMEPIECES_ZIP = 'ioncore_ready_to_sell_brochure_mint_5_with_solana_desc.html.zip';
const TIMEPIECES_HTML = 'ioncore_ready_to_sell_brochure_mint_5_with_solana_desc.html';

const BRAND = {
  name: 'Ioncore Energy',
  themeColor: '#6aff3b',
  icon: '/battery.svg'
};

app.use(express.json());
app.use(express.urlencoded({ extended: false }));

const metrics = {
  live: 0,
  viewed: 0
};

const activeSessions = new Map();

const AUTH_USER = process.env.BASIC_AUTH_USER || 'investor';
const AUTH_PASS = process.env.BASIC_AUTH_PASS || 'ioncore';

const COOKIE_NAME = 'ioncore_session';
const COOKIE_MAX_AGE_MS = 1000 * 60 * 60 * 12; // 12 hours

const authSessions = new Map();
const meknxRegistry = new Map();

function registerSession() {
  const sessionId = randomUUID();
  activeSessions.set(sessionId, Date.now());
  metrics.live = activeSessions.size;
  metrics.viewed += 1;
  return sessionId;
}

function endSession(sessionId) {
  if (typeof sessionId !== 'string' || !sessionId) {
    return;
  }
  if (activeSessions.delete(sessionId)) {
    metrics.live = activeSessions.size;
  }
}

async function sendHtml(res, filePath) {
  try {
    let html = await fs.readFile(filePath, 'utf8');
    res.type('html').send(html);
  } catch {
    res.status(404).send('Not found');
  }
}

function createAuthSession() {
  const sessionId = randomUUID();
  authSessions.set(sessionId, Date.now());
  return sessionId;
}

function validateAuthSession(sessionId) {
  if (typeof sessionId !== 'string' || !sessionId) {
    return false;
  }
  const lastSeen = authSessions.get(sessionId);
  if (!lastSeen) {
    return false;
  }
  if (Date.now() - lastSeen > COOKIE_MAX_AGE_MS) {
    authSessions.delete(sessionId);
    return false;
  }
  authSessions.set(sessionId, Date.now());
  return true;
}

function buildHead(pageTitle) {
  const brandName = BRAND.name;
  const fullTitle = pageTitle.toLowerCase().includes(brandName.toLowerCase())
    ? pageTitle
    : `${brandName} | ${pageTitle}`;
  const ogImage = BRAND.icon;
  const themeColor = BRAND.themeColor;
  return `<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="application-name" content="${brandName}"><meta name="apple-mobile-web-app-title" content="${brandName}"><meta name="theme-color" content="${themeColor}"><meta property="og:site_name" content="${brandName}"><meta property="og:title" content="${fullTitle}"><meta property="og:image" content="${ogImage}"><title>${fullTitle}</title><link rel="icon" type="image/svg+xml" href="${BRAND.icon}"><link rel="apple-touch-icon" href="${BRAND.icon}"><link href="https://fonts.googleapis.com/css?family=Montserrat:700,400&display=swap" rel="stylesheet"><link rel="stylesheet" href="/styles.css">`;
}

function destroyAuthSession(sessionId) {
  if (typeof sessionId !== 'string' || !sessionId) {
    return;
  }
  authSessions.delete(sessionId);
}

function getSessionIdFromCookies(req) {
  const cookieHeader = req.headers.cookie;
  if (!cookieHeader) {
    return '';
  }
  const cookies = cookieHeader.split(';');
  for (const cookie of cookies) {
    const [rawName, ...rest] = cookie.trim().split('=');
    if (rawName === COOKIE_NAME) {
      return rest.join('=');
    }
  }
  return '';
}

function setSessionCookie(res, sessionId) {
  const maxAgeSeconds = Math.floor(COOKIE_MAX_AGE_MS / 1000);
  res.setHeader(
    'Set-Cookie',
    `${COOKIE_NAME}=${sessionId}; HttpOnly; Path=/; SameSite=Lax; Max-Age=${maxAgeSeconds}`
  );
}

function clearSessionCookie(res) {
  res.setHeader('Set-Cookie', `${COOKIE_NAME}=; HttpOnly; Path=/; SameSite=Lax; Max-Age=0`);
}

function normalizeProvider(provider) {
  return provider === 'solana' ? 'solana' : 'evm';
}

function generateMeknxPassId() {
  return `MEKNX-${randomUUID().replace(/-/g, '').slice(0, 10).toUpperCase()}`;
}

app.get('/login', async (req, res) => {
  const sessionId = getSessionIdFromCookies(req);
  if (validateAuthSession(sessionId)) {
    setSessionCookie(res, sessionId);
    const queryNext = typeof req.query.next === 'string' ? req.query.next : '/';
    const safeNext = queryNext.startsWith('/') && !queryNext.startsWith('//') ? queryNext : '/';
    return res.redirect(safeNext);
  }
  await sendHtml(res, path.join(__dirname, 'login.html'));
});

app.post('/login', (req, res) => {
  const username = (req.body && typeof req.body.username === 'string' && req.body.username) || '';
  const password = (req.body && typeof req.body.password === 'string' && req.body.password) || '';
  let nextPath = (req.body && typeof req.body.next === 'string' && req.body.next) || '/';

  if (!nextPath.startsWith('/') || nextPath.startsWith('//')) {
    nextPath = '/';
  }

  if (username === AUTH_USER && password === AUTH_PASS) {
    const sessionId = createAuthSession();
    setSessionCookie(res, sessionId);
    return res.json({ redirect: nextPath });
  }

  clearSessionCookie(res);
  res.status(401).json({ message: 'Access denied. Invalid clearance credentials.' });
});

app.post('/logout', (req, res) => {
  const sessionId = getSessionIdFromCookies(req);
  destroyAuthSession(sessionId);
  clearSessionCookie(res);
  res.json({ message: 'Logged out' });
});

app.post('/access/meknx', (req, res) => {
  const body = req.body || {};
  const walletAddress = typeof body.walletAddress === 'string' ? body.walletAddress.trim() : '';
  const actionRaw = typeof body.action === 'string' ? body.action.trim().toLowerCase() : 'verify';
  const requestedProvider =
    typeof body.walletProvider === 'string' && body.walletProvider.trim()
      ? normalizeProvider(body.walletProvider.trim())
      : '';

  if (!walletAddress) {
    return res.status(400).json({ message: 'Wallet address required for MEKNX clearance.' });
  }

  if (actionRaw !== 'verify' && actionRaw !== 'mint') {
    return res.status(400).json({ message: 'Unsupported MEKNX clearance action.' });
  }

  const nowIso = new Date().toISOString();
  const existing = meknxRegistry.get(walletAddress);
  const walletProvider = requestedProvider || (existing ? existing.walletProvider : 'evm');

  if (actionRaw === 'verify') {
    if (!existing) {
      return res.status(404).json({ message: 'No MEKNX pass found for this wallet. Mint a clearance token first.' });
    }

    existing.lastVerifiedAt = nowIso;
    meknxRegistry.set(walletAddress, existing);
    return res.json({
      status: 'verified',
      passId: existing.passId,
      mintedAt: existing.mintedAt,
      walletProvider: existing.walletProvider,
      ioncTokens: existing.ioncTokens || 0,
      message: 'MEKNX verification confirmed.'
    });
  }

  if (existing) {
    existing.walletProvider = walletProvider;
    if (existing.walletProvider === 'solana' && (!existing.ioncTokens || existing.ioncTokens < 1)) {
      existing.ioncTokens = 1;
    }
    existing.lastVerifiedAt = nowIso;
    meknxRegistry.set(walletAddress, existing);
    return res.json({
      status: 'minted',
      passId: existing.passId,
      mintedAt: existing.mintedAt,
      walletProvider: existing.walletProvider,
      ioncTokens: existing.ioncTokens || 0,
      message: 'Existing MEKNX pass located. Verification refreshed.'
    });
  }

  const passId = generateMeknxPassId();
  const mintedAt = nowIso;
  const ioncTokens = walletProvider === 'solana' ? 1 : 0;
  const record = {
    walletAddress,
    walletProvider,
    passId,
    mintedAt,
    lastVerifiedAt: nowIso,
    ioncTokens
  };
  meknxRegistry.set(walletAddress, record);

  return res.status(201).json({
    status: 'minted',
    passId,
    mintedAt,
    walletProvider,
    ioncTokens,
    message: 'MEKNX pass minted successfully.'
  });
});

app.post('/access/ionc', (req, res) => {
  const body = req.body || {};
  const walletAddress = typeof body.walletAddress === 'string' ? body.walletAddress.trim() : '';
  const walletProviderRaw =
    typeof body.walletProvider === 'string' ? body.walletProvider.trim().toLowerCase() : '';
  const walletProvider = walletProviderRaw === 'solana' ? 'solana' : walletProviderRaw;
  const passId = typeof body.meknxPassId === 'string' ? body.meknxPassId.trim() : '';

  if (!walletAddress) {
    return res.status(400).json({ message: 'Wallet address required for IONC verification.' });
  }

  if (walletProvider !== 'solana') {
    return res.status(400).json({ message: 'IONC verification is only available for Solana wallets.' });
  }

  const record = meknxRegistry.get(walletAddress);
  if (!record) {
    return res.status(404).json({ message: 'Mint a MEKNX clearance before requesting IONC verification.' });
  }

  if (passId && record.passId && passId !== record.passId) {
    return res.status(409).json({ message: 'MEKNX pass mismatch. Re-verify your clearance token.' });
  }

  record.walletProvider = 'solana';
  if (!record.ioncTokens || record.ioncTokens < 1) {
    return res.status(403).json({ message: 'No IONC access tokens assigned to this wallet. Mint a MEKNX pass on Solana or request a top-up.' });
  }

  record.lastVerifiedAt = new Date().toISOString();
  meknxRegistry.set(walletAddress, record);

  return res.json({
    status: 'verified',
    passId: record.passId,
    tokens: record.ioncTokens,
    message: 'IONC verification complete.'
  });
});

function isPublicRoute(req) {
  if (
    req.method === 'POST' &&
    ['/login', '/logout', '/access/meknx', '/access/ionc'].includes(req.path)
  ) {
    return true;
  }

  if (req.method === 'GET') {
    const publicHtml = new Set(['/login', '/login.html', '/', '/webpage.html']);
    if (publicHtml.has(req.path)) {
      return true;
    }

    const publicAssets = new Set(['.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico', '.json', '.txt']);
    const extension = path.extname(req.path).toLowerCase();
    if (publicAssets.has(extension)) {
      return true;
    }
  }

  return false;
}

function requireAuth(req, res, next) {
  if (isPublicRoute(req)) {
    return next();
  }

  const sessionId = getSessionIdFromCookies(req);
  if (validateAuthSession(sessionId)) {
    setSessionCookie(res, sessionId);
    return next();
  }

  clearSessionCookie(res);

  const expectsHtml = req.method === 'GET' && req.accepts('html');
  const nextPath = encodeURIComponent(req.originalUrl || req.url || '/');
  if (expectsHtml) {
    return res.redirect(`/login?next=${nextPath}`);
  }
  res.status(401).json({ message: 'Authentication required' });
}

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

app.use(requireAuth);

// Public homepage
app.get('/', async (req, res) => {
  await sendHtml(res, path.join(__dirname, 'webpage.html'));
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
    const html = buffer.toString('utf8');
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
app.get('/admin', async (req, res) => {
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
    const html = `<!DOCTYPE html><html lang="en"><head>${buildHead('Brochures Dashboard')}</head><body><header><h1>Brochures</h1><div class="cta-buttons"><a class="btn" href="/">Home</a></div></header><div class="grid">${list}</div><footer id="contact"><h3>Ready to Energize Your Future?</h3><p>Contact Ioncore Energy today for partnership, investment, or project inquiries.</p><a href="mailto:ioncoreenergy@gmail.com" class="footer-btn">Contact Us</a><div class="copyright">&copy; <script>document.write(new Date().getFullYear())</script> Ioncore Energy. All rights reserved.</div></footer></body></html>`;
    res.send(html);
  } catch (err) {
    res.status(500).send('Failed to load index');
  }
});

app.get('/view', async (req, res) => {
  const rel = req.query.f;
  if (!rel) return res.status(400).send('Missing file');
  const filePath = path.join(__dirname, rel);
  if (!filePath.startsWith(__dirname)) return res.status(400).send('Invalid path');
  try {
    const html = await fs.readFile(filePath, 'utf8');
    const title = await getTitle(filePath);
    const wrapped = `<!DOCTYPE html><html lang="en"><head>${buildHead(title)}</head><body><header><div class="cta-buttons"><a class="btn" href="/admin">Back</a><a class="btn" href="/index.html">Index Page</a></div></header>${html}<footer id="contact"><h3>Ready to Energize Your Future?</h3><p>Contact Ioncore Energy today for partnership, investment, or project inquiries.</p><a href="mailto:ioncoreenergy@gmail.com" class="footer-btn">Contact Us</a><div class="copyright">&copy; <script>document.write(new Date().getFullYear())</script> Ioncore Energy. All rights reserved.</div></footer></body></html>`;
    res.send(wrapped);
  } catch {
    res.status(404).send('Not found');
  }
});

app.post('/metrics/view', (req, res) => {
  const sessionId = registerSession();
  res.json({ sessionId, live: metrics.live, viewed: metrics.viewed });
});

app.post('/metrics/leave', (req, res) => {
  const sessionId =
    (req.body && typeof req.body.sessionId === 'string' && req.body.sessionId) ||
    (req.query && typeof req.query.sessionId === 'string' && req.query.sessionId) ||
    '';
  endSession(sessionId);
  res.json({ live: metrics.live, viewed: metrics.viewed });
});

app.get('/metrics', (req, res) => {
  res.json({ live: metrics.live, viewed: metrics.viewed });
});

app.listen(PORT, () => {
  console.log(`Server listening on http://localhost:${PORT}`);
});

