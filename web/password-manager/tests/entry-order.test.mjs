import test from 'node:test';
import assert from 'node:assert/strict';
import { sortEntries, savedEntryOrder, rememberEntryOrder } from '../dist/entry-order.js';

test('alphabetical and recent-first sorting do not mutate entries', () => {
  const entries = [
    { id: '1', title: 'Яндекс', updated_at: '2026-10-27T12:00:00Z' },
    { id: '2', title: 'Альфа', updated_at: '2026-10-26T12:00:00Z' },
    { id: '3', title: 'Бета', updated_at: '2026-10-27T12:00:00Z' },
  ];
  assert.deepEqual(sortEntries(entries).map(e => e.id), ['2', '3', '1']);
  assert.deepEqual(sortEntries(entries, 'updated').map(e => e.id), ['3', '1', '2']);
  assert.deepEqual(entries.map(e => e.id), ['1', '2', '3']);
});

test('sort preference restores valid values and handles unavailable storage', () => {
  const previous = globalThis.localStorage;
  let value;
  try {
    globalThis.localStorage = { getItem: () => value, setItem: (key, v) => { value = v; } };
    assert.equal(savedEntryOrder(), 'title');
    rememberEntryOrder('updated');
    assert.equal(savedEntryOrder(), 'updated');
    value = 'unknown';
    assert.equal(savedEntryOrder(), 'title');
    globalThis.localStorage = { getItem: () => { throw Error(); }, setItem: () => { throw Error(); } };
    assert.equal(savedEntryOrder(), 'title');
    assert.doesNotThrow(() => rememberEntryOrder('updated'));
  } finally { globalThis.localStorage = previous; }
});
