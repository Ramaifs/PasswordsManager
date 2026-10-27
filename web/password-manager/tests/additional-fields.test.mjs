import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import * as core from '../dist/core.js';
import { additionalFields, migrateOldPasswords, splitPasswords, EXTRA_FIELDS } from '../dist/additional-fields.js';
import { seed, project } from '../dist/sync.js';
import { matchesEntry } from '../dist/search.js';
import { suggestions } from '../dist/suggestions.js';

test('additional fields and legacy migration preserve ciphertext, causal bytes and Python compatibility', async () => {
  const created = await core.createVault('12345678'), doc = created.document, id = crypto.randomUUID();
  const entry = {...Object.fromEntries(core.FIELDS.map(key => [key, ''])), title:'Fixture', id, category:null, deleted_at:null, updated_at:new Date().toISOString(), old_passwords:'  OLD;\nSECRET  ', additional_fields:Object.fromEntries(EXTRA_FIELDS.map(key => [key, [key + '-EXTRA-MARKER']]))};
  doc.entries[id] = entry;
  const state = seed(doc, crypto.randomUUID());
  doc.sync = {state, pending:null, published:null, seen:{}};
  const before = core.canonical(state);
  assert.deepEqual(additionalFields(entry).password, ['  OLD;\nSECRET  ', 'password-EXTRA-MARKER']);
  const original = structuredClone(doc);
  migrateOldPasswords(doc);
  core.trackChanges(original, doc, crypto.randomUUID());
  assert.deepEqual(core.canonical(original.sync.state), before);
  assert.equal(entry.old_passwords, '');
  assert.equal(matchesEntry(entry, 'email-EXTRA'), true);
  assert.deepEqual(suggestions(doc, 'email'), ['email-EXTRA-MARKER']);
  doc.settings.accent_color = '#007755';
  const bytes = await core.encodeVault(created.access, core.validateDocument(doc));
  assert.equal(new TextDecoder().decode(bytes).includes('EXTRA-MARKER'), false);
  const result = spawnSync(process.env.PM_TEST_PYTHON || path.resolve('../../.venv/Scripts/python.exe'), ['-c', "import sys,json,base64; from password_manager.crypto import unlock; from password_manager import model; a,d=unlock(base64.b64decode(sys.stdin.read()),'12345678'); model.validate(d); print(json.dumps(next(iter(d['entries'].values()))['additional_fields']))"], {input:core.b64(bytes),encoding:'utf8',env:{...process.env,PYTHONPATH:path.resolve('../../src')}});
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(result.stdout), entry.additional_fields);
  for (const invalid of [[], {password:'bad'}, {password:[null]}, {password:Array(101).fill('x')}, {other:['x']}]) {
    const bad = structuredClone(doc); bad.entries[id].additional_fields = invalid;
    assert.throws(() => core.validateDocument(bad));
  }
});

test('bulk paste splits line endings without changing spaces in passwords', () => {
  assert.deepEqual(splitPasswords(' first \r\nsecond\n\nthird\r'), [' first ', 'second', 'third']);
  assert.throws(() => splitPasswords('\n\r\n'));
  assert.throws(() => splitPasswords('x'.repeat(100001)));
});
