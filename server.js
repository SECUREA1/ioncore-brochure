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
const CARDANO_POLICY_ID =
  process.env.CARDANO_POLICY_ID || 'f1a2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8';

const BRAND = {
  name: 'Ioncore Energy',
  themeColor: '#6aff3b',
  icon: '/battery.svg'
};

const DATA_DIR = path.join(__dirname, 'data');
await fs.mkdir(DATA_DIR, { recursive: true });

const STORE_PATH = path.join(DATA_DIR, 'gateway-store.json');

const defaultStore = {
  loginEvents: [],
  contactSubmissions: [],
  gatewaySubmissions: [],
  gatewayUsers: {}
};

async function loadStore() {
  try {
    const raw = await fs.readFile(STORE_PATH, 'utf8');
    const parsed = JSON.parse(raw);
    return {
      loginEvents: Array.isArray(parsed.loginEvents) ? parsed.loginEvents : [],
      contactSubmissions: Array.isArray(parsed.contactSubmissions) ? parsed.contactSubmissions : [],
      gatewaySubmissions: Array.isArray(parsed.gatewaySubmissions) ? parsed.gatewaySubmissions : [],
      gatewayUsers:
        parsed.gatewayUsers && typeof parsed.gatewayUsers === 'object' && !Array.isArray(parsed.gatewayUsers)
          ? parsed.gatewayUsers
          : {}
    };
  } catch (error) {
    if (error && error.code !== 'ENOENT') {
      console.error('Failed to read gateway store. Using defaults.', error);
    }
    return JSON.parse(JSON.stringify(defaultStore));
  }
}

let store = await loadStore();

async function saveStore() {
  try {
    await fs.writeFile(STORE_PATH, JSON.stringify(store, null, 2), 'utf8');
  } catch (error) {
    console.error('Failed to persist gateway store', error);
    throw error;
  }
}

