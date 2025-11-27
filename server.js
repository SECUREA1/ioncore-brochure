import express from 'express';
import path from 'path';
import { promises as fs } from 'fs';
import { fileURLToPath } from 'url';
import os from 'os';
import unzipper from 'unzipper';
import { createHash, randomUUID } from 'crypto';
import { executeMeknxGate, isThirdwebConfigured } from './integrations/thirdweb-client.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const app = express();
const PORT = process.env.PORT || 3000;

const TIMEPIECES_ZIP = 'ioncore_ready_to_sell_brochure_mint_5_with_solana_desc.html.zip';
const TIMEPIECES_HTML = 'ioncore_ready_to_sell_brochure_mint_5_with_solana_desc.html';
const ADMIN_PROMO_SECTION = `
  <section id="admin-control-hub" style="position:relative;margin:80px auto;max-width:960px;padding:56px 48px;border-radius:28px;background:rgba(9,16,29,0.9);box-shadow:0 32px 80px rgba(3,7,18,0.56);border:1px solid rgba(106,255,59,0.22);overflow:hidden;">
    <div style="position:absolute;inset:auto -60px -120px auto;width:360px;height:360px;background:radial-gradient(circle,rgba(106,255,59,0.16)0%,rgba(106,255,59,0)68%);"></div>
    <span style="display:inline-flex;align-items:center;gap:10px;font-size:0.85rem;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:#6aff3b;">Admin Access</span>
    <h2 style="font-size:2.4rem;margin:18px 0 12px;color:#f5f8ff;">Command Center for Stripe &amp; Membership Intelligence</h2>
    <p style="max-width:640px;font-size:1.05rem;line-height:1.7;color:#b7c7e4;">
      Unlock the administrative console to review Stripe transaction history, manage Ioncore user credentials, audit poll and question box submissions, and recall precise activity timestamps for due diligence.
    </p>
    <div style="display:flex;flex-wrap:wrap;gap:18px;margin-top:36px;">
      <div style="flex:1 1 240px;min-width:240px;padding:22px;border-radius:18px;background:rgba(106,255,59,0.12);border:1px solid rgba(106,255,59,0.28);color:#0d182e;">
        <h3 style="margin:0 0 10px;font-size:1.2rem;color:#071225;">Unified Data Access</h3>
        <p style="margin:0;color:#071225;opacity:0.82;">
          Review gateway submissions, credential changes, and contact center history from a single timeline.
        </p>
      </div>
      <div style="flex:1 1 240px;min-width:240px;padding:22px;border-radius:18px;background:rgba(12,20,36,0.88);border:1px solid rgba(255,255,255,0.08);color:#f5f8ff;">
        <h3 style="margin:0 0 10px;font-size:1.2rem;">Credential Controls</h3>
        <p style="margin:0;color:rgba(247,249,255,0.78);">
          Edit user roles, refresh permissions, and attach investigative notes with automatic timestamping.
        </p>
      </div>
    </div>
    <a href="/admin.html" class="btn" style="margin-top:38px;display:inline-flex;padding:16px 34px;border-radius:999px;background:#6aff3b;color:#030712;font-weight:700;font-size:1.05rem;text-decoration:none;">Launch Admin Control Center</a>
  </section>
`;
const TIMEPIECE_LOCK_OVERLAY = `
  <style id="timepiece-lock-overlay-styles">
    .timepiece-lock-overlay {
      position: fixed;
      inset: 0;
      z-index: 9999;
      background: rgba(3, 7, 18, 0.92);
      backdrop-filter: blur(6px);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 32px;
    }
    .timepiece-lock-overlay__card {
      max-width: 520px;
      width: min(520px, 92vw);
      border-radius: 28px;
      border: 1px solid rgba(255, 255, 255, 0.18);
      background: rgba(7, 12, 22, 0.94);
      text-align: center;
      padding: clamp(28px, 6vw, 48px);
      box-shadow: 0 30px 90px rgba(0, 0, 0, 0.65);
    }
    .timepiece-lock-overlay__badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: #facc15;
      border: 1px solid rgba(250, 204, 21, 0.45);
      border-radius: 999px;
      padding: 6px 18px;
      font-size: 0.78rem;
      font-weight: 700;
      margin-bottom: 18px;
    }
    .timepiece-lock-overlay__title {
      margin: 0 0 12px;
      font-size: clamp(1.6rem, 3vw, 2rem);
      color: #f5f8ff;
    }
    .timepiece-lock-overlay__text {
      margin: 0 0 16px;
      color: #c7d2e0;
      line-height: 1.6;
    }
    .timepiece-lock-overlay__contact {
      margin: 0;
      color: #f5f8ff;
      font-weight: 600;
    }
    .timepiece-lock-overlay__contact a {
      color: #6aff3b;
      text-decoration: none;
    }
  </style>
  <div class="timepiece-lock-overlay" role="alert" aria-live="assertive">
    <div class="timepiece-lock-overlay__card">
      <div class="timepiece-lock-overlay__badge">Locked for updates</div>
      <h2 class="timepiece-lock-overlay__title">Timepiece minting is temporarily paused.</h2>
      <p class="timepiece-lock-overlay__text">We&apos;re refreshing the Ioncore Timepieces mint experience and have disabled on-page minting while the update is deployed.</p>
      <p class="timepiece-lock-overlay__contact">Contact <a href="mailto:ioncoreenergy@gmail.com">ioncoreenergy@gmail.com</a> to reserve an edition.</p>
    </div>
  </div>
`;
const CARDANO_POLICY_ID =
  process.env.CARDANO_POLICY_ID || 'f1a2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8';

const BRAND = {
  name: 'Ioncore Energy',
  themeColor: '#6aff3b',
  icon: '/battery.svg'
};

const BITCOIN_ADDRESS =
  (process.env.IONCORE_BTC_ADDRESS || 'bc1qioncoreenergy0u0ytsc4p58u4k3p9l4f3d9s7').trim();
const BITCOIN_CONFIRMATIONS_REQUIRED = Math.min(
  Math.max(Number.parseInt(process.env.IONCORE_BTC_CONFIRMATIONS || '2', 10) || 2, 1),
  6
);
const BITCOIN_SETTLEMENT_WINDOW_MINUTES = Math.min(
  Math.max(Number.parseInt(process.env.IONCORE_BTC_SETTLEMENT_MINUTES || '45', 10) || 45, 10),
  180
);

const DATA_DIR = path.join(__dirname, 'data');
await fs.mkdir(DATA_DIR, { recursive: true });

const STORE_PATH = path.join(DATA_DIR, 'gateway-store.json');
const BACKUP_DIR = path.join(DATA_DIR, 'backups');
await fs.mkdir(BACKUP_DIR, { recursive: true });

const FILE_BROADCAST_SCAN_INTERVAL_MS = 1000 * 60;
const FILE_BROADCAST_IGNORE_DIRS = new Set(['node_modules', 'data', '.git', '.github', '.cache', '.next']);
const FILE_AUDIO_EXTENSIONS = new Set(['.mp3', '.wav', '.ogg', '.m4a', '.flac']);
const FILE_VIDEO_EXTENSIONS = new Set(['.mp4', '.mov', '.webm', '.mkv', '.avi']);
const FILE_IMAGE_EXTENSIONS = new Set(['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico']);
const FILE_DOCUMENT_EXTENSIONS = new Set(['.html', '.htm', '.md', '.txt', '.pdf']);
const FILE_SCRIPT_EXTENSIONS = new Set(['.js', '.mjs', '.cjs', '.ts']);
const FILE_ARCHIVE_EXTENSIONS = new Set(['.zip', '.tar', '.gz']);

const FILE_TRACK_EXTENSIONS = new Set(
  [
    ...FILE_AUDIO_EXTENSIONS,
    ...FILE_VIDEO_EXTENSIONS,
    ...FILE_IMAGE_EXTENSIONS,
    ...FILE_DOCUMENT_EXTENSIONS,
    ...FILE_SCRIPT_EXTENSIONS,
    ...FILE_ARCHIVE_EXTENSIONS,
    '.json',
    '.css'
  ].map((ext) => ext.toLowerCase())
);

const FILE_BROADCAST_ROOT = DATA_DIR;

const defaultStore = {
  loginEvents: [],
  contactSubmissions: [],
  gatewaySubmissions: [],
  gatewayUsers: {},
  magstripeTransactions: [],
  bitcoinTransactions: [],
  marketplaceUploads: [],
  marketplaceBids: [],
  timepieceMintLedger: [],
  fileBroadcasts: [],
  chatServerLedger: []
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
          : {},
      magstripeTransactions: Array.isArray(parsed.magstripeTransactions) ? parsed.magstripeTransactions : [],
      bitcoinTransactions: Array.isArray(parsed.bitcoinTransactions) ? parsed.bitcoinTransactions : [],
      marketplaceUploads: Array.isArray(parsed.marketplaceUploads) ? parsed.marketplaceUploads : [],
      marketplaceBids: Array.isArray(parsed.marketplaceBids) ? parsed.marketplaceBids : [],
      timepieceMintLedger: Array.isArray(parsed.timepieceMintLedger) ? parsed.timepieceMintLedger : [],
      fileBroadcasts: Array.isArray(parsed.fileBroadcasts) ? parsed.fileBroadcasts : [],
      chatServerLedger: Array.isArray(parsed.chatServerLedger) ? parsed.chatServerLedger : []
    };
  } catch (error) {
    if (error && error.code !== 'ENOENT') {
      console.error('Failed to read gateway store. Using defaults.', error);
    }
    return JSON.parse(JSON.stringify(defaultStore));
  }
}

let store = await loadStore();

let saveChain = Promise.resolve();

