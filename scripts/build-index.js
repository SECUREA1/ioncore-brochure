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

let output = `<!DOCTYPE html>\n<html>\n<head>\n<meta charset="utf-8">\n<title>Ioncore Brochure Index</title>\n<style>body{font-family:Arial, sans-serif; margin:40px;} ul{list-style-type:none; padding-left:0;} li{margin-bottom:8px;} details{margin-top:4px;}</style>\n</head>\n<body>\n<h1>Ioncore Brochure Index</h1>\n<p>This front page maps each brochure for easy exploration. Similar brochures include annotated differences.</p>\n<ul>\n`;

const sortedKeys = Object.keys(groups).sort();
for (const key of sortedKeys) {
  const files = groups[key];
  if (files.length === 1) {
    const f = files[0];
    output += `<li><a href="${encodeURI(f.file)}">${escapeHtml(f.title)}</a></li>\n`;
  } else {
    output += `<li>${escapeHtml(files[0].title)}<ul>`;
    const ref = files[0];
    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      output += `<li><a href="${encodeURI(f.file)}">${escapeHtml(f.file)}</a>`;
      if (i > 0) {
        const diffResult = spawnSync('diff', ['-u', ref.filePath, f.filePath], {encoding: 'utf8'});
        const diff = diffResult.stdout ? diffResult.stdout : 'No differences';
        output += `<details><summary>Differences from ${escapeHtml(ref.file)}</summary><pre>${escapeHtml(diff)}</pre></details>`;
      }
      output += `</li>`;
    }
    output += `</ul></li>\n`;
  }
}

output += `</ul>\n</body>\n</html>\n`;

fs.writeFileSync(path.join(rootDir, 'index.html'), output);
