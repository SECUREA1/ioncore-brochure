import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawn, execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { once } from 'node:events';
import { readFile, mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';

// An independent server exercises routing without cookies or an existing login.
test('public main webpage, category index and linked project resources', async (t) => {
  const dataDir = await mkdtemp(path.join(tmpdir(), 'ioncore-contact-test-'));
  const server = spawn(process.execPath, ['server.js'], {
    cwd: new URL('..', import.meta.url),
    env: { ...process.env, PORT: '3107', IONCORE_DATA_DIR: dataDir },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  t.after(async () => {
    if (server.exitCode === null) {
      server.kill();
      await once(server, 'exit');
    }
    await rm(dataDir, { recursive: true, force: true });
  });
  await new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('Server did not start')), 15000);
    server.once('error', reject);
    server.once('exit', code => { clearTimeout(timeout); reject(new Error(`Server exited: ${code}`)); });
    server.stdout.on('data', data => {
      if (data.toString().includes('Server listening')) { clearTimeout(timeout); resolve(); }
    });
  });
  const get = async (path) => {
    const response = await fetch(`http://127.0.0.1:3107${path}`);
    assert.equal(response.status, 200, path);
    return response.text();
  };
  const main = await get('/');
  assert.ok(main.includes('High-End Energy Ecosystems'));
  assert.ok(main.includes('href="index.html">Explore Ioncore projects</a>'));
  assert.ok(!main.includes('webpage-login.js'));
  const home = await get('/index.html');
  assert.ok(home.includes('href="webpage.html">Back to main webpage</a>'));
  assert.equal((home.match(/class="category-card"/g) || []).length, 5);
  assert.ok(!home.includes('Open catalogue login'));
  assert.ok(home.includes('href="login.html">Login (optional)</a>'));
  assert.ok((await get('/index.html')).includes('category-grid'));
  for (const path of ['/webpage.html', '/catalogue']) {
    assert.ok(!(await get(path)).includes('webpage-login.js'), path);
  }
  const catalogue = JSON.parse(await readFile(new URL('../data/project-catalogue.json', import.meta.url), 'utf8'));
  assert.equal((home.match(/class="project-item"/g) || []).length, catalogue.projects.length);
  assert.ok(home.includes('src="project-index.js"'));
  const ids = new Set([...home.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]));
  const resources = new Set();
  for (const [, url] of home.matchAll(/(?:href|src)="([^"]+)"/g)) {
    if (url.startsWith('#')) assert.ok(ids.has(url.slice(1)), url);
    else if (!/^(?:[a-z]+:|\/\/)/i.test(url)) resources.add('/' + url.replace(/^\//, ''));
  }
  for (const path of resources) {
    const content = await get(path);
    for (const match of content.matchAll(/mailto:([a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,})/gi)) {
      assert.equal(match[1], 'jodelchad@chaines.io', `Company contact in ${path}`);
    }
  }
  const response = await fetch('http://127.0.0.1:3107/contact', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: 'Inquiry Test', email: 'visitor@example.test', message: 'IP & patent inquiry? Costs #1' }),
  });
  assert.equal(response.status, 200);
  const result = await response.json();
  const draft = new URL(result.emailUrl);
  assert.equal(draft.protocol, 'mailto:');
  assert.equal(draft.pathname, 'jodelchad@chaines.io');
  assert.ok(draft.searchParams.get('body').includes('IP & patent inquiry? Costs #1'));
  assert.ok(draft.searchParams.get('body').includes('visitor@example.test'));
  assert.ok(result.message.includes('send it'));
  const stored = JSON.parse(await readFile(path.join(dataDir, 'gateway-store.json'), 'utf8'));
  assert.equal(stored.contactSubmissions.at(-1).email, 'visitor@example.test');
});


test('catalogue is current and every repository HTML page has a reviewed disposition', async () => {
  await promisify(execFile)(process.execPath, ['scripts/build-index.js', '--check'], {
    cwd: new URL('..', import.meta.url),
  });
});
