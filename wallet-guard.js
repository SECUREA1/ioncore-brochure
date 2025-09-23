const OVERLAY_ID = 'wallet-guard-overlay';
const BODY_LOCK_CLASS = 'wallet-guard-locked';
const STORAGE_KEY = 'ioncoreApesAccess';

const DEFAULT_ACCESS_CONFIG = {
  membershipName: 'Ioncore Apes',
  requiredChainId: '0x1',
  // Matches DEFAULT_MEMBERSHIP_CONTRACT in server.js so standalone pages still gate properly.
  membershipContract: '0xaef8b6346ca4dadaa71783dddf4a3d00633b679d',
  tokenType: 'erc721',
  tokenId: null,
  minBalance: 1n
};

const ACCESS_CONFIG = (() => {
  const raw = window.__IONCORE_ACCESS__ || {};
  return {
    membershipName: typeof raw.membershipName === 'string' && raw.membershipName.trim()
      ? raw.membershipName.trim()
      : DEFAULT_ACCESS_CONFIG.membershipName,
    requiredChainId: typeof raw.requiredChainId === 'string' && raw.requiredChainId.trim()
      ? raw.requiredChainId.trim()
      : DEFAULT_ACCESS_CONFIG.requiredChainId,
    membershipContract: typeof raw.membershipContract === 'string' && raw.membershipContract.trim()
      ? raw.membershipContract.trim().toLowerCase()
      : DEFAULT_ACCESS_CONFIG.membershipContract,
    tokenType: typeof raw.tokenType === 'string' && raw.tokenType.trim()
      ? raw.tokenType.trim().toLowerCase()
      : DEFAULT_ACCESS_CONFIG.tokenType,
    tokenId: raw.tokenId ?? DEFAULT_ACCESS_CONFIG.tokenId,
    minBalance: parseMinBalance(raw.minBalance ?? DEFAULT_ACCESS_CONFIG.minBalance)
  };
})();

let isVerifying = false;
let accessGranted = false;
let provider = null;
let listenersAttached = false;

function detectMetaMaskProvider() {
  const { ethereum } = window;
  if (!ethereum) return null;
  if (ethereum.isMetaMask) return ethereum;

  if (Array.isArray(ethereum.providers)) {
    return ethereum.providers.find((p) => p && p.isMetaMask) || null;
  }

  if (ethereum.providerMap && typeof ethereum.providerMap.get === 'function') {
    return ethereum.providerMap.get('MetaMask') || null;
  }

  return null;
}

function getProvider() {
  const detected = detectMetaMaskProvider();
  if (detected && detected !== provider) {
    if (provider && typeof provider.removeListener === 'function') {
      provider.removeListener('accountsChanged', handleAccountsChanged);
      provider.removeListener('chainChanged', handleChainChanged);
    }
    provider = detected;
    listenersAttached = false;
  }
  return provider;
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
  return Boolean(getProvider());
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
  message.innerHTML = `Verify your ${ACCESS_CONFIG.membershipName} membership with MetaMask to continue.`;
  message.style.maxWidth = '420px';
  message.style.marginBottom = '12px';
  message.style.lineHeight = '1.6';
  message.dataset.message = 'true';

  const supplierNotice = document.createElement('p');
  supplierNotice.textContent =
    'Ioncore IONC Supplier Apes token build coming soon — your access key will ship with the supply.';
  supplierNotice.style.maxWidth = '420px';
  supplierNotice.style.marginBottom = '20px';
  supplierNotice.style.lineHeight = '1.5';

  const button = document.createElement('button');
  button.textContent = `Verify ${ACCESS_CONFIG.membershipName} Access`;
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

  overlay.append(title, message, supplierNotice, button, feedback, download);
  document.body.appendChild(overlay);
  document.body.classList.add(BODY_LOCK_CLASS);
  document.body.style.overflow = 'hidden';
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
  }
}

