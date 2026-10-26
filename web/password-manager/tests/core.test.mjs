import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import * as core from '../dist/core.js';

const python = process.env.PM_TEST_PYTHON || path.resolve('../../.venv/Scripts/python.exe');
const sourceRoot = path.resolve('../../src');
function py(code, payload) {
  const result = spawnSync(python, ['-c', code], { input: JSON.stringify(payload), encoding: 'utf8', env: { ...process.env, PYTHONPATH: sourceRoot, PYTHONIOENCODING: 'utf-8' }, maxBuffer: 4 * 1024 * 1024 });
  assert.equal(result.status, 0, result.stderr);
  return JSON.parse(result.stdout);
}
const fixtures = await fs.mkdir('artifacts', { recursive: true });

test('8 character master, wrong password, recovery, nonce and no open markers', async () => {
  const result = await core.createVault('тест1234');
  const id = crypto.randomUUID(); result.document.entries[id] = { title: 'Fixture', site: '', username: 'FICTIONAL-USERNAME', email: 'fixture@example.invalid', phone: '', password: 'UNIQUE-FICTIONAL-ENTRY-MARKER', note: '', id, category: null, updated_at: new Date().toISOString(), deleted_at: null };
  const bytes = await core.encodeVault(result.access, result.document);
  assert.ok(!new TextDecoder().decode(bytes).includes('UNIQUE-FICTIONAL-ENTRY-MARKER'));
  assert.deepEqual((await core.unlockVault(bytes, 'тест1234')).document.entries[id].password, 'UNIQUE-FICTIONAL-ENTRY-MARKER');
  assert.deepEqual((await core.unlockVault(bytes, result.recovery, true)).document.entries[id].username, 'FICTIONAL-USERNAME');
  await assert.rejects(core.unlockVault(bytes, 'wrong123'));
  assert.notDeepEqual((core.inspect(bytes)).payload.nonce, core.inspect(await core.encodeVault(result.access, result.document)).payload.nonce);
  const decoded = py("import json,sys,base64; from password_manager.crypto import unlock; from password_manager.model import validate; p=json.load(sys.stdin); a,d=unlock(base64.b64decode(p['blob']),p['password']); validate(d); print(json.dumps({'entries':len(d['entries']),'password':next(iter(d['entries'].values()))['password']}))", { blob: core.b64(bytes), password: 'тест1234' });
  assert.deepEqual(decoded, { entries: 1, password: 'UNIQUE-FICTIONAL-ENTRY-MARKER' });
  await fs.writeFile('artifacts/browser-compatible.pmvault', bytes);
});

test('Python → browser → Python including changed master and original recovery', async () => {
  const made = py("import json,base64; from password_manager.crypto import Access; from password_manager.model import new_document,save_entry; a,r=Access.create('старый12'); d=new_document(); save_entry(d,{'title':'Из Python','password':'PYTHON-FICTIONAL-SECRET','note':'Кириллица и emoji 🗝️'}); a=a.change_password('новый123'); print(json.dumps({'blob':base64.b64encode(a.encode(d)).decode(),'recovery':r}))", {});
  const bytes = core.unb64(made.blob), opened = await core.unlockVault(bytes, 'новый123');
  assert.equal(Object.values(opened.document.entries)[0].title, 'Из Python');
  assert.equal(Object.values((await core.unlockVault(bytes, made.recovery, true)).document.entries)[0].note, 'Кириллица и emoji 🗝️');
  const updated = await core.changePassword(opened.access, 'браузер8');
  const encoded = await core.encodeVault(updated, opened.document);
  const checked = py("import json,sys,base64; from password_manager.crypto import unlock; p=json.load(sys.stdin); a,d=unlock(base64.b64decode(p['blob']),p['password']); b,e=unlock(base64.b64decode(p['blob']),p['recovery'],recovery=True); print(json.dumps({'same':d==e,'title':next(iter(d['entries'].values()))['title']}))", { blob: core.b64(encoded), password: 'браузер8', recovery: made.recovery });
  assert.equal(checked.same, true); assert.equal(checked.title, 'Из Python');
  await fs.writeFile('artifacts/python-compatible.pmvault', bytes);
});