function normalizeForStorage(value) {
  if (typeof value !== 'string') {
    return value == null ? null : String(value);
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function serializeMetadata(value) {
  if (value == null) {
    return null;
  }
  try {
    return JSON.stringify(value);
  } catch (err) {
    console.error('Failed to serialize metadata for storage', err);
    return null;
  }
}

async function recordLoginEvent(event) {
  try {
    store.loginEvents.push({
      createdAt: new Date().toISOString(),
      method: normalizeForStorage(event.method) || 'credentials',
      username: normalizeForStorage(event.username),
      walletAddress: normalizeForStorage(event.walletAddress),
      walletProvider: normalizeForStorage(event.walletProvider),
      meknxPassId: normalizeForStorage(event.meknxPassId),
      success: event.success ? 1 : 0,
      metadata: normalizeForStorage(event.metadata)
    });
    await saveStore();
  } catch (err) {
    console.error('Failed to record login event', err);
  }
}

async function recordContactSubmission(submission) {
  try {
    store.contactSubmissions.push({
      createdAt: new Date().toISOString(),
      name: normalizeForStorage(submission.name),
      email: normalizeForStorage(submission.email),
      message: normalizeForStorage(submission.message),
      source: normalizeForStorage(submission.source)
    });
    await saveStore();
    return true;
  } catch (err) {
    console.error('Failed to record contact submission', err);
    return false;
  }
}

async function recordGatewaySubmission(submission) {
  try {
    store.gatewaySubmissions.push({
      createdAt: new Date().toISOString(),
      role: normalizeForStorage(submission.role),
      name: normalizeForStorage(submission.name),
      email: normalizeForStorage(submission.email),
      accessCode: normalizeForStorage(submission.accessCode),
      engagementFocus: normalizeForStorage(submission.engagementFocus),
      userAgent: normalizeForStorage(submission.userAgent),
      referer: normalizeForStorage(submission.referer),
      ipAddress: normalizeForStorage(submission.ipAddress)
    });
    await saveStore();
    return true;
  } catch (err) {
    console.error('Failed to record gateway submission', err);
    return false;
  }
}

app.use(express.json());
app.use(express.urlencoded({ extended: false }));

const metrics = {
  live: 0,
  viewed: 0
};

const activeSessions = new Map();
const SESSION_TIMEOUT_MS = 1000 * 60; // 1 minute tolerance for inactive sessions

function pruneSessions() {
  const now = Date.now();
  let changed = false;
  for (const [sessionId, lastSeen] of activeSessions.entries()) {
    if (typeof lastSeen !== 'number' || now - lastSeen > SESSION_TIMEOUT_MS) {
      activeSessions.delete(sessionId);
      changed = true;
    }
  }

  if (changed) {
    metrics.live = activeSessions.size;
  }
}

const AUTH_USER = process.env.BASIC_AUTH_USER || 'investor';
const AUTH_PASS = process.env.BASIC_AUTH_PASS || 'burrito';

const COOKIE_NAME = 'ioncore_session';
const COOKIE_MAX_AGE_MS = 1000 * 60 * 60 * 12; // 12 hours

const authSessions = new Map();
const meknxRegistry = new Map();

function registerSession() {
  pruneSessions();
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
  pruneSessions();
  if (activeSessions.delete(sessionId)) {
    metrics.live = activeSessions.size;
  }
}

function touchSession(sessionId) {
  if (typeof sessionId !== 'string' || !sessionId) {
    return false;
  }
  pruneSessions();
  if (!activeSessions.has(sessionId)) {
    return false;
  }
  activeSessions.set(sessionId, Date.now());
  return true;
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
  if (typeof provider !== 'string') {
    return 'evm';
  }
  const normalized = provider.trim().toLowerCase();
  if (!normalized) {
    return 'evm';
  }
  if (normalized === 'solana') {
    return 'solana';
  }
  if (normalized === 'cardano' || normalized.startsWith('cardano-')) {
    return 'cardano';
  }
  return 'evm';
}

function generateMeknxPassId() {
  return `MEKNX-${randomUUID().replace(/-/g, '').slice(0, 10).toUpperCase()}`;
}

function generateAccessCode() {
  return Math.floor(100000 + Math.random() * 900000).toString();
}

app.get(['/login', '/login.html'], (req, res) => {
  const sessionId = getSessionIdFromCookies(req);
  if (validateAuthSession(sessionId)) {
    setSessionCookie(res, sessionId);
  } else if (sessionId) {
    clearSessionCookie(res);
  }

  let redirectTarget = '/';
  if (typeof req.query.next === 'string') {
    const candidate = req.query.next;
    if (candidate.startsWith('/') && !candidate.startsWith('//')) {
      redirectTarget = candidate;
    }
  }

  if (redirectTarget === '/login' || redirectTarget === '/login.html') {
    redirectTarget = '/';
  }

  res.redirect(redirectTarget);
});

app.post('/login', async (req, res) => {
  const body = req.body && typeof req.body === 'object' ? req.body : {};

  await recordLoginEvent({
    method: 'retired',
    username: normalizeForStorage(body.username),
    walletAddress: normalizeForStorage(body.walletAddress),
    walletProvider: normalizeForStorage(body.walletProvider),
    meknxPassId: normalizeForStorage(body.meknxPassId),
    success: false,
    metadata: serializeMetadata({ reason: 'Login portal disabled' })
  });

  clearSessionCookie(res);
  res.status(410).json({
    message: 'The login portal has been retired. Access the brochure directly from the homepage.'
  });
});

app.post('/contact', async (req, res) => {
  const body = req.body && typeof req.body === 'object' ? req.body : {};
  const name = typeof body.name === 'string' ? body.name.trim() : '';
  const email = typeof body.email === 'string' ? body.email.trim() : '';
  const message = typeof body.message === 'string' ? body.message.trim() : '';

  const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!email || !emailPattern.test(email)) {
    return res.status(400).json({ message: 'Provide a valid email address before submitting.' });
  }

  const stored = await recordContactSubmission({
    name,
    email,
    message,
    source: 'webpage.html'
  });

  if (!stored) {
    return res.status(500).json({ message: 'Unable to record your request right now. Please try again shortly.' });
  }

  res.json({ message: 'Submission received. Our advisors will reach out shortly.' });
});

app.post('/gateway', async (req, res) => {
  const body = req.body && typeof req.body === 'object' ? req.body : {};
  const role = typeof body.role === 'string' ? body.role.trim().toLowerCase() : '';
  const name = typeof body.name === 'string' ? body.name.trim() : '';
  const emailRaw = typeof body.email === 'string' ? body.email.trim() : '';
  const code = typeof body.code === 'string' ? body.code.trim() : '';
  const intent = typeof body.intent === 'string' ? body.intent.trim() : '';

  const allowedRoles = new Set(['investor', 'buyer', 'team']);
  if (!allowedRoles.has(role)) {
    return res
      .status(400)
      .json({ message: 'Select the access profile that best represents your relationship with Ioncore Energy.' });
  }

  if (!name) {
    return res.status(400).json({ message: 'Enter your full name to continue.' });
  }

  const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRaw || !emailPattern.test(emailRaw)) {
    return res.status(400).json({ message: 'Provide a valid work email address.' });
  }

  const email = emailRaw.toLowerCase();
  const existingUser = store.gatewayUsers[email] || null;
  const isExistingUser = !!existingUser;

  if (isExistingUser) {
    if (!/^\d{6}$/.test(code)) {
      return res.status(400).json({ message: 'Enter the 6-digit access code issued on your first login.' });
    }
    if (code !== existingUser.accessCode) {
      return res.status(401).json({ message: 'Incorrect access code. Use the 6-digit code provided on your initial login.' });
    }
    if (intent && intent.length > 0 && intent.length < 12) {
      return res
        .status(400)
        .json({ message: 'Share at least 12 characters if you would like to update your engagement focus, or leave it blank to keep the previous entry.' });
    }
  } else if (code) {
    if (!/^\d{6}$/.test(code)) {
      return res.status(400).json({ message: 'Access codes must be 6 digits. Leave this field blank for first-time access.' });
    }
  }

  if (!isExistingUser) {
    if (!intent || intent.length < 12) {
      return res
        .status(400)
        .json({ message: 'Share a brief summary of your engagement focus (12+ characters).' });
    }

    const accessCode = generateAccessCode();
    if (store.gatewayUsers[email]) {
      return res
        .status(409)
        .json({ message: 'An access code has already been issued for this email. Enter your 6-digit code to continue.' });
    }

    const nowIso = new Date().toISOString();
    store.gatewayUsers[email] = {
      role,
      name,
      email,
      engagementFocus: intent,
      accessCode,
      createdAt: nowIso,
      updatedAt: nowIso,
      lastLogin: nowIso
    };

    try {
      await saveStore();
    } catch (error) {
      console.error('Failed to create gateway user', error);
      delete store.gatewayUsers[email];
      return res.status(500).json({ message: 'We were unable to record your access request. Please try again shortly.' });
    }

    const stored = await recordGatewaySubmission({
      role,
      name,
      email,
      accessCode,
      engagementFocus: intent,
      userAgent: req.get('user-agent'),
      referer: req.get('referer'),
      ipAddress: req.ip
    });

    if (!stored) {
      return res
        .status(500)
        .json({ message: 'We were unable to record your access request. Please try again shortly.' });
    }

    const expiresAt = new Date(Date.now() + COOKIE_MAX_AGE_MS).toISOString();
    return res.status(201).json({
      message: 'Access granted. Your personal 6-digit code has been issued. Save it for your next visit.',
      assignedCode: accessCode,
      isNewUser: true,
      expiresAt
    });
  }

  const engagementFocusUpdate = intent && intent.length >= 12 ? intent : null;
  const resolvedEngagementFocus = engagementFocusUpdate || existingUser.engagementFocus || 'Existing engagement focus retained';

  const nowIso = new Date().toISOString();
  try {
    const updatedUser = {
      ...existingUser,
      role,
      name,
      lastLogin: nowIso,
      updatedAt: nowIso
    };
    if (engagementFocusUpdate) {
      updatedUser.engagementFocus = engagementFocusUpdate;
    }
    store.gatewayUsers[email] = updatedUser;
    await saveStore();
  } catch (error) {
    console.error('Failed to update gateway user', error);
    store.gatewayUsers[email] = existingUser;
    return res.status(500).json({ message: 'We were unable to refresh your access. Please try again shortly.' });
  }

  const refreshedUser = store.gatewayUsers[email];
  if (!refreshedUser) {
    console.error('Gateway user missing after update for email:', email);
    return res.status(500).json({ message: 'We were unable to refresh your access. Please try again shortly.' });
  }

  const stored = await recordGatewaySubmission({
    role,
    name,
    email,
    accessCode: refreshedUser.accessCode,
    engagementFocus: resolvedEngagementFocus,
    userAgent: req.get('user-agent'),
    referer: req.get('referer'),
    ipAddress: req.ip
  });

  if (!stored) {
    return res
      .status(500)
      .json({ message: 'We were unable to record your access request. Please try again shortly.' });
  }

  const expiresAt = new Date(Date.now() + COOKIE_MAX_AGE_MS).toISOString();
  res.json({
    message: 'Access verified. Redirecting to brochure.',
    assignedCode: refreshedUser.accessCode,
    isNewUser: false,
    expiresAt
  });
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
  const fallbackProvider = existing ? normalizeProvider(existing.walletProvider) : 'evm';
  const walletProvider = requestedProvider || fallbackProvider;

  if (actionRaw === 'verify') {
    if (!existing) {
      return res.status(404).json({ message: 'No MEKNX pass found for this wallet. Mint a clearance token first.' });
    }

    existing.walletProvider = walletProvider;
    existing.lastVerifiedAt = nowIso;
    if (existing.walletProvider === 'cardano' && !existing.cardanoPolicyId) {
      existing.cardanoPolicyId = CARDANO_POLICY_ID;
    }
    meknxRegistry.set(walletAddress, existing);
    return res.json({
      status: 'verified',
      passId: existing.passId,
      mintedAt: existing.mintedAt,
      walletProvider: existing.walletProvider,
      ioncTokens: existing.ioncTokens || 0,
      cardanoPolicyId: existing.cardanoPolicyId || '',
      cardanoPolicyVerified: !!existing.cardanoPolicyVerified,
      message: 'MEKNX verification confirmed.'
    });
  }

  if (existing) {
    existing.walletProvider = walletProvider;
    if (existing.walletProvider === 'solana' && (!existing.ioncTokens || existing.ioncTokens < 1)) {
      existing.ioncTokens = 1;
    }
    if (existing.walletProvider === 'cardano') {
      existing.cardanoPolicyId = existing.cardanoPolicyId || CARDANO_POLICY_ID;
      existing.cardanoPolicyVerified = existing.cardanoPolicyVerified === true;
    } else if (existing.cardanoPolicyVerified) {
      existing.cardanoPolicyVerified = false;
    }
    existing.lastVerifiedAt = nowIso;
    meknxRegistry.set(walletAddress, existing);
    return res.json({
      status: 'minted',
      passId: existing.passId,
      mintedAt: existing.mintedAt,
      walletProvider: existing.walletProvider,
      ioncTokens: existing.ioncTokens || 0,
      cardanoPolicyId: existing.cardanoPolicyId || '',
      cardanoPolicyVerified: !!existing.cardanoPolicyVerified,
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
    ioncTokens,
    cardanoPolicyId: walletProvider === 'cardano' ? CARDANO_POLICY_ID : '',
    cardanoPolicyVerified: false
  };
  meknxRegistry.set(walletAddress, record);

  return res.status(201).json({
    status: 'minted',
    passId,
    mintedAt,
    walletProvider,
    ioncTokens,
    cardanoPolicyId: record.cardanoPolicyId,
    cardanoPolicyVerified: record.cardanoPolicyVerified,
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

app.post('/access/cardano', (req, res) => {
  const body = req.body || {};
  const walletAddress = typeof body.walletAddress === 'string' ? body.walletAddress.trim() : '';
  const walletProvider = normalizeProvider(
    typeof body.walletProvider === 'string' ? body.walletProvider.trim() : ''
  );
  const passId = typeof body.meknxPassId === 'string' ? body.meknxPassId.trim() : '';
  const policyIdRaw = typeof body.policyId === 'string' ? body.policyId.trim() : '';

  if (!walletAddress) {
    return res
      .status(400)
      .json({ message: 'Wallet address required for Cardano policy verification.' });
  }

  if (walletProvider !== 'cardano') {
    return res
      .status(400)
      .json({ message: 'Cardano policy verification requires a Cardano wallet session.' });
  }

  if (!policyIdRaw) {
    return res.status(400).json({ message: 'Policy identifier required for verification.' });
  }

  const expectedPolicyId = (CARDANO_POLICY_ID || '').toLowerCase();
  const providedPolicyId = policyIdRaw.toLowerCase();

  if (expectedPolicyId && providedPolicyId !== expectedPolicyId) {
    return res
      .status(403)
      .json({ message: 'Wallet does not hold the required Cardano policy asset.' });
  }

  const record = meknxRegistry.get(walletAddress);
  if (!record) {
    return res
      .status(404)
      .json({ message: 'Mint a MEKNX clearance before verifying Cardano policies.' });
  }

  if (passId && record.passId && passId !== record.passId) {
    return res.status(409).json({ message: 'MEKNX pass mismatch. Re-verify your clearance token.' });
  }

  record.walletProvider = 'cardano';
  record.cardanoPolicyId = CARDANO_POLICY_ID;
  record.cardanoPolicyVerified = true;
  record.cardanoPolicyVerifiedAt = new Date().toISOString();
  record.lastVerifiedAt = record.cardanoPolicyVerifiedAt;
  meknxRegistry.set(walletAddress, record);

  return res.json({
    status: 'verified',
    passId: record.passId,
    policyId: record.cardanoPolicyId,
    message: 'Cardano policy verification complete.'
  });
});

function isPublicRoute(req) {
  if (
    req.method === 'POST' &&
    ['/login', '/logout', '/access/meknx', '/access/ionc', '/access/cardano', '/contact', '/gateway'].includes(req.path)
  ) {
    return true;
  }

  if (req.method === 'GET') {
    const publicHtml = new Set([
      '/login',
      '/login.html',
      '/',
      '/webpage.html',
      '/webpage-login.html',
      '/index',
      '/index.html',
      '/index/',
      '/IONCORECHAT',
      '/IONCORECHAT/',
      '/IONCORECHAT/index',
      '/IONCORECHAT/index.html'
    ]);
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
  return next();
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
  res.json({ sessionId, live: metrics.live, viewed: metrics.viewed, sessionActive: true });
});

app.post('/metrics/leave', (req, res) => {
  const sessionId =
    (req.body && typeof req.body.sessionId === 'string' && req.body.sessionId) ||
    (req.query && typeof req.query.sessionId === 'string' && req.query.sessionId) ||
    '';
  endSession(sessionId);
  res.json({ live: metrics.live, viewed: metrics.viewed, sessionActive: false });
});

app.get('/metrics', (req, res) => {
  pruneSessions();
  const sessionId = typeof req.query.sessionId === 'string' ? req.query.sessionId : '';
  const sessionActive = sessionId ? touchSession(sessionId) : false;
  res.json({ live: metrics.live, viewed: metrics.viewed, sessionActive });
});

app.listen(PORT, () => {
  console.log(`Server listening on http://localhost:${PORT}`);
});

