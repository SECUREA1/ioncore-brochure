(() => {
  const uploadsList = document.getElementById('marketplace-uploads');
  const bidsList = document.getElementById('marketplace-bids');
  if (!uploadsList || !bidsList || typeof fetch !== 'function') {
    return;
  }

  const uploadForm = document.getElementById('marketplace-upload-form');
  const bidForm = document.getElementById('marketplace-bid-form');
  const feedStatus = document.getElementById('marketplace-feed-status');
  const uploadStatus = uploadForm ? uploadForm.querySelector('.marketplace-status') : null;
  const bidStatus = bidForm ? bidForm.querySelector('.marketplace-status') : null;
  const assetSelect = bidForm ? bidForm.querySelector('select[name="assetId"]') : null;
  const bidSubmit = bidForm ? bidForm.querySelector('button[type="submit"]') : null;

  const state = {
    uploads: [],
    bids: []
  };

  const dedupeById = (records) => {
    const map = new Map();
    for (const record of records) {
      if (!record || typeof record !== 'object') continue;
      const key = typeof record.id === 'string' && record.id ? record.id : JSON.stringify(record);
      map.set(key, record);
    }
    return Array.from(map.values());
  };

  const setStatus = (element, message, variant) => {
    if (!element) return;
    element.textContent = message || '';
    element.dataset.state = variant || '';
  };

  const formatDate = (value) => {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString();
  };

  const formatAmount = (amount, currency) => {
    if (typeof amount !== 'number' || !Number.isFinite(amount)) {
      return '—';
    }
    const formatted = amount.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 });
    return `${currency || ''} ${formatted}`.trim();
  };

  const updateAssetOptions = () => {
    if (!assetSelect) {
      return;
    }
    const currentValue = assetSelect.value;
    assetSelect.innerHTML = '';
    if (!state.uploads.length) {
      const option = document.createElement('option');
      option.value = '';
      option.textContent = 'No uploads available yet';
      assetSelect.appendChild(option);
      assetSelect.disabled = true;
      if (bidSubmit) bidSubmit.disabled = true;
      return;
    }

    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = 'Select an upload';
    assetSelect.appendChild(placeholder);

    for (const upload of state.uploads) {
      const option = document.createElement('option');
      option.value = upload.id;
      option.textContent = upload.title || upload.id;
      if (currentValue && currentValue === upload.id) option.selected = true;
      assetSelect.appendChild(option);
    }

    assetSelect.disabled = false;
    if (bidSubmit) bidSubmit.disabled = false;
  };

  const renderUploads = () => {
    uploadsList.innerHTML = '';
    if (!state.uploads.length) {
      const empty = document.createElement('div');
      empty.className = 'marketplace-empty';
      empty.textContent = 'No marketplace uploads yet.';
      uploadsList.appendChild(empty);
      return;
    }

    for (const upload of state.uploads) {
      const card = document.createElement('article');
      card.className = 'marketplace-item';

      const heading = document.createElement('h4');
      heading.textContent = upload.title || 'Marketplace upload';
      card.appendChild(heading);

      const meta = document.createElement('div');
      meta.className = 'marketplace-item__meta';

      if (upload.username) {
        const creatorSpan = document.createElement('span');
        creatorSpan.textContent = `Creator: ${upload.username}`;
        meta.appendChild(creatorSpan);
      }
      if (upload.walletAddress) {
        const walletSpan = document.createElement('span');
        walletSpan.textContent = `Wallet: ${upload.walletAddress}`;
        meta.appendChild(walletSpan);
      }

      const bidCountSpan = document.createElement('span');
      bidCountSpan.textContent = `Bids: ${upload.bidCount || 0}`;
      meta.appendChild(bidCountSpan);

      if (typeof upload.highestBidAmount === 'number' && Number.isFinite(upload.highestBidAmount)) {
        const topBidSpan = document.createElement('span');
        topBidSpan.textContent = `Top: ${formatAmount(upload.highestBidAmount, upload.highestBidCurrency)}`;
        meta.appendChild(topBidSpan);
      }
      if (upload.updatedAt) {
        const updatedSpan = document.createElement('span');
        updatedSpan.textContent = `Updated: ${formatDate(upload.updatedAt)}`;
        meta.appendChild(updatedSpan);
      }

      card.appendChild(meta);

      if (upload.description) {
        const description = document.createElement('p');
        description.textContent = upload.description;
        card.appendChild(description);
      }

      if (upload.mediaUrl) {
        const media = document.createElement('div');
        media.className = 'marketplace-item__media';
        const link = document.createElement('a');
        link.href = upload.mediaUrl;
        link.target = '_blank';
        link.rel = 'noopener';
        link.textContent = 'Open media';
        media.appendChild(link);
        card.appendChild(media);
      }

      uploadsList.appendChild(card);
    }
  };

  const renderBids = () => {
    bidsList.innerHTML = '';
    if (!state.bids.length) {
      const empty = document.createElement('div');
      empty.className = 'marketplace-empty';
      empty.textContent = 'No marketplace bids yet.';
      bidsList.appendChild(empty);
      return;
    }

    for (const bid of state.bids) {
      const card = document.createElement('article');
      card.className = 'marketplace-item';

      const heading = document.createElement('h4');
      const amountText = formatAmount(bid.amount, bid.currency);
      heading.textContent = `${amountText !== '—' ? amountText : 'Bid'} on ${bid.assetTitle || 'Marketplace upload'}`;
      card.appendChild(heading);

      const meta = document.createElement('div');
      meta.className = 'marketplace-item__meta';

      const assetSpan = document.createElement('span');
      assetSpan.textContent = `Asset: ${bid.assetTitle || bid.assetId || '—'}`;
      meta.appendChild(assetSpan);
      if (bid.bidderName) {
        const bidderSpan = document.createElement('span');
        bidderSpan.textContent = `Bidder: ${bid.bidderName}`;
        meta.appendChild(bidderSpan);
      }
      if (bid.bidderWallet) {
        const walletSpan = document.createElement('span');
        walletSpan.textContent = `Wallet: ${bid.bidderWallet}`;
        meta.appendChild(walletSpan);
      }
      if (bid.bidderContact) {
        const contactSpan = document.createElement('span');
        contactSpan.textContent = `Contact: ${bid.bidderContact}`;
        meta.appendChild(contactSpan);
      }

      const timeSpan = document.createElement('span');
      timeSpan.textContent = `Submitted: ${formatDate(bid.createdAt)}`;
      meta.appendChild(timeSpan);

      card.appendChild(meta);

      if (bid.message) {
        const message = document.createElement('p');
        message.textContent = bid.message;
        card.appendChild(message);
      }

      bidsList.appendChild(card);
    }
  };

  const refreshMarketplace = async (options = {}) => {
    const silent = Boolean(options.silent);
    if (!silent) setStatus(feedStatus, 'Synchronizing marketplace feed…', 'pending');
    try {
      const response = await fetch('/api/marketplace', { headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error('Failed to load marketplace feed');
      const payload = await response.json();
      state.uploads = dedupeById(Array.isArray(payload.uploads) ? payload.uploads : []);
      state.bids = dedupeById(Array.isArray(payload.bids) ? payload.bids : []);
      renderUploads();
      renderBids();
      updateAssetOptions();
      if (!silent) setStatus(feedStatus, 'Marketplace feed synchronized.', 'success');
      return payload;
    } catch (error) {
      console.warn('Unable to refresh marketplace feed', error);
      if (!silent) setStatus(feedStatus, 'Unable to load marketplace feed. Retry shortly.', 'error');
      throw error;
    }
  };

  if (uploadForm) {
    const uploadSubmit = uploadForm.querySelector('button[type="submit"]');
    uploadForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (uploadSubmit) {
        uploadSubmit.disabled = true;
        uploadSubmit.textContent = 'Submitting…';
      }
      setStatus(uploadStatus, 'Publishing asset to marketplace…', 'pending');

      const formData = new FormData(uploadForm);
      const payload = {
        title: String(formData.get('title') || '').trim(),
        description: String(formData.get('description') || '').trim(),
        username: String(formData.get('username') || '').trim(),
        walletAddress: String(formData.get('walletAddress') || '').trim(),
        mediaUrl: String(formData.get('mediaUrl') || '').trim(),
        contact: String(formData.get('contact') || '').trim()
      };

      if (!payload.title) {
        setStatus(uploadStatus, 'Enter a title before submitting your upload.', 'error');
        if (uploadSubmit) {
          uploadSubmit.disabled = false;
          uploadSubmit.textContent = 'Submit upload';
        }
        return;
      }

      try {
        const response = await fetch('/api/marketplace/uploads', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error((data && data.message) || 'Unable to publish upload. Retry shortly.');
        setStatus(uploadStatus, 'Upload transmitted to the Ioncore marketplace.', 'success');
        uploadForm.reset();
        await refreshMarketplace({ silent: true }).catch(() => {});
      } catch (error) {
        setStatus(uploadStatus, error.message || 'Unable to publish upload. Retry shortly.', 'error');
      } finally {
        if (uploadSubmit) {
          uploadSubmit.disabled = false;
          uploadSubmit.textContent = 'Submit upload';
        }
      }
    });
  }

  if (bidForm) {
    bidForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (!assetSelect || !assetSelect.value) {
        setStatus(bidStatus, 'Select a marketplace upload before submitting a bid.', 'error');
        return;
      }
      if (bidSubmit) {
        bidSubmit.disabled = true;
        bidSubmit.textContent = 'Submitting…';
      }
      setStatus(bidStatus, 'Registering bid with the marketplace…', 'pending');

      const formData = new FormData(bidForm);
      const payload = {
        assetId: assetSelect.value,
        bidderName: String(formData.get('bidderName') || '').trim(),
        bidderWallet: String(formData.get('bidderWallet') || '').trim(),
        amount: String(formData.get('amount') || '').trim(),
        currency: String(formData.get('currency') || '').trim().toUpperCase() || 'USD',
        contact: String(formData.get('contact') || '').trim(),
        message: String(formData.get('message') || '').trim()
      };

      if (!payload.amount) {
        setStatus(bidStatus, 'Enter a bid amount to continue.', 'error');
        if (bidSubmit) {
          bidSubmit.disabled = false;
          bidSubmit.textContent = 'Submit bid';
        }
        return;
      }

      try {
        const response = await fetch('/api/marketplace/bids', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error((data && data.message) || 'Unable to register bid. Retry shortly.');
        setStatus(bidStatus, 'Bid logged with the marketplace.', 'success');
        bidForm.reset();
        await refreshMarketplace({ silent: true }).catch(() => {});
      } catch (error) {
        setStatus(bidStatus, error.message || 'Unable to register bid. Retry shortly.', 'error');
      } finally {
        if (bidSubmit) {
          bidSubmit.disabled = state.uploads.length === 0;
          bidSubmit.textContent = 'Submit bid';
        }
      }
    });
  }

  updateAssetOptions();
  renderUploads();
  renderBids();
  refreshMarketplace().catch(() => {});

  window.setInterval(() => {
    refreshMarketplace({ silent: true }).catch(() => {});
  }, 12000);

  window.addEventListener('focus', () => {
    refreshMarketplace({ silent: true }).catch(() => {});
  });
})();
