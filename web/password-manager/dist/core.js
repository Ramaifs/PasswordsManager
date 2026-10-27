import { EXTRA_FIELDS } from './additional-fields.js';
import { validateParents } from './categories.js';
import { argon2id } from './vendor/hash-wasm.js';

export const MAX_FILE = 16 * 1024 * 1024;
export const KDF = { name: 'argon2id', memory: 65536, time: 3, parallelism: 4 };
export const FIELDS = ['title', 'site', 'username', 'email', 'phone', 'password', 'second_password', 'old_passwords', 'note'];
export const passwordTitle = note => [...(note.split(/\r\n|[\r\n]/).find(line => line.trim())?.trim() || 'Пароль')].slice(0, 80).join('');
const optionalFields = ['second_password', 'old_passwords'];
const encoder = new TextEncoder();
const decoder = new TextDecoder('utf-8', { fatal: true });
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const fail = () => { throw new Error('Неверный секрет или повреждённое хранилище.'); };
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const keys = (value, expected) => object(value) && Object.keys(value).sort().join('\0') === [...expected].sort().join('\0');
export const charLength = text => [...text].length;
const text = value => typeof value === 'string' && value.isWellFormed();

// Reject duplicate keys and unsafe integers before any KDF or model operation.
export function parseStrict(bytes) {
  if (!(bytes instanceof Uint8Array) || bytes.byteLength > MAX_FILE) fail();
  let source;
  try { source = decoder.decode(bytes); } catch { fail(); }
  let i = 0;
  const space = () => { while (/[\t\n\r ]/.test(source[i] || 'x')) i++; };
  function string() {
    const start = i++;
    while (i < source.length) {
      const c = source[i++];
      if (c === '\\') { i++; continue; }
      if (c === '"') {
        try { const result = JSON.parse(source.slice(start, i)); if (!text(result)) fail(); return result; } catch { fail(); }
      }
    }
    fail();
  }
  function value(depth = 0) {
    if (depth > 64) fail();
    space();
    if (source[i] === '"') return string();
    if (source[i] === '{') {
      i++; space(); const result = Object.create(null);
      if (source[i] === '}') { i++; return result; }
      while (i < source.length) {
        space(); if (source[i] !== '"') fail();
        const key = string(); space();
        if (Object.hasOwn(result, key) || source[i++] !== ':') fail();
        result[key] = value(depth + 1); space();
        const c = source[i++]; if (c === '}') return result; if (c !== ',') fail();
      }
      fail();
    }
    if (source[i] === '[') {
      i++; space(); const result = [];
      if (source[i] === ']') { i++; return result; }
      while (i < source.length) {
        result.push(value(depth + 1)); space();
        const c = source[i++]; if (c === ']') return result; if (c !== ',') fail();
      }
      fail();
    }
    for (const [literal, result] of [['true', true], ['false', false], ['null', null]]) {
      if (source.startsWith(literal, i)) { i += literal.length; return result; }
    }
    const match = /-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/.exec(source.slice(i));
    if (!match || match.index !== 0) fail();
    i += match[0].length;
    const number = Number(match[0]);
    if (!Number.isSafeInteger(number)) fail();
    return number;
  }
  const result = value(); space(); if (i !== source.length) fail(); return result;
}

export function canonical(value) {
  function serialize(item) {
    if (item === null || typeof item === 'boolean') return JSON.stringify(item);
    if (typeof item === 'number') { if (!Number.isSafeInteger(item)) fail(); return JSON.stringify(item); }
    if (typeof item === 'string') { if (!text(item)) fail(); return JSON.stringify(item); }
    if (Array.isArray(item)) return '[' + item.map(serialize).join(',') + ']';
    if (!object(item)) fail();
    return '{' + Object.keys(item).sort((a, b) => {
      const x = [...a].map(c => c.codePointAt(0)), y = [...b].map(c => c.codePointAt(0));
      for (let j = 0; j < Math.min(x.length, y.length); j++) if (x[j] !== y[j]) return x[j] - y[j];
      return x.length - y.length;
    }).map(key => JSON.stringify(key) + ':' + serialize(item[key])).join(',') + '}';
  }
  return encoder.encode(serialize(value));
}

