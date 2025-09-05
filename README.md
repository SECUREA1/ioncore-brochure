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

## Images

Some pages reference images hosted remotely. To download those images for offline use and rewrite the HTML to reference local copies, run:

```bash
npm run fetch-images
```

Images will be placed under `pages/images`.
