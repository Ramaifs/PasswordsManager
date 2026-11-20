export const SUGGESTION_FIELDS = ['email', 'phone', 'username', 'site'];

export function suggestionSources(doc, field) {
  if (!SUGGESTION_FIELDS.includes(field)) return [];
  const values = new Map();
  const hidden = new Set(doc.settings?.entry_input?.hidden?.[field] || []);
  for (const entry of Object.values(doc.entries)) {
    if (entry.deleted_at) continue;
    for (const value of [entry[field], ...(entry.additional_fields?.[field] || [])]) {
      const key = value?.toLowerCase();
      if (key && !/[\s\u0085]$/u.test(value) && !hidden.has(key) && !values.has(key)) values.set(key, {value, entry});
    }
  }
  return [...values.values()].sort((a, b) => a.value.localeCompare(b.value, 'ru'));
}

export function suggestions(doc, field) {
  return suggestionSources(doc, field).map(item => item.value);
}

export function hideSuggestion(doc, field, value) {
  const preferences = doc.settings.entry_input ??= {};
  preferences.hidden ??= {};
  const hidden = preferences.hidden[field] ??= [];
  const key = value.toLowerCase();
  if (hidden.includes(key)) return;
  if (hidden.length >= 1000) throw new Error('Список скрытых подсказок для этого поля заполнен.');
  hidden.push(key);
}
