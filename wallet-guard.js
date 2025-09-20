const OVERLAY_ID = 'wallet-guard-overlay';
const BODY_LOCK_CLASS = 'wallet-guard-locked';

function createOverlay() {
  if (document.getElementById(OVERLAY_ID)) return document.getElementById(OVERLAY_ID);
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
  title.textContent = 'Connect Phantom Wallet';
  title.style.fontFamily = "'Montserrat', Arial, sans-serif";
  title.style.marginBottom = '16px';

  const message = document.createElement('p');
  message.innerHTML = 'A verified Phantom wallet connection is required to access Ioncore resources.';
  message.style.maxWidth = '420px';
  message.style.marginBottom = '24px';
  message.style.lineHeight = '1.6';

  const button = document.createElement('button');
  button.textContent = 'Connect Phantom Wallet';
  button.style.background = '#5FE084';
  button.style.color = '#071521';
  button.style.border = 'none';
  button.style.padding = '14px 28px';
  button.style.fontWeight = '600';
  button.style.borderRadius = '999px';
  button.style.cursor = 'pointer';
  button.style.fontFamily = "'Montserrat', Arial, sans-serif";
  button.style.fontSize = '1rem';
  button.addEventListener('click', connectWallet);

  const download = document.createElement('a');
  download.textContent = 'Install Phantom';
  download.href = 'https://phantom.app/download';
  download.style.color = '#93c5fd';
  download.style.marginTop = '18px';
  download.target = '_blank';
  download.rel = 'noopener noreferrer';

  overlay.append(title, message, button, download);
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

async function connectWallet() {
  if (!window.solana || !window.solana.isPhantom) {
    createOverlay();
    return;
  }

  const overlay = createOverlay();
  const button = overlay.querySelector('button');
  button.disabled = true;
  button.textContent = 'Connecting…';
  try {
    const response = await window.solana.connect();
    if (!response || !response.publicKey) {
      throw new Error('Connection rejected');
    }
    removeOverlay();
  } catch (err) {
    console.warn('Wallet connection failed', err);
    button.disabled = false;
    button.textContent = 'Connect Phantom Wallet';
  }
}

async function enforceConnection() {
  if (!window.solana || !window.solana.isPhantom) {
    createOverlay();
    return;
  }

  try {
    const resp = await window.solana.connect({ onlyIfTrusted: true });
    if (resp && resp.publicKey) {
      removeOverlay();
      return;
    }
  } catch (err) {
    console.debug('Wallet not trusted yet', err);
  }

  createOverlay();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', enforceConnection);
} else {
  enforceConnection();
}

if (!window.solana) {
  window.addEventListener('solana#initialized', enforceConnection, { once: true });
  setTimeout(enforceConnection, 500);
}

window.addEventListener('focus', enforceConnection);

if (window.solana) {
  window.solana.on && window.solana.on('disconnect', createOverlay);
  window.solana.on && window.solana.on('connect', removeOverlay);
}