export function b64(bytes) {
  let binary = ''; for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
  return btoa(binary);
}
export function unb64(value, size) {
  if (typeof value !== 'string' || value.length > MAX_FILE * 2) fail();
  let bytes;
  try { bytes = Uint8Array.from(atob(value), c => c.charCodeAt(0)); } catch { fail(); }
  if (b64(bytes) !== value || (size !== undefined && bytes.length !== size)) fail();
  return bytes;
}
const random = length => crypto.getRandomValues(new Uint8Array(length));
export function validatePassword(password) {
  if (!text(password) || charLength(password) < 8 || charLength(password) > 128) throw new Error('Мастер-пароль должен содержать от 8 до 128 символов.');
}
async function derive(password, salt) {
  validatePassword(password);
  return argon2id({ password: encoder.encode(password), salt, parallelism: 4, iterations: 3, memorySize: 65536, hashLength: 32, outputType: 'binary' });
}
const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
export function recoveryString(bytes = random(32)) {
  let bits = 0, buffer = 0, result = '';
  for (const byte of bytes) { buffer = (buffer << 8) | byte; bits += 8; while (bits >= 5) { bits -= 5; result += alphabet[(buffer >>> bits) & 31]; } }
  if (bits) result += alphabet[(buffer << (5 - bits)) & 31];
  return result;
}
function recoveryBytes(value) {
  if (typeof value !== 'string' || !/^[A-Z2-7]{52}$/i.test(value)) fail();
  let bits = 0, buffer = 0; const result = [];
  for (const c of value.toUpperCase()) { buffer = (buffer << 5) | alphabet.indexOf(c); bits += 5; if (bits >= 8) { bits -= 8; result.push((buffer >>> bits) & 255); } }
  const bytes = new Uint8Array(result);
  if (bytes.length !== 32 || recoveryString(bytes) !== value.toUpperCase()) fail(); return bytes;
}
async function aes(key, mode, data, nonce, aad) {
  const imported = await crypto.subtle.importKey('raw', key, 'AES-GCM', false, [mode]);
  return new Uint8Array(await crypto.subtle[mode]({ name: 'AES-GCM', iv: nonce, additionalData: aad, tagLength: 128 }, imported, data));
}
async function seal(key, plaintext, aad) { const nonce = random(12); return { nonce: b64(nonce), ciphertext: b64(await aes(key, 'encrypt', plaintext, nonce, aad)) }; }
async function unseal(key, box, aad) {
  if (!keys(box, ['nonce', 'ciphertext'])) fail();
  try { return await aes(key, 'decrypt', unb64(box.ciphertext), unb64(box.nonce, 12), aad); } catch { fail(); }
}
function wrapperAAD(base, kind) { const a = canonical(base), b = encoder.encode('/' + kind); return new Uint8Array([...a, ...b]); }
function baseHeader(header) { return Object.fromEntries(Object.entries(header).filter(([k]) => !['master', 'recovery', 'recovery_base'].includes(k))); }
export function inspect(bytes) {
  const envelope = parseStrict(bytes);
  if (!keys(envelope, ['header', 'payload'])) fail();
  const h = envelope.header;
  const required = ['format', 'version', 'vault_id', 'epoch', 'kdf', 'salt', 'master', 'recovery'];
  if (!keys(h, required) && !keys(h, [...required, 'recovery_base'])) fail();
  if (h.format !== 'PMVAULT' || h.version !== 1 || !uuidPattern.test(h.vault_id) || !Number.isInteger(h.epoch) || h.epoch < 1 || h.epoch > 2 ** 31 || decoder.decode(canonical(h.kdf)) !== decoder.decode(canonical(KDF))) fail();
  unb64(h.salt, 16); return envelope;
}
export async function createVault(password) {
  validatePassword(password);
  const salt = random(16), key = random(32), recovery = recoveryString();
  const base = { format: 'PMVAULT', version: 1, vault_id: crypto.randomUUID(), epoch: 1, kdf: KDF, salt: b64(salt) };
  const masterKey = await derive(password, salt);
  try {
    const header = { ...base, master: await seal(masterKey, key, wrapperAAD(base, 'master')), recovery: await seal(recoveryBytes(recovery), key, wrapperAAD(base, 'recovery')) };
    return { access: { header, key }, recovery, document: newDocument() };
  } finally { masterKey.fill(0); }
}
export async function encodeVault(access, document) {
  const bytes = canonical({ header: access.header, payload: await seal(access.key, canonical(document), canonical(access.header)) });
  if (bytes.length > MAX_FILE) throw new Error('Хранилище превышает 16 МиБ.'); return bytes;
}
export async function unlockVault(bytes, secret, recovery = false) {
  const opened = await unlockPayload(bytes, secret, recovery);
  opened.document = validateDocument(opened.document); return opened;
}
export async function unlockPayload(bytes, secret, recovery = false) {
  const envelope = inspect(bytes), h = envelope.header, base = baseHeader(h);
  const wrapping = recovery ? recoveryBytes(secret) : await derive(secret, unb64(h.salt, 16));
  let key;
  try { key = await unseal(wrapping, h[recovery ? 'recovery' : 'master'], wrapperAAD(recovery ? h.recovery_base || base : base, recovery ? 'recovery' : 'master')); }
  finally { wrapping.fill(0); }
  if (key.length !== 32) fail();
  const document = parseStrict(await unseal(key, envelope.payload, canonical(h)));
  return { access: { header: h, key }, document };
}
export async function decodeVault(access, bytes) {
  return validateDocument(await decodePayload(access, bytes));
}
export async function decodePayload(access, bytes) {
  const envelope = inspect(bytes);
  if (decoder.decode(canonical(envelope.header)) !== decoder.decode(canonical(access.header))) fail();
  return parseStrict(await unseal(access.key, envelope.payload, canonical(access.header)));
}
export async function changePassword(access, password) {
  validatePassword(password);
  const salt = random(16), base = { ...baseHeader(access.header), salt: b64(salt) };
  const recoveryBase = access.header.recovery_base || baseHeader(access.header);
  const wrapping = await derive(password, salt);
  try { return { key: access.key, header: { ...base, recovery_base: recoveryBase, recovery: access.header.recovery, master: await seal(wrapping, access.key, wrapperAAD(base, 'master')) } }; }
  finally { wrapping.fill(0); }
}
export function newDocument() {
  return { schema: 1, entries: {}, categories: {}, category_parents: {}, tombstones: {}, drafts: {}, settings: { theme: 'system', lock_minutes: 30 }, revision: 0, sync: null };
}
function timestamp(value) { return text(value) && /(?:Z|[+-]\d\d:\d\d)$/.test(value) && Number.isFinite(Date.parse(value)); }
function validFields(value, extra) {
  // Preserve old wire values exactly: adding empty fields would reuse causal dots.
  return object(value) && keys(value, [...FIELDS.filter(f => !optionalFields.includes(f) || Object.hasOwn(value, f)), ...extra, ...(Object.hasOwn(value, 'entry_type') ? ['entry_type'] : []), ...(Object.hasOwn(value, 'additional_fields') ? ['additional_fields'] : [])]) &&
    (!Object.hasOwn(value, 'additional_fields') || (object(value.additional_fields) && Object.entries(value.additional_fields).every(([key, items]) => EXTRA_FIELDS.includes(key) && Array.isArray(items) && items.length <= 100 && items.every(item => text(item) && charLength(item) <= 100000)))) &&
    (!Object.hasOwn(value, 'entry_type') || ['account', 'password'].includes(value.entry_type)) &&
    FIELDS.every(f => !Object.hasOwn(value, f) || (text(value[f]) && charLength(value[f]) <= 100000)) &&
    (value.entry_type !== 'password' || (value.category === null && !Object.values(value.additional_fields || {}).some(items => items.length) && FIELDS.every(f => ['title', 'password', 'note'].includes(f) || !value[f]) && (!extra.includes('id') || !!value.password)));
}
function validateRecord(entry, id) {
  if (!validFields(entry, ['id', 'category', 'deleted_at', 'updated_at']) || entry.id !== id || !uuidPattern.test(id)) fail();
  if (!entry.title.trim()) fail();
  if (entry.category !== null && !uuidPattern.test(entry.category)) fail();
  for (const field of ['deleted_at', 'updated_at']) if (entry[field] !== null && !timestamp(entry[field])) fail();
}
export function validateDocument(doc) {
  if (object(doc) && !Object.hasOwn(doc, 'sync')) doc.sync = null;
  if (object(doc) && !Object.hasOwn(doc, 'category_parents')) doc.category_parents = {};
  if (!keys(doc, Object.keys(newDocument())) || doc.schema !== 1 || !Number.isSafeInteger(doc.revision) || doc.revision < 0) fail();
  for (const field of ['entries', 'categories', 'tombstones', 'drafts', 'settings']) if (!object(doc[field])) fail();
  for (const [id, name] of Object.entries(doc.categories)) if (!uuidPattern.test(id) || !text(name) || !name.trim() || charLength(name) > 256) fail();
  validateParents(doc);
  for (const [id, entry] of Object.entries(doc.entries)) { validateRecord(entry, id); if (entry.category !== null && !Object.hasOwn(doc.categories, entry.category)) fail(); }
  for (const [id, time] of Object.entries(doc.tombstones)) if (!uuidPattern.test(id) || Object.hasOwn(doc.entries, id) || !timestamp(time)) fail();
  for (const [id, draft] of Object.entries(doc.drafts)) {
    if (id !== 'new' && !uuidPattern.test(id)) fail();
    if (!validFields(draft, ['category']) || (draft.category !== null && typeof draft.category !== 'string')) fail();
  }
  const s = doc.settings;
  if (Object.keys(s).some(k => !['theme', 'accent_color', 'lock_minutes', 'generator', 'sync_minutes', 'category_colors', 'check_updates', 'vault_name'].includes(k)) || !['system', 'light', 'dark'].includes(s.theme) || !Number.isInteger(s.lock_minutes) || s.lock_minutes < 1 || s.lock_minutes > 1440) fail();
  if (Object.hasOwn(s, 'accent_color') && (typeof s.accent_color !== 'string' || !/^#[0-9a-fA-F]{6}$/.test(s.accent_color))) fail();
  if (Object.hasOwn(s, 'sync_minutes') && (!Number.isInteger(s.sync_minutes) || s.sync_minutes < 0 || s.sync_minutes > 1440)) fail();
  if (s.category_colors !== undefined && (!object(s.category_colors) || Object.entries(s.category_colors).some(([id, color]) => !uuidPattern.test(id) || typeof color !== 'string' || !/^#[0-9a-fA-F]{6}$/.test(color)))) fail();
  if (Object.hasOwn(s, 'vault_name') && (typeof s.vault_name !== 'string' || !s.vault_name.trim() || charLength(s.vault_name) > 100 || /[\x00-\x1f]/.test(s.vault_name))) fail();
  if (Object.hasOwn(s, 'check_updates') && typeof s.check_updates !== 'boolean') fail();
  if (s.generator) generate(s.generator, true);
  if (doc.sync !== null) validateSync(doc.sync);
  return doc;
}
function validateSync(meta) {
  if (!keys(meta, ['state', 'pending', 'published', 'seen']) || !keys(meta.state, ['vector', 'registers']) || !object(meta.seen)) fail();
  const { vector, registers } = meta.state;
  if (!object(vector) || Object.keys(vector).length > 4096 || !object(registers) || Object.keys(registers).length > 50000) fail();
  for (const [actor, counter] of Object.entries(vector)) if (!uuidPattern.test(actor) || !Number.isSafeInteger(counter) || counter < 1) fail();
  const dots = new Set();
  for (const [key, variants] of Object.entries(registers)) {
    const [kind, id, extra] = key.split(':');
    if (extra || !['entry', 'category', 'category_parent', 'category_color'].includes(kind) || !uuidPattern.test(id) || !object(variants) || !Object.keys(variants).length || Object.keys(variants).length > 4096) fail();
    for (const [dot, value] of Object.entries(variants)) {
      const [actor, counter, tail] = dot.split(':');
      if (tail || !uuidPattern.test(actor) || !/^[1-9]\d*$/.test(counter) || !Number.isSafeInteger(Number(counter)) || Number(counter) > (vector[actor] || 0) || dots.has(dot)) fail();
      dots.add(dot);
      if (kind === 'category_color') { if (value !== null && (typeof value !== 'string' || !/^#[0-9a-fA-F]{6}$/.test(value))) fail(); }
      else if (kind === 'category_parent') { if (value !== null && (typeof value !== 'string' || !uuidPattern.test(value))) fail(); }
      else if (kind === 'category') { if (value !== null && (!text(value) || !value.trim() || charLength(value) > 256)) fail(); }
      else if (keys(value, ['purged_at'])) { if (!timestamp(value.purged_at)) fail(); }
      else validateRecord(value, id);
    }
  }
  if (Object.keys(meta.seen).length > 10000 || (meta.published !== null && !/^[0-9a-f]{64}$/.test(meta.published))) fail();
  for (const [id, observation] of Object.entries(meta.seen)) {
    if (!uuidPattern.test(id) || !keys(observation, ['digest', 'vector']) || !/^[0-9a-f]{64}$/.test(observation.digest) || !object(observation.vector)) fail();
    for (const [actor, counter] of Object.entries(observation.vector)) if (!uuidPattern.test(actor) || !Number.isSafeInteger(counter) || counter < 1) fail();
  }
  if (meta.pending !== null && (!keys(meta.pending, ['id', 'blob', 'state_id']) || !uuidPattern.test(meta.pending.id) || unb64(meta.pending.blob).length > 4 * 1024 * 1024 || !/^[0-9a-f]{64}$/.test(meta.pending.state_id))) fail();
}
export function trackChanges(before, after, actor) {
  if (!after.sync) return;
  const shared = doc => Object.fromEntries([...Object.entries(doc.categories).map(([id, v]) => ['category:' + id, v]), ...Object.entries(doc.category_parents || {}).map(([id, v]) => ['category_parent:' + id, v]), ...Object.entries(doc.settings.category_colors || {}).filter(([id]) => Object.hasOwn(doc.categories, id)).map(([id, v]) => ['category_color:' + id, v]), ...Object.entries(doc.entries).map(([id, v]) => ['entry:' + id, v]), ...Object.entries(doc.tombstones).map(([id, v]) => ['entry:' + id, { purged_at: v }])]);
  const a = shared(before), b = shared(after), state = after.sync.state;
  for (const key of new Set([...Object.keys(a), ...Object.keys(b)])) {
    if (JSON.stringify(a[key]) === JSON.stringify(b[key])) continue;
    const variants = state.registers[key] || {};
    if (new Set(Object.values(variants).map(v => decoder.decode(canonical(v)))).size > 1) throw new Error('Для этой записи есть конфликт. Сначала разрешите его в Windows-приложении.');
    const count = (state.vector[actor] || 0) + 1;
    state.vector[actor] = count;
    state.registers[key] = { [actor + ':' + count]: structuredClone(b[key] ?? null) };
  }
}
export const defaultGenerator = { length: 20, count: 1, lower: true, upper: true, digits: true, symbols: true, exclude_similar: false };
export function generate(options = defaultGenerator, validateOnly = false) {
  if (!keys(options, Object.keys(defaultGenerator)) || !Number.isInteger(options.length) || options.length < 8 || options.length > 128 || !Number.isInteger(options.count) || options.count < 1 || options.count > 100) throw new Error('Длина: 8–128. Количество: 1–100.');
  const choices = [['lower', 'abcdefghijklmnopqrstuvwxyz'], ['upper', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'], ['digits', '0123456789'], ['symbols', '!@#$%^&*()-_=+[]{};:,.?/']];
  for (const name of ['lower', 'upper', 'digits', 'symbols', 'exclude_similar']) if (typeof options[name] !== 'boolean') fail();
  const groups = choices.filter(([name]) => options[name]).map(([, chars]) => options.exclude_similar ? [...chars].filter(c => !'Il1O0o|'.includes(c)).join('') : chars);
  if (!groups.length) throw new Error('Выберите хотя бы одну группу символов.');
  if (validateOnly) return [];
  const chars = groups.join(''), ceiling = Math.floor(256 / chars.length) * chars.length;
  const result = [];
  for (let n = 0; n < options.count; n++) {
    while (true) {
      let password = '';
      while (password.length < options.length) for (const byte of random(options.length * 2)) { if (byte < ceiling) password += chars[byte % chars.length]; if (password.length === options.length) break; }
      if (groups.every(group => [...password].some(c => group.includes(c)))) { result.push(password); break; }
    }
  }
  return result;
}
