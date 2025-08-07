# Ioncore Brochure

This repository contains a collection of HTML brochures. A small Express server is included so the pages can be browsed locally or deployed on Render.

The server's root page lists every HTML file along with the `<title>` found inside each page. Selecting a link opens the brochure wrapped with a "Back" button so you can return to the index, and the browser tab title reflects the brochure's own title.

## Development

Install dependencies and start the server:

```bash
npm install
npm start
```

Visit <http://localhost:3000> to view an index of all brochure pages.

## Images

Some pages reference images hosted remotely. To download those images for offline use and rewrite the HTML to reference local copies, run:

```bash
npm run fetch-images
```

Images will be placed under `pages/images`.
