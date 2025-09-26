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

app.use(express.json());
app.use(express.urlencoded({ extended: false }));

const metrics = {
  live: 0,
  viewed: 0
};

const activeSessions = new Map();

const AUTH_USER = process.env.BASIC_AUTH_USER || 'Chad01';
const AUTH_PASS = process.env.BASIC_AUTH_PASS || 'happy';

const COOKIE_NAME = 'ioncore_session';
const COOKIE_MAX_AGE_MS = 1000 * 60 * 60 * 12; // 12 hours

const authSessions = new Map();

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

function isPublicRoute(req) {
  if (req.method === 'GET' && (req.path === '/login' || req.path === '/login.html')) {
    return true;
  }
  if (req.method === 'GET' && req.path === '/battery.svg') {
    return true;
  }
  if (req.method === 'POST' && req.path === '/login') {
    return true;
  }
  if (req.method === 'POST' && req.path === '/logout') {
    return true;
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
    const html = `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Brochures</title><link rel="icon" type="image/svg+xml" href="/battery.svg"><link href="https://fonts.googleapis.com/css?family=Montserrat:700,400&display=swap" rel="stylesheet"><link rel="stylesheet" href="/styles.css"></head><body><header><h1>Brochures</h1><div class="cta-buttons"><a class="btn" href="/">Home</a></div></header><div class="grid">${list}</div><footer id="contact"><h3>Ready to Energize Your Future?</h3><p>Contact Ioncore Energy today for partnership, investment, or project inquiries.</p><a href="mailto:ioncoreenergy@gmail.com" class="footer-btn">Contact Us</a><div class="copyright">&copy; <script>document.write(new Date().getFullYear())</script> Ioncore Energy. All rights reserved.</div></footer></body></html>`;
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
    const wrapped = `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>${title}</title><link rel="icon" type="image/svg+xml" href="/battery.svg"><link href="https://fonts.googleapis.com/css?family=Montserrat:700,400&display=swap" rel="stylesheet"><link rel="stylesheet" href="/styles.css"></head><body><header><div class="cta-buttons"><a class="btn" href="/admin">Back</a><a class="btn" href="/index.html">Index Page</a></div></header>${html}<footer id="contact"><h3>Ready to Energize Your Future?</h3><p>Contact Ioncore Energy today for partnership, investment, or project inquiries.</p><a href="mailto:ioncoreenergy@gmail.com" class="footer-btn">Contact Us</a><div class="copyright">&copy; <script>document.write(new Date().getFullYear())</script> Ioncore Energy. All rights reserved.</div></footer></body></html>`;
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

