const OVERLAY_ID = 'wallet-guard-overlay';
const BODY_LOCK_CLASS = 'wallet-guard-locked';
const STORAGE_KEY = 'ioncoreApesAccess';

const CHAIN_NAME_MAP = {
  '0x1': 'Ethereum Mainnet',
  '0x5': 'Goerli',
  '0xa': 'Optimism',
  '0x89': 'Polygon',
  '0x13881': 'Polygon Mumbai',
  '0xa4b1': 'Arbitrum One',
  '0x2105': 'Base',
  '0x38': 'BNB Chain',
  '0x2a': 'Kovan'
};

function normalizeChainId(value) {
  if (typeof value === 'bigint') {
    return value > 0n ? `0x${value.toString(16)}` : null;
  }
  if (typeof value === 'number') {
    if (!Number.isFinite(value) || value <= 0) return null;
    return `0x${Math.trunc(value).toString(16)}`;
  }
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) return null;
    if (/^0x[0-9a-f]+$/i.test(trimmed)) {
      return trimmed.toLowerCase();
    }
    if (/^[0-9]+$/.test(trimmed)) {
      try {
        return `0x${BigInt(trimmed).toString(16)}`;
      } catch {
        return null;
      }
    }
  }
  return null;
}

function inferChainLabel(chainId) {
  return CHAIN_NAME_MAP[chainId] || `Chain ${chainId}`;
}

function createChainOption(chainIdValue, labelValue) {
  const chainId = normalizeChainId(chainIdValue);
  if (!chainId) return null;
  const label = typeof labelValue === 'string' && labelValue.trim() ? labelValue.trim() : inferChainLabel(chainId);
  return { chainId, label };
}

function parseChainOptions(raw, fallbackChainId) {
  if (!Array.isArray(raw)) {
    if (fallbackChainId) {
      const fallback = createChainOption(fallbackChainId);
      return fallback ? [fallback] : [];
    }
    return [];
  }
  const seen = new Set();
  const options = [];
  for (const entry of raw) {
    const option = createChainOption(entry?.chainId ?? entry?.id ?? entry?.network, entry?.label ?? entry?.name);
    if (option && !seen.has(option.chainId)) {
      options.push(option);
      seen.add(option.chainId);
    }
  }
  if (options.length === 0 && fallbackChainId) {
    const fallback = createChainOption(fallbackChainId);
    if (fallback) {
      options.push(fallback);
    }
  }
  return options;
}

const DEFAULT_ACCESS_CONFIG = {
  membershipName: 'Ioncore Apes',
  requiredChainId: '0x1',
  membershipContract: '',
  tokenType: 'erc721',
  tokenId: null,
  minBalance: 1n,
  chainOptions: []
};

const ACCESS_CONFIG = (() => {
  const raw = window.__IONCORE_ACCESS__ || {};
  const defaultChainId = normalizeChainId(raw.requiredChainId) ?? DEFAULT_ACCESS_CONFIG.requiredChainId;
  const chainOptions = parseChainOptions(raw.chainOptions, defaultChainId);
  return {
    membershipName: typeof raw.membershipName === 'string' && raw.membershipName.trim()
      ? raw.membershipName.trim()
      : DEFAULT_ACCESS_CONFIG.membershipName,
    requiredChainId: chainOptions.length > 0 ? chainOptions[0].chainId : defaultChainId,
    membershipContract: typeof raw.membershipContract === 'string' && raw.membershipContract.trim()
      ? raw.membershipContract.trim().toLowerCase()
      : DEFAULT_ACCESS_CONFIG.membershipContract,
    tokenType: typeof raw.tokenType === 'string' && raw.tokenType.trim()
      ? raw.tokenType.trim().toLowerCase()
      : DEFAULT_ACCESS_CONFIG.tokenType,
    tokenId: raw.tokenId ?? DEFAULT_ACCESS_CONFIG.tokenId,
    minBalance: parseMinBalance(raw.minBalance ?? DEFAULT_ACCESS_CONFIG.minBalance),
    chainOptions
  };
})();

let isVerifying = false;
let accessGranted = false;
let activeChainId = ACCESS_CONFIG.requiredChainId;

