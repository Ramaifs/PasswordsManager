import { FIELDS } from './core.js';

export function matchesEntry(entry, query) {
  const text = query.trim().toLocaleLowerCase('ru');
  if (FIELDS.some(field => (entry[field] || '').toLocaleLowerCase('ru').includes(text))) return true;
  const digits = /^\+?[0-9\s().-]+$/.test(text) ? text.replace(/[^0-9]/g, '') : '';
  return !!digits && FIELDS.some(field => ((entry[field] || '').match(/\+?[0-9][0-9\s().-]*/g) || [])
    .some(number => number.replace(/[^0-9]/g, '').includes(digits)));
}
