# Ioncore Brochure

This repository contains a collection of HTML brochures. A small Express server is included so the pages can be browsed locally or deployed on Render.

The public homepage lives at `/` and links to an admin-only index of every HTML file. That listing resides at `/admin` and is protected with Basic Auth (`admin`/`1234`). All brochure HTML files—even those not included on the old `index.html` page—require the same credentials. Selecting a link opens the brochure wrapped with a "Back" button so you can return to the index, and the browser tab title reflects the brochure's own title.

## Development

Install dependencies and start the server:

```bash
npm install
npm start
```

Visit <http://localhost:3000> for the homepage. Click **All HTML Files** and sign in with the admin credentials to browse the full index of brochures.

## Live engagement counters

The homepage now displays real-time counters showing how many visitors are viewing the experience and the total number of visits during the current server session. The Express server provides `/metrics`, `/metrics/view`, and `/metrics/leave` endpoints that keep these numbers in sync. When the homepage loads it registers a new view, periodically refreshes the counts, and signals when the visitor departs so the live total stays accurate.

## Images

Some pages reference images hosted remotely. To download those images for offline use and rewrite the HTML to reference local copies, run:

```bash
npm run fetch-images
```

Images will be placed under `pages/images`.

## Sentinel Track Console (track.py)

`track.py` now requires ownership of a specific token before the UI loads. Access can be
granted via an Ethereum-compatible wallet (MetaMask/WalletConnect) or a Solana wallet
(Phantom). A desktop wallet-connect bridge is bundled directly into the login flow so users can
authorize access without manually pasting addresses. Configure the following environment
variables before launching the application:

| Variable | Purpose |
| --- | --- |
| `NFT_GATE_ENABLED` | Set to `0`, `false`, or `no` to bypass the gate (defaults to enabled). |
| `NFT_GATE_CONTRACT_ADDRESS` | Contract address of the NFT collection required for EVM access. |
| `NFT_GATE_ALCHEMY_API_KEY` | Alchemy API key with NFT access permissions (required for EVM checks). |
| `NFT_GATE_NETWORK` | (Optional) Network slug for the Alchemy endpoint (defaults to `eth-mainnet`). |
| `NFT_GATE_SOLANA_MINT_ADDRESS` | (Optional) Token mint required for Solana/Phantom access. |
| `NFT_GATE_SOLANA_RPC` | (Optional) Solana RPC endpoint used to query token balances. |
| `NFT_GATE_WALLET_ADDRESS` | (Optional) Wallet address to verify. If omitted, the program opens the wallet connect dialog. |
| `NFT_GATE_CHAIN` | (Optional) Default chain to pre-select in the wallet dialog (`evm` or `solana`). |
| `NFT_GATE_WALLET_CHAIN` | (Optional) Chain to assume when `NFT_GATE_WALLET_ADDRESS` is preconfigured. |

At startup the script either uses the configured wallet address or opens the wallet connect
dialog. When the user connects MetaMask the bridge captures their address and verifies the
required contract through Alchemy's `getNFTs` endpoint. If Phantom is connected the script checks
the configured Solana mint via `getTokenAccountsByOwner`. If verification fails, the program exits
after displaying an error message.
