import test from 'node:test';
import assert from 'node:assert/strict';
import { FIELDS } from '../dist/core.js';
import { matchesEntry } from '../dist/search.js';

const entry = () => Object.fromEntries(FIELDS.map(field => [field, '']));

test('search covers all record fields without changing legacy records', () => {
  for (const field of FIELDS) {
    const record = { ...entry(), [field]: 'Начало ИСКОМЫЙ конец' };
    assert.equal(matchesEntry(record, '  искомый  '), true, field);
  }
  const legacy = entry(); delete legacy.second_password; delete legacy.old_passwords;
  const before = structuredClone(legacy);
  assert.equal(matchesEntry(legacy, 'missing'), false);
  assert.equal(matchesEntry(legacy, '   '), true);
  assert.deepEqual(legacy, before);
});

test('phone search ignores spaces, parentheses and dashes', () => {
  const record = { ...entry(), phone: '+7 (999) 123-45-67' };
  for (const query of ['+7', '+7999', '9991234567', '+7 999 123-45-67', '(999) 123', '  +7 (999) 123-45-67  ']) assert.equal(matchesEntry(record, query), true, query);
  for (const query of ['+1212', '+7-no-match', '---']) assert.equal(matchesEntry(record, query), false, query);
  assert.equal(matchesEntry({ ...entry(), note: 'Контакт: +79991234567' }, '+7999'), true);
  assert.equal(matchesEntry({ ...entry(), note: 'Контакт: +7 (999) 123-45-67' }, '+7999'), true);
  assert.equal(matchesEntry({ ...entry(), note: 'Первый: 1234. Второй: 5678' }, '3456'), false);
});
