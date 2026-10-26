import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import * as core from '../dist/core.js';
import * as sync from '../dist/sync.js';
import { DriveTransport } from '../dist/drive.js';
import { validClientId, authorize, clearGoogle, cancelGoogleLogin, connected, accessToken } from '../dist/google.js';
import { putVault, saveSnapshot, listVaults } from '../dist/storage.js';
import { GOOGLE_WEB_CLIENT_ID } from '../dist/oauth-config.js';

const entry = () => ({ id: crypto.randomUUID(), title: 'Fictional', site: '', username: '', email: '', phone: '', password: 'NEVER-PLAINTEXT-ON-WIRE', note: '', category: null, updated_at: new Date().toISOString(), deleted_at: null });
const python = process.env.PM_TEST_PYTHON || path.resolve('../../.venv/Scripts/python.exe');
function py(code, input) {
  const p = spawnSync(python, ['-c', code], { input: JSON.stringify(input), encoding: 'utf8', env: { ...process.env, PYTHONPATH: path.resolve('../../src'), PYTHONIOENCODING: 'utf-8' } });
  assert.equal(p.status, 0, p.stderr); return JSON.parse(p.stdout);
}
test('web pending queue is immutable, Python consumes web versions and web consumes Python versions', async () => {
  const made = await core.createVault('тест1234'), actor = crypto.randomUUID(), e = entry();
  made.document.settings.sync_minutes = 0;
  made.document.entries[e.id] = e;
  const prepared = await sync.prepare(made.access, made.document, actor, []), pending = prepared.sync.pending;
  assert.ok(!new TextDecoder().decode(core.unb64(pending.blob)).includes(e.password));
  const result = py("import json,sys,base64; from password_manager.crypto import unlock; from password_manager.sync import version_payload; from password_manager import sync_state; p=json.load(sys.stdin); a,d=unlock(base64.b64decode(p['doc']),'тест1234'); v=version_payload(base64.b64decode(p['blob']),a,p['id']); s=v['state']; key=next(iter(s['registers'])); value=next(iter(s['registers'][key].values())); value['note']='edited in Python'; sync_state.write(s,p['actor'],key,value); print(json.dumps({'blob':base64.b64encode(a.encode({'protocol':1,'id':p['next'],'state':s})).decode(),'state':s}))", { doc: core.b64(await core.encodeVault(made.access, prepared)), blob: pending.blob, id: pending.id, actor: crypto.randomUUID(), next: actor });
  const acknowledged = await sync.acknowledge(made.access, prepared, pending.id, core.unb64(pending.blob));
  const merged = await sync.prepare(made.access, acknowledged, actor, [{ id: actor, blob: core.unb64(result.blob) }]);
  assert.equal(merged.entries[e.id].note, 'edited in Python');
  assert.deepEqual(sync.merge(prepared.sync.state, result.state), result.state);
  const retry = await sync.prepare(made.access, prepared, actor, []);
  assert.deepEqual(retry.sync.pending, pending);
  await assert.rejects(sync.acknowledge(made.access, prepared, pending.id, new Uint8Array([1,2])));
});
test('concurrent edits preserve both variants, resolution dominates and settings stay local', () => {
  const doc = core.newDocument(), e = entry(), a = crypto.randomUUID(), b = crypto.randomUUID(); doc.entries[e.id] = e;
  const initial = sync.seed(doc, a); doc.sync = { state: initial, pending: null, published: null, seen: {} };
  const left = structuredClone(doc), right = structuredClone(doc);
  left.entries[e.id].note = 'left'; right.entries[e.id].note = 'right';
  core.trackChanges(doc, left, a); core.trackChanges(doc, right, b);
  const merged = sync.merge(left.sync.state, right.sync.state), key = 'entry:' + e.id;
  assert.deepEqual(sync.merge(left.sync.state, right.sync.state), sync.merge(right.sync.state, left.sync.state));
  assert.equal(Object.keys(sync.conflicts(merged)).length, 1);
  doc.settings.theme = 'light'; doc.drafts.new = Object.fromEntries([...core.FIELDS.map(k => [k, '']), ['category', null]]);
  const view = sync.project(doc, merged); assert.equal(view.entries[e.id].note, ''); assert.equal(view.settings.theme, 'light'); assert.ok(view.drafts.new);
  const resolved = sync.resolve(view, crypto.randomUUID(), key, Object.keys(merged.registers[key])[0]);
  assert.equal(Object.keys(sync.conflicts(resolved.sync.state)).length, 0);
  assert.deepEqual(sync.merge(resolved.sync.state, merged), resolved.sync.state);
  const collision = structuredClone(initial); Object.values(collision.registers[key])[0].note = 'collision';
  assert.throws(() => sync.merge(initial, collision));
});
test('foreign access and missing/tampered versions stop before overwrite', async () => {
  const made = await core.createVault('тест1234'), foreign = await core.createVault('другой12');
  const id = crypto.randomUUID(), blob = await core.encodeVault(foreign.access, { protocol: 1, id, state: { vector: {}, registers: {} } });
  await assert.rejects(sync.prepare(made.access, made.document, crypto.randomUUID(), [{ id, blob }]), /другое хранилище/);
  await assert.rejects(sync.prepare(made.access, made.document, crypto.randomUUID(), [{ id, blob: new Uint8Array([1]) }]));
});
test('deletion versus edit, permanent tombstone and category deletion retain causal meaning', () => {
  const doc = core.newDocument(), e = entry(), a = crypto.randomUUID(), b = crypto.randomUUID(), category = crypto.randomUUID();
  doc.categories[category] = 'Category'; e.category = category; doc.entries[e.id] = e;
  doc.sync = { state: sync.seed(doc, a), pending: null, published: null, seen: {} };
  const deleted = structuredClone(doc), edited = structuredClone(doc);
  deleted.entries[e.id].deleted_at = new Date().toISOString(); edited.entries[e.id].password = 'OTHER-FICTIONAL';
  core.trackChanges(doc, deleted, a); core.trackChanges(doc, edited, b);
  const conflict = sync.merge(deleted.sync.state, edited.sync.state);
  assert.equal(Object.keys(sync.conflicts(conflict)).length, 1);
  const removed = structuredClone(doc); delete removed.categories[category]; removed.entries[e.id].category = null;
  delete removed.entries[e.id]; removed.tombstones[e.id] = new Date().toISOString();
  core.trackChanges(doc, removed, a);
  const view = sync.project(doc, sync.merge(doc.sync.state, removed.sync.state));
  assert.deepEqual(view.entries, {}); assert.deepEqual(view.categories, {}); assert.ok(view.tombstones[e.id]);
});

