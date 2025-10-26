(() => {
  const DEFAULT_SOLANA_RPC = 'https://api.mainnet-beta.solana.com';
  const DEFAULT_TREASURY = '9U7yidFgkYrzNRMx8BsXB14F6gttxyPjdvVSdGJySLvT';
  const LAMPORTS_PER_SOL = 1_000_000_000;
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

    const normalizedAmount = Number.isFinite(amountSol) && amountSol > 0 ? amountSol : 1;
    const lamports = Math.max(Math.round(normalizedAmount * LAMPORTS_PER_SOL), LAMPORTS_PER_SOL);

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
      statusElement.textContent = 'Presenting 1 SOL access retainer for approval…';
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
      onSignature(signature, lamports);
    }

    if (statusElement) {
      statusElement.textContent = `1 SOL access retainer submitted. Reference: ${shortenSignature(signature)}`;
      statusElement.classList.add('wallet-status--connected');
    }

    return { signature, lamports, destination: treasury.toBase58() };
  };

  window.IoncoreSolana = {
    loadSolanaWeb3,
    requestDeposit,
    LAMPORTS_PER_SOL,
    getDefaultTreasury: getTreasuryAddress,
    getDefaultRpc: getRpcEndpoint,
    shortenSignature
  };
})();