function normalizeHex(value) {
  if (typeof value !== 'string') return value;
  return value.startsWith('0x') ? value.toLowerCase() : `0x${value.toLowerCase()}`;
}

async function ensureCorrectChain() {
  if (!ACCESS_CONFIG.requiredChainId) return;
  const metamask = getProvider();
  if (!metamask) {
    throw new Error('NO_PROVIDER');
  }
  const currentChain = await metamask.request({ method: 'eth_chainId' });
  if (currentChain === ACCESS_CONFIG.requiredChainId) return;
  try {
    await metamask.request({
      method: 'wallet_switchEthereumChain',
      params: [{ chainId: ACCESS_CONFIG.requiredChainId }]
    });
  } catch (err) {
    if (err && err.code === 4902 && ACCESS_CONFIG.addChainParameters) {
      await metamask.request({
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
  const metamask = getProvider();
  if (!metamask) {
    throw new Error('NO_PROVIDER');
  }
  try {
    const result = await metamask.request({
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
  } catch (err) {
    const message = `${err?.message || err}`.toLowerCase();
    if (
      message.includes('execution reverted') ||
      err?.code === 3 ||
      err?.code === -32000 ||
      err?.code === -32603
    ) {
      const error = new Error('EXECUTION_REVERTED');
      error.originalError = err;
      throw error;
    }
    throw err;
  }
}

async function checkErc721Balance(address) {
  const payload = `0x70a08231${encodeAddress(address)}`;
  let balanceHex;
  try {
    balanceHex = await callContract(payload);
  } catch (err) {
    if (err?.message === 'EXECUTION_REVERTED') {
      return false;
    }
    throw err;
  }
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
  let ownerHex;
  try {
    ownerHex = await callContract(payload);
  } catch (err) {
    if (err?.message === 'EXECUTION_REVERTED') {
      throw err;
    }
    throw err;
  }
  if (!ownerHex || ownerHex.length < 66) {
    return false;
  }
  const owner = `0x${ownerHex.slice(-40)}`.toLowerCase();
  return owner === address.toLowerCase();
}

async function checkErc1155Balance(address) {
  if (ACCESS_CONFIG.tokenId === null || ACCESS_CONFIG.tokenId === undefined) {
    throw new Error('MISSING_TOKEN_ID');
  }
  const payload = `0x00fdd58e${encodeAddress(address)}${encodeUint(ACCESS_CONFIG.tokenId)}`;
  let balanceHex;
  try {
    balanceHex = await callContract(payload);
  } catch (err) {
    if (err?.message === 'EXECUTION_REVERTED') {
      return false;
    }
    throw err;
  }
  try {
    const balance = BigInt(balanceHex);
    return balance >= ACCESS_CONFIG.minBalance;
  } catch {
    return false;
  }
}

async function verifyMembership(address) {
  try {
    if (ACCESS_CONFIG.tokenType === 'erc1155') {
      return await checkErc1155Balance(address);
    }
    return await checkErc721Token(address);
  } catch (err) {
    if (err?.message === 'EXECUTION_REVERTED') {
      if (
        ACCESS_CONFIG.tokenType === 'erc721' &&
        ACCESS_CONFIG.tokenId !== null &&
        ACCESS_CONFIG.tokenId !== undefined
      ) {
        try {
          return await checkErc1155Balance(address);
        } catch (innerErr) {
          if (innerErr?.message === 'EXECUTION_REVERTED') {
            return false;
          }
          throw innerErr;
        }
      }
      return false;
    }
    throw err;
  }
}

function rememberAccess(address) {
  try {
    sessionStorage.setItem(STORAGE_KEY, address.toLowerCase());
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
  if (code === 'NO_PROVIDER') {
    return 'MetaMask is required to verify Ioncore Apes access. Install it to continue.';
  }
  if (code === 'WRONG_CHAIN') {
    return 'Switch to the required network in MetaMask and try again.';
  }
  if (code === 'MISSING_CONTRACT') {
    return 'Ioncore Apes membership contract is not configured.';
  }
  if (code === 'MISSING_TOKEN_ID') {
    return 'Ioncore Apes token ID is required for ERC-1155 verification.';
  }
  if (code === 'EXECUTION_REVERTED') {
    return 'Unable to verify membership token ownership on-chain. Please try again or contact support.';
  }
  if (err.code === 4001) {
    return 'MetaMask request was rejected. Please authorize to continue.';
  }
  if (err.code === -32002) {
    return 'Complete the pending MetaMask request to continue.';
  }
  return err.message || 'Verification failed. Please try again.';
}

function attachProviderListeners() {
  const metamask = getProvider();
  if (!metamask || typeof metamask.on !== 'function' || listenersAttached) {
    return;
  }
  metamask.on('accountsChanged', handleAccountsChanged);
  metamask.on('chainChanged', handleChainChanged);
  listenersAttached = true;
}

async function handleAccountsChanged(accounts) {
  accessGranted = false;
  if (!accounts || accounts.length === 0) {
    clearRememberedAccess();
    createOverlay();
    setFeedback(friendlyError('NO_ACCOUNTS'), 'info');
    setButtonState({ disabled: false, label: `Verify ${ACCESS_CONFIG.membershipName} Access` });
    return;
  }
  await verifyAccess(false);
}

async function handleChainChanged() {
  accessGranted = false;
  await verifyAccess(false);
}

async function verifyAccess(interactive = false) {
  createOverlay();
  setFeedback('');

  if (!hasMetaMask()) {
    setFeedback('MetaMask is required to verify Ioncore Apes access. Install it to continue.');
    return false;
  }

  const metamask = getProvider();
  if (!metamask) {
    setFeedback('MetaMask is required to verify Ioncore Apes access. Install it to continue.');
    return false;
  }

  attachProviderListeners();

  if (isVerifying) return false;
  isVerifying = true;

  try {
    setButtonState({ disabled: true, label: 'Verifying…' });
    const method = interactive ? 'eth_requestAccounts' : 'eth_accounts';
    const accounts = await metamask.request({ method });
    if (!accounts || accounts.length === 0) {
      setFeedback(friendlyError('NO_ACCOUNTS'), 'info');
      setButtonState({ disabled: false, label: `Verify ${ACCESS_CONFIG.membershipName} Access` });
      return false;
    }
    const address = accounts[0];
    try {
      await ensureCorrectChain();
    } catch (err) {
      setFeedback(friendlyError(err), 'error');
      setButtonState({ disabled: false, label: `Verify ${ACCESS_CONFIG.membershipName} Access` });
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
    setFeedback(`Verified address does not hold a ${ACCESS_CONFIG.membershipName} token.`);
    setButtonState({ disabled: false, label: `Verify ${ACCESS_CONFIG.membershipName} Access` });
    return false;
  } catch (err) {
    console.warn('Ioncore Apes verification failed', err);
    setFeedback(friendlyError(err));
    setButtonState({ disabled: false, label: `Verify ${ACCESS_CONFIG.membershipName} Access` });
    return false;
  } finally {
    isVerifying = false;
  }
}

async function enforceAccess() {
  if (accessGranted) return;
  const stored = (() => {
    try {
      return sessionStorage.getItem(STORAGE_KEY);
    } catch {
      return null;
    }
  })();

  await verifyAccess(false);

  if (accessGranted || !stored || !hasMetaMask()) return;

  const metamask = getProvider();
  if (!metamask) return;

  try {
    const accounts = await metamask.request({ method: 'eth_accounts' });
    if (accounts && accounts.some((addr) => addr.toLowerCase() === stored)) {
      accessGranted = true;
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

attachProviderListeners();

window.addEventListener('ethereum#initialized', () => {
  provider = null;
  listenersAttached = false;
  attachProviderListeners();
  if (!accessGranted) {
    verifyAccess(false);
  }
});

window.addEventListener('focus', () => {
  attachProviderListeners();
  if (!accessGranted) {
    verifyAccess(false);
  }
});
