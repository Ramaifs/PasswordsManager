import { categoryRows } from './categories.js';

export function sortEntries(entries, order = 'title', doc = {categories:{}}) {
  const paths = new Map(categoryRows(doc).map(row => [row.id, row.path]));
  const category = entry => paths.get(entry.category) || (entry.entry_type === 'password' ? 'Прочие пароли' : 'Без категории');
  return [...entries].sort((a, b) =>
    (order === 'category' ? category(a).localeCompare(category(b), 'ru', {sensitivity:'base'}) : 0) ||
    (order === 'updated' ? b.updated_at.localeCompare(a.updated_at) : 0) ||
    a.title.localeCompare(b.title, 'ru', { sensitivity: 'base' }) || a.id.localeCompare(b.id));
}

export function savedEntryOrder() {
  try { const value = localStorage.getItem('pm-entry-sort'); return ['updated', 'category'].includes(value) ? value : 'title'; }
  catch { return 'title'; }
}

export function rememberEntryOrder(order) {
  try { localStorage.setItem('pm-entry-sort', ['updated', 'category'].includes(order) ? order : 'title'); }
  catch { /* Sorting remains available when browser storage is disabled. */ }
}