function getActiveChain() {
  return activeChainId;
}

function setActiveChain(chainId, { updateSelect = true } = {}) {
  const normalized = normalizeChainId(chainId);
  if (!normalized) return;
  if (ACCESS_CONFIG.chainOptions.length > 0) {
    const supported = ACCESS_CONFIG.chainOptions.some((option) => option.chainId === normalized);
    if (!supported) return;
  }
  activeChainId = normalized;
  ACCESS_CONFIG.requiredChainId = normalized;
  if (!updateSelect) return;
  const overlay = document.getElementById(OVERLAY_ID);
  if (!overlay) return;
  const select = overlay.querySelector('[data-chain-select="true"]');
  if (select && select.value !== normalized) {
    select.value = normalized;
  }
}

function getUnlockLabel() {
  return `Unlock ${ACCESS_CONFIG.membershipName}`;
}

function parseMinBalance(value) {
  try {
    if (typeof value === 'bigint') return value;
    if (typeof value === 'number') return BigInt(Math.max(1, value));
    if (typeof value === 'string' && value.trim()) {
      return BigInt(value.trim());
    }
  } catch (err) {
    console.warn('Invalid Ioncore Apes minimum balance, defaulting to 1', err);
  }
  return DEFAULT_ACCESS_CONFIG.minBalance;
}

function hasMetaMask() {
  return typeof window.ethereum !== 'undefined' && Boolean(window.ethereum.isMetaMask);
}

function createOverlay() {
  const existing = document.getElementById(OVERLAY_ID);
  if (existing) return existing;

  const overlay = document.createElement('div');
  overlay.id = OVERLAY_ID;
  overlay.style.position = 'fixed';
  overlay.style.inset = '0';
  overlay.style.background = 'rgba(3, 7, 18, 0.94)';
  overlay.style.display = 'flex';
  overlay.style.flexDirection = 'column';
  overlay.style.alignItems = 'center';
  overlay.style.justifyContent = 'center';
  overlay.style.color = '#e2e8f0';
  overlay.style.zIndex = '9999';
  overlay.style.padding = '32px 16px';
  overlay.style.textAlign = 'center';
  overlay.style.backdropFilter = 'blur(4px)';

  const title = document.createElement('h2');
  title.textContent = `${ACCESS_CONFIG.membershipName} Access Required`;
  title.style.fontFamily = "'Montserrat', Arial, sans-serif";
  title.style.marginBottom = '16px';

  const message = document.createElement('p');
  if (ACCESS_CONFIG.chainOptions.length > 1) {
    message.innerHTML = `Select the network that holds your ${ACCESS_CONFIG.membershipName} NFT, then connect MetaMask to unlock access.`;
  } else {
    message.innerHTML = `Verify your ${ACCESS_CONFIG.membershipName} membership with MetaMask to continue.`;
  }
  message.style.maxWidth = '420px';
  message.style.marginBottom = '20px';
  message.style.lineHeight = '1.6';
  message.dataset.message = 'true';

  let selectorContainer = null;
  if (ACCESS_CONFIG.chainOptions.length > 0) {
    selectorContainer = document.createElement('div');
    selectorContainer.style.display = 'flex';
    selectorContainer.style.flexDirection = 'column';
    selectorContainer.style.alignItems = 'stretch';
    selectorContainer.style.gap = '8px';
    selectorContainer.style.marginBottom = '20px';

    const selectLabel = document.createElement('label');
    selectLabel.textContent = ACCESS_CONFIG.chainOptions.length > 1 ? 'Choose Network' : 'Selected Network';
    selectLabel.style.fontFamily = "'Montserrat', Arial, sans-serif";
    selectLabel.style.fontSize = '0.95rem';
    selectLabel.style.fontWeight = '600';
    selectLabel.style.textAlign = 'left';

    const select = document.createElement('select');
    select.dataset.chainSelect = 'true';
    select.style.padding = '12px 16px';
    select.style.borderRadius = '12px';
    select.style.border = '1px solid rgba(148, 163, 184, 0.35)';
    select.style.background = 'rgba(15, 23, 42, 0.85)';
    select.style.color = '#e2e8f0';
    select.style.fontFamily = "'Montserrat', Arial, sans-serif";
    select.style.fontSize = '0.95rem';
    select.style.cursor = ACCESS_CONFIG.chainOptions.length > 1 ? 'pointer' : 'default';
    select.style.outline = 'none';
    select.style.transition = 'border-color 0.2s ease';

    for (const option of ACCESS_CONFIG.chainOptions) {
      const opt = document.createElement('option');
      opt.value = option.chainId;
      opt.textContent = option.label;
      select.appendChild(opt);
    }

    select.value = getActiveChain();
    if (ACCESS_CONFIG.chainOptions.length === 1) {
      select.disabled = true;
      select.style.opacity = '0.8';
    }

    select.addEventListener('change', (event) => {
      setActiveChain(event.target.value, { updateSelect: false });
    });

    selectorContainer.append(selectLabel, select);
  }

  const button = document.createElement('button');
  button.textContent = getUnlockLabel();
  button.style.background = '#5FE084';
  button.style.color = '#071521';
  button.style.border = 'none';
  button.style.padding = '14px 28px';
  button.style.fontWeight = '600';
  button.style.borderRadius = '999px';
  button.style.cursor = 'pointer';
  button.style.fontFamily = "'Montserrat', Arial, sans-serif";
  button.style.fontSize = '1rem';
  button.addEventListener('click', () => verifyAccess(true));

  const feedback = document.createElement('p');
  feedback.dataset.feedback = 'true';
  feedback.style.display = 'none';
  feedback.style.marginTop = '16px';
  feedback.style.maxWidth = '420px';
  feedback.style.lineHeight = '1.5';

  const download = document.createElement('a');
  download.textContent = 'Install MetaMask';
  download.href = 'https://metamask.io/download/';
  download.style.color = '#93c5fd';
  download.style.marginTop = '18px';
  download.style.display = 'inline-block';
  download.target = '_blank';
  download.rel = 'noopener noreferrer';

  if (selectorContainer) {
    overlay.append(title, message, selectorContainer, button, feedback, download);
  } else {
    overlay.append(title, message, button, feedback, download);
  }
  document.body.appendChild(overlay);
  document.body.classList.add(BODY_LOCK_CLASS);
  document.body.style.overflow = 'hidden';
  setActiveChain(getActiveChain());
  return overlay;
}

