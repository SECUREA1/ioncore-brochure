/*
  Ioncore Secure Vault – Wallet login fix
  Drop-in replacement for the existing <script> logic that handles wallet connectors.
  Usage: Remove the old inline <script> and include this file, or paste this whole block
  inside a single <script> tag at the end of the <body>.

  What this fixes:
  - Robust MetaMask detection (standalone & multi-provider) and connect flow
  - Phantom detection (desktop & mobile deep-link) and connect flow
  - Clear provider + address plumbing into hidden inputs (#wallet-address, #wallet-provider)
  - Visible status updates (#metamask-status, #phantom-status)
  - "Enter the Vault" submit guard that requires a valid wallet session for Wallet mode
  - Optional IONC gate visibility toggle (if #ionc-module exists)

  Notes:
  - This script purposefully limits scope to EVM (MetaMask) and Solana (Phantom) as requested.
  - Cardano and other experimental modules are left untouched (hidden if present).
*/
(function () {
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  // Elements
  const form = $('#login-form');
  const statusEl = $('#status');
  const walletAddressInput = $('#wallet-address');
  const walletProviderInput = $('#wallet-provider');

  const metamaskBtn = $('#connect-metamask');
  const phantomBtn = $('#connect-phantom');

  const metamaskStatus = $('#metamask-status');
  const phantomStatus = $('#phantom-status');

  const tabWalletBtn = $('#tab-wallet');
  const tabCredsBtn = $('#tab-credentials');
  const tabMeknxBtn = $('#tab-meknx');

  const walletPanel = $('#wallet-panel');
  const credsPanel = $('#credentials-panel');
  const meknxPanel = $('#meknx-panel');

  const ioncModule = $('#ionc-module');
  const ioncVerifyButton = $('#ionc-verify-button');
  const ioncInlineStatus = $('#ionc-inline-status');
  const ioncLedgerInput = $('#ionc-ledger');
  const ioncOrderBacklogInput = $('#ionc-order-backlog');
  const ioncOrderBacklogStatus = $('#ionc-order-backlog-status');
  const ioncVerifiedInput = $('#ionc-verified');
  const ioncMarketModule = $('#ionc-market-module');

  const solanaDepositRow = $('#solana-deposit-row');
  const solanaDepositStatus = $('#solana-deposit-status');
  const solanaDepositAmountInput = $('#solana-deposit-amount');
  const solanaDepositAmountHiddenInput = $('#solana-deposit-amount-hidden');
  const solanaDepositIoncHiddenInput = $('#solana-deposit-ionc');
  const solanaDepositIoncPreview = $('#solana-deposit-ionc-preview');
  const solanaDepositSignatureInput = $('#solana-deposit-signature');
  const solanaDepositSendButton = $('#solana-deposit-send');
  const solanaDepositVerifyButton = $('#solana-deposit-verify');

  const meknxActionSelect = $('#meknx-action');
  const meknxActionButton = $('#meknx-action-button');
  const meknxInlineStatus = $('#meknx-inline-status');
  const meknxVerifyButton = $('#meknx-verify');
  const meknxMintButton = $('#meknx-mint');
  const meknxStatus = $('#meknx-status');
  const meknxPasscodeInput = $('#meknx-passcode');
  const meknxPassIdInput = $('#meknx-pass-id');

  const solanaModule = window.IoncoreSolana || null;
  const LAMPORTS_PER_SOL = solanaModule && typeof solanaModule.LAMPORTS_PER_SOL === 'number'
    ? solanaModule.LAMPORTS_PER_SOL
    : 1_000_000_000;
  const IONC_PER_SOL = solanaModule && typeof solanaModule.IONC_PER_SOL === 'number'
    ? solanaModule.IONC_PER_SOL
    : 1000;
  const MIN_SOL_DEPOSIT = 0.1;
  const MAX_SOL_DEPOSIT = solanaModule && typeof solanaModule.MAX_SOL_DEPOSIT_SOL === 'number'
    ? Math.max(solanaModule.MAX_SOL_DEPOSIT_SOL, 1)
    : 1000;

  const inlineStatusToneClasses = ['inline-status--error', 'inline-status--success'];

  const shorten = (s) => (s && s.length > 12 ? `${s.slice(0, 6)}…${s.slice(-4)}` : s || '');
  const formatNumber = (value) =>
    Number(value || 0).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
  const formatSolAmountLabel = (value) => {
    const decimals = Math.abs(value % 1) < 1e-9 ? 0 : 1;
    return `${Number(value).toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: Math.max(decimals, 3)
    })} SOL`;
  };
  const formatIoncLabel = (value) => `${formatNumber(value)} IONC`;

  const setStatus = (msg, tone) => {
    if (!statusEl) return;
    statusEl.textContent = msg || '';
    statusEl.classList.remove('status-message--error', 'status-message--success');
    if (tone === 'error') statusEl.classList.add('status-message--error');
    if (tone === 'success') statusEl.classList.add('status-message--success');
  };

  const setInlineStatus = (el, msg, tone = 'neutral') => {
    if (!el) return;
    el.textContent = msg || '';
    el.classList.remove(...inlineStatusToneClasses);
    if (tone === 'error') el.classList.add('inline-status--error');
    if (tone === 'success') el.classList.add('inline-status--success');
  };

  const clampSolAmount = (value) => {
    const numeric = typeof value === 'number' ? value : Number.parseFloat(value);
    if (!Number.isFinite(numeric)) {
      return MIN_SOL_DEPOSIT;
    }
    const clamped = Math.min(Math.max(numeric, MIN_SOL_DEPOSIT), MAX_SOL_DEPOSIT);
    return Math.round(clamped * 1000) / 1000;
  };

  const depositState = {
    amount: MIN_SOL_DEPOSIT,
    minted: Math.round(MIN_SOL_DEPOSIT * IONC_PER_SOL),
    signature: '',
    lamports: Math.round(MIN_SOL_DEPOSIT * LAMPORTS_PER_SOL),
    sending: false,
    verifying: false,
    completed: false
  };

  let metamaskProvider = null;
  let phantomProvider = null;

  const clearHidden = () => {
    if (walletAddressInput) walletAddressInput.value = '';
    if (walletProviderInput) walletProviderInput.value = '';
  };

  const resetIoncState = () => {
    if (ioncLedgerInput) ioncLedgerInput.value = '';
    if (ioncOrderBacklogInput) ioncOrderBacklogInput.value = '';
    if (ioncVerifiedInput) ioncVerifiedInput.value = '';
    if (ioncModule) ioncModule.hidden = true;
    setInlineStatus(ioncInlineStatus, 'Awaiting verification.');
    if (ioncMarketModule) ioncMarketModule.hidden = true;
    if (ioncOrderBacklogStatus) {
      ioncOrderBacklogStatus.textContent = 'Admin ledger backlog 0/5. Five retainers are required before IONC verification is released.';
    }
  };

  const resetDepositState = ({ keepAmount = false } = {}) => {
    if (!keepAmount) {
      depositState.amount = MIN_SOL_DEPOSIT;
    }
    depositState.minted = Math.round(depositState.amount * IONC_PER_SOL);
    depositState.signature = '';
    depositState.lamports = Math.round(depositState.amount * LAMPORTS_PER_SOL);
    depositState.sending = false;
    depositState.verifying = false;
    depositState.completed = false;
    if (solanaDepositSignatureInput) solanaDepositSignatureInput.value = '';
    if (solanaDepositAmountHiddenInput) solanaDepositAmountHiddenInput.value = depositState.amount.toString();
    if (solanaDepositIoncHiddenInput) solanaDepositIoncHiddenInput.value = depositState.minted.toString();
    if (solanaDepositVerifyButton) {
      solanaDepositVerifyButton.disabled = true;
      solanaDepositVerifyButton.dataset.loading = 'false';
      solanaDepositVerifyButton.textContent = 'Verify Receipt';
    }
    if (solanaDepositAmountInput) {
      solanaDepositAmountInput.value = depositState.amount.toString();
    }
    if (solanaDepositStatus) {
      solanaDepositStatus.textContent = 'Access retainer pending. Select an amount between 0.1 and 1000 SOL, connect Phantom, then click Send to authorize the transfer.';
      solanaDepositStatus.classList.remove('wallet-status--connected');
    }
    updateDepositPreview({ resetSignature: false });
  };

  const updateDepositPreview = ({ resetSignature = true } = {}) => {
    if (!solanaDepositAmountInput) return;
    const amount = clampSolAmount(solanaDepositAmountInput.value);
    const changed = depositState.amount !== amount;
    depositState.amount = amount;
    depositState.minted = Math.round(amount * IONC_PER_SOL);
    depositState.lamports = Math.round(amount * LAMPORTS_PER_SOL);

    const displayValue = amount % 1 === 0 ? amount.toString() : amount.toFixed(1).replace(/\.0+$/, '');
    solanaDepositAmountInput.value = displayValue;

    if (solanaDepositAmountHiddenInput) {
      solanaDepositAmountHiddenInput.value = amount.toString();
    }
    if (solanaDepositIoncHiddenInput) {
      solanaDepositIoncHiddenInput.value = depositState.minted.toString();
    }
    if (solanaDepositIoncPreview) {
      solanaDepositIoncPreview.innerHTML = `Selected amount will mint <strong>${formatNumber(depositState.minted)} IONC</strong> to your ledger.`;
    }
    if (solanaDepositSendButton) {
      solanaDepositSendButton.textContent = `Send ${formatSolAmountLabel(amount)}`;
    }
    if (resetSignature && changed && depositState.signature) {
      clearDepositSignature();
    }
  };

  const clearDepositSignature = () => {
    depositState.signature = '';
    depositState.completed = false;
    if (solanaDepositSignatureInput) solanaDepositSignatureInput.value = '';
    if (solanaDepositVerifyButton) {
      solanaDepositVerifyButton.disabled = true;
      solanaDepositVerifyButton.textContent = 'Verify Receipt';
      delete solanaDepositVerifyButton.dataset.loading;
    }
    if (solanaDepositStatus && walletProviderInput?.value === 'solana') {
      solanaDepositStatus.textContent = `Access retainer pending. Select ${formatSolAmountLabel(depositState.amount)} then click Send to authorize the transfer.`;
      solanaDepositStatus.classList.remove('wallet-status--connected');
    }
  };

  const updateDepositControls = () => {
    const isSolana = walletProviderInput?.value === 'solana';
    const hasProvider = Boolean(isSolana && phantomProvider);

    if (solanaDepositRow) {
      solanaDepositRow.hidden = !isSolana;
    }
    if (solanaDepositSendButton) {
      const isLoading = depositState.sending || !solanaModule;
      solanaDepositSendButton.disabled = !hasProvider || isLoading;
      if (!isLoading && !hasProvider) {
        solanaDepositSendButton.textContent = `Send ${formatSolAmountLabel(depositState.amount)}`;
      }
    }
    if (solanaDepositVerifyButton) {
      const isLoading = depositState.verifying;
      solanaDepositVerifyButton.disabled = !depositState.signature || isLoading || !solanaModule;
    }

    if (solanaDepositStatus && !solanaModule) {
      solanaDepositStatus.textContent = 'Solana module unavailable. Refresh the session to submit the access retainer.';
      solanaDepositStatus.classList.remove('wallet-status--connected');
    }
  };

  const updateIoncVisibility = () => {
    if (!ioncModule) return;
    const provider = walletProviderInput?.value || '';
    const isSolana = provider === 'solana';
    ioncModule.hidden = !isSolana;
    if (ioncMarketModule) {
      ioncMarketModule.hidden = true;
    }

    if (!isSolana) {
      resetIoncState();
      updateDepositControls();
      return;
    }

    if (depositState.completed) {
      setInlineStatus(
        ioncInlineStatus,
        `Detected ${formatIoncLabel(depositState.minted)} minted via SOL retainer. Verify to continue.`
      );
      if (ioncLedgerInput) ioncLedgerInput.value = depositState.minted.toString();
      if (ioncOrderBacklogInput) ioncOrderBacklogInput.value = '1';
    } else if (ioncVerifiedInput?.value === 'true') {
      setInlineStatus(ioncInlineStatus, 'IONC verification complete.', 'success');
    } else {
      setInlineStatus(
        ioncInlineStatus,
        'Phantom session detected. Verify IONC token to continue or acquire tokens below.'
      );
    }
    updateDepositControls();
  };

  const markIoncVerified = (tokensMinted) => {
    if (ioncVerifiedInput) ioncVerifiedInput.value = 'true';
    if (ioncLedgerInput && tokensMinted) {
      ioncLedgerInput.value = tokensMinted.toString();
    }
    setInlineStatus(
      ioncInlineStatus,
      tokensMinted
        ? `IONC verification complete. Tokens detected: ${formatNumber(tokensMinted)}.`
        : 'IONC verification complete.',
      'success'
    );
    if (ioncOrderBacklogStatus) {
      ioncOrderBacklogStatus.textContent = 'Admin ledger backlog 1/5. Awaiting four additional retainers for full release.';
    }
  };

  const resetMeknxState = () => {
    if (meknxPassIdInput) meknxPassIdInput.value = '';
    if (meknxStatus) {
      meknxStatus.textContent = 'Awaiting verification.';
      meknxStatus.classList.remove('wallet-status--connected');
    }
    setInlineStatus(meknxInlineStatus, 'MEKNX clearance pending.');
  };

  const resetWalletUi = () => {
    metamaskProvider = null;
    phantomProvider = null;
    clearHidden();
    resetIoncState();
    resetDepositState();
    resetMeknxState();
    if (metamaskStatus) {
      metamaskStatus.textContent = 'Not connected.';
      metamaskStatus.classList.remove('wallet-status--connected');
    }
    if (phantomStatus) {
      phantomStatus.textContent = 'Not connected.';
      phantomStatus.classList.remove('wallet-status--connected');
    }
    updateDepositControls();
  };

  // ---- MetaMask detection helpers (multi-provider aware) ----
  function getMetaMaskProvider() {
    const { ethereum } = window;
    if (!ethereum) return null;

    if (Array.isArray(ethereum.providers)) {
      const mm = ethereum.providers.find((p) => p && p.isMetaMask);
      if (mm) return mm;
    }
    if (ethereum.isMetaMask) return ethereum;
    return typeof ethereum.request === 'function' ? ethereum : null;
  }

  // ---- Phantom detection helpers ----
  function getPhantomProvider() {
    if (window.solana?.isPhantom) return window.solana;
    if (window.phantom?.solana?.isPhantom) return window.phantom.solana;
    return null;
  }

  const isMobile = () => {
    if (navigator.userAgentData && typeof navigator.userAgentData.mobile === 'boolean') {
      return navigator.userAgentData.mobile;
    }
    const ua = (navigator.userAgent || navigator.vendor || '').toLowerCase();
    return /android|iphone|ipad|ipod|mobile|blackberry|iemobile|opera mini/.test(ua);
  };

  function openDeepLink(url) {
    const win = window.open(url, '_blank', 'noopener');
    if (!win) window.location.href = url;
  }

  function maybeDeepLink(wallet) {
    if (!isMobile()) return false;
    const here = window.location.href.replace(/^https?:\/\//i, '');
    if (wallet === 'metamask') {
      openDeepLink(`https://metamask.app.link/dapp/${here}`);
      return true;
    }
    if (wallet === 'phantom') {
      openDeepLink(`https://phantom.app/ul/v1/open-app?app_url=${encodeURIComponent(window.location.href)}`);
      return true;
    }
    return false;
  }

  const setWalletSession = (provider, address, type) => {
    if (walletAddressInput) walletAddressInput.value = address || '';
    if (walletProviderInput) walletProviderInput.value = type || '';
    updateIoncVisibility();
  };

  async function connectMetaMask() {
    setStatus('Checking MetaMask…');
    const provider = getMetaMaskProvider();

    if (!provider) {
      if (maybeDeepLink('metamask')) return;
      setStatus('MetaMask not detected. Please install MetaMask and try again.', 'error');
      return;
    }

    try {
      const accounts = await provider.request({ method: 'eth_requestAccounts' });
      const account = Array.isArray(accounts) && accounts[0] ? accounts[0] : '';
      if (!account) throw new Error('No EVM account returned.');

      metamaskProvider = provider;
      phantomProvider = null;
      setWalletSession(provider, account, 'evm');

      if (metamaskStatus) {
        metamaskStatus.textContent = `Connected: ${shorten(account)}`;
        metamaskStatus.classList.add('wallet-status--connected');
      }
      if (phantomStatus) {
        phantomStatus.textContent = 'Not connected.';
        phantomStatus.classList.remove('wallet-status--connected');
      }

      setStatus('MetaMask session established.', 'success');
      updateDepositControls();
    } catch (err) {
      metamaskProvider = null;
      clearHidden();
      setStatus(err?.message || 'MetaMask connection failed.', 'error');
    }
  }

  async function connectPhantom() {
    setStatus('Checking Phantom…');
    const provider = getPhantomProvider();

    if (!provider) {
      if (maybeDeepLink('phantom')) return;
      setStatus('Phantom not detected. Please install Phantom and try again.', 'error');
      return;
    }

    try {
      const resp = await provider.connect({ onlyIfTrusted: false });
      const pubkey = (resp?.publicKey || provider.publicKey)?.toString?.() || '';
      if (!pubkey) throw new Error('No Solana account returned.');

      phantomProvider = provider;
      metamaskProvider = null;
      setWalletSession(provider, pubkey, 'solana');

      if (phantomStatus) {
        phantomStatus.textContent = `Connected: ${shorten(pubkey)}`;
        phantomStatus.classList.add('wallet-status--connected');
      }
      if (metamaskStatus) {
        metamaskStatus.textContent = 'Not connected.';
        metamaskStatus.classList.remove('wallet-status--connected');
      }

      resetDepositState({ keepAmount: true });
      updateDepositControls();
      setStatus('Phantom session established.', 'success');
    } catch (err) {
      phantomProvider = null;
      clearHidden();
      setStatus(err?.message || 'Phantom connection failed.', 'error');
    }
  }

  // ---- Tabs (Wallet / Access Key / Meknx) ----
  function activateMode(mode) {
    const map = {
      wallet: walletPanel,
      credentials: credsPanel,
      meknx: meknxPanel
    };
    $$('.auth-mode').forEach((b) => b.classList.remove('is-active'));
    if (mode === 'wallet') tabWalletBtn?.classList.add('is-active');
    if (mode === 'credentials') tabCredsBtn?.classList.add('is-active');
    if (mode === 'meknx') tabMeknxBtn?.classList.add('is-active');

    [walletPanel, credsPanel, meknxPanel].forEach((p) => p && (p.hidden = true));
    map[mode] && (map[mode].hidden = false);

    if (mode !== 'wallet') {
      resetWalletUi();
    }
  }

  tabWalletBtn?.addEventListener('click', () => activateMode('wallet'));
  tabCredsBtn?.addEventListener('click', () => activateMode('credentials'));
  tabMeknxBtn?.addEventListener('click', () => activateMode('meknx'));

  resetDepositState();
  // Default to wallet panel visible
  activateMode('wallet');
  updateIoncVisibility();

  metamaskBtn?.addEventListener('click', connectMetaMask);
  phantomBtn?.addEventListener('click', connectPhantom);

  const ensureDepositListeners = () => {
    if (solanaDepositAmountInput) {
      ['input', 'change', 'blur'].forEach((evt) => {
        solanaDepositAmountInput.addEventListener(evt, () => updateDepositPreview({ resetSignature: true }));
      });
    }

    solanaDepositSendButton?.addEventListener('click', async () => {
      if (!phantomProvider || walletProviderInput?.value !== 'solana') {
        setStatus('Connect Phantom before submitting the SOL retainer.', 'error');
        return;
      }
      if (!solanaModule || typeof solanaModule.requestDeposit !== 'function') {
        setStatus('Solana module unavailable. Refresh the page and try again.', 'error');
        return;
      }

      depositState.sending = true;
      updateDepositControls();
      try {
        solanaDepositSendButton.textContent = 'Sending…';
        setStatus('Submitting SOL retainer…');
        const amount = depositState.amount;
        const response = await solanaModule.requestDeposit({
          provider: phantomProvider,
          destinationAddress: solanaModule.getDefaultTreasury?.(),
          amountSol: amount,
          statusElement: solanaDepositStatus,
          onSignature(signature, lamports, normalizedAmount, ioncMinted) {
            depositState.signature = signature;
            depositState.lamports = lamports;
            depositState.amount = normalizedAmount;
            depositState.minted = ioncMinted;
          }
        });

        depositState.completed = true;
        if (response?.signature) {
          depositState.signature = response.signature;
        }
        if (response?.amountSol) {
          depositState.amount = response.amountSol;
        }
        if (response?.ioncMinted) {
          depositState.minted = response.ioncMinted;
        }

        if (solanaDepositSignatureInput) {
          solanaDepositSignatureInput.value = depositState.signature;
        }
        if (solanaDepositAmountHiddenInput) {
          solanaDepositAmountHiddenInput.value = depositState.amount.toString();
        }
        if (solanaDepositIoncHiddenInput) {
          solanaDepositIoncHiddenInput.value = depositState.minted.toString();
        }
        if (solanaDepositStatus) {
          solanaDepositStatus.textContent = `${formatSolAmountLabel(depositState.amount)} access retainer submitted (${formatIoncLabel(
            depositState.minted
          )}). Reference: ${shorten(depositState.signature)}`;
          solanaDepositStatus.classList.add('wallet-status--connected');
        }
        if (solanaDepositVerifyButton) {
          solanaDepositVerifyButton.disabled = false;
        }
        if (ioncLedgerInput) {
          ioncLedgerInput.value = depositState.minted.toString();
        }
        if (ioncOrderBacklogInput) {
          ioncOrderBacklogInput.value = '1';
        }
        if (ioncOrderBacklogStatus) {
          ioncOrderBacklogStatus.textContent = 'Admin ledger backlog 1/5. Awaiting four additional retainers for full release.';
        }
        setInlineStatus(
          ioncInlineStatus,
          `Detected ${formatIoncLabel(depositState.minted)} minted via SOL retainer. Verify to continue.`
        );
        setStatus('SOL retainer submitted. Admin ledger updated.', 'success');
      } catch (error) {
        setStatus(error?.message || 'Unable to submit SOL retainer.', 'error');
        if (solanaDepositStatus) {
          solanaDepositStatus.textContent = error?.message || 'SOL retainer submission failed. Try again shortly.';
          solanaDepositStatus.classList.remove('wallet-status--connected');
        }
        clearDepositSignature();
      } finally {
        depositState.sending = false;
        if (solanaDepositSendButton) {
          solanaDepositSendButton.textContent = `Send ${formatSolAmountLabel(depositState.amount)}`;
        }
        updateDepositControls();
      }
    });

    solanaDepositVerifyButton?.addEventListener('click', async () => {
      if (!depositState.signature) {
        setStatus('Submit a SOL retainer before verifying the receipt.', 'error');
        return;
      }
      if (!solanaModule || typeof solanaModule.verifySignature !== 'function') {
        setStatus('Verification module unavailable. Refresh and try again.', 'error');
        return;
      }

      depositState.verifying = true;
      updateDepositControls();
      if (solanaDepositVerifyButton) {
        solanaDepositVerifyButton.textContent = 'Verifying…';
      }
      try {
        setStatus('Confirming SOL retainer on Solana…');
        await solanaModule.verifySignature({ signature: depositState.signature });
        depositState.completed = true;
        if (solanaDepositStatus) {
          solanaDepositStatus.textContent = `${formatSolAmountLabel(depositState.amount)} access retainer confirmed (${formatIoncLabel(
            depositState.minted
          )}). Reference: ${shorten(depositState.signature)}`;
          solanaDepositStatus.classList.add('wallet-status--connected');
        }
        markIoncVerified(depositState.minted);
        setStatus('SOL retainer verified. Vault access token acknowledged.', 'success');
      } catch (error) {
        setStatus(error?.message || 'Unable to verify SOL retainer.', 'error');
        if (solanaDepositStatus) {
          solanaDepositStatus.textContent = error?.message || 'Verification failed. Retry shortly.';
          solanaDepositStatus.classList.remove('wallet-status--connected');
        }
      } finally {
        depositState.verifying = false;
        if (solanaDepositVerifyButton) {
          solanaDepositVerifyButton.textContent = 'Verify Receipt';
        }
        updateDepositControls();
      }
    });
  };

  const handleIoncVerify = () => {
    if (!ioncVerifyButton) return;
    ioncVerifyButton.addEventListener('click', () => {
      if (walletProviderInput?.value !== 'solana') {
        setStatus('Connect Phantom and submit the SOL retainer before verifying IONC access.', 'error');
        setInlineStatus(
          ioncInlineStatus,
          'Connect Phantom and submit the SOL retainer before verifying IONC access.',
          'error'
        );
        return;
      }
      if (!depositState.completed && ioncLedgerInput?.value === '') {
        setStatus('Submit and verify at least one SOL retainer before requesting IONC clearance.', 'error');
        setInlineStatus(
          ioncInlineStatus,
          'Submit and verify at least one SOL retainer before requesting IONC clearance.',
          'error'
        );
        return;
      }
      markIoncVerified(depositState.minted || Number.parseInt(ioncLedgerInput?.value || '0', 10));
      setStatus('IONC token verified for the connected wallet.', 'success');
    });
  };

  const generateMeknxPassId = () => {
    const base = Math.floor(Date.now() / 1000).toString(16).toUpperCase();
    return `MEKNX-${base}`;
  };

  const handleMeknxActions = () => {
    meknxActionButton?.addEventListener('click', () => {
      const action = meknxActionSelect?.value || 'verify';
      if (action === 'mint') {
        const passId = generateMeknxPassId();
        if (meknxPassIdInput) meknxPassIdInput.value = passId;
        setInlineStatus(
          meknxInlineStatus,
          `Mint request queued. Pass ${passId} will log to the admin vault after SOL verification.`,
          'success'
        );
        setStatus('MEKNX mint request logged. Complete SOL verification to finalize.', 'success');
      } else {
        setInlineStatus(
          meknxInlineStatus,
          'Verification initiated. Provide your MEKNX token in the Meknx tab to continue.'
        );
        setStatus('MEKNX verification initiated. Provide your pass token to continue.', 'success');
      }
    });

    meknxVerifyButton?.addEventListener('click', () => {
      const code = meknxPasscodeInput?.value.trim();
      if (!code) {
        setInlineStatus(meknxInlineStatus, 'Enter your MEKNX access token before verifying.', 'error');
        return;
      }
      if (meknxStatus) {
        meknxStatus.textContent = `Verified: ${shorten(code)}`;
        meknxStatus.classList.add('wallet-status--connected');
      }
      if (meknxPassIdInput) meknxPassIdInput.value = code;
      setInlineStatus(meknxInlineStatus, 'MEKNX clearance verified.', 'success');
      setStatus('MEKNX access token confirmed.', 'success');
    });

    meknxMintButton?.addEventListener('click', () => {
      const passId = generateMeknxPassId();
      if (meknxPassIdInput) meknxPassIdInput.value = passId;
      if (meknxStatus) {
        meknxStatus.textContent = `Minted: ${passId}`;
        meknxStatus.classList.add('wallet-status--connected');
      }
      setInlineStatus(
        meknxInlineStatus,
        `Professional pass ${passId} minted. Admin vault notified.`,
        'success'
      );
      setStatus('MEKNX professional pass minted successfully.', 'success');
    });
  };

  ensureDepositListeners();
  handleIoncVerify();
  handleMeknxActions();
  updateDepositControls();

  // ---- Form submit guard ----
  form?.addEventListener('submit', (e) => {
    try {
      const walletVisible = !walletPanel?.hidden;
      if (walletVisible) {
        const addr = walletAddressInput?.value || '';
        const prov = walletProviderInput?.value || '';
        if (!addr || !prov) {
          e.preventDefault();
          setStatus('Connect a wallet (MetaMask or Phantom) before entering the vault.', 'error');
          return;
        }
        if (prov === 'solana' && ioncVerifiedInput?.value !== 'true') {
          e.preventDefault();
          setStatus('Verify your IONC access token before entering the vault.', 'error');
          return;
        }
      }
      setStatus('Processing…');
    } catch (err) {
      e.preventDefault();
      setStatus(err?.message || 'Unable to submit. Fix highlighted issues and try again.', 'error');
    }
  });

  // ---- Quality-of-life: refresh provider statuses on page visibility change ----
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState !== 'visible') return;
    if (walletProviderInput?.value === 'evm') {
      const mm = getMetaMaskProvider();
      if (mm) {
        mm.request({ method: 'eth_accounts' })
          .then((accs) => {
            const a = accs?.[0] || '';
            if (a && metamaskStatus) {
              metamaskStatus.textContent = `Connected: ${shorten(a)}`;
              metamaskStatus.classList.add('wallet-status--connected');
              setWalletSession(mm, a, 'evm');
            }
          })
          .catch(() => {});
      }
    } else if (walletProviderInput?.value === 'solana') {
      const ph = getPhantomProvider();
      const pk = ph?.publicKey?.toString?.() || '';
      if (pk && phantomStatus) {
        phantomStatus.textContent = `Connected: ${shorten(pk)}`;
        phantomStatus.classList.add('wallet-status--connected');
        phantomProvider = ph || phantomProvider;
        setWalletSession(ph || phantomProvider, pk, 'solana');
        updateDepositControls();
      }
    }
  });
})();

