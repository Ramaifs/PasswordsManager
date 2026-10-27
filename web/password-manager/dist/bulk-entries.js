export function bulkEdit(doc, ids, field, value) {
  if (!ids.length || ids.some(id => !Object.hasOwn(doc.entries, id))) throw new Error('Выберите существующие записи.');
  if (field === 'category') {
    if (value !== null && !Object.hasOwn(doc.categories, value)) throw new Error('Категория не найдена.');
  } else if (field === 'color') {
    if (value !== null && (typeof value !== 'string' || !/^#[0-9a-fA-F]{6}$/.test(value))) throw new Error('Некорректный цвет записи.');
  } else throw new Error('Неизвестное свойство записи.');
  const timestamp = new Date().toISOString();
  for (const id of new Set(ids)) {
    if (field === 'color' && value === null) delete doc.entries[id].color;
    else doc.entries[id][field] = value;
    doc.entries[id].updated_at = timestamp;
  }
}