function enqueueStoreSave() {
  saveChain = saveChain
    .catch(() => {
      // Swallow prior errors so a single failure does not block future writes.
    })
    .then(async () => {
      const snapshot = JSON.stringify(store, null, 2);
      await fs.writeFile(STORE_PATH, snapshot, 'utf8');
    });

  return saveChain;
}

async function saveStore() {
  try {
    await enqueueStoreSave();
  } catch (error) {
    console.error('Failed to persist gateway store', error);
    throw error;
  }
}

async function listBackups() {
  try {
    const entries = await fs.readdir(BACKUP_DIR, { withFileTypes: true });
    const files = entries.filter((entry) => entry.isFile() && entry.name.endsWith('.json'));
    const details = await Promise.all(
      files.map(async (file) => {
        const fullPath = path.join(BACKUP_DIR, file.name);
        const stats = await fs.stat(fullPath);
        return {
          name: file.name,
          path: fullPath,
          sizeBytes: stats.size,
          modifiedAt: stats.mtime.toISOString()
        };
      })
    );
    details.sort((a, b) => new Date(b.modifiedAt).getTime() - new Date(a.modifiedAt).getTime());
    return details;
  } catch (error) {
    console.error('Unable to list backups', error);
    return [];
  }
}

async function createBackupSnapshot() {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const filename = `gateway-store-${timestamp}.json`;
  const fullPath = path.join(BACKUP_DIR, filename);
  const payload = {
    savedAt: new Date().toISOString(),
    store
  };
  await fs.writeFile(fullPath, JSON.stringify(payload, null, 2), 'utf8');
  const stats = await fs.stat(fullPath);
  return {
    name: filename,
    path: fullPath,
    sizeBytes: stats.size,
    modifiedAt: stats.mtime.toISOString()
  };
}

async function getBackupSummary() {
  const backups = await listBackups();
  const latest = backups[0] || null;
  return {
    totalBackups: backups.length,
    lastBackupAt: latest ? latest.modifiedAt : null,
    lastBackupFile: latest ? latest.name : null,
    lastBackupSizeBytes: latest ? latest.sizeBytes : null
  };
}

function injectSnippetBeforeBodyClose(html, snippet, marker) {
  if (!html || !snippet) {
    return html;
  }
  if (marker && html.includes(marker)) {
    return html;
  }
  if (/<\/body>/i.test(html)) {
    return html.replace(/<\/body>/i, `${snippet}</body>`);
  }
  return `${html}${snippet}`;
}

function formatFileSize(bytes) {
  if (typeof bytes !== 'number' || !Number.isFinite(bytes) || bytes < 0) {
    return null;
  }
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let value = bytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  const precision = unitIndex === 0 ? 0 : unitIndex === 1 ? 1 : 2;
  return `${value.toFixed(precision)} ${units[unitIndex]}`;
}

async function getDirectoryUsage(dir) {
  const stack = [dir];
  let sizeBytes = 0;
  let fileCount = 0;

  while (stack.length) {
    const current = stack.pop();
    let entries;
    try {
      entries = await fs.readdir(current, { withFileTypes: true });
    } catch (error) {
      if (error && error.code === 'ENOENT') {
        continue;
      }
      throw error;
    }

    for (const entry of entries) {
      if (entry.isSymbolicLink && entry.isSymbolicLink()) {
        continue;
      }

      const fullPath = path.join(current, entry.name);
      if (entry.isDirectory()) {
        stack.push(fullPath);
        continue;
      }

      if (!entry.isFile()) {
        continue;
      }

      try {
        const stats = await fs.stat(fullPath);
        sizeBytes += stats.size;
        fileCount += 1;
      } catch (error) {
        console.warn('Unable to measure file size for directory usage', fullPath, error);
      }
    }
  }

  return { sizeBytes, fileCount };
}

function shouldTrackFile(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  return FILE_TRACK_EXTENSIONS.has(ext);
}

function categorizeFileBroadcast(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  if (FILE_AUDIO_EXTENSIONS.has(ext)) return 'audio';
  if (FILE_VIDEO_EXTENSIONS.has(ext)) return 'video';
  if (FILE_IMAGE_EXTENSIONS.has(ext)) return 'image';
  if (FILE_DOCUMENT_EXTENSIONS.has(ext)) return 'document';
  if (FILE_SCRIPT_EXTENSIONS.has(ext)) return 'script';
  if (FILE_ARCHIVE_EXTENSIONS.has(ext)) return 'archive';
  if (ext === '.json') return 'data';
  if (ext === '.css') return 'stylesheet';
  return ext ? ext.replace('.', '') : 'asset';
}

async function collectTrackableFiles(dir, root = dir, results = []) {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.name.startsWith('.')) {
      if (entry.isDirectory()) {
        if (entry.name === '.well-known') {
          // allow .well-known directories to pass through
        } else {
          continue;
        }
      } else {
        continue;
      }
    }
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (FILE_BROADCAST_IGNORE_DIRS.has(entry.name)) {
        continue;
      }
      await collectTrackableFiles(fullPath, root, results);
    } else if (entry.isFile() && shouldTrackFile(fullPath)) {
      let stats;
      try {
        stats = await fs.stat(fullPath);
      } catch (error) {
        console.warn('Unable to stat file for broadcast tracking', fullPath, error);
        continue;
      }
      results.push({
        path: fullPath,
        relPath: path.relative(root, fullPath).split(path.sep).join('/'),
        size: stats.size,
        modifiedAt: new Date(stats.mtimeMs).toISOString()
      });
    }
  }
  return results;
}

let lastFileBroadcastScan = 0;

async function syncFileBroadcasts(options = {}) {
  const { force = false } = options || {};
  const now = Date.now();
  if (!force && now - lastFileBroadcastScan < FILE_BROADCAST_SCAN_INTERVAL_MS) {
    return false;
  }

  let files = [];
  try {
    files = await collectTrackableFiles(FILE_BROADCAST_ROOT, FILE_BROADCAST_ROOT, []);
  } catch (error) {
    console.error('Failed to enumerate broadcast files', error);
    files = [];
  }
  lastFileBroadcastScan = Date.now();

  if (!Array.isArray(store.fileBroadcasts)) {
    store.fileBroadcasts = [];
  }

  const existingByPath = new Map();
  for (const entry of store.fileBroadcasts) {
    if (entry && typeof entry.path === 'string') {
      existingByPath.set(entry.path, entry);
    }
  }

  const seenIds = new Set();
  let changed = false;
  const timestamp = new Date().toISOString();

  for (const file of files) {
    const relPath = file.relPath;
    const existing = existingByPath.get(relPath);
    if (!existing) {
      const record = {
        id: randomUUID(),
        path: relPath,
        displayName: path.basename(relPath),
        category: categorizeFileBroadcast(relPath),
        status: 'active',
        lastEvent: 'discovered',
        createdAt: timestamp,
        updatedAt: timestamp,
        indexedAt: timestamp,
        fileSize: file.size,
        modifiedAt: file.modifiedAt,
        removedAt: null
      };
      store.fileBroadcasts.push(record);
      existingByPath.set(relPath, record);
      seenIds.add(record.id);
      changed = true;
      continue;
    }

    if (!existing.id) {
      existing.id = randomUUID();
      changed = true;
    }

    const sizeChanged = existing.fileSize !== file.size;
    const modifiedChanged = existing.modifiedAt !== file.modifiedAt;
    const statusChanged = existing.status === 'removed';

    if (sizeChanged || modifiedChanged || statusChanged) {
      existing.fileSize = file.size;
      existing.modifiedAt = file.modifiedAt;
      existing.updatedAt = timestamp;
      existing.status = 'active';
      existing.lastEvent = statusChanged ? 'restored' : 'updated';
      if (!existing.createdAt) {
        existing.createdAt = timestamp;
      }
      changed = true;
    }

    if (!existing.indexedAt) {
      existing.indexedAt = existing.createdAt || timestamp;
    }
    if (!existing.displayName) {
      existing.displayName = path.basename(relPath);
    }
    const category = categorizeFileBroadcast(relPath);
    if (existing.category !== category) {
      existing.category = category;
      changed = true;
    }

    seenIds.add(existing.id);
  }

  for (const entry of store.fileBroadcasts) {
    if (!entry) {
      continue;
    }
    if (!entry.id) {
      entry.id = randomUUID();
      changed = true;
    }
    if (!seenIds.has(entry.id) && entry.status !== 'removed') {
      entry.status = 'removed';
      entry.lastEvent = 'removed';
      entry.updatedAt = timestamp;
      entry.removedAt = timestamp;
      changed = true;
    }
  }

  if (changed) {
    try {
      await saveStore();
    } catch (error) {
      console.error('Failed to persist file broadcast updates', error);
    }
  }

  return changed;
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

function sanitizeSelectionsForStorage(value) {
  if (value == null) {
    return null;
  }
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) {
      return null;
    }
    try {
      const parsed = JSON.parse(trimmed);
      return JSON.stringify(parsed);
    } catch {
      return trimmed;
    }
  }
  try {
    return JSON.stringify(value);
  } catch {
    return normalizeForStorage(value);
  }
}

function stableStringify(value) {
  if (value === null || value === undefined) {
    return 'null';
  }
  if (typeof value === 'string') {
    return JSON.stringify(value);
  }
  if (typeof value === 'number') {
    return Number.isFinite(value) ? String(value) : JSON.stringify(String(value));
  }
  if (typeof value === 'boolean') {
    return value ? 'true' : 'false';
  }
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableStringify(item)).join(',')}]`;
  }
  if (typeof value === 'object') {
    const keys = Object.keys(value).sort();
    const serialized = keys.map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`);
    return `{${serialized.join(',')}}`;
  }
  return JSON.stringify(String(value));
}

