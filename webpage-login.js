(() => {
  const GATEWAY_KEY = 'ioncore-gateway';
  const WEBPAGE_KEY = 'ioncore-webpage-login';
  const LOGIN_TTL_MS = 12 * 60 * 60 * 1000;

  const now = () => Date.now();

  function readJson(key) {
    try {
      const raw = sessionStorage.getItem(key);
      return raw ? JSON.parse(raw) : null;
    } catch (error) {
      console.warn(`Unable to read ${key}`, error);
      return null;
    }
  }

  function writeJson(key, value) {
    try {
      sessionStorage.setItem(key, JSON.stringify(value));
    } catch (error) {
      console.warn(`Unable to write ${key}`, error);
    }
  }

  function isFresh(record) {
    return !!record && typeof record.expires === 'number' && record.expires > now();
  }

  function getGatewaySession() {
    const session = readJson(GATEWAY_KEY);
    if (!isFresh(session) || !session.name || !session.role) {
      return null;
    }
    return session;
  }

  function getWebpageSession(gatewaySession) {
    const login = readJson(WEBPAGE_KEY);
    if (!isFresh(login) || !login.gatewayGrantedAt || !gatewaySession) {
      return null;
    }
    return Number(login.gatewayGrantedAt) === Number(gatewaySession.grantedAt) ? login : null;
  }

  function lockPage() {
    document.documentElement.classList.add('webpage-login-locked');
    document.body.classList.add('webpage-login-locked');
  }

  function unlockPage() {
    document.documentElement.classList.remove('webpage-login-locked');
    document.body.classList.remove('webpage-login-locked');
    const overlay = document.getElementById('webpage-login-overlay');
    overlay?.remove();
  }

  function redirectToGateway() {
    window.location.replace('/index.html#gateway-entry');
  }

  async function postWebpageLogin(payload) {
    const response = await fetch('/webpage-login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.message || 'Webpage login failed.');
    }
    return data;
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>\"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '\"': '&quot;' })[char]);
  }

  function renderOverlay(gatewaySession) {
    lockPage();
    if (document.getElementById('webpage-login-overlay')) return;

    const overlay = document.createElement('div');
    overlay.id = 'webpage-login-overlay';
    overlay.className = 'webpage-login';
    overlay.innerHTML = `
      <div class="webpage-login__card" role="dialog" aria-modal="true" aria-labelledby="webpage-login-title">
        <div class="webpage-login__brand">
          <img src="battery.svg" alt="" aria-hidden="true">
          <span>Ioncore Energy</span>
        </div>
        <p class="eyebrow">Gateway verified</p>
        <h1 id="webpage-login-title">Complete webpage login</h1>
        <p class="webpage-login__copy">${escapeHtml(gatewaySession.name)}, your gateway session is active. Enter the webpage access code to unlock the full Ioncore web experience.</p>
        <form id="webpage-login-form" novalidate>
          <label for="webpage-login-code">Webpage access code</label>
          <input id="webpage-login-code" name="code" type="password" autocomplete="current-password" required autofocus>
          <p class="webpage-login__error" id="webpage-login-error" role="alert"></p>
          <div class="webpage-login__actions">
            <button class="btn btn-primary" type="submit">Unlock webpage</button>
            <button class="btn btn-outline" type="button" id="webpage-login-back">Return to gateway</button>
          </div>
        </form>
      </div>`;
    document.body.prepend(overlay);

    const form = document.getElementById('webpage-login-form');
    const input = document.getElementById('webpage-login-code');
    const error = document.getElementById('webpage-login-error');
    const back = document.getElementById('webpage-login-back');
    const submit = form?.querySelector('button[type="submit"]');

    back?.addEventListener('click', redirectToGateway);
    input?.focus();

    form?.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (!input?.value.trim()) {
        error.textContent = 'Enter the webpage access code.';
        return;
      }
      error.textContent = '';
      if (submit) {
        submit.disabled = true;
        submit.textContent = 'Verifying…';
      }
      try {
        const data = await postWebpageLogin({ code: input.value.trim(), gatewaySession });
        const expires = data.expiresAt ? Date.parse(data.expiresAt) : now() + LOGIN_TTL_MS;
        writeJson(WEBPAGE_KEY, {
          grantedAt: now(),
          gatewayGrantedAt: gatewaySession.grantedAt,
          entryId: gatewaySession.entryId || '',
          expires: Number.isNaN(expires) ? now() + LOGIN_TTL_MS : expires
        });
        unlockPage();
      } catch (err) {
        error.textContent = err?.message || 'Unable to verify the webpage login.';
      } finally {
        if (submit) {
          submit.disabled = false;
          submit.textContent = 'Unlock webpage';
        }
      }
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    const gatewaySession = getGatewaySession();
    if (!gatewaySession) {
      redirectToGateway();
      return;
    }
    if (getWebpageSession(gatewaySession)) {
      unlockPage();
      return;
    }
    renderOverlay(gatewaySession);
  });
})();
