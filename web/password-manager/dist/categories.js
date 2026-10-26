// Category hierarchy shared by the UI, document validation and sync projection.
export function descendants(doc, id) {
  const result = new Set([id]), children = new Map(), pending = [id];
  for (const [child, parent] of Object.entries(doc.category_parents || {})) {
    if (!children.has(parent)) children.set(parent, []);
    children.get(parent).push(child);
  }
  while (pending.length) for (const child of children.get(pending.pop()) || []) if (!result.has(child)) { result.add(child); pending.push(child); }
  return result;
}
export function categoryRows(doc) {
  const children = new Map();
  for (const id of Object.keys(doc.categories)) {
    const parent = doc.category_parents?.[id] || null;
    if (!children.has(parent)) children.set(parent, []);
    children.get(parent).push(id);
  }
  const pending = (children.get(null) || []).toReversed().map(id => [id, 0, '']), rows = [];
  while (pending.length) {
    const [id, depth, prefix] = pending.pop(), name = doc.categories[id], path = prefix + name;
    rows.push({id, name, depth, path});
    for (const child of (children.get(id) || []).toReversed()) pending.push([child, depth + 1, path + ' / ']);
  }
  return rows;
}
export function visibleCategoryRows(doc, collapsed = new Set()) {
  const hidden = new Set(), parents = doc.category_parents || {}, hasChildren = new Set(Object.values(parents));
  return categoryRows(doc).filter(row => {
    if (collapsed.has(parents[row.id]) || hidden.has(parents[row.id])) { hidden.add(row.id); return false; }
    row.hasChildren = hasChildren.has(row.id); row.collapsed = collapsed.has(row.id);
    return true;
  });
}
export function moveCategory(doc, id, parent = null) {
  if (!Object.hasOwn(doc.categories, id) || (parent !== null && !Object.hasOwn(doc.categories, parent))) throw new Error('Категория не найдена.');
  if (descendants(doc, id).has(parent)) throw new Error('Категорию нельзя поместить внутрь неё самой или её подкатегории.');
  doc.category_parents ??= {};
  if (parent === null) delete doc.category_parents[id]; else doc.category_parents[id] = parent;
}
export function validateParents(doc) {
  const parents = doc.category_parents;
  if (!parents || typeof parents !== 'object' || Array.isArray(parents)) throw new Error('Некорректная иерархия категорий.');
  for (const [id, initialParent] of Object.entries(parents)) {
    if (!Object.hasOwn(doc.categories, id) || typeof initialParent !== 'string' || !Object.hasOwn(doc.categories, initialParent)) throw new Error('Родительская категория не найдена.');
    const seen = new Set([id]); let parent = initialParent;
    while (parent !== undefined) {
      if (seen.has(parent)) throw new Error('Категорию нельзя поместить внутрь неё самой или её подкатегории.');
      seen.add(parent); parent = parents[parent];
    }
  }
}
export function normalizeParents(doc) {
  const parents = Object.fromEntries(Object.entries(doc.category_parents || {}).filter(([id, parent]) => id !== parent && Object.hasOwn(doc.categories, id) && Object.hasOwn(doc.categories, parent)));
  const cyclic = new Set();
  for (let id of Object.keys(parents).sort()) {
    const chain = [], positions = new Map();
    while (Object.hasOwn(parents, id)) {
      if (positions.has(id)) { for (const member of chain.slice(positions.get(id))) cyclic.add(member); break; }
      positions.set(id, chain.length); chain.push(id); id = parents[id];
    }
  }
  doc.category_parents = Object.fromEntries(Object.entries(parents).filter(([id]) => !cyclic.has(id)));
  return doc;
}
export function removeCategory(doc, id) {
  const parent = doc.category_parents?.[id];
  delete doc.categories[id]; delete doc.category_parents?.[id]; delete doc.settings.category_colors?.[id];
  for (const [child, currentParent] of Object.entries(doc.category_parents || {})) if (currentParent === id) {
    if (parent) doc.category_parents[child] = parent; else delete doc.category_parents[child];
  }
  for (const entry of Object.values(doc.entries)) if (entry.category === id) { entry.category = null; entry.updated_at = new Date().toISOString(); }
  for (const draft of Object.values(doc.drafts)) if (draft.category === id) draft.category = null;
}
