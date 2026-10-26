import { normalizeParents } from './categories.js';
// PMVAULT sync protocol 1. Keys stay in vault-worker; no wall-clock winner.
import { canonical, newDocument, validateDocument, encodeVault, decodePayload, inspect, b64, unb64 } from './core.js';
const text = value => new TextDecoder().decode(canonical(value));
const clone = value => structuredClone(value);
const same = (a, b) => text(a) === text(b);
const uuid = value => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value);
export const MAX_CLOUD = 4 * 1024 * 1024;
export async function digest(bytes) { return [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(v => v.toString(16).padStart(2, '0')).join(''); }
export function validateState(state) {
  const doc = newDocument(); doc.sync = { state, pending: null, published: null, seen: {} }; validateDocument(doc); return state;
}
export const conflicted = variants => new Set(Object.values(variants).map(text)).size > 1;
export function conflicts(state) { return Object.fromEntries(Object.entries(state.registers).filter(([, v]) => conflicted(v))); }
export function merge(left, right) {
  validateState(left); validateState(right);
  const result = { vector: {}, registers: {} }, known = new Map();
  for (const state of [left, right]) {
    for (const [actor, count] of Object.entries(state.vector)) result.vector[actor] = Math.max(result.vector[actor] || 0, count);
    for (const [key, variants] of Object.entries(state.registers)) for (const [dot, value] of Object.entries(variants)) {
      const fingerprint = text([key, value]);
      if (known.has(dot) && known.get(dot) !== fingerprint) throw new Error('Обнаружено повторное использование причинной версии. Обмен остановлен.');
      known.set(dot, fingerprint);
    }
  }
  const observed = (dot, vector) => { const [actor, count] = dot.split(':'); return (vector[actor] || 0) >= Number(count); };
  for (const key of new Set([...Object.keys(left.registers), ...Object.keys(right.registers)])) {
    const a = left.registers[key] || {}, b = right.registers[key] || {}, variants = {};
    for (const [dot, value] of Object.entries(a)) if (Object.hasOwn(b, dot) || !observed(dot, right.vector)) variants[dot] = clone(value);
    for (const [dot, value] of Object.entries(b)) if (Object.hasOwn(a, dot) || !observed(dot, left.vector)) variants[dot] = clone(value);
    if (Object.keys(variants).length) result.registers[key] = variants;
  }
  return validateState(result);
}
export function seed(doc, actor) {
  const shared = { ...Object.fromEntries(Object.entries(doc.category_parents || {}).map(([id,v]) => ['category_parent:' + id, v])), ...Object.fromEntries(Object.entries(doc.categories).map(([id, v]) => ['category:' + id, v])),
    ...Object.fromEntries(Object.entries(doc.settings.category_colors || {}).filter(([id]) => Object.hasOwn(doc.categories, id)).map(([id, v]) => ['category_color:' + id, v])),
    ...Object.fromEntries(Object.entries(doc.entries).map(([id, v]) => ['entry:' + id, v])),
    ...Object.fromEntries(Object.entries(doc.tombstones).map(([id, v]) => ['entry:' + id, { purged_at: v }])) };
  const state = { vector: {}, registers: {} }; let count = 0;
  for (const key of Object.keys(shared).sort()) state.registers[key] = { [actor + ':' + (++count)]: clone(shared[key]) };
  if (count) state.vector[actor] = count;
  return validateState(state);
}
export function migrateCategoryColors(doc, actor) {
  const state = doc.sync.state;
  for (const [id, color] of Object.entries(doc.settings.category_colors || {})) {
    const key = 'category_color:' + id;
    if (!Object.hasOwn(doc.categories, id) || Object.hasOwn(state.registers, key)) continue;
    const count = (state.vector[actor] || 0) + 1;
    state.vector[actor] = count;
    state.registers[key] = { [actor + ':' + count]: color };
  }
}
export function project(document, state) {
  const doc = clone(document); doc.categories = {}; doc.category_parents = {}; doc.entries = {}; doc.tombstones = {};
  for (const [key, variants] of Object.entries(state.registers)) {
    const [kind, id] = key.split(':'); if (kind !== 'category') continue;
    const value = Object.values(variants)[0];
    if (conflicted(variants)) doc.categories[id] = document.categories[id] || 'Конфликт категории';
    else if (value !== null) doc.categories[id] = value;
  }
  for (const [key, variants] of Object.entries(state.registers)) {
    const [kind, id] = key.split(':');
    if (kind === 'category_parent') { const parent = conflicted(variants) ? document.category_parents?.[id] : Object.values(variants)[0]; if (parent) doc.category_parents[id] = parent; }
    if (kind !== 'entry') continue;
    const value = Object.values(variants)[0];
    if (conflicted(variants)) {
      if (Object.hasOwn(document.entries, id)) doc.entries[id] = clone(document.entries[id]);
      else if (Object.hasOwn(document.tombstones, id)) doc.tombstones[id] = document.tombstones[id];
    } else if (Object.hasOwn(value, 'purged_at')) doc.tombstones[id] = value.purged_at;
    else doc.entries[id] = clone(value);
  }
  const colors = Object.fromEntries(Object.entries(document.settings.category_colors || {}).filter(([id]) => Object.hasOwn(doc.categories, id)));
  for (const [key, variants] of Object.entries(state.registers)) {
    const [kind, id] = key.split(':');
    if (kind !== 'category_color' || !Object.hasOwn(doc.categories, id) || conflicted(variants)) continue;
    const color = Object.values(variants)[0];
    if (color === null) delete colors[id]; else colors[id] = color;
  }
  if (Object.keys(colors).length || Object.hasOwn(doc.settings, 'category_colors')) doc.settings.category_colors = colors;
  for (const entry of Object.values(doc.entries)) if (!Object.hasOwn(doc.categories, entry.category)) entry.category = null;
  doc.sync.state = clone(state); normalizeParents(doc); return validateDocument(doc);
}
async function payload(access, bytes, id) {
  if (!uuid(id) || bytes.length > MAX_CLOUD) throw new Error('Некорректная облачная версия.');
  const value = await decodePayload(access, bytes);
  if (text(Object.keys(value).sort()) !== text(['id', 'protocol', 'state']) || value.protocol !== 1 || value.id !== id) throw new Error('Некорректный протокол облачной версии.');
  validateState(value.state); return value;
}
export async function prepare(access, document, actor, remote) {
  if (!Array.isArray(remote) || remote.length > 1000 || remote.reduce((n, v) => n + v.blob.length, 0) > 64 * 1024 * 1024) throw new Error('Облачная история превышает безопасный предел.');
  let doc = clone(document);
  if (!doc.sync) doc.sync = { state: seed(doc, actor), pending: null, published: null, seen: {} };
  else migrateCategoryColors(doc, actor);
  const meta = doc.sync;
  if (meta.pending && !same(inspect(unb64(meta.pending.blob)).header, access.header)) {
    meta.seen[meta.pending.id] = { digest: await digest(unb64(meta.pending.blob)), vector: clone(meta.state.vector) }; meta.pending = null;
  }
  let state = meta.state; const parsed = [], ids = new Set();
  for (const item of remote) {
    if (!uuid(item.id) || ids.has(item.id)) throw new Error('Некорректная или повторная облачная версия.'); ids.add(item.id);
    const bytes = new Uint8Array(item.blob); if (bytes.length > MAX_CLOUD) throw new Error('Облачная версия превышает 4 МиБ.');
    const fingerprint = await digest(bytes);
    if (!same(inspect(bytes).header, access.header)) {
      if (meta.seen[item.id]?.digest === fingerprint) continue;
      throw new Error('В Drive другое хранилище или изменён мастер-пароль. Обмен остановлен; локальные данные сохранены. Объедините версии в Windows.');
    }
    const decoded = await payload(access, bytes, item.id);
    state = merge(state, decoded.state); parsed.push(decoded);
    meta.seen[item.id] = { digest: fingerprint, vector: clone(decoded.state.vector) };
  }
  meta.state = state; doc = project(doc, state);
  const fingerprint = await digest(canonical([access.header, state]));
  if (!meta.pending && (meta.published !== fingerprint || !parsed.some(v => same(v.state, state)))) {
    const id = crypto.randomUUID(), bytes = await encodeVault(access, { protocol: 1, id, state });
    if (bytes.length > MAX_CLOUD) throw new Error('Облачная версия превышает 4 МиБ. Локальные данные сохранены.');
    meta.pending = { id, blob: b64(bytes), state_id: fingerprint };
  }
  doc.sync = meta; return validateDocument(doc);
}
export async function acknowledge(access, document, id, blob) {
  const doc = clone(document), pending = doc.sync?.pending;
  const expected = pending ? unb64(pending.blob) : null;
  if (!pending || pending.id !== id || expected.length !== blob.length || !expected.every((v, i) => v === blob[i])) throw new Error('Drive не подтвердил байты локальной очереди.');
  const decoded = await payload(access, blob, id);
  doc.sync.seen[id] = { digest: await digest(blob), vector: clone(decoded.state.vector) };
  doc.sync.published = pending.state_id; doc.sync.pending = null; return validateDocument(doc);
}
export function resolve(document, actor, key, dot) {
  const doc = clone(document), variants = conflicts(doc.sync.state)[key];
  if (!variants || !Object.hasOwn(variants, dot)) throw new Error('Вариант конфликта уже изменился.');
  const count = (doc.sync.state.vector[actor] || 0) + 1;
  doc.sync.state.vector[actor] = count;
  doc.sync.state.registers[key] = { [actor + ':' + count]: clone(variants[dot]) };
  return project(doc, doc.sync.state);
}
