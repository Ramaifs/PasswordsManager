export const SUGGESTION_FIELDS = ['email', 'phone', 'username', 'site'];

export function suggestions(doc, field) {
  if (!SUGGESTION_FIELDS.includes(field)) return [];
  const values = new Map();
  for (const entry of Object.values(doc.entries)) {
    for (const value of [entry[field], ...(entry.additional_fields?.[field] || [])]) {
    if (!entry.deleted_at && value.trim() && !values.has(value.toLocaleLowerCase('ru'))) values.set(value.toLocaleLowerCase('ru'), value);
    }
  }
  return [...values.values()].sort((a, b) => a.localeCompare(b, 'ru'));
}