function fakeDrive() {
  const files = new Map(), calls = []; let serial = 0, failReadback = false;
  const response = (value, status = 200) => new Response(value instanceof Uint8Array ? value : JSON.stringify(value), { status });
  const fetcher = async (url, options) => {
    calls.push({ url, options }); assert.equal(options.credentials, 'omit'); assert.equal(options.redirect, 'error');
    assert.equal(options.headers.Authorization, 'Bearer TEST-TOKEN');
    const u = new URL(url);
    if (u.pathname.endsWith('/about')) return response({ user: { permissionId: 'account1', emailAddress: 'fictional@example.invalid' } });
    if (u.pathname.endsWith('/generateIds')) return response({ ids: ['file' + (++serial)] });
    if (options.method === 'POST') {
      let metadata, blob;
      if (options.body instanceof Blob) {
        const boundary = options.headers['Content-Type'].split('boundary=')[1];
        const bytes = new Uint8Array(await options.body.arrayBuffer()), raw = new TextDecoder().decode(bytes);
        const parts = raw.split('--' + boundary); metadata = JSON.parse(parts[1].split('\r\n\r\n')[1].trim());
        blob = new TextEncoder().encode(parts[2].split('\r\n\r\n')[1].slice(0, -2));
      } else { metadata = core.parseStrict(options.body); blob = new Uint8Array(); }
      files.set(metadata.id, { ...metadata, blob, size: String(blob.length), version: '1' }); return response({ id: metadata.id });
    }
    if (u.searchParams.get('alt') === 'media') {
      const f = files.get(u.pathname.split('/').at(-1)); return response(failReadback ? new Uint8Array([1]) : f.blob);
    }
    if (u.pathname.endsWith('/files')) {
      const q = u.searchParams.get('q');
      return response({ files: [...files.values()].filter(f => q.includes('mimeType =') ? f.mimeType === 'application/vnd.google-apps.folder' : f.parents?.includes(q.match(/'([^']+)' in parents/)[1])).map(({ blob, ...meta }) => meta) });
    }
    throw new Error('Unexpected fake URL ' + url);
  };
  return { fetcher, files, calls, failReadback: () => { failReadback = true; } };
}
test('Drive invokes fetch with the Window/global receiver required by browser WebIDL', async () => {
  async function browserFetch(url, options) {
    if (this !== globalThis) throw new TypeError("'fetch' called on an object that does not implement interface Window.");
    assert.equal(url, 'https://www.googleapis.com/drive/v3/about?fields=user(permissionId,emailAddress)');
    assert.equal(options.headers.Authorization, 'Bearer TEST-TOKEN');
    return new Response('{"user":{"permissionId":"account1"}}');
  }
  const transport = new DriveTransport('TEST-TOKEN', { fetcher: browserFetch });
  assert.equal((await transport.identity()).id, 'account1');
});
test('Drive reuses a complete listing and downloads only changed file revisions across exchanges', async () => {
  const fake = fakeDrive(), cache = new Map();
  const seed = new DriveTransport('TEST-TOKEN', { fetcher: fake.fetcher });
  await seed.publish(crypto.randomUUID(), new TextEncoder().encode('encrypted-history'));
  fake.calls.length = 0;
  const t = new DriveTransport('TEST-TOKEN', { fetcher: fake.fetcher, cache });
  await t.fetch();
  const lists = () => fake.calls.filter(c => new URL(c.url).searchParams.has('q')).length;
  const reads = () => fake.calls.filter(c => new URL(c.url).searchParams.get('alt') === 'media').length;
  const beforePublish = lists();
  await t.publish(crypto.randomUUID(), new TextEncoder().encode('new-encrypted-version'));
  assert.equal(lists(), beforePublish, 'publish should reuse the already complete listing');
  await t.fetch();
  const beforeWarm = reads();
  const warm = new DriveTransport('TEST-TOKEN', { fetcher: fake.fetcher, cache });
  await warm.fetch();
  assert.equal(reads(), beforeWarm, 'unchanged revisions should not be downloaded again');
  const changed = [...fake.files.values()].find(f => f.appProperties.pm_version);
  changed.blob = new TextEncoder().encode('modified-encrypted'); changed.size = String(changed.blob.length); changed.version = '2';
  const current = await new DriveTransport('TEST-TOKEN', { fetcher: fake.fetcher, cache }).fetch();
  assert.equal(reads(), beforeWarm + 1);
  assert.ok(current.some(v => new TextDecoder().decode(v.blob) === 'modified-encrypted'));
  fake.files.delete(changed.id);
  const afterDelete = await new DriveTransport('TEST-TOKEN', { fetcher: fake.fetcher, cache }).fetch();
  assert.equal(afterDelete.length, 1); assert.ok(!cache.has(changed.id));
});
test('Drive creates owned folder, uploads encrypted versions, reads back, retries without duplicates', async () => {
  const fake = fakeDrive(), transport = new DriveTransport('TEST-TOKEN', { fetcher: fake.fetcher });
  assert.equal((await transport.identity()).id, 'account1');
  const id = crypto.randomUUID(), bytes = new TextEncoder().encode('{"encrypted":"fixture"}');
  assert.deepEqual(await transport.publish(id, bytes), bytes);
  assert.deepEqual(await transport.publish(id, bytes), bytes);
  assert.equal(fake.files.size, 2);
  await transport.checkpoint(crypto.randomUUID(), bytes);
  const copies = await transport.checkpoints();
  assert.equal(copies.length, 2);
  assert.equal(copies[0].version, null, 'full checkpoints should precede randomly named wire versions');
  assert.equal((await transport.fetch()).length, 1); // checkpoint excluded from shared wire
  const metadata = [...fake.files.values()].find(f => f.appProperties.pm_version);
  metadata.appProperties.pm_object = 'copied-object'; assert.equal((await transport.fetch()).length, 0);
});
test('Drive rejects missing pinned folder, incomplete lists, expiry, oversized streams and bad readback', async () => {
  const fake = fakeDrive();
  await assert.rejects(new DriveTransport('TEST-TOKEN', { fetcher: fake.fetcher, folder: 'deleted' }).fetch(), /Папка/);
  for (const [fetcher, match] of [
    [async () => new Response('{"incompleteSearch":true,"files":[]}'), /полный список/],
    [async () => new Response('', { status: 401 }), /истёк/],
    [async () => new Response(new Uint8Array(32)), /предел/]
  ]) {
    const t = new DriveTransport('TEST-TOKEN', { fetcher });
    await assert.rejects(match.source === 'предел' ? t.call('GET', 'https://www.googleapis.com', { binary: true, limit: 8 }) : t.fetch(), match);
  }
  const t = new DriveTransport('TEST-TOKEN', { fetcher: fake.fetcher }); await t.folders(); fake.failReadback();
  await assert.rejects(t.publish(crypto.randomUUID(), new TextEncoder().encode('ciphertext')), /байты/);
  const controller = new AbortController(); controller.abort();
  await assert.rejects(new DriveTransport('TEST-TOKEN', { fetcher: fake.fetcher, signal: controller.signal }).fetch(), { name: 'AbortError' });
});
test('OAuth scope, cancellation and token are memory only; new storage never calls IndexedDB', async () => {
  assert.equal(GOOGLE_WEB_CLIENT_ID, '8811944829-v7id2c1rrcu5qv590mp2h9fn8bfv6sl1.apps.googleusercontent.com');
  assert.ok(validClientId(GOOGLE_WEB_CLIENT_ID));
  const id = '123-test.apps.googleusercontent.com'; assert.ok(validClientId(id)); assert.ok(!validClientId('secret.json'));
  let callback;
  globalThis.google = { accounts: { oauth2: { initTokenClient: config => { assert.equal(config.scope, 'https://www.googleapis.com/auth/drive.file'); callback = config.callback; return { requestAccessToken(options) { assert.equal(options.prompt, ''); } }; }, hasGrantedAllScopes: () => true } } };
  const login = authorize(id); callback({ access_token: 'TEST-TOKEN', expires_in: 3600 }); await login; assert.ok(connected());
  cancelGoogleLogin(); assert.ok(connected()); assert.equal(accessToken(), 'TEST-TOKEN');
  const interrupted = authorize(id); cancelGoogleLogin(); await assert.rejects(interrupted);
  callback({ access_token: 'LATE-TOKEN', expires_in: 3600 }); assert.equal(accessToken(), 'TEST-TOKEN');
  const realNow = Date.now;
  try { Date.now = () => realNow() + 3600000; assert.ok(!connected()); assert.throws(accessToken); }
  finally { Date.now = realNow; }
  clearGoogle(); assert.throws(accessToken);
  const cancelled = authorize(id), staleCallback = callback; clearGoogle(); await assert.rejects(cancelled);
  const nextLogin = authorize(id); staleCallback({ access_token: 'STALE', expires_in: 3600 });
  assert.ok(!connected()); clearGoogle(); await assert.rejects(nextLogin);
  globalThis.indexedDB = { open() { throw new Error('New vault must not enter IndexedDB'); } };
  const record = await putVault({ id: crypto.randomUUID(), blob: new Uint8Array([1]), updatedAt: new Date().toISOString() });
  await saveSnapshot(record, new Uint8Array([2])); assert.ok((await listVaults()).some(v => v.id === record.id));
  const fresh = await import('../dist/storage.js?fresh-session'); assert.deepEqual(await fresh.listVaults(), []);
});
