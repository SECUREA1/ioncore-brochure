import fs from 'fs';
import path from 'path';

const pagesDir = path.join(process.cwd(), 'pages');
const imagesDir = path.join(pagesDir, 'images');
fs.mkdirSync(imagesDir, { recursive: true });

for (const file of fs.readdirSync(pagesDir)) {
  if (!file.endsWith('.html')) continue;
  const fullPath = path.join(pagesDir, file);
  let html = fs.readFileSync(fullPath, 'utf8');
  const matches = [...html.matchAll(/<img[^>]+src="([^"]+)"[^>]*>/g)];
  for (const m of matches) {
    const url = m[1];
    if (!url.startsWith('http')) continue;
    const fileName = path.basename(new URL(url).pathname);
    const dest = path.join(imagesDir, fileName);
    try {
      const res = await fetch(url);
      if (res.ok) {
        const buf = Buffer.from(await res.arrayBuffer());
        fs.writeFileSync(dest, buf);
        html = html.replace(url, `images/${fileName}`);
      }
    } catch (err) {
      console.error('Failed to fetch', url, err);
    }
  }
  fs.writeFileSync(fullPath, html);
}
