(() => {
  const GATEWAY_KEY = 'ioncore-gateway';
  const WEBPAGE_KEY = 'ioncore-webpage-login';
  const read = (key) => { try { return JSON.parse(sessionStorage.getItem(key) || 'null'); } catch { return null; } };
  const fresh = (value) => value && Number(value.expires) > Date.now();
  const gateway = read(GATEWAY_KEY);

  function requireGateway() {
    if (!fresh(gateway) || !gateway.name || !gateway.role) {
      window.location.replace('/login.html');
      return false;
    }
    return true;
  }

  document.addEventListener('DOMContentLoaded', () => {
    if (!requireGateway()) return;
    const form = document.querySelector('#webpage-login-form');
    if (!form) {
      const webpage = read(WEBPAGE_KEY);
      if (!fresh(webpage) || Number(webpage.gatewayGrantedAt) !== Number(gateway.grantedAt)) window.location.replace('/webpage-login.html');
      return;
    }
    const copy = document.querySelector('#catalogue-login-copy');
    if (copy) copy.textContent = `${gateway.name}, your dossier acknowledgement is active. Enter the webpage access code to unlock catalogue information.`;
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const input = form.elements.code;
      const error = document.querySelector('#webpage-login-error');
      const button = form.querySelector('button[type="submit"]');
      error.textContent = '';
      if (!input.value.trim()) { error.textContent = 'Enter the webpage access code.'; return; }
      button.disabled = true; button.textContent = 'Verifying…';
      try {
        const response = await fetch('/webpage-login', {method:'POST', headers:{'Content-Type':'application/json','Accept':'application/json'}, body:JSON.stringify({code:input.value.trim(), gatewaySession:gateway})});
        const result = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(result.message || 'Webpage login failed.');
        const expires = result.expiresAt ? Date.parse(result.expiresAt) : Date.now() + 43200000;
        sessionStorage.setItem(WEBPAGE_KEY, JSON.stringify({grantedAt:Date.now(), gatewayGrantedAt:gateway.grantedAt, expires}));
        window.location.assign('/webpage.html');
      } catch (reason) { error.textContent = reason.message || 'Unable to verify access.'; }
      finally { button.disabled = false; button.textContent = 'Unlock catalogue'; }
    });
  });
})();
