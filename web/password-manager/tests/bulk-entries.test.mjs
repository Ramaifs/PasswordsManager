import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import path from 'node:path';
import * as core from '../dist/core.js';
import {bulkEdit} from '../dist/bulk-entries.js';
import {nextPasswordNumber} from '../dist/additional-fields.js';

test('numbering continues after highest active password note', () => {
  const doc = {entries:{a:{entry_type:'password',note:'31',deleted_at:null}, b:{entry_type:'password',note:'100',deleted_at:'deleted'}, c:{note:'999',deleted_at:null}}};
  assert.equal(nextPasswordNumber(doc),32);
  doc.entries.d = {entry_type:'password',note:'32',deleted_at:null};
  assert.equal(nextPasswordNumber(doc),33);
});

test('bulk metadata survives encryption and Python validation, including categorized password-only records', async () => {
  const created = await core.createVault('12345678'), doc = created.document;
  const category = crypto.randomUUID(), a = crypto.randomUUID(), b = crypto.randomUUID();
  doc.categories[category] = 'Batch category';
  const record = id => ({...Object.fromEntries(core.FIELDS.map(key => [key,''])), id, title:'Fixture', password:'BULK-SECRET', category:null, updated_at:new Date().toISOString(), deleted_at:null});
  doc.entries[a] = {...record(a),entry_type:'password',note:'31'};
  doc.entries[b] = record(b);
  bulkEdit(doc,[a],'color','#12ab34'); bulkEdit(doc,[a],'category',category);
  assert.equal(doc.entries[b].color,undefined);
  const bytes = await core.encodeVault(created.access,core.validateDocument(doc));
  assert.equal(new TextDecoder().decode(bytes).includes('BULK-SECRET'),false);
  const result = spawnSync(process.env.PM_TEST_PYTHON || path.resolve('../../.venv/Scripts/python.exe'),['-c',"import json,sys,base64; from password_manager.crypto import unlock; from password_manager import model; a,d=unlock(base64.b64decode(sys.stdin.read()),'12345678'); model.validate(d); print(json.dumps({'colored':sum(e.get('color')=='#12ab34' for e in d['entries'].values()),'categorized':sum(e['category'] is not None for e in d['entries'].values())}))"],{input:core.b64(bytes),encoding:'utf8',env:{...process.env,PYTHONPATH:path.resolve('../../src')}});
  assert.equal(result.status,0,result.stderr);
  assert.deepEqual(JSON.parse(result.stdout),{colored:1,categorized:1});
  bulkEdit(doc,[a],'color',null); assert.equal(doc.entries[a].color,undefined);
  const before = core.canonical(doc);
  assert.throws(()=>bulkEdit(doc,[a,'missing'],'category',category));
  assert.deepEqual(core.canonical(doc),before);
});
