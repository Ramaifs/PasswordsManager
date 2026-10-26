export function sortEntries(entries, order = 'title') {
  return [...entries].sort((a, b) =>
    (order === 'updated' ? b.updated_at.localeCompare(a.updated_at) : 0) ||
    a.title.localeCompare(b.title, 'ru', { sensitivity: 'base' }) || a.id.localeCompare(b.id));
}

export function savedEntryOrder() {
  try { return localStorage.getItem('pm-entry-sort') === 'updated' ? 'updated' : 'title'; }
  catch { return 'title'; }
}

export function rememberEntryOrder(order) {
  try { localStorage.setItem('pm-entry-sort', order === 'updated' ? 'updated' : 'title'); }
  catch { /* Sorting remains available when browser storage is disabled. */ }
}