function removeOverlay() {
  const overlay = document.getElementById(OVERLAY_ID);
  if (overlay) {
    overlay.remove();
  }
  document.body.classList.remove(BODY_LOCK_CLASS);
  document.body.style.overflow = '';
}

function setFeedback(message, type = 'error') {
  const overlay = document.getElementById(OVERLAY_ID);
  if (!overlay) return;
  const feedback = overlay.querySelector('[data-feedback="true"]');
  if (!feedback) return;
  if (!message) {
    feedback.style.display = 'none';
    feedback.textContent = '';
    return;
  }
  feedback.textContent = message;
  feedback.style.display = 'block';
  feedback.style.color = type === 'error' ? '#fca5a5' : '#93c5fd';
}

function setButtonState({ disabled, label }) {
  const overlay = document.getElementById(OVERLAY_ID);
  if (!overlay) return;
  const button = overlay.querySelector('button');
  if (!button) return;
  if (typeof disabled === 'boolean') {
    button.disabled = disabled;
    button.style.opacity = disabled ? '0.7' : '1';
    button.style.cursor = disabled ? 'not-allowed' : 'pointer';
  }
  if (typeof label === 'string') {
    button.textContent = label;
  } else if (label === undefined) {
    button.textContent = getUnlockLabel();
  }
}

function normalizeHex(value) {
  if (typeof value !== 'string') return value;
  return value.startsWith('0x') ? value.toLowerCase() : `0x${value.toLowerCase()}`;
}

