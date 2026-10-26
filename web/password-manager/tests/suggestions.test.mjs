import test from 'node:test';
import assert from 'node:assert/strict';
import { suggestions } from '../dist/suggestions.js';

test('suggestions use existing active values with no duplicates or secret fields', () => {
  const doc = { entries: {
    a: { email:'Name@example.invalid', phone:'+7999', username:'Login', site:'example.invalid', password:'Secret', deleted_at:null },
    b: { email:'name@example.invalid', phone:'', username:'', site:'', deleted_at:null },
    c: { email:'gone@example.invalid', phone:'', username:'', site:'', deleted_at:'2026-10-27T00:00:00Z' },
  } };
  const before = structuredClone(doc);
  assert.deepEqual(suggestions(doc, 'email'), ['Name@example.invalid']);
  assert.deepEqual(suggestions(doc, 'phone'), ['+7999']);
  assert.deepEqual(suggestions(doc, 'username'), ['Login']);
  assert.deepEqual(suggestions(doc, 'site'), ['example.invalid']);
  assert.deepEqual(suggestions(doc, 'password'), []);
  assert.deepEqual(doc, before);
});
