// Repeatable request/latency benchmark on in-memory Drive, never a Google account.
import { execFileSync } from 'node:child_process';
import fs from 'node:fs/promises';
import { setTimeout as sleep } from 'node:timers/promises';
import { DriveTransport } from '../dist/drive.js';
import { parseStrict } from '../dist/core.js';

const baselineCommit = '308a84ca4ec5d276488f6500e54ae7c064039493';
const previous = execFileSync('git', ['show', baselineCommit + ':dist/drive.js'], { encoding: 'utf8' })
  .replace("'./core.js'", JSON.stringify(new URL('../dist/core.js', import.meta.url).href));
const Baseline = (await import('data:text/javascript;base64,' + Buffer.from(previous).toString('base64'))).DriveTransport;
function fixture() {
  const files = new Map(), calls = []; let serial = 100;
  const props = id => ({ pm_app: 'personal-password-manager-v1', pm_object: id });
  files.set('folder', { id: 'folder', name: 'Fixture', mimeType: 'application/vnd.google-apps.folder', appProperties: props('folder'), version: '1' });
  for (let n = 0; n < 10; n++) {
    const id = 'history' + n, version = crypto.randomUUID(), blob = new TextEncoder().encode('opaque-encrypted-fixture-' + n);
    files.set(id, { id, name: `version-${version}.pmvault`, parents: ['folder'], appProperties: { ...props(id), pm_version: version }, blob, size: String(blob.length), version: '1' });
  }
  const fetcher = async (url, options) => {
    calls.push(url); await sleep(5);
    const u = new URL(url), reply = value => new Response(value instanceof Uint8Array ? value : JSON.stringify(value));
    if (u.pathname.endsWith('/generateIds')) return reply({ ids: ['new' + (++serial)] });
    if (options.method === 'POST') {
      let metadata, blob;
      if (options.body instanceof Blob) {
        const boundary = options.headers['Content-Type'].split('boundary=')[1], parts = (await options.body.text()).split('--' + boundary);
        metadata = JSON.parse(parts[1].split('\r\n\r\n')[1].trim()); blob = new TextEncoder().encode(parts[2].split('\r\n\r\n')[1].slice(0, -2));
      } else { metadata = parseStrict(options.body); blob = new Uint8Array(); }
      files.set(metadata.id, { ...metadata, blob, size: String(blob.length), version: '1' }); return reply({ id: metadata.id });
    }
    if (u.searchParams.get('alt') === 'media') return reply(files.get(u.pathname.split('/').at(-1)).blob);
    const q = u.searchParams.get('q');
    return reply({ files: [...files.values()].filter(f => q.includes('mimeType =') ? f.mimeType === 'application/vnd.google-apps.folder' : f.parents?.includes('folder')).map(({ blob, ...m }) => m) });
  };
  return { fetcher, calls };
}
async function measure(Constructor) {
  const fake = fixture(), cache = new Map(), started = performance.now();
  const transport = new Constructor('BENCHMARK-FIXTURE', { fetcher: fake.fetcher, cache });
  await transport.fetch();
  await transport.publish(crypto.randomUUID(), new TextEncoder().encode('new-encrypted-fixture'));
  await transport.fetch();
  await new Constructor('BENCHMARK-FIXTURE', { fetcher: fake.fetcher, cache }).fetch();
  return { requests: fake.calls.length, content_downloads: fake.calls.filter(url => new URL(url).searchParams.get('alt') === 'media').length, elapsed_ms: Math.round(performance.now() - started) };
}
const before = await measure(Baseline), after = await measure(DriveTransport);
if (after.requests >= before.requests || after.content_downloads >= before.content_downloads) throw new Error('No reduction in requests');
const report = { baseline_commit: baselineCommit, level: 'simulated Drive / 10 history files / 5ms artificial latency per request', workflow: 'cold fetch, publish with readback, refetch, warm exchange', before, after, real_google_latency_measured: false };
await fs.mkdir('artifacts', { recursive: true });
await fs.writeFile('artifacts/drive-benchmark.json', JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
