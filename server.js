import express from 'express';
import path from 'path';
import { promises as fs } from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const app = express();
const PORT = process.env.PORT || 3000;

// Serve static assets like CSS and HTML files
app.use(express.static(__dirname));

async function getHtmlFiles(dir) {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  let files = [];
  for (const entry of entries) {
    if (entry.name.startsWith('.')) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (['node_modules', 'scripts'].includes(entry.name)) continue;
      files = files.concat(await getHtmlFiles(full));
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith('.html')) {
      files.push(full);
    }
  }
  return files;
}

async function getTitle(filePath) {
  const content = await fs.readFile(filePath, 'utf8');
  const match = content.match(/<title>([^<]*)<\/title>/i);
  return match ? match[1].trim() : path.basename(filePath);
}

app.get('/', async (req, res) => {
  try {
    const files = await getHtmlFiles(__dirname);
    const items = await Promise.all(
      files.map(async (f) => ({
        rel: path.relative(__dirname, f),
        title: await getTitle(f)
      }))
    );
    items.sort((a, b) => a.title.localeCompare(b.title));
    const list = items
      .map((i) => `<div class="card"><h2>${i.title}</h2><a class="btn" href="/view?f=${encodeURIComponent(i.rel)}">View</a></div>`)
      .join('');
    res.send(`<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Brochures</title><link href="https://fonts.googleapis.com/css?family=Montserrat:700,400&display=swap" rel="stylesheet"><link rel="stylesheet" href="/styles.css"></head><body><header><h1>Brochures</h1><div class="cta-buttons"><a class="btn" href="/webpage.html">Home</a></div></header><div class="grid">${list}</div><footer id="contact"><h3>Ready to Energize Your Future?</h3><p>Contact Ioncore Energy today for partnership, investment, or project inquiries.</p><a href="mailto:info@ioncoreenergy.com" class="footer-btn">Contact Us</a><div class="copyright">&copy; <script>document.write(new Date().getFullYear())</script> Ioncore Energy. All rights reserved.</div></footer></body></html>`);
  } catch (err) {
    res.status(500).send('Failed to load index');
  }
});

app.get('/view', async (req, res) => {
  const rel = req.query.f;
  if (!rel) return res.status(400).send('Missing file');
  const filePath = path.join(__dirname, rel);
  if (!filePath.startsWith(__dirname)) return res.status(400).send('Invalid path');
  try {
    const html = await fs.readFile(filePath, 'utf8');
    const title = await getTitle(filePath);
    res.send(`<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>${title}</title><link href="https://fonts.googleapis.com/css?family=Montserrat:700,400&display=swap" rel="stylesheet"><link rel="stylesheet" href="/styles.css"></head><body><header><div class="cta-buttons"><a class="btn" href="/">Back</a></div></header>${html}<footer id="contact"><h3>Ready to Energize Your Future?</h3><p>Contact Ioncore Energy today for partnership, investment, or project inquiries.</p><a href="mailto:info@ioncoreenergy.com" class="footer-btn">Contact Us</a><div class="copyright">&copy; <script>document.write(new Date().getFullYear())</script> Ioncore Energy. All rights reserved.</div></footer></body></html>`);
  } catch {
    res.status(404).send('Not found');
  }
});

app.listen(PORT, () => {
  console.log(`Server listening on http://localhost:${PORT}`);
});