function computeTreasuryHash(value) {
  try {
    const normalized = stableStringify(value);
    return createHash('sha256').update(normalized).digest('hex');
  } catch (error) {
    console.error('Failed to compute treasury hash', error);
    return null;
  }
}

function sanitizeUrl(value) {
  if (typeof value !== 'string') {
    return null;
  }
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  if (trimmed.startsWith('ipfs://')) {
    return trimmed;
  }
  try {
    const url = new URL(trimmed);
    if (url.protocol === 'http:' || url.protocol === 'https:') {
      return url.toString();
    }
  } catch (error) {
    return null;
  }
  return null;
}

function parseCurrencyAmount(raw) {
  if (typeof raw === 'number') {
    return Number.isFinite(raw) ? raw : 0;
  }
  if (typeof raw === 'string') {
    const normalized = raw.replace(/[^0-9.\-]/g, '');
    if (!normalized) {
      return 0;
    }
    const value = Number.parseFloat(normalized);
    return Number.isFinite(value) ? value : 0;
  }
  return 0;
}

function toTimestamp(value) {
  if (!value) {
    return 0;
  }
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}

function sortByTimestampDesc(collection, primaryKey = 'createdAt', fallbackKey = null) {
  return collection
    .slice()
    .sort(
      (a, b) =>
        toTimestamp(b?.[primaryKey] || (fallbackKey ? b?.[fallbackKey] : null)) -
        toTimestamp(a?.[primaryKey] || (fallbackKey ? a?.[fallbackKey] : null))
    );
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
      metadata: normalizeForStorage(event.metadata),
      ipAddress: normalizeForStorage(event.ipAddress)
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
  const createdAt = new Date().toISOString();
  const selectionsValue = Array.isArray(submission.selections) ? submission.selections : [];
  const record = {
    createdAt,
    role: normalizeForStorage(submission.role),
    name: normalizeForStorage(submission.name),
    email: normalizeForStorage(submission.email),
    selections: serializeMetadata(selectionsValue),
    databaseOptIn: submission.databaseOptIn ? 1 : 0,
    userAgent: normalizeForStorage(submission.userAgent),
    referer: normalizeForStorage(submission.referer),
    ipAddress: normalizeForStorage(submission.ipAddress)
  };

  let entryId = null;

  if (submission.databaseOptIn) {
    entryId = randomUUID();
    store.gatewayUsers[entryId] = {
      role: record.role,
      name: record.name,
      email: record.email,
      selections: record.selections,
      databaseOptIn: 1,
      createdAt,
      updatedAt: createdAt
    };
  }

  try {
    store.gatewaySubmissions.push({ ...record, entryId });
    await saveStore();
    return { success: true, entryId };
  } catch (err) {
    if (entryId) {
      delete store.gatewayUsers[entryId];
    }
    console.error('Failed to record gateway submission', err);
    return { success: false, error: err };
  }
}

async function persistMarketplaceUpload(record) {
  try {
    if (!Array.isArray(store.marketplaceUploads)) {
      store.marketplaceUploads = [];
    }
    store.marketplaceUploads.push(record);
    await saveStore();
    return record;
  } catch (error) {
    console.error('Failed to store marketplace upload', error);
    throw error;
  }
}

async function persistMarketplaceBid(record, assetId) {
  try {
    if (!Array.isArray(store.marketplaceBids)) {
      store.marketplaceBids = [];
    }
    store.marketplaceBids.push(record);
    if (Array.isArray(store.marketplaceUploads)) {
      const target = store.marketplaceUploads.find((upload) => upload.id === assetId);
      if (target) {
        target.lastBidAt = record.createdAt;
        target.updatedAt = record.createdAt;
      }
    }
    await saveStore();
    return record;
  } catch (error) {
    console.error('Failed to store marketplace bid', error);
    throw error;
  }
}

function maskCardNumber(cardNumber) {
  if (typeof cardNumber !== 'string') {
    return null;
  }
  const digitsOnly = cardNumber.replace(/\D+/g, '');
  if (digitsOnly.length < 4) {
    return null;
  }
  const last4 = digitsOnly.slice(-4);
  return `${'•'.repeat(Math.max(digitsOnly.length - 4, 0))}${last4}`;
}

function validateLuhn(cardNumber) {
  if (typeof cardNumber !== 'string') {
    return false;
  }
  const digits = cardNumber.replace(/\D+/g, '');
  if (!digits) {
    return false;
  }

  let sum = 0;
  let doubleDigit = false;

  for (let i = digits.length - 1; i >= 0; i -= 1) {
    let value = Number.parseInt(digits[i], 10);
    if (Number.isNaN(value)) {
      return false;
    }
    if (doubleDigit) {
      value *= 2;
      if (value > 9) {
        value -= 9;
      }
    }
    sum += value;
    doubleDigit = !doubleDigit;
  }

  return sum % 10 === 0;
}

async function recordMagstripeTransaction(transaction) {
  try {
    const entryId = transaction.transactionId || randomUUID();
    const createdAt = new Date().toISOString();
    const record = {
      createdAt,
      entryId,
      transactionId: entryId,
      cardholder: normalizeForStorage(transaction.cardholder),
      maskedCardNumber: normalizeForStorage(transaction.maskedCardNumber),
      amount: transaction.amount,
      currency: transaction.currency,
      projectReference: normalizeForStorage(transaction.projectReference),
      authorizationCode: normalizeForStorage(transaction.authorizationCode),
      status: normalizeForStorage(transaction.status),
      processor: normalizeForStorage(transaction.processor),
      ipAddress: normalizeForStorage(transaction.ipAddress)
    };

    record.ledgerHash = computeTreasuryHash({
      createdAt: record.createdAt,
      transactionId: record.transactionId,
      cardholder: record.cardholder,
      maskedCardNumber: record.maskedCardNumber,
      amount: record.amount,
      currency: record.currency,
      projectReference: record.projectReference,
      authorizationCode: record.authorizationCode,
      processor: record.processor,
      ipAddress: record.ipAddress
    });

    store.magstripeTransactions.push(record);
    await saveStore();
  } catch (error) {
    console.error('Failed to store magnetic stripe transaction', error);
    throw error;
  }
}

function parseBtcAmount(amountRaw) {
  if (typeof amountRaw === 'number') {
    return amountRaw;
  }
  if (typeof amountRaw === 'string') {
    const normalized = amountRaw.replace(/[^0-9.\-]/g, '');
    if (!normalized) {
      return 0;
    }
    return Number.parseFloat(normalized);
  }
  return 0;
}

function generateBitcoinInvoiceId() {
  const timestamp = Date.now().toString(36).toUpperCase();
  const randomChunk = Math.floor(Math.random() * 46656)
    .toString(36)
    .toUpperCase()
    .padStart(3, '0');
  return `BTC-${timestamp}-${randomChunk}`;
}

async function recordBitcoinTransaction(transaction) {
  try {
    const entryId = transaction.invoiceId || randomUUID();
    const createdAt = new Date().toISOString();
    const btcAmount =
      typeof transaction.btcAmount === 'number' && Number.isFinite(transaction.btcAmount)
        ? Number(transaction.btcAmount.toFixed(8))
        : null;
    const usdAmount =
      typeof transaction.usdAmount === 'number' && Number.isFinite(transaction.usdAmount)
        ? Number(transaction.usdAmount.toFixed(2))
        : null;

    const record = {
      createdAt,
      entryId,
      invoiceId: entryId,
      cardholder: normalizeForStorage(transaction.cardholder),
      btcAddress: normalizeForStorage(transaction.btcAddress || BITCOIN_ADDRESS),
      btcAmount,
      usdAmount,
      transactionId: normalizeForStorage(transaction.transactionId),
      remittingContact: normalizeForStorage(transaction.remittingContact),
      projectReference: normalizeForStorage(transaction.projectReference),
      status:
        normalizeForStorage(transaction.status) || (transaction.transactionId ? 'pending-confirmation' : 'awaiting-txid'),
      confirmationsRequired: BITCOIN_CONFIRMATIONS_REQUIRED,
      settlementWindowMinutes: BITCOIN_SETTLEMENT_WINDOW_MINUTES,
      ipAddress: normalizeForStorage(transaction.ipAddress)
    };

    record.ledgerHash = computeTreasuryHash({
      createdAt: record.createdAt,
      invoiceId: record.invoiceId,
      cardholder: record.cardholder,
      btcAddress: record.btcAddress,
      btcAmount: record.btcAmount,
      usdAmount: record.usdAmount,
      transactionId: record.transactionId,
      projectReference: record.projectReference,
      status: record.status,
      ipAddress: record.ipAddress
    });

    store.bitcoinTransactions.push(record);
    await saveStore();
  } catch (error) {
    console.error('Failed to store bitcoin transaction', error);
    throw error;
  }
}

