(() => {
  const AUTH_STORAGE_KEY = 'ioncore-gateway';
  const form = document.getElementById('gateway-form');

  if (!form) {
    return;
  }

  sessionStorage.removeItem(AUTH_STORAGE_KEY);

  const roleButtons = document.querySelectorAll('.gateway-role');
  const status = document.getElementById('gateway-status');
  const statusCode = document.getElementById('gateway-status-code');
  const submitButton = document.querySelector('.gateway__submit');
  const walletInput = document.getElementById('gateway-wallet');
  const walletProvider = document.getElementById('gateway-wallet-provider');
  const walletStatus = document.getElementById('gateway-wallet-status');
  const meknxPassInput = document.getElementById('gateway-meknx-pass');
  const connectWalletButton = document.getElementById('gateway-connect-wallet');
  const defaultSubmitLabel = submitButton ? submitButton.innerHTML : '';
  let selectedRole = '';

  roleButtons.forEach((button) => {
    button.addEventListener('click', () => {
      roleButtons.forEach((item) => item.classList.remove('is-selected'));
      button.classList.add('is-selected');
      selectedRole = button.dataset.role;
    });
  });

  function setError(id, message) {
    const field = document.getElementById(id);
    const errorEl = document.querySelector(`[data-error-for="${id}"]`);
    if (errorEl) {
      errorEl.textContent = message;
    }
    if (field) {
      if (message) {
        field.setAttribute('aria-invalid', 'true');
      } else {
        field.removeAttribute('aria-invalid');
      }
    }
  }

  function clearErrors() {
    ['gateway-name', 'gateway-email', 'gateway-streams', 'gateway-passphrase'].forEach((id) => setError(id, ''));
    const generalError = document.getElementById('gateway-general-error');
    if (generalError) generalError.remove();
    form?.removeAttribute('aria-describedby');
  }

  function showGeneralError(message) {
    let general = document.getElementById('gateway-general-error');
    if (!general) {
      general = document.createElement('p');
      general.id = 'gateway-general-error';
      general.className = 'gateway__error';
      general.setAttribute('role', 'alert');
      form.prepend(general);
    }
    general.textContent = message;
    form.setAttribute('aria-describedby', 'gateway-general-error');
  }


  function setWalletStatus(message, isError = false) {
    if (!walletStatus) return;
    walletStatus.textContent = message;
    walletStatus.classList.toggle('is-error', isError);
  }

  async function postAccess(path, payload) {
    const response = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.message || 'Wallet clearance could not be completed.');
    }
    return data;
  }

  async function detectWalletAddress(provider) {
    if (provider === 'solana' && window.solana?.connect) {
      const response = await window.solana.connect();
      return response?.publicKey?.toString() || window.solana.publicKey?.toString() || '';
    }
    if (provider === 'evm' && window.ethereum?.request) {
      const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
      return Array.isArray(accounts) ? accounts[0] || '' : '';
    }
    if (provider === 'cardano' && window.cardano) {
      const walletName = Object.keys(window.cardano).find((key) => window.cardano[key]?.enable);
      if (walletName) {
        const api = await window.cardano[walletName].enable();
        const addresses = await api.getUsedAddresses();
        return Array.isArray(addresses) ? addresses[0] || '' : '';
      }
    }
    return walletInput?.value.trim() || '';
  }

  connectWalletButton?.addEventListener('click', async () => {
    const provider = walletProvider?.value || 'solana';
    connectWalletButton.disabled = true;
    setWalletStatus('Connecting wallet and completing crypto clearance…');
    try {
      const address = await detectWalletAddress(provider);
      if (!address) throw new Error('No wallet address was returned. Paste an address or install the matching wallet.');
      if (walletInput) walletInput.value = address;
      const pass = await postAccess('/access/meknx', { walletAddress: address, walletProvider: provider, action: 'mint' });
      if (meknxPassInput) meknxPassInput.value = pass.passId || '';
      if (provider === 'solana') {
        await postAccess('/access/ionc', { walletAddress: address, walletProvider: provider, meknxPassId: pass.passId });
      }
      if (provider === 'cardano') {
        await postAccess('/access/cardano', { walletAddress: address, walletProvider: provider, meknxPassId: pass.passId, policyId: pass.cardanoPolicyId });
      }
      setWalletStatus(`${provider.toUpperCase()} crypto clearance complete for ${address.slice(0, 8)}…${address.slice(-6)}.`);
    } catch (error) {
      setWalletStatus(error?.message || 'Wallet clearance failed.', true);
    } finally {
      connectWalletButton.disabled = false;
    }
  });

  function setSubmitting(isSubmitting) {
    if (!submitButton) return;
    if (isSubmitting) {
      submitButton.disabled = true;
      submitButton.setAttribute('aria-busy', 'true');
      submitButton.innerHTML = 'PROCESSING…';
    } else {
      submitButton.disabled = false;
      submitButton.removeAttribute('aria-busy');
      submitButton.innerHTML = defaultSubmitLabel;
    }
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    clearErrors();

    let hasError = false;

    if (!selectedRole) {
      hasError = true;
      showGeneralError('Please choose the profile that best describes your relationship with Ioncore Energy.');
    }

    const name = form.elements.namedItem('name');
    const email = form.elements.namedItem('email');
    const streamInputs = Array.from(form.querySelectorAll('input[name="streams"]'));
    const databaseToggle = form.elements.namedItem('databaseOptIn');
    const passphrase = form.elements.namedItem('passphrase');

    if (!name.value.trim()) {
      setError('gateway-name', 'Enter your full name to continue.');
      hasError = true;
    }

    const emailValue = email.value.trim();
    if (emailValue && !/^\S+@\S+\.\S+$/.test(emailValue)) {
      setError('gateway-email', 'Provide a valid work email address or leave this field blank.');
      hasError = true;
    }

    const selectedStreams = streamInputs.filter((input) => input.checked).map((input) => input.value);
    if (selectedStreams.length === 0) {
      setError('gateway-streams', 'Select at least one access toggle to continue.');
      hasError = true;
    }

    const passphraseValue = passphrase?.value.trim();
    if (!passphraseValue) {
      setError('gateway-passphrase', 'Enter the required access code to proceed.');
      hasError = true;
    } else if (passphraseValue.toLowerCase() !== 'boots') {
      setError('gateway-passphrase', 'Access code is incorrect.');
      hasError = true;
    }

    if (hasError) {
      return;
    }

    setSubmitting(true);
    form.setAttribute('aria-busy', 'true');

    const requestPayload = {
      role: selectedRole,
      name: name.value.trim(),
      email: emailValue,
      streams: selectedStreams,
      databaseOptIn: !!databaseToggle && databaseToggle.checked,
      walletAddress: walletInput?.value.trim() || '',
      walletProvider: walletProvider?.value || '',
      meknxPassId: meknxPassInput?.value.trim() || ''
    };

    const roleLabels = {
      investor: 'Overview access',
      buyer: 'Technical access',
      team: 'Team access'
    };

    let responseData;
    try {
      const response = await fetch('/gateway', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json'
        },
        body: JSON.stringify(requestPayload)
      });

      if (!response.ok) {
        let message = 'We were unable to verify your details. Please try again.';
        try {
          const data = await response.json();
          if (data && data.message) {
            message = data.message;
          }
        } catch (error) {
          // ignore JSON parse errors
        }
        throw new Error(message);
      }

      responseData = await response.json();
    } catch (error) {
      showGeneralError(error?.message || 'We were unable to verify your details. Please try again.');
      setSubmitting(false);
      form.removeAttribute('aria-busy');
      return;
    }

    const now = Date.now();
    const twelveHours = 12 * 60 * 60 * 1000;
    const payload = {
      role: selectedRole,
      name: name.value.trim(),
      streams: selectedStreams,
      databaseOptIn: !!(databaseToggle && databaseToggle.checked),
      walletAddress: walletInput?.value.trim() || '',
      walletProvider: walletProvider?.value || '',
      meknxPassId: meknxPassInput?.value.trim() || '',
      grantedAt: now,
      expires: now + twelveHours
    };

    if (responseData && typeof responseData.expiresAt === 'string') {
      const expires = Date.parse(responseData.expiresAt);
      if (!Number.isNaN(expires)) {
        payload.expires = expires;
      }
    }

    try {
      sessionStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(payload));
    } catch (error) {
      console.error('Unable to persist gateway access token', error);
    }

    form.setAttribute('aria-hidden', 'true');
    form.style.display = 'none';
    status.setAttribute('aria-live', 'assertive');
    const label = roleLabels[selectedRole] || 'Partner';
    const baseMessage = (responseData && responseData.message) || `${label} preferences saved. Redirecting to brochure.`;
    const selectionCopy =
      responseData && Array.isArray(responseData.selections) && responseData.selections.length
        ? ` Focus: ${responseData.selections.join(', ')}.`
        : '';
    status.querySelector('.status-message').textContent = `${baseMessage}${selectionCopy}`;

    if (statusCode) {
      if (responseData && typeof responseData.entryId === 'string' && responseData.entryId.trim()) {
        statusCode.textContent = `Record ID: ${responseData.entryId}`;
        statusCode.classList.add('is-visible');
      } else {
        statusCode.textContent = '';
        statusCode.classList.remove('is-visible');
      }
    }

    const redirectDelay = responseData && responseData.delayMs ? Number(responseData.delayMs) : 1400;
    setTimeout(() => {
      window.location.href = 'webpage.html';
    }, redirectDelay);
  });
})();