async function ensureCorrectChain() {
  if (!ACCESS_CONFIG.requiredChainId) return;
  const currentChain = await window.ethereum.request({ method: 'eth_chainId' });
  if (currentChain === ACCESS_CONFIG.requiredChainId) return;
  try {
    await window.ethereum.request({
      method: 'wallet_switchEthereumChain',
      params: [{ chainId: ACCESS_CONFIG.requiredChainId }]
    });
  } catch (err) {
    if (err && err.code === 4902 && ACCESS_CONFIG.addChainParameters) {
      await window.ethereum.request({
        method: 'wallet_addEthereumChain',
        params: [ACCESS_CONFIG.addChainParameters]
      });
      return;
    }
    throw new Error('WRONG_CHAIN');
  }
}

function encodeAddress(address) {
  if (typeof address !== 'string' || !/^0x[0-9a-fA-F]{40}$/.test(address)) {
    throw new Error('INVALID_ADDRESS');
  }
  return address.toLowerCase().replace('0x', '').padStart(64, '0');
}

function encodeUint(value) {
  const bigintValue = typeof value === 'bigint' ? value : BigInt(value);
  return bigintValue.toString(16).padStart(64, '0');
}

async function callContract(data) {
  const contract = ACCESS_CONFIG.membershipContract;
  if (!contract) {
    throw new Error('MISSING_CONTRACT');
  }
  const result = await window.ethereum.request({
    method: 'eth_call',
    params: [
      {
        to: normalizeHex(contract),
        data
      },
      'latest'
    ]
  });
  if (!result || result === '0x') return '0x0';
  return result;
}

async function checkErc721Balance(address) {
  const payload = `0x70a08231${encodeAddress(address)}`;
  const balanceHex = await callContract(payload);
  try {
    const balance = BigInt(balanceHex);
    return balance >= ACCESS_CONFIG.minBalance;
  } catch {
    return false;
  }
}

async function checkErc721Token(address) {
  if (ACCESS_CONFIG.tokenId === null || ACCESS_CONFIG.tokenId === undefined) {
    return checkErc721Balance(address);
  }
  const payload = `0x6352211e${encodeUint(ACCESS_CONFIG.tokenId)}`;
  try {
    const ownerHex = await callContract(payload);
    const owner = `0x${ownerHex.slice(-40)}`.toLowerCase();
    return owner === address.toLowerCase();
  } catch {
    return false;
  }
}

async function checkErc1155Balance(address) {
  if (ACCESS_CONFIG.tokenId === null || ACCESS_CONFIG.tokenId === undefined) {
    throw new Error('MISSING_TOKEN_ID');
  }
  const payload = `0x00fdd58e${encodeAddress(address)}${encodeUint(ACCESS_CONFIG.tokenId)}`;
  const balanceHex = await callContract(payload);
  try {
    const balance = BigInt(balanceHex);
    return balance >= ACCESS_CONFIG.minBalance;
  } catch {
    return false;
  }
}

async function verifyMembership(address) {
  if (ACCESS_CONFIG.tokenType === 'erc1155') {
    return checkErc1155Balance(address);
  }
  return checkErc721Token(address);
}

function getStoredAccess() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    try {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === 'object' && typeof parsed.address === 'string') {
        return {
          address: parsed.address.toLowerCase(),
          chainId: typeof parsed.chainId === 'string' ? normalizeChainId(parsed.chainId) : null
        };
      }
    } catch {
      if (typeof raw === 'string') {
        return { address: raw.toLowerCase(), chainId: null };
      }
    }
  } catch (err) {
    console.debug('Unable to read Ioncore Apes access cache', err);
  }
  return null;
}

function rememberAccess(address) {
  try {
    const payload = JSON.stringify({ address: address.toLowerCase(), chainId: getActiveChain() });
    sessionStorage.setItem(STORAGE_KEY, payload);
  } catch (err) {
    console.debug('Unable to persist Ioncore Apes access', err);
  }
}

function clearRememberedAccess() {
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch (err) {
    console.debug('Unable to clear Ioncore Apes access cache', err);
  }
}