test('password Unicode codepoints, min/max and no trimming', async () => {
  assert.throws(() => core.validatePassword('1234567'));
  assert.throws(() => core.validatePassword('a'.repeat(129)));
  core.validatePassword(' '.repeat(8)); core.validatePassword('🗝'.repeat(128));
  const made = await core.createVault('🗝'.repeat(8));
  const bytes = await core.encodeVault(made.access, made.document);
  assert.equal((await core.unlockVault(bytes, '🗝'.repeat(8))).document.schema, 1);
});

test('duplicate keys, invalid encoding, prototype keys, KDF and payload tampering', async () => {
  assert.throws(() => core.parseStrict(new TextEncoder().encode('{"key":1,"key":2}')));
  assert.throws(() => core.parseStrict(new Uint8Array([255])));
  assert.throws(() => core.parseStrict(new TextEncoder().encode('9007199254740992')));
  const obj = core.parseStrict(new TextEncoder().encode('{"__proto__":{"polluted":true}}'));
  assert.equal({}.polluted, undefined); assert.equal(obj.__proto__.polluted, true);
  const made = await core.createVault('12345678'), blob = await core.encodeVault(made.access, made.document);
  const altered = JSON.parse(new TextDecoder().decode(blob)); altered.header.kdf.memory = 999999999;
  assert.throws(() => core.inspect(core.canonical(altered)));
  const damaged = JSON.parse(new TextDecoder().decode(blob)); damaged.payload.ciphertext = damaged.payload.ciphertext.replace(/^./, damaged.payload.ciphertext[0] === 'A' ? 'B' : 'A');
  await assert.rejects(core.unlockVault(core.canonical(damaged), '12345678'));
});

test('generator constraints and allowed groups', () => {
  for (const length of [8, 20, 128]) for (const password of core.generate({ ...core.defaultGenerator, length, count: 10, exclude_similar: true })) {
    assert.equal(password.length, length); assert.match(password, /[a-z]/); assert.match(password, /[A-Z]/); assert.match(password, /[0-9]/); assert.match(password, /[^a-zA-Z0-9]/); assert.ok(!/[Il1O0o|]/.test(password));
  }
  assert.throws(() => core.generate({ ...core.defaultGenerator, lower: false, upper: false, digits: false, symbols: false }));
  assert.throws(() => core.generate({ ...core.defaultGenerator, count: 101 }));
});

test('desktop causal state remains valid after browser edit', async () => {
  const made = py("import json,base64,uuid; from password_manager.crypto import Access; from password_manager.model import new_document,save_entry; from password_manager.sync_state import seed; a,r=Access.create('12345678'); d=new_document(); eid=save_entry(d,{'title':'Sync fixture'}); d['sync']={'state':seed(d,str(uuid.uuid4())),'pending':None,'published':None,'seen':{}}; print(json.dumps({'blob':base64.b64encode(a.encode(d)).decode(),'id':eid}))", {});
  const opened = await core.unlockVault(core.unb64(made.blob), '12345678'), next = structuredClone(opened.document);
  next.entries[made.id].password = 'BROWSER-FICTIONAL-CHANGE'; next.entries[made.id].updated_at = new Date().toISOString();
  core.trackChanges(opened.document, next, crypto.randomUUID()); next.revision++;
  const bytes = await core.encodeVault(opened.access, core.validateDocument(next));
  const checked = py("import json,sys,base64; from password_manager.crypto import unlock; from password_manager.model import validate; p=json.load(sys.stdin); a,d=unlock(base64.b64decode(p['blob']),'12345678'); validate(d); print(json.dumps({'ok':True}))", { blob: core.b64(bytes) });
  assert.equal(checked.ok, true);
});
