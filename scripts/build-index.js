import { promises as fs } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';

const root = fileURLToPath(new URL('..', import.meta.url));
const catalogue = JSON.parse(await fs.readFile(path.join(root, 'data/project-catalogue.json'), 'utf8'));
const escape = text => text.replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
const href = file => file.startsWith('/') ? file : file.split('/').map(encodeURIComponent).join('/');
async function discover(dir = root) {
  const files = [];
  for (const item of await fs.readdir(dir, { withFileTypes: true })) {
    if (item.name.startsWith('.') || item.name === 'node_modules') continue;
    const full = path.join(dir, item.name);
    if (item.isDirectory()) files.push(...await discover(full));
    else if (item.name.toLowerCase().endsWith('.html')) files.push(path.relative(root, full));
  }
  return files;
}
const files = await discover();
const listed = new Set();
const hashes = new Set();
for (const project of catalogue.projects) {
  if (listed.has(project.file)) throw new Error(`Duplicate listing: ${project.file}`);
  listed.add(project.file);
  if (!catalogue.categories.some(category => category.id === project.category)) throw new Error(`Unknown category: ${project.category}`);
  if (project.file === '/timepieces') {
    await fs.access(path.join(root, 'ioncore_ready_to_sell_brochure_mint_5_with_solana_desc.html.zip'));
    continue;
  }
  if (!files.includes(project.file)) throw new Error(`Missing page: ${project.file}`);
  const bytes = await fs.readFile(path.join(root, project.file));
  const hash = createHash('sha256').update(bytes).digest('hex');
  if (hashes.has(hash)) throw new Error(`Duplicate content: ${project.file}`);
  hashes.add(hash);
}
for (const file of files) {
  if (!listed.has(file) && !catalogue.excluded[file]) throw new Error(`Review new page before building: ${file}`);
}
for (const [file, omission] of Object.entries(catalogue.excluded)) {
  if (!files.includes(file) || listed.has(file) || !omission.reason) throw new Error(`Invalid omission: ${file}`);
  if (omission.canonical && !listed.has(omission.canonical)) throw new Error(`Canonical page is not listed: ${file}`);
}
let output = `    <!-- PROJECT CATALOGUE START -->
    <section class="container page-section--tight project-catalogue" id="projects" aria-labelledby="projects-title">
      <h2 class="section-title" id="projects-title">Explore every project</h2>
      <p class="section-subtitle">${catalogue.projects.length} project pages, brochures, plans and demos. Choose a category above or browse the complete library below.</p>
      <div class="project-search" hidden>
        <label for="project-search">Find a project</label>
        <input id="project-search" type="search" placeholder="Search projects, specifications or demos…" autocomplete="off" aria-controls="project-groups">
        <p id="project-count" role="status" aria-live="polite"></p>
      </div>
      <div id="project-groups">
`;
for (const category of catalogue.categories) {
  const projects = catalogue.projects.filter(p => p.category === category.id).sort((a,b) => a.title.localeCompare(b.title, 'en'));
  output += `        <section class="project-group" id="projects-${category.id}" aria-labelledby="title-${category.id}">
          <h3 id="title-${category.id}">${escape(category.title)} <span class="project-group__count">${projects.length} pages</span></h3>
          <ul class="project-list">\n`;
  for (const project of projects) {
    output += `            <li class="project-item"><a href="${escape(href(project.file))}"><span>${escape(project.title)}</span><span class="project-open">Open <span aria-hidden="true">→</span></span></a></li>\n`;
  }
  output += '          </ul>\n        </section>\n';
}
output += '      </div>\n      <p id="project-empty" hidden>No matching projects. Try another name or clear the search.</p>\n    </section>\n    <!-- PROJECT CATALOGUE END -->';
const index = path.join(root, 'index.html');
const current = await fs.readFile(index, 'utf8');
const marker = /    <!-- PROJECT CATALOGUE START -->[\s\S]*?    <!-- PROJECT CATALOGUE END -->/;
if (!marker.test(current)) throw new Error('Catalogue markers missing; refusing to overwrite homepage');
const next = current.replace(marker, () => output);
if (process.argv.includes('--check')) {
  if (current !== next) throw new Error('Catalogue is stale. Run npm run build-index.');
} else if (next !== current) await fs.writeFile(index, next);
console.log(`Catalogue verified: ${catalogue.projects.length} entries; ${files.length} HTML files reviewed; ${Object.keys(catalogue.excluded).length} documented omissions.`);