function friendlyError(err) {
  if (!err) return 'Verification failed. Please try again.';
  const code = typeof err === 'string' ? err : err.message;
  if (code === 'NO_ACCOUNTS') {
    return 'Connect your MetaMask wallet to continue.';
  }
  if (code === 'WRONG_CHAIN') {
    return 'Switch to the selected network in MetaMask and try again.';
  }
  if (code === 'MISSING_CONTRACT') {
    return 'Ioncore Apes membership contract is not configured.';
  }
  if (code === 'MISSING_TOKEN_ID') {
    return 'Ioncore Apes token ID is required for ERC-1155 verification.';
  }
  if (err.code === 4001) {
    return 'MetaMask request was rejected. Please authorize to continue.';
  }
  if (err.code === -32002) {
    return 'Complete the pending MetaMask request to continue.';
  }
  return err.message || 'Verification failed. Please try again.';
}

async function verifyAccess(interactive = false, preferredChainId) {
  createOverlay();
  if (preferredChainId) {
    setActiveChain(preferredChainId);
  }
  setActiveChain(getActiveChain());
  setFeedback('');

  if (!hasMetaMask()) {
    setFeedback('MetaMask is required to verify Ioncore Apes access. Install it to continue.');
    return false;
  }

  if (isVerifying) return false;
  isVerifying = true;

  try {
    setButtonState({ disabled: true, label: 'Unlocking…' });
    const method = interactive ? 'eth_requestAccounts' : 'eth_accounts';
    const accounts = await window.ethereum.request({ method });
    if (!accounts || accounts.length === 0) {
      setFeedback(friendlyError('NO_ACCOUNTS'), 'info');
      setButtonState({ disabled: false, label: getUnlockLabel() });
      return false;
    }
    const address = accounts[0];
    try {
      await ensureCorrectChain();
    } catch (err) {
      setFeedback(friendlyError(err), 'error');
      setButtonState({ disabled: false, label: getUnlockLabel() });
      return false;
    }

    const hasAccess = await verifyMembership(address);
    if (hasAccess) {
      accessGranted = true;
      rememberAccess(address);
      setButtonState({ disabled: true, label: 'Access Granted' });
      setFeedback('');
      removeOverlay();
      return true;
    }

    clearRememberedAccess();
    setFeedback(`Verified address does not hold a ${ACCESS_CONFIG.membershipName} token on the selected network.`);
    setButtonState({ disabled: false, label: getUnlockLabel() });
    return false;
  } catch (err) {
    console.warn('Ioncore Apes verification failed', err);
    setFeedback(friendlyError(err));
    setButtonState({ disabled: false, label: getUnlockLabel() });
    return false;
  } finally {
    isVerifying = false;
  }
}

async function enforceAccess() {
  if (accessGranted) return;
  const stored = getStoredAccess();
  if (stored?.chainId) {
    setActiveChain(stored.chainId, { updateSelect: false });
  }

  await verifyAccess(false, stored?.chainId ?? getActiveChain());

  if (accessGranted || !stored || !stored.address || !hasMetaMask()) return;

  try {
    const accounts = await window.ethereum.request({ method: 'eth_accounts' });
    if (accounts && accounts.some((addr) => addr.toLowerCase() === stored.address)) {
      accessGranted = true;
      setActiveChain(stored.chainId ?? getActiveChain());
      removeOverlay();
    }
  } catch (err) {
    console.debug('Unable to reuse stored Ioncore Apes access', err);
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', enforceAccess);
} else {
  enforceAccess();
}

if (window.ethereum && window.ethereum.on) {
  window.ethereum.on('accountsChanged', async (accounts) => {
    accessGranted = false;
    if (!accounts || accounts.length === 0) {
      clearRememberedAccess();
      createOverlay();
      setFeedback(friendlyError('NO_ACCOUNTS'), 'info');
      setButtonState({ disabled: false, label: getUnlockLabel() });
      return;
    }
    const stored = getStoredAccess();
    if (stored?.chainId) {
      setActiveChain(stored.chainId, { updateSelect: false });
    }
    await verifyAccess(false, stored?.chainId ?? getActiveChain());
  });

  window.ethereum.on('chainChanged', async () => {
    accessGranted = false;
    await verifyAccess(false, getActiveChain());
  });
}

window.addEventListener('focus', () => {
  if (!accessGranted) {
    verifyAccess(false, getActiveChain());
  }
});
