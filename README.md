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

## Ioncore Apes token gate

Every brochure is wrapped with a MetaMask-based access gate. Visitors must connect a wallet that holds the Ioncore Apes token before the overlay will clear. Configure the gate through environment variables when starting the Express server:

| Variable | Description |
| --- | --- |
| `IONCORE_APES_CONTRACT` | Optional. ERC-721 or ERC-1155 contract address that represents Ioncore Apes membership (defaults to `0x495f947276749ce646f68ac8c248420045cb7b5e`). |
| `IONCORE_APES_CHAIN_ID` | Optional. Chain ID in hex (defaults to `0x1` for Ethereum mainnet). |
| `IONCORE_APES_TOKEN_TYPE` | Optional. Either `erc721` (default) or `erc1155`. |
| `IONCORE_APES_TOKEN_ID` | Optional. Required for ERC-1155 gating; for ERC-721 it restricts access to a specific token ID. |
| `IONCORE_APES_MIN_BALANCE` | Optional. Minimum token balance required (defaults to `1`). |

Example:

```bash
IONCORE_APES_CONTRACT=0x1234567890abcdef1234567890abcdef12345678 npm start
```

With the variables set, the injected gate requests MetaMask access, checks the configured network, and verifies the holder’s token balance before revealing the brochure content.

## Images

Some pages reference images hosted remotely. To download those images for offline use and rewrite the HTML to reference local copies, run:

```bash
npm run fetch-images
```

Images will be placed under `pages/images`.
