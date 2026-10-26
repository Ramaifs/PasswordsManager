import {test} from 'node:test';
import assert from 'node:assert/strict';
import {orderedCopies, groupCopies} from '../dist/cloud-backups.js';
import {DriveTransport} from '../dist/drive.js';

test('copy dates order all kinds newest first and pin newest copy of last opened vault once', async () => {
  const copies = [
    {id: 'old-full', vaultId: 'a', modifiedAt: '2026-10-26T10:00:00Z'},
    {id: 'new-wire', vaultId: 'a', version: 'wire', modifiedAt: '2026-10-26T12:00:00Z'},
    {id: 'newest-other', vaultId: 'b', modifiedAt: '2026-10-26T14:00:00+01:00'},
    {id: 'fallback', name: 'Main-Backup-2026-10-26-11:00:00.pmvault'},
    {id: 'unknown', modifiedAt: 'invalid'},
  ];
  assert.deepEqual(orderedCopies(copies).map(c => c.id), ['newest-other','new-wire','fallback','old-full','unknown']);
  const {latest, others} = groupCopies(copies, 'a');
  assert.equal(latest.id, 'new-wire');
  assert.deepEqual(others.map(c => c.id), ['newest-other','fallback','old-full','unknown']);
  const transport = new DriveTransport('FICTIONAL');
  transport.folders = async () => ['folder'];
  transport.list = async () => copies.slice(0, 2).map(c => ({id:c.id, name:c.id, size:'123', modifiedTime:c.modifiedAt, appProperties:{pm_app:'personal-password-manager-v1', pm_object:c.id, ...(c.version ? {pm_version: crypto.randomUUID()} : {pm_checkpoint:'1'})}}));
  assert.deepEqual((await transport.checkpoints()).map(c => c.id), ['new-wire','old-full']);
});

test('last opened UUID survives a fresh module and storage refusal keeps latest in memory', async () => {
  const saved = globalThis.localStorage, values = new Map();
  globalThis.localStorage = {getItem:key => values.get(key), setItem:(key,value) => values.set(key,value)};
  try {
    const first = await import('../dist/cloud-backups.js?first');
    const id = crypto.randomUUID(); first.rememberOpenedVault(id);
    const fresh = await import('../dist/cloud-backups.js?reload');
    assert.equal(fresh.lastOpenedVault(), id);
    assert.deepEqual([...values.values()], [id]);
    globalThis.localStorage.setItem = () => { throw new Error('Storage unavailable'); };
    const other = crypto.randomUUID(); fresh.rememberOpenedVault(other);
    assert.equal(fresh.lastOpenedVault(), other);
    fresh.rememberOpenedVault('invalid');
    assert.equal(fresh.lastOpenedVault(), other);
  } finally {
    if (saved === undefined) delete globalThis.localStorage; else globalThis.localStorage = saved;
  }
});