async function recordChatLedgerEntry(entry) {
  try {
    if (!Array.isArray(store.chatServerLedger)) {
      store.chatServerLedger = [];
    }

    const nowIso = new Date().toISOString();
    const ledgerId = normalizeForStorage(entry.ledgerId) || normalizeForStorage(entry.messageId) || randomUUID();
    const createdAt = entry.createdAt && !Number.isNaN(Date.parse(entry.createdAt))
      ? new Date(entry.createdAt).toISOString()
      : nowIso;
    const message = typeof entry.message === 'string' ? entry.message.slice(0, 800) : '';
    const sanitizedMessage = normalizeForStorage(message);

    const payload = {
      createdAt,
      updatedAt: nowIso,
      ledgerId,
      messageId: ledgerId,
      server: normalizeForStorage(entry.server) || 'Ioncore Live Forum',
      room: normalizeForStorage(entry.room),
      user: normalizeForStorage(entry.user),
      message: sanitizedMessage,
      broadcast: entry.broadcast ? 1 : 0,
      isAction: entry.isAction ? 1 : 0,
      hasAttachment: entry.hasAttachment ? 1 : 0,
      attachmentName: normalizeForStorage(entry.attachmentName || entry.fileName),
      attachmentType: normalizeForStorage(entry.attachmentType || entry.fileType),
      transport: normalizeForStorage(entry.transport),
      clientId: normalizeForStorage(entry.clientId),
      status: normalizeForStorage(entry.status) || 'recorded',
      likes: Number.isFinite(entry.likes) ? Number(entry.likes) : null,
      commentCount: Number.isFinite(entry.commentCount) ? Number(entry.commentCount) : null,
      region: normalizeForStorage(entry.region || entry.cluster || entry.shard),
      activeSessions: Number.isFinite(entry.activeSessions) ? Number(entry.activeSessions) : null,
      ipAddress: normalizeForStorage(entry.ipAddress)
    };

    payload.ledgerHash = computeTreasuryHash({
      createdAt: payload.createdAt,
      ledgerId: payload.ledgerId,
      room: payload.room,
      user: payload.user,
      message: payload.message,
      transport: payload.transport,
      status: payload.status,
      ipAddress: payload.ipAddress
    });

    const existingIndex = store.chatServerLedger.findIndex((item) => item && item.ledgerId === payload.ledgerId);
    if (existingIndex >= 0) {
      store.chatServerLedger[existingIndex] = {
        ...store.chatServerLedger[existingIndex],
        ...payload,
        updatedAt: nowIso
      };
      await saveStore();
      return { created: false, entry: store.chatServerLedger[existingIndex] };
    }

    store.chatServerLedger.push(payload);
    await saveStore();
    return { created: true, entry: payload };
  } catch (error) {
    console.error('Failed to store chat ledger event', error);
    throw error;
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

const AUTH_USER = process.env.BASIC_AUTH_USER || 'guest';
const AUTH_PASS = process.env.BASIC_AUTH_PASS || 'boots';

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

app.post('/login', async (req, res) => {
  const body = req.body && typeof req.body === 'object' ? req.body : {};
  const username = typeof body.username === 'string' ? body.username.trim() : '';
  const password = typeof body.password === 'string' ? body.password : '';
  const walletAddress = typeof body.walletAddress === 'string' ? body.walletAddress.trim() : '';
  const walletProvider = typeof body.walletProvider === 'string' ? body.walletProvider.trim() : '';
  const meknxPassId = typeof body.meknxPassId === 'string' ? body.meknxPassId.trim() : '';
  let nextPath = typeof body.next === 'string' ? body.next : '/webpage.html';

  if (!nextPath.startsWith('/') || nextPath.startsWith('//')) {
    nextPath = '/webpage.html';
  }

  const method = walletAddress
    ? 'wallet'
    : !username && meknxPassId && !password
      ? 'meknx'
      : 'credentials';

  const metadataBase = {
    nextPath,
    meknxStatus: body.meknxStatus,
    meknxMintedAt: body.meknxMintedAt,
    ioncTokens: body.ioncTokens,
    ioncVerified: body.ioncVerified,
    cardanoPolicyVerified: body.cardanoPolicyVerified,
    cardanoPolicyId: body.cardanoPolicyId
  };
  const metadata = serializeMetadata(metadataBase);

  const recordFailure = async (message, statusCode = 401) => {
    await recordLoginEvent({
      method,
      username,
      walletAddress,
      walletProvider,
      meknxPassId,
      success: false,
      metadata,
      ipAddress: req.ip
    });
    clearSessionCookie(res);
    return res
      .status(statusCode)
      .json({ message: message || 'Access denied. Invalid clearance credentials.' });
  };

  if (method === 'credentials') {
    if (username === AUTH_USER && password === AUTH_PASS) {
      await recordLoginEvent({
        method,
        username,
        walletAddress,
        walletProvider,
        meknxPassId,
        success: true,
        metadata,
        ipAddress: req.ip
      });
      const sessionId = createAuthSession();
      setSessionCookie(res, sessionId);
      return res.json({ redirect: nextPath });
    }
    return recordFailure();
  }

  if (method === 'wallet') {
    if (!walletAddress) {
      return recordFailure('Wallet session required for clearance validation. Connect a wallet and retry.');
    }

    if (!meknxPassId) {
      return recordFailure('MEKNX clearance token required for wallet entry. Verify your pass before continuing.');
    }

    const meknxRecord = meknxRegistry.get(walletAddress);
    const normalizedProvider = walletProvider
      ? normalizeProvider(walletProvider)
      : normalizeProvider(meknxRecord?.walletProvider || '');

    if (!meknxRecord) {
      return recordFailure(
        'No MEKNX clearance found for this wallet. Mint or verify a MEKNX pass before requesting entry.',
        403
      );
    }

    if (meknxRecord.passId && meknxRecord.passId !== meknxPassId) {
      return recordFailure('MEKNX pass mismatch detected. Re-verify your clearance token and try again.', 409);
    }

    if (!meknxRecord.passId) {
      return recordFailure('MEKNX clearance token not yet minted for this wallet. Complete minting first.', 403);
    }

    const meknxStatusRaw = typeof body.meknxStatus === 'string' ? body.meknxStatus.trim().toLowerCase() : '';
    const meknxStatus =
      meknxStatusRaw === 'verified' || meknxStatusRaw === 'minted'
        ? meknxStatusRaw
        : meknxRecord.lastVerifiedAt
        ? 'verified'
        : 'minted';

    const hasRecentVerification = Boolean(meknxRecord.lastVerifiedAt || meknxRecord.mintedAt);
    if (!hasRecentVerification) {
      return recordFailure('MEKNX clearance has not been verified recently. Re-run the MEKNX gate.', 403);
    }

    if (normalizedProvider === 'solana') {
      const ioncVerified =
        body.ioncVerified === true ||
        body.ioncVerified === 'true' ||
        body.ioncVerified === 1 ||
        body.ioncVerified === '1';
      const ioncTokens = Number.isFinite(body.ioncTokens) ? body.ioncTokens : Number(body.ioncTokens || 0);
      const recordedTokens = Number.isFinite(meknxRecord.ioncTokens) ? meknxRecord.ioncTokens : 0;
      if (!ioncVerified && (!ioncTokens || ioncTokens < 1)) {
        return recordFailure('IONC verification required for Solana sessions. Confirm token holdings before entry.', 403);
      }
      if (!recordedTokens || recordedTokens < 1) {
        return recordFailure('IONC access tokens not detected for this wallet. Mint or refresh MEKNX clearance first.', 403);
      }
    }

    if (normalizedProvider === 'cardano') {
      const policyVerified =
        body.cardanoPolicyVerified === true ||
        body.cardanoPolicyVerified === 'true' ||
        body.cardanoPolicyVerified === 1 ||
        body.cardanoPolicyVerified === '1';
      if (!policyVerified) {
        return recordFailure('Cardano policy verification required before entry. Confirm the policy and retry.', 403);
      }
      if (!meknxRecord.cardanoPolicyVerified || !meknxRecord.cardanoPolicyId) {
        return recordFailure('Cardano policy not confirmed for this wallet. Complete policy verification and try again.', 403);
      }
      if (CARDANO_POLICY_ID && meknxRecord.cardanoPolicyId) {
        const expectedPolicy = CARDANO_POLICY_ID.toLowerCase();
        const recordedPolicy = meknxRecord.cardanoPolicyId.toLowerCase();
        if (expectedPolicy && recordedPolicy !== expectedPolicy) {
          return recordFailure('Recorded Cardano policy does not match the required asset. Re-verify the policy.', 403);
        }
      }
    }

    meknxRecord.walletProvider = normalizedProvider;
    meknxRecord.lastLoginAt = new Date().toISOString();
    meknxRegistry.set(walletAddress, meknxRecord);

    const walletMetadata = serializeMetadata({
      ...metadataBase,
      walletLogin: {
        provider: normalizedProvider,
        meknxStatus,
        meknxPassId,
        meknxLastVerifiedAt: meknxRecord.lastVerifiedAt || null,
        meknxMintedAt: meknxRecord.mintedAt || null,
        ioncTokens: meknxRecord.ioncTokens || 0,
        cardanoPolicyVerified: Boolean(meknxRecord.cardanoPolicyVerified),
        cardanoPolicyId: meknxRecord.cardanoPolicyId || null
      }
    });

    await recordLoginEvent({
      method,
      username,
      walletAddress,
      walletProvider: normalizedProvider,
      meknxPassId,
      success: true,
      metadata: walletMetadata,
      ipAddress: req.ip
    });

    const sessionId = createAuthSession();
    setSessionCookie(res, sessionId);

    return res.json({
      redirect: nextPath,
      wallet: {
        address: walletAddress,
        provider: normalizedProvider,
        meknxPassId: meknxRecord.passId,
        meknxStatus,
        mintedAt: meknxRecord.mintedAt || null,
        lastVerifiedAt: meknxRecord.lastVerifiedAt || null,
        ioncTokens: meknxRecord.ioncTokens || 0,
        cardanoPolicyVerified: Boolean(meknxRecord.cardanoPolicyVerified),
        cardanoPolicyId: meknxRecord.cardanoPolicyId || null
      }
    });
  }

  if (method === 'meknx') {
    if (!isThirdwebConfigured()) {
      return recordFailure(
        'MEKNX verification temporarily offline. Contact support for clearance.',
        503
      );
    }

    try {
      const verification = await executeMeknxGate({
        passId: meknxPassId,
        walletAddress
      });

      if (!verification.authorized) {
        const failureMessage =
          verification.message || 'MEKNX contract denied this clearance request.';
        return recordFailure(failureMessage, 403);
      }

      const enrichedMetadata = serializeMetadata({
        ...metadataBase,
        meknxContract: {
          authorized: verification.authorized,
          message: verification.message,
          contractAddress: verification.contractAddress,
          method: verification.method,
          params: verification.params,
          rawResult: verification.rawResult
        }
      });

      await recordLoginEvent({
        method,
        username,
        walletAddress,
        walletProvider,
        meknxPassId,
        success: true,
        metadata: enrichedMetadata,
        ipAddress: req.ip
      });

      const sessionId = createAuthSession();
      setSessionCookie(res, sessionId);

      return res.json({
        redirect: nextPath,
        meknx: {
          authorized: verification.authorized,
          message: verification.message,
          contractAddress: verification.contractAddress,
          method: verification.method,
          params: verification.params
        }
      });
    } catch (error) {
      const failureMessage =
        error && typeof error.message === 'string'
          ? error.message
          : 'MEKNX contract verification failed. Try again shortly.';
      return recordFailure(failureMessage, 502);
    }
  }

  return recordFailure(
    method === 'wallet'
      ? 'Wallet verification not yet provisioned for automated vault entry.'
      : 'MEKNX verification not yet provisioned for automated vault entry.'
  );
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
  const streamsRaw = body.streams;
  const databaseOptInRaw = body.databaseOptIn;

  const roleLabels = new Map([
    ['investor', 'Investor'],
    ['buyer', 'Industrial buyer'],
    ['team', 'Ioncore team']
  ]);

  if (!roleLabels.has(role)) {
    return res
      .status(400)
      .json({ message: 'Select the access profile that best represents your relationship with Ioncore Energy.' });
  }

  if (!name) {
    return res.status(400).json({ message: 'Enter your full name to continue.' });
  }

  const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  let email = '';
  if (emailRaw) {
    if (!emailPattern.test(emailRaw)) {
      return res.status(400).json({ message: 'Provide a valid work email address or leave the field blank.' });
    }
    email = emailRaw.toLowerCase();
  }

  const streamOptions = new Map([
    ['investor-dossier', 'Investor dossiers'],
    ['industrial-playbooks', 'Industrial deployment playbooks'],
    ['team-ops', 'Operations alignment']
  ]);

  const streamValues = Array.isArray(streamsRaw) ? streamsRaw : streamsRaw ? [streamsRaw] : [];
  const normalizedStreams = Array.from(
    new Set(
      streamValues
        .map((value) => (typeof value === 'string' ? value.trim().toLowerCase() : ''))
        .filter((value) => value && streamOptions.has(value))
    )
  );

  if (normalizedStreams.length === 0) {
    return res.status(400).json({ message: 'Select at least one access toggle to continue.' });
  }

  const databaseOptIn =
    databaseOptInRaw === true ||
    databaseOptInRaw === 'true' ||
    databaseOptInRaw === 'yes' ||
    databaseOptInRaw === 'on' ||
    databaseOptInRaw === '1';

  const submission = {
    role,
    name,
    email,
    selections: normalizedStreams,
    databaseOptIn,
    userAgent: req.get('user-agent'),
    referer: req.get('referer'),
    ipAddress: req.ip
  };

  const stored = await recordGatewaySubmission(submission);

  if (!stored || !stored.success) {
    return res
      .status(500)
      .json({ message: 'We were unable to record your access request. Please try again shortly.' });
  }

  const expiresAt = new Date(Date.now() + COOKIE_MAX_AGE_MS).toISOString();
  const readableSelections = normalizedStreams.map((value) => streamOptions.get(value));
  const message = `${roleLabels.get(role)} preferences saved. Redirecting to brochure.`;

  return res.status(201).json({
    message,
    entryId: stored.entryId || '',
    selections: readableSelections,
    delayMs: 1400,
    expiresAt
  });
});

app.get('/api/payments/bitcoin/config', (req, res) => {
  res.json({
    btcAddress: BITCOIN_ADDRESS,
    confirmationsRequired: BITCOIN_CONFIRMATIONS_REQUIRED,
    settlementWindowMinutes: BITCOIN_SETTLEMENT_WINDOW_MINUTES
  });
});

app.post('/payments/bitcoin', async (req, res) => {
  const body = req.body && typeof req.body === 'object' ? req.body : {};
  const cardholder = typeof body.cardholder === 'string' ? body.cardholder.trim() : '';
  const btcWalletRaw = typeof body.btcWallet === 'string' ? body.btcWallet.trim() : '';
  const btcAmountRaw = body.btcAmount;
  const usdAmountRaw = body.amount;
  const projectReference = typeof body.projectReference === 'string' ? body.projectReference.trim() : '';
  const transactionIdRaw = typeof body.transactionId === 'string' ? body.transactionId.trim() : '';
  const remittingContact = typeof body.remittingContact === 'string' ? body.remittingContact.trim() : '';

  if (cardholder.length < 2) {
    return res.status(400).json({ message: 'Customer name required to register the bitcoin payment.' });
  }

  const btcAddress = btcWalletRaw || BITCOIN_ADDRESS;
  if (BITCOIN_ADDRESS && btcAddress !== BITCOIN_ADDRESS) {
    return res.status(400).json({ message: 'Use the designated Ioncore settlement address for bitcoin remittance.' });
  }

  const btcAmount = parseBtcAmount(btcAmountRaw);
  if (!Number.isFinite(btcAmount) || btcAmount <= 0) {
    return res.status(400).json({ message: 'Enter the bitcoin amount being remitted on-chain.' });
  }
  if (btcAmount > 21_000_000) {
    return res.status(400).json({ message: 'Bitcoin amount exceeds the valid range.' });
  }

  let usdAmount = 0;
  if (typeof usdAmountRaw === 'number') {
    usdAmount = usdAmountRaw;
  } else if (typeof usdAmountRaw === 'string') {
    usdAmount = Number.parseFloat(usdAmountRaw.replace(/[^0-9.\-]/g, ''));
  }

  if (!Number.isFinite(usdAmount) || usdAmount <= 0) {
    return res.status(400).json({ message: 'Enter the USD invoice amount linked to this bitcoin transfer.' });
  }

  const txIdPattern = /^[0-9a-fA-F]{10,}$/;
  const transactionId = transactionIdRaw;
  if (transactionId && !txIdPattern.test(transactionId)) {
    return res.status(400).json({ message: 'Provide a valid bitcoin transaction ID or leave the field blank until broadcast.' });
  }

  const invoiceId = generateBitcoinInvoiceId();
  const settlementEta = `~${BITCOIN_SETTLEMENT_WINDOW_MINUTES} minutes after ${BITCOIN_CONFIRMATIONS_REQUIRED} confirmation${
    BITCOIN_CONFIRMATIONS_REQUIRED === 1 ? '' : 's'
  }`;

  try {
    await recordBitcoinTransaction({
      invoiceId,
      cardholder,
      btcAddress,
      btcAmount,
      usdAmount,
      transactionId,
      remittingContact,
      projectReference,
      status: transactionId ? 'pending-confirmation' : 'awaiting-txid',
      ipAddress: req.ip
    });
  } catch (error) {
    return res
      .status(502)
      .json({ message: 'We could not register the bitcoin payment. Verify the details or retry shortly.' });
  }

  return res.status(201).json({
    message: 'Bitcoin payment logged. Awaiting network confirmations.',
    invoiceId,
    btcAddress: BITCOIN_ADDRESS,
    btcAmount: Number(btcAmount.toFixed(8)),
    amount: Number(usdAmount.toFixed(2)),
    currency: 'USD',
    transactionId: transactionId || undefined,
    settlementEta,
    remittingContact: remittingContact || undefined,
    explorerUrl: transactionId ? `https://mempool.space/tx/${transactionId}` : undefined,
    projectReference: projectReference || undefined
  });
});

app.post('/payments/magnetic-stripe', async (req, res) => {
  const body = req.body && typeof req.body === 'object' ? req.body : {};
  const cardholder = typeof body.cardholder === 'string' ? body.cardholder.trim() : '';
  const cardNumber = typeof body.cardNumber === 'string' ? body.cardNumber.trim() : '';
  const expiryRaw = typeof body.expiry === 'string' ? body.expiry.trim() : '';
  const cvv = typeof body.cvv === 'string' ? body.cvv.trim() : '';
  const amountRaw = body.amount;
  const projectReference = typeof body.projectReference === 'string' ? body.projectReference.trim() : '';

  if (cardholder.length < 2) {
    return res.status(400).json({ message: 'Cardholder name is required to authorize this transaction.' });
  }

  const normalizedCardDigits = typeof cardNumber === 'string' ? cardNumber.replace(/\D+/g, '') : '';
  if (normalizedCardDigits.length < 12 || normalizedCardDigits.length > 19 || !validateLuhn(cardNumber)) {
    return res.status(400).json({ message: 'Enter a valid magnetic stripe account number before submitting.' });
  }

  const expiryValue = expiryRaw.replace(/\s+/g, '');
  const expiryMatch = /^(0[1-9]|1[0-2])\/?(\d{2}|\d{4})$/.exec(expiryValue);
  if (!expiryMatch) {
    return res.status(400).json({ message: 'Provide the card expiration in MM/YY format.' });
  }

  const expiryMonth = Number.parseInt(expiryMatch[1], 10);
  let expiryYear = Number.parseInt(expiryMatch[2], 10);
  if (expiryMatch[2].length === 2) {
    expiryYear += expiryYear >= 70 ? 1900 : 2000;
  }
  const expirationBoundary = new Date(expiryYear, expiryMonth, 1);
  const now = new Date();
  if (expirationBoundary <= now) {
    return res.status(400).json({ message: 'This card is expired. Request an alternate payment method.' });
  }

  const cvvDigits = cvv.replace(/\D+/g, '');
  if (cvvDigits.length < 3 || cvvDigits.length > 4) {
    return res.status(400).json({ message: 'Security code must contain 3 or 4 digits.' });
  }

  let amount = 0;
  if (typeof amountRaw === 'number') {
    amount = amountRaw;
  } else if (typeof amountRaw === 'string') {
    amount = Number.parseFloat(amountRaw.replace(/[^0-9.\-]/g, ''));
  }

  if (!Number.isFinite(amount) || amount <= 0) {
    return res.status(400).json({ message: 'Enter a positive charge amount in USD.' });
  }

  const maskedCardNumber = maskCardNumber(cardNumber);
  const authorizationCode = Math.floor(100000 + Math.random() * 900000).toString();
  const transactionId = randomUUID();

  try {
    await recordMagstripeTransaction({
      cardholder,
      maskedCardNumber,
      amount: Number(amount.toFixed(2)),
      currency: 'USD',
      projectReference,
      authorizationCode,
      status: 'authorized',
      processor: 'ioncore-magnetic-stripe',
      transactionId,
      ipAddress: req.ip
    });
  } catch (error) {
    return res
      .status(502)
      .json({ message: 'We could not finalize the authorization. Try again shortly or escalate to support.' });
  }

  return res.status(201).json({
    message: 'Magstripe authorization approved and queued for settlement.',
    transactionId,
    authorizationCode,
    cardholder,
    maskedCardNumber,
    amount: Number(amount.toFixed(2)),
    currency: 'USD',
    projectReference,
    captureWindowHours: 24
  });
});

app.post('/api/chat/ledger', async (req, res) => {
  const body = req.body && typeof req.body === 'object' ? req.body : {};
  const messageIdRaw = typeof body.messageId === 'string' ? body.messageId.trim() : '';
  const textRaw = typeof body.text === 'string' ? body.text.trim() : '';
  const user = typeof body.user === 'string' ? body.user.trim() : '';
  const room = typeof body.room === 'string' ? body.room.trim() : '';
  const hasAttachment = Boolean(body.hasAttachment || body.fileName || body.fileType);

  if (!messageIdRaw) {
    return res.status(400).json({ message: 'Message reference required for ledger entry.' });
  }

  if (!textRaw && !hasAttachment) {
    return res.status(400).json({ message: 'Provide chat text or attachment metadata to log the event.' });
  }

  const entry = {
    ledgerId: messageIdRaw,
    messageId: messageIdRaw,
    message: textRaw,
    user,
    room,
    broadcast: body.broadcast === true,
    isAction: body.isAction === true,
    hasAttachment,
    fileName: typeof body.fileName === 'string' ? body.fileName.slice(0, 180) : null,
    fileType: typeof body.fileType === 'string' ? body.fileType.slice(0, 120) : null,
    createdAt: typeof body.createdAt === 'string' ? body.createdAt : null,
    transport: typeof body.transport === 'string' ? body.transport : null,
    clientId: typeof body.clientId === 'string' ? body.clientId : null,
    status: typeof body.status === 'string' ? body.status : 'recorded',
    likes: Number.isFinite(body.likes) ? Number(body.likes) : null,
    commentCount: Number.isFinite(body.commentCount) ? Number(body.commentCount) : null,
    region: typeof body.region === 'string' ? body.region : null,
    cluster: typeof body.cluster === 'string' ? body.cluster : null,
    shard: typeof body.shard === 'string' ? body.shard : null,
    activeSessions: Number.isFinite(body.activeSessions) ? Number(body.activeSessions) : null,
    server: typeof body.server === 'string' ? body.server : null
  };

  entry.ipAddress = req.ip;

  try {
    const result = await recordChatLedgerEntry(entry);
    res
      .status(result.created ? 201 : 200)
      .json({ message: result.created ? 'Chat message logged to ledger.' : 'Chat ledger entry refreshed.' });
  } catch (error) {
    res.status(502).json({ message: 'Unable to record chat ledger entry. Retry shortly.' });
  }
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

app.post('/api/marketplace/uploads', async (req, res) => {
  const body = req.body && typeof req.body === 'object' ? req.body : {};
  const title = normalizeForStorage(body.title);
  const username = normalizeForStorage(body.username || body.creator || body.handle);
  const walletAddress = normalizeForStorage(body.walletAddress || body.wallet);
  const description = normalizeForStorage(body.description || body.summary || body.notes);
  const contact = normalizeForStorage(body.contact || body.email || body.link);
  const mediaUrl = sanitizeUrl(typeof body.mediaUrl === 'string' ? body.mediaUrl : body.previewUrl);

  if (!title) {
    return res.status(400).json({ message: 'Provide a title or label for this marketplace upload.' });
  }

  const now = new Date().toISOString();
  const record = {
    id: randomUUID(),
    title,
    description,
    username,
    walletAddress,
    mediaUrl,
    contact,
    createdAt: now,
    updatedAt: now,
    lastBidAt: null
  };

  try {
    await persistMarketplaceUpload(record);
  } catch (error) {
    return res.status(500).json({ message: 'Unable to register the marketplace upload. Retry shortly.' });
  }

  res.status(201).json({
    ...record,
    bidCount: 0,
    highestBidAmount: null,
    highestBidCurrency: null
  });
});

app.post('/api/marketplace/bids', async (req, res) => {
  const body = req.body && typeof req.body === 'object' ? req.body : {};
  const assetIdRaw = typeof body.assetId === 'string' ? body.assetId.trim() : '';
  if (!assetIdRaw) {
    return res.status(400).json({ message: 'Specify the marketplace upload you are bidding on.' });
  }

  const uploads = Array.isArray(store.marketplaceUploads) ? store.marketplaceUploads : [];
  const asset = uploads.find((upload) => upload.id === assetIdRaw);
  if (!asset) {
    return res.status(404).json({ message: 'Marketplace upload not found. Refresh and try again.' });
  }

  const amount = parseCurrencyAmount(body.amount || body.bidAmount);
  if (!Number.isFinite(amount) || amount <= 0) {
    return res.status(400).json({ message: 'Enter a valid bid amount greater than zero.' });
  }

  if (amount > 1_000_000_000) {
    return res.status(400).json({ message: 'Bid amount exceeds the allowable range.' });
  }

  const currencyRaw = typeof body.currency === 'string' ? body.currency.trim().toUpperCase() : '';
  const currency = /^[A-Z]{2,6}$/.test(currencyRaw) ? currencyRaw : 'USD';
  const bidderName = normalizeForStorage(body.bidderName || body.username || body.name);
  const bidderWallet = normalizeForStorage(body.bidderWallet || body.walletAddress || body.wallet);
  const bidderContact = normalizeForStorage(body.contact || body.email || body.communicationHandle);
  const message = normalizeForStorage(body.message || body.notes || body.memo);

  const now = new Date().toISOString();
  const amountValue = Number(amount.toFixed(2));
  const record = {
    id: randomUUID(),
    assetId: assetIdRaw,
    amount: amountValue,
    currency,
    bidderName,
    bidderWallet,
    bidderContact,
    message,
    createdAt: now,
    updatedAt: now
  };

  try {
    await persistMarketplaceBid(record, assetIdRaw);
  } catch (error) {
    return res.status(500).json({ message: 'Unable to register the bid. Please try again shortly.' });
  }

  res.status(201).json({
    ...record,
    assetTitle: asset.title || null,
    assetOwner: asset.username || asset.walletAddress || null
  });
});

app.get('/api/marketplace', (req, res) => {
  const uploads = Array.isArray(store.marketplaceUploads) ? store.marketplaceUploads : [];
  const bids = Array.isArray(store.marketplaceBids) ? store.marketplaceBids : [];
  const bidLookup = new Map();

  for (const bid of bids) {
    if (!bidLookup.has(bid.assetId)) {
      bidLookup.set(bid.assetId, []);
    }
    bidLookup.get(bid.assetId).push(bid);
  }

  const orderedUploads = sortByTimestampDesc(uploads, 'updatedAt', 'createdAt').map((upload) => {
    const relatedBids = bidLookup.get(upload.id) || [];
    const highestBid = relatedBids.reduce((current, candidate) => {
      if (!candidate || typeof candidate.amount !== 'number') {
        return current;
      }
      if (!current) {
        return candidate;
      }
      return candidate.amount > current.amount ? candidate : current;
    }, null);

    return {
      id: upload.id,
      title: upload.title,
      description: upload.description,
      username: upload.username,
      walletAddress: upload.walletAddress,
      mediaUrl: upload.mediaUrl,
      contact: upload.contact,
      createdAt: upload.createdAt,
      updatedAt: upload.updatedAt,
      lastBidAt: upload.lastBidAt || null,
      bidCount: relatedBids.length,
      highestBidAmount: highestBid ? highestBid.amount : null,
      highestBidCurrency: highestBid ? highestBid.currency : null
    };
  });

  const uploadLookup = new Map(uploads.map((upload) => [upload.id, upload]));
  const orderedBids = sortByTimestampDesc(bids, 'createdAt').map((bid) => {
    const asset = uploadLookup.get(bid.assetId);
    return {
      id: bid.id,
      assetId: bid.assetId,
      amount: bid.amount,
      currency: bid.currency,
      bidderName: bid.bidderName,
      bidderWallet: bid.bidderWallet,
      bidderContact: bid.bidderContact,
      message: bid.message,
      createdAt: bid.createdAt,
      updatedAt: bid.updatedAt,
      assetTitle: asset?.title || null,
      assetOwner: asset?.username || asset?.walletAddress || null
    };
  });

  res.json({
    generatedAt: new Date().toISOString(),
    uploads: orderedUploads,
    bids: orderedBids
  });
});

function isPublicRoute(req) {
  const method = typeof req.method === 'string' ? req.method.toUpperCase() : 'GET';

  if (
    method === 'POST' &&
    [
      '/login',
      '/logout',
      '/access/meknx',
      '/access/ionc',
      '/access/cardano',
      '/contact',
      '/gateway',
      '/api/marketplace/uploads',
      '/api/marketplace/bids'
    ].includes(req.path)
  ) {
    return true;
  }

  const isReadOnlyRequest = method === 'GET' || method === 'HEAD';

  if (isReadOnlyRequest) {
    const publicHtml = new Set([
      '/login',
      '/login.html',
      '/',
      '/webpage.html',
      '/ioncore-contracting.html',
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

    const publicApis = new Set(['/api/marketplace']);
    if (publicApis.has(req.path)) {
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
  await sendHtml(res, path.join(__dirname, 'webpage-login.html'));
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
    let html = buffer.toString('utf8');
    if (!html.includes('admin.html')) {
      const closingTagMatch = html.match(/<\/body>/i);
      if (closingTagMatch) {
        html = html.replace(/<\/body>/i, `${ADMIN_PROMO_SECTION}</body>`);
      } else {
        html += ADMIN_PROMO_SECTION;
      }
    }
    html = injectSnippetBeforeBodyClose(html, TIMEPIECE_LOCK_OVERLAY, 'timepiece-lock-overlay');
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

app.get('/api/admin/overview', async (req, res) => {
  try {
    await syncFileBroadcasts();
  } catch (error) {
    console.error('File broadcast synchronization failed', error);
  }

  const gatewayUsers = Object.entries(store.gatewayUsers || {}).map(([id, user]) => ({ id, ...user }));
  const marketplaceUploads = Array.isArray(store.marketplaceUploads) ? store.marketplaceUploads : [];
  const marketplaceBids = Array.isArray(store.marketplaceBids) ? store.marketplaceBids : [];
  const timepieceMintLedger = Array.isArray(store.timepieceMintLedger) ? store.timepieceMintLedger : [];
  const fileBroadcasts = Array.isArray(store.fileBroadcasts) ? store.fileBroadcasts : [];
  const chatServerLedger = Array.isArray(store.chatServerLedger) ? store.chatServerLedger : [];
  const uploadMap = new Map(marketplaceUploads.map((upload) => [upload.id, upload]));

  let dataDirectoryUsage = { sizeBytes: 0, fileCount: 0 };
  try {
    dataDirectoryUsage = await getDirectoryUsage(DATA_DIR);
  } catch (error) {
    console.error('Unable to inspect data directory usage', error);
  }

  const uptimeSeconds = Math.max(0, Math.floor(process.uptime()));
  const startedAt = new Date(Date.now() - uptimeSeconds * 1000).toISOString();
  const lastBroadcastScan = lastFileBroadcastScan ? new Date(lastFileBroadcastScan).toISOString() : null;
  const backupSummary = await getBackupSummary();

  const serverStatus = {
    activeSessions: metrics.live,
    totalVisitors: metrics.viewed,
    uptimeSeconds,
    startedAt,
    host: {
      hostname: os.hostname(),
      platform: os.platform()
    },
    environment: {
      nodeVersion: process.version
    },
    process: {
      pid: process.pid,
      memory: process.memoryUsage()
    },
    dataStore: {
      path: path.relative(__dirname, DATA_DIR) || 'data',
      fileCount: dataDirectoryUsage.fileCount,
      sizeBytes: dataDirectoryUsage.sizeBytes
    },
    fileBroadcasts: {
      total: fileBroadcasts.length,
      lastScanCompletedAt: lastBroadcastScan
    },
    backups: backupSummary
  };

  const activityTimeline = [];

  for (const event of store.loginEvents) {
    activityTimeline.push({
      type: 'login',
      timestamp: event.createdAt,
      headline: event.username || event.walletAddress || 'Credential Access',
      detail: `${event.success ? 'Successful' : 'Failed'} ${event.method || 'login'} verification`,
      reference: event
    });
  }

  for (const submission of store.gatewaySubmissions) {
    activityTimeline.push({
      type: 'gateway-submission',
      timestamp: submission.updatedAt || submission.createdAt,
      headline: submission.name || submission.email || 'Gateway submission',
      detail: `Role: ${submission.role || 'Unspecified'} · Opt-in: ${submission.databaseOptIn ? 'Yes' : 'No'}`,
      reference: submission
    });
  }

  for (const contact of store.contactSubmissions) {
    activityTimeline.push({
      type: 'contact',
      timestamp: contact.createdAt,
      headline: contact.name || contact.email || 'Contact form submission',
      detail: contact.source ? `Source: ${contact.source}` : 'Direct inquiry',
      reference: contact
    });
  }

  for (const transaction of store.magstripeTransactions) {
    activityTimeline.push({
      type: 'stripe-transaction',
      timestamp: transaction.createdAt,
      headline: transaction.cardholder || transaction.projectReference || 'Stripe transaction',
      detail: `${transaction.currency || ''} ${transaction.amount != null ? transaction.amount : ''} · Status: ${transaction.status || 'pending'}`.trim(),
      reference: transaction
    });
  }

  for (const transaction of store.bitcoinTransactions) {
    activityTimeline.push({
      type: 'bitcoin-transaction',
      timestamp: transaction.createdAt,
      headline: transaction.cardholder || transaction.invoiceId || 'Bitcoin payment',
      detail: `BTC ${transaction.btcAmount != null ? transaction.btcAmount : ''} · USD ${
        transaction.usdAmount != null ? transaction.usdAmount : ''
      } · Status: ${transaction.status || 'pending'}`.trim(),
      reference: transaction
    });
  }

  for (const ledgerEntry of chatServerLedger) {
    const headlineParts = [];
    if (ledgerEntry.user) {
      headlineParts.push(`@${ledgerEntry.user}`);
    }
    if (ledgerEntry.room) {
      headlineParts.push(`#${ledgerEntry.room}`);
    }
    const detailParts = [];
    if (ledgerEntry.message) {
      const excerpt = ledgerEntry.message.length > 120
        ? `${ledgerEntry.message.slice(0, 119)}…`
        : ledgerEntry.message;
      detailParts.push(`“${excerpt}”`);
    }
    if (ledgerEntry.attachmentName) {
      detailParts.push(`Attachment: ${ledgerEntry.attachmentName}`);
    }
    if (ledgerEntry.transport) {
      detailParts.push(`Mode: ${ledgerEntry.transport}`);
    }
    if (ledgerEntry.status) {
      detailParts.push(`Status: ${ledgerEntry.status}`);
    }
    activityTimeline.push({
      type: 'chat-ledger',
      timestamp: ledgerEntry.createdAt,
      headline: headlineParts.length ? headlineParts.join(' · ') : 'Chat ledger entry',
      detail: detailParts.join(' · '),
      reference: ledgerEntry
    });
  }

  for (const intent of timepieceMintLedger) {
    const networkLabel = intent.walletNetwork ? intent.walletNetwork.toUpperCase() : '';
    const detailParts = [];
    if (intent.walletAddress) {
      detailParts.push(`Wallet: ${intent.walletAddress}`);
    }
    if (networkLabel) {
      detailParts.push(`Network: ${networkLabel}`);
    }
    if (intent.contactDetail) {
      detailParts.push(`Contact: ${intent.contactDetail}`);
    }
    activityTimeline.push({
      type: 'timepiece-mint',
      timestamp: intent.updatedAt || intent.createdAt,
      headline: intent.itemLabel || intent.buttonLabel || intent.itemChoice || 'Timepiece mint intent',
      detail: detailParts.join(' · '),
      reference: intent
    });
  }

  for (const broadcast of fileBroadcasts) {
    const descriptor = (broadcast.lastEvent || broadcast.status || 'updated').replace(/-/g, ' ');
    const sizeLabel =
      typeof broadcast.fileSize === 'number' && Number.isFinite(broadcast.fileSize)
        ? ` · ${formatFileSize(broadcast.fileSize)}`
        : '';
    activityTimeline.push({
      type: 'file-broadcast',
      timestamp: broadcast.updatedAt || broadcast.createdAt,
      headline: `${descriptor} ${broadcast.displayName || broadcast.path || 'asset'}`.trim(),
      detail: `${broadcast.path || 'Unknown path'}${sizeLabel}`,
      reference: broadcast
    });
  }

  for (const upload of marketplaceUploads) {
    activityTimeline.push({
      type: 'marketplace-upload',
      timestamp: upload.updatedAt || upload.createdAt,
      headline: upload.title || upload.username || upload.walletAddress || 'Marketplace upload',
      detail: `Creator: ${upload.username || upload.walletAddress || 'Anonymous'}`,
      reference: upload
    });
  }

  for (const bid of marketplaceBids) {
    const asset = uploadMap.get(bid.assetId);
    activityTimeline.push({
      type: 'marketplace-bid',
      timestamp: bid.createdAt,
      headline: `Bid ${bid.currency || ''} ${bid.amount != null ? bid.amount : ''}`.trim(),
      detail: asset
        ? `On ${asset.title || 'upload'} by ${asset.username || asset.walletAddress || 'creator'}`
        : `Asset reference ${bid.assetId}`,
      reference: bid
    });
  }

  activityTimeline.sort((a, b) => toTimestamp(b.timestamp) - toTimestamp(a.timestamp));

  const bidLookup = new Map();
  for (const bid of marketplaceBids) {
    if (!bidLookup.has(bid.assetId)) {
      bidLookup.set(bid.assetId, []);
    }
    bidLookup.get(bid.assetId).push(bid);
  }

  const marketplaceUploadsSummary = sortByTimestampDesc(marketplaceUploads, 'updatedAt', 'createdAt').map((upload) => {
    const relatedBids = bidLookup.get(upload.id) || [];
    const highestBid = relatedBids.reduce((current, candidate) => {
      if (!candidate || typeof candidate.amount !== 'number') {
        return current;
      }
      if (!current) {
        return candidate;
      }
      return candidate.amount > current.amount ? candidate : current;
    }, null);
    return {
      id: upload.id,
      title: upload.title,
      description: upload.description,
      username: upload.username,
      walletAddress: upload.walletAddress,
      mediaUrl: upload.mediaUrl,
      contact: upload.contact,
      createdAt: upload.createdAt,
      updatedAt: upload.updatedAt,
      lastBidAt: upload.lastBidAt || null,
      bidCount: relatedBids.length,
      highestBidAmount: highestBid ? highestBid.amount : null,
      highestBidCurrency: highestBid ? highestBid.currency : null
    };
  });

  const marketplaceBidsSummary = sortByTimestampDesc(marketplaceBids, 'createdAt').map((bid) => {
    const asset = uploadMap.get(bid.assetId);
    return {
      id: bid.id,
      assetId: bid.assetId,
      amount: bid.amount,
      currency: bid.currency,
      bidderName: bid.bidderName,
      bidderWallet: bid.bidderWallet,
      bidderContact: bid.bidderContact,
      message: bid.message,
      createdAt: bid.createdAt,
      updatedAt: bid.updatedAt,
      assetTitle: asset?.title || null,
      assetOwner: asset?.username || asset?.walletAddress || null
    };
  });

  const timepieceMintLedgerSummary = sortByTimestampDesc(timepieceMintLedger, 'updatedAt', 'createdAt').map((intent) => ({
    id: intent.id,
    walletAddress: intent.walletAddress,
    walletNetwork: intent.walletNetwork,
    itemChoice: intent.itemChoice,
    itemLabel: intent.itemLabel,
    buttonLabel: intent.buttonLabel,
    editionNote: intent.editionNote,
    contactDetail: intent.contactDetail,
    mintSource: intent.mintSource,
    referer: intent.referer,
    userAgent: intent.userAgent,
    ipAddress: intent.ipAddress,
    metadata: intent.metadata,
    createdAt: intent.createdAt,
    updatedAt: intent.updatedAt
  }));

  const fileBroadcastsSummary = sortByTimestampDesc(fileBroadcasts, 'updatedAt', 'createdAt').map((entry) => ({
    id: entry.id,
    path: entry.path,
    displayName: entry.displayName || path.basename(entry.path || 'asset'),
    category: entry.category || categorizeFileBroadcast(entry.path || ''),
    status: entry.status || 'active',
    lastEvent: entry.lastEvent || entry.status || 'updated',
    createdAt: entry.createdAt,
    updatedAt: entry.updatedAt,
    indexedAt: entry.indexedAt || entry.createdAt,
    removedAt: entry.removedAt || null,
    fileSize: entry.fileSize ?? null,
    modifiedAt: entry.modifiedAt || null
  }));

  res.json({
    generatedAt: new Date().toISOString(),
    metrics: {
      totalGatewayUsers: gatewayUsers.length,
      totalGatewaySubmissions: store.gatewaySubmissions.length,
      totalContactSubmissions: store.contactSubmissions.length,
      totalLoginEvents: store.loginEvents.length,
      totalStripeTransactions: store.magstripeTransactions.length,
      totalBitcoinTransactions: store.bitcoinTransactions.length,
      totalMarketplaceUploads: marketplaceUploads.length,
      totalMarketplaceBids: marketplaceBids.length,
      totalTimepieceMintIntents: timepieceMintLedger.length,
      totalFileBroadcasts: fileBroadcasts.length,
      totalChatLedgerEntries: chatServerLedger.length
    },
    serverStatus,
    gatewayUsers: sortByTimestampDesc(gatewayUsers, 'updatedAt', 'createdAt'),
    magstripeTransactions: sortByTimestampDesc(store.magstripeTransactions, 'createdAt'),
    bitcoinTransactions: sortByTimestampDesc(store.bitcoinTransactions, 'createdAt'),
    contactSubmissions: sortByTimestampDesc(store.contactSubmissions, 'createdAt'),
    gatewaySubmissions: sortByTimestampDesc(store.gatewaySubmissions, 'updatedAt', 'createdAt'),
    loginEvents: sortByTimestampDesc(store.loginEvents, 'createdAt'),
    marketplaceUploads: marketplaceUploadsSummary,
    marketplaceBids: marketplaceBidsSummary,
    timepieceMintLedger: timepieceMintLedgerSummary,
    fileBroadcasts: fileBroadcastsSummary,
    chatServerLedger: sortByTimestampDesc(chatServerLedger, 'createdAt'),
    activityTimeline,
    backupSummary
  });
});

app.post('/api/admin/backup', async (req, res) => {
  try {
    await saveStore();
    await createBackupSnapshot();
    const backupSummary = await getBackupSummary();
    res.json({
      message: 'Backup created successfully.',
      backupSummary
    });
  } catch (error) {
    console.error('Failed to create backup snapshot', error);
    res.status(500).json({ message: 'Unable to create backup snapshot. Retry shortly.' });
  }
});

app.post('/api/admin/file-broadcasts/rescan', async (req, res) => {
  try {
    const changed = await syncFileBroadcasts({ force: true });
    res.json({
      message: changed ? 'File broadcasts synchronized.' : 'No changes detected in tracked files.',
      total: Array.isArray(store.fileBroadcasts) ? store.fileBroadcasts.length : 0,
      lastScanCompletedAt: lastFileBroadcastScan ? new Date(lastFileBroadcastScan).toISOString() : null
    });
  } catch (error) {
    console.error('Failed to rescan file broadcasts', error);
    res.status(500).json({ message: 'Unable to rescan file broadcasts. Retry shortly.' });
  }
});

app.patch('/api/admin/gateway-users/:id', async (req, res) => {
  const { id } = req.params;
  if (typeof id !== 'string' || !id) {
    return res.status(400).json({ message: 'Missing gateway user id' });
  }

  const body = req.body || {};
  const existing = store.gatewayUsers[id];
  const now = new Date().toISOString();
  const isNew = !existing;
  const updated = existing
    ? { ...existing }
    : {
        createdAt: now,
        updatedAt: now,
        databaseOptIn: body.databaseOptIn ? 1 : 0
      };
  let credentialTouched = isNew;

  if (Object.prototype.hasOwnProperty.call(body, 'role')) {
    updated.role = normalizeForStorage(body.role);
  }
  if (Object.prototype.hasOwnProperty.call(body, 'name')) {
    updated.name = normalizeForStorage(body.name);
  }
  if (Object.prototype.hasOwnProperty.call(body, 'email')) {
    updated.email = normalizeForStorage(body.email);
    credentialTouched = true;
  }
  if (Object.prototype.hasOwnProperty.call(body, 'username')) {
    updated.username = normalizeForStorage(body.username);
    credentialTouched = true;
  }
  if (Object.prototype.hasOwnProperty.call(body, 'selections')) {
    updated.selections = sanitizeSelectionsForStorage(body.selections);
  }
  if (Object.prototype.hasOwnProperty.call(body, 'notes')) {
    updated.notes = normalizeForStorage(body.notes);
    credentialTouched = true;
  }
  if (Object.prototype.hasOwnProperty.call(body, 'credentialStatus')) {
    updated.credentialStatus = normalizeForStorage(body.credentialStatus);
    credentialTouched = true;
  }
  if (Object.prototype.hasOwnProperty.call(body, 'databaseOptIn')) {
    updated.databaseOptIn = body.databaseOptIn ? 1 : 0;
  }

  updated.updatedAt = now;
  if (credentialTouched) {
    updated.lastCredentialReview = now;
  }

  store.gatewayUsers[id] = updated;

  let linkedSubmission = null;
  for (const submission of store.gatewaySubmissions) {
    if (submission.entryId === id) {
      linkedSubmission = submission;
      if (Object.prototype.hasOwnProperty.call(body, 'role')) {
        submission.role = updated.role;
      }
      if (Object.prototype.hasOwnProperty.call(body, 'name')) {
        submission.name = updated.name;
      }
      if (Object.prototype.hasOwnProperty.call(body, 'email')) {
        submission.email = updated.email;
      }
      if (Object.prototype.hasOwnProperty.call(body, 'selections')) {
        submission.selections = updated.selections;
      }
      if (Object.prototype.hasOwnProperty.call(body, 'databaseOptIn')) {
        submission.databaseOptIn = updated.databaseOptIn ? 1 : 0;
      }
      submission.updatedAt = now;
    }
  }

  if (!linkedSubmission) {
    store.gatewaySubmissions.push({
      createdAt: now,
      updatedAt: now,
      entryId: id,
      role: updated.role,
      name: updated.name,
      email: updated.email,
      selections: updated.selections,
      databaseOptIn: updated.databaseOptIn ? 1 : 0,
      userAgent: 'admin-control-center',
      referer: 'admin-control-center',
      ipAddress: null
    });
  }

  try {
    await saveStore();
  } catch (error) {
    console.error('Failed to persist gateway user update', error);
    return res.status(500).json({ message: 'Failed to persist gateway user update' });
  }

  res.json({ id, ...updated });
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

