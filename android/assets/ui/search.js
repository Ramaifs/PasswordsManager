import { FIELDS } from './core.js';

export function matchesEntry(entry, query) {
  const text = query.trim().toLocaleLowerCase('ru');
  const values = [...FIELDS.map(field => entry[field] || ''), ...Object.values(entry.additional_fields || {}).flat()];
  if (values.some(value => value.toLocaleLowerCase('ru').includes(text))) return true;
  const digits = /^\+?[0-9\s().-]+$/.test(text) ? text.replace(/[^0-9]/g, '') : '';
  return !!digits && values.some(value => (value.match(/\+?[0-9][0-9\s().-]*/g) || [])
    .some(number => number.replace(/[^0-9]/g, '').includes(digits)));
}
