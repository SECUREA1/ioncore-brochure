import fs from 'fs';
import path from 'path';
import {spawnSync} from 'child_process';

const rootDir = path.resolve(new URL('..', import.meta.url).pathname);
const htmlFiles = fs.readdirSync(rootDir).filter(f => f.endsWith('.html') && f !== 'index.html');

function escapeHtml(str) {
  return str.replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
}

const groups = {};
for (const file of htmlFiles) {
  const filePath = path.join(rootDir, file);
  const content = fs.readFileSync(filePath, 'utf8');
  const match = content.match(/<title>([^<]*)<\/title>/i);
  const title = match ? match[1].trim() : path.basename(file, '.html');
  const key = title.toLowerCase();
  if (!groups[key]) groups[key] = [];
  groups[key].push({file, title, filePath});
}

let output = `<!DOCTYPE html>\n<html>\n<head>\n<meta charset="utf-8">\n<title>Ioncore Brochure Index</title>\n<style>
body{font-family:Arial, sans-serif; margin:40px; background:#f5f5f5;}
h1{text-align:center;}
.grid{display:flex; flex-wrap:wrap; gap:20px; justify-content:center;}
.card{background:#fff; border-radius:8px; padding:20px; box-shadow:0 2px 4px rgba(0,0,0,0.1); width:260px;}
.card h2{margin-top:0;font-size:1.2em;}
.btn{display:inline-block;margin-top:10px;padding:8px 12px;background:#007bff;color:#fff;text-decoration:none;border-radius:4px;}
.btn:hover{background:#0056b3;}
.card ul{list-style:none;padding-left:0;}
.card li{margin-bottom:6px;}
details{margin-top:8px;}
</style>\n</head>\n<body>\n<h1>Ioncore Brochure Index</h1>\n<p>Select a brochure to view.</p>\n<div class="grid">\n`;

const sortedKeys = Object.keys(groups).sort();
for (const key of sortedKeys) {
  const files = groups[key];
  if (files.length === 1) {
    const f = files[0];
    output += `<div class="card"><h2>${escapeHtml(f.title)}</h2><a class="btn" href="${encodeURI(f.file)}">View</a></div>\n`;
  } else {
    output += `<div class="card"><h2>${escapeHtml(files[0].title)}</h2><ul>`;
    const ref = files[0];
    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      output += `<li><a class="btn" href="${encodeURI(f.file)}">${escapeHtml(f.file)}</a>`;
      if (i > 0) {
        const diffResult = spawnSync('diff', ['-u', ref.filePath, f.filePath], {encoding: 'utf8'});
        let diff = diffResult.stdout ? diffResult.stdout : 'No differences';
        if (diff.length > 1000) diff = diff.slice(0, 1000) + '\n...';
        output += `<details><summary>Differences from ${escapeHtml(ref.file)}</summary><pre>${escapeHtml(diff)}</pre></details>`;
      }
      output += `</li>`;
    }
    output += `</ul></div>\n`;
  }
}

output += `</div>\n</body>\n</html>\n`;

fs.writeFileSync(path.join(rootDir, 'index.html'), output);
