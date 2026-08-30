(() => {
  const KEY = 'ioncore-gateway';
  const form = document.querySelector('#dossier-form');
  const error = document.querySelector('#dossier-error');
  if (!form) return;
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    error.textContent = '';
    const button = form.querySelector('button[type="submit"]');
    const data = new FormData(form);
    if (!data.get('name')?.trim() || !data.get('passphrase')?.trim() || !data.get('ndaAccepted')) {
      error.textContent = 'Enter your name and gateway code, then acknowledge the confidentiality notice.';
      return;
    }
    button.disabled = true; button.textContent = 'Verifying…';
    try {
      const response = await fetch('/gateway', {method:'POST', headers:{'Content-Type':'application/json','Accept':'application/json'}, body:JSON.stringify({role:'investor', name:data.get('name').trim(), email:data.get('email').trim(), passphrase:data.get('passphrase'), streams:['investor-dossier'], databaseOptIn:false, ndaAccepted:true})});
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.message || 'Dossier entry could not be verified.');
      const expires = result.expiresAt ? Date.parse(result.expiresAt) : Date.now() + 43200000;
      sessionStorage.setItem(KEY, JSON.stringify({name:data.get('name').trim(), role:'investor', entryId:result.entryId || '', grantedAt:Date.now(), expires}));
      window.location.assign('/index.html');
    } catch (reason) { error.textContent = reason.message || 'Unable to continue.'; }
    finally { button.disabled = false; button.textContent = 'Acknowledge & open index'; }
  });
})();
