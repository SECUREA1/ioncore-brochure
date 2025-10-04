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

`track.py` now requires ownership of a specific NFT before the UI loads. The gate is verified
through Alchemy's NFT API. Configure the following environment variables before launching the
application:

| Variable | Purpose |
| --- | --- |
| `NFT_GATE_ENABLED` | Set to `0`, `false`, or `no` to bypass the gate (defaults to enabled). |
| `NFT_GATE_CONTRACT_ADDRESS` | Contract address of the NFT collection required for access. |
| `NFT_GATE_ALCHEMY_API_KEY` | Alchemy API key with NFT access permissions. |
| `NFT_GATE_NETWORK` | (Optional) Network slug for the Alchemy endpoint (defaults to `eth-mainnet`). |
| `NFT_GATE_WALLET_ADDRESS` | (Optional) Wallet address to verify. If omitted, the program prompts for one. |

At startup the script calls Alchemy's `getNFTs` endpoint to confirm the provided wallet holds at
least one token from the specified contract. If verification fails, the program exits after
displaying an error message.
