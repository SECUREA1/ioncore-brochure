(() => {
  const DEFAULT_SOLANA_RPC = 'https://api.mainnet-beta.solana.com';
  const DEFAULT_TREASURY = '9U7yidFgkYrzNRMx8BsXB14F6gttxyPjdvVSdGJySLvT';
  const LAMPORTS_PER_SOL = 1_000_000_000;
  const MIN_SOL_DEPOSIT_SOL = 0.1;
  const MAX_SOL_DEPOSIT_SOL = 1000;
  const IONC_PER_SOL = 1000;
  const WEB3_CDN_SRC = 'https://unpkg.com/@solana/web3.js@1.91.9/lib/index.iife.min.js';

  let solanaLoaderPromise = null;

  const getTreasuryAddress = () => {
    if (typeof window !== 'undefined') {
      const override = window.IONCORE_SOL_TREASURY;
      if (typeof override === 'string' && override.trim().length > 0) {
        return override.trim();
      }
    }
    return DEFAULT_TREASURY;
  };

  const getRpcEndpoint = () => {
    if (typeof window !== 'undefined') {
      const override = window.IONCORE_SOL_RPC;
      if (typeof override === 'string' && override.trim().length > 0) {
        return override.trim();
      }
    }
    return DEFAULT_SOLANA_RPC;
  };

  const loadSolanaWeb3 = async () => {
    if (typeof window === 'undefined') {
      throw new Error('Solana web3 is unavailable in this environment.');
    }

    if (window.solanaWeb3) {
      return window.solanaWeb3;
    }

    if (!solanaLoaderPromise) {
      solanaLoaderPromise = new Promise((resolve, reject) => {
        if (window.solanaWeb3) {
          resolve(window.solanaWeb3);
          return;
        }

        const script = document.createElement('script');
        script.src = WEB3_CDN_SRC;
        script.async = true;
        script.onload = () => {
          if (window.solanaWeb3) {
            resolve(window.solanaWeb3);
          } else {
            reject(new Error('Failed to initialise Solana web3 library.'));
          }
        };
        script.onerror = () => {
          reject(new Error('Unable to load Solana web3 library.'));
        };
        document.head.appendChild(script);
      });
    }

    return solanaLoaderPromise;
  };

  const shortenSignature = (value) => {
    if (!value || typeof value !== 'string' || value.length < 10) {
      return value || '';
    }
    return `${value.slice(0, 6)}…${value.slice(-6)}`;
  };

  const clampSolAmount = (value) => {
    const numeric = typeof value === 'number' ? value : Number.parseFloat(value);
    if (!Number.isFinite(numeric)) {
      return MIN_SOL_DEPOSIT_SOL;
    }
    const clamped = Math.min(Math.max(numeric, MIN_SOL_DEPOSIT_SOL), MAX_SOL_DEPOSIT_SOL);
    return Number.parseFloat(clamped.toFixed(3));
  };

  const formatSolAmountLabel = (value) => {
    const safeValue = clampSolAmount(value);
    const hasFraction = Math.abs(safeValue % 1) > 1e-9;
    return `${safeValue.toLocaleString('en-US', {
      minimumFractionDigits: hasFraction ? 1 : 0,
      maximumFractionDigits: 3
    })} SOL`;
  };

  const requestDeposit = async ({
    provider,
    fromAddress,
    destinationAddress,
    rpcEndpoint,
    amountSol = 1,
    statusElement,
    commitment = 'confirmed',
    onSignature
  }) => {
    if (!provider) {
      throw new Error('Phantom provider is required to submit the SOL retainer.');
    }

    const address = fromAddress || (provider.publicKey && provider.publicKey.toBase58 && provider.publicKey.toBase58());
    if (!address) {
      throw new Error('Unable to determine the connected wallet address.');
    }

    const solanaWeb3 = await loadSolanaWeb3();
    const { Connection, PublicKey, SystemProgram, Transaction } = solanaWeb3;

    const connection = new Connection(rpcEndpoint || getRpcEndpoint(), commitment);
    const fromPubkey = new PublicKey(address);
    const treasury = new PublicKey(destinationAddress || getTreasuryAddress());

    const normalizedAmount = clampSolAmount(amountSol);
    const lamports = Math.max(
      Math.round(normalizedAmount * LAMPORTS_PER_SOL),
      Math.round(MIN_SOL_DEPOSIT_SOL * LAMPORTS_PER_SOL)
    );
    const ioncMinted = Math.round(normalizedAmount * IONC_PER_SOL);
    const formattedAmount = formatSolAmountLabel(normalizedAmount);

    const latestBlockhash = await connection.getLatestBlockhash(commitment);
    const transaction = new Transaction({
      feePayer: fromPubkey,
      recentBlockhash: latestBlockhash.blockhash
    });

    transaction.add(
      SystemProgram.transfer({
        fromPubkey,
        toPubkey: treasury,
        lamports
      })
    );

    if (statusElement) {
      statusElement.textContent = `Presenting ${formattedAmount} access retainer for approval…`;
      statusElement.classList.remove('wallet-status--connected');
    }

    let signature;
    if (typeof provider.signAndSendTransaction === 'function') {
      const result = await provider.signAndSendTransaction(transaction);
      signature = typeof result === 'object' && result ? result.signature || result.txid || result : result;
    } else if (typeof provider.sendTransaction === 'function') {
      signature = await provider.sendTransaction(transaction, connection);
    } else {
      throw new Error('Connected Phantom wallet cannot submit transactions.');
    }

    if (!signature || typeof signature !== 'string') {
      throw new Error('Phantom did not return a transaction signature.');
    }

    if (statusElement) {
      statusElement.textContent = 'Awaiting confirmation from Solana validators…';
    }

    await connection.confirmTransaction(
      {
        signature,
        blockhash: latestBlockhash.blockhash,
        lastValidBlockHeight: latestBlockhash.lastValidBlockHeight
      },
      commitment
    );

    if (typeof onSignature === 'function') {
      onSignature(signature, lamports, normalizedAmount, ioncMinted);
    }

    if (statusElement) {
      statusElement.textContent = `${formattedAmount} access retainer submitted (${ioncMinted.toLocaleString(
        'en-US'
      )} IONC). Reference: ${shortenSignature(signature)}`;
      statusElement.classList.add('wallet-status--connected');
    }

    return { signature, lamports, destination: treasury.toBase58(), amountSol: normalizedAmount, ioncMinted };
  };

  const verifySignature = async ({ signature, rpcEndpoint, commitment = 'confirmed' }) => {
    if (!signature || typeof signature !== 'string') {
      throw new Error('Transaction signature is required for verification.');
    }

    const solanaWeb3 = await loadSolanaWeb3();
    const { Connection } = solanaWeb3;

    const connection = new Connection(rpcEndpoint || getRpcEndpoint(), commitment);
    const statusResponse = await connection.getSignatureStatuses([signature]);
    const status = (statusResponse && statusResponse.value && statusResponse.value[0]) || null;

    if (!status) {
      throw new Error('Transaction signature not located on Solana yet. Retry shortly.');
    }

    if (status.err) {
      throw new Error('Transaction failed verification on Solana. Resubmit the access retainer.');
    }

    return status;
  };

  window.IoncoreSolana = {
    loadSolanaWeb3,
    requestDeposit,
    verifySignature,
    LAMPORTS_PER_SOL,
    MAX_SOL_DEPOSIT_SOL,
    IONC_PER_SOL,
    getDefaultTreasury: getTreasuryAddress,
    getDefaultRpc: getRpcEndpoint,
    shortenSignature,
    formatSolAmountLabel,
    clampSolAmount
  };
})();
