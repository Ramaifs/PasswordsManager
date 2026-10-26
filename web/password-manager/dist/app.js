import { categoryRows, visibleCategoryRows, moveCategory, descendants, validateParents, removeCategory } from './categories.js';
import { FIELDS, defaultGenerator, generate, inspect, validatePassword, charLength, canonical } from './core.js';
import { listVaults, getVault, putVault, forgetVault, saveSnapshot } from './storage.js';
import { legacyVaults, removeLegacy } from './legacy.js';
import { DriveTransport } from './drive.js';
import { loadGoogle, authorize, accessToken, connected, cancelGoogleLogin, initializeGoogleSession, ensureAccessToken, disconnectGoogle, persistentSessionEnabled } from './google.js';
import { GOOGLE_WEB_CLIENT_ID } from './oauth-config.js';
import { vaultName } from './vault-names.js';
import { SyncSchedule, syncMinutes } from './sync-schedule.js';
import { conflicts } from './sync.js';

const app = document.querySelector('#app'), modal = document.querySelector('#modal');
const iconPaths = {
  lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2"/>',
  vault: '<rect x="3" y="3" width="18" height="18" rx="4"/><circle cx="12" cy="12" r="4"/><path d="m9 9 6 6m0-6-6 6m3-10v3m0 14v3"/>',
  plus: '<path d="M12 5v14M5 12h14"/>', folder: '<path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v10H3z"/>',
  arrow: '<path d="m9 5 7 7-7 7M16 12H3"/>', back: '<path d="m10 5-7 7 7 7M3 12h18"/>',
  shield: '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6z"/><path d="m8 12 3 3 5-6"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>',
  moon: '<path d="M20 14a8 8 0 0 1-10-10 8 8 0 1 0 10 10z"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 4 2c-1.5 1-1.5 1.5-1.5 3m0 3h.01"/>',
  check: '<path d="m5 12 4 4L19 6"/>', copy: '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>', eye: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12"/><circle cx="12" cy="12" r="3"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>', key: '<circle cx="8" cy="15" r="5"/><path d="m12 11 8-8m-3 3 3 3m-6 0 3 3"/>',
  trash: '<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/>', settings: '<path d="m9 3-1 3-3 1 1 4-2 2 2 3 3 1 1 4h4l1-4 3-1 2-3-2-2 1-4-3-1-1-3z"/><circle cx="12" cy="12" r="3"/>',
  dice: '<rect x="3" y="3" width="18" height="18" rx="4"/><path d="M7 7h.01M17 7h.01M12 12h.01M7 17h.01M17 17h.01"/>',
  chevron: '<path d="m8 9 4-4 4 4m-8 6 4 4 4-4"/>', clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>', cloud: '<path d="M6 18a5 5 0 1 1 1-10 6 6 0 0 1 11 2 4 4 0 0 1 0 8z"/>', close: '<path d="m6 6 12 12M6 18 18 6"/>', restore: '<path d="M3 10a9 9 0 1 1 1 8M3 3v7h7M12 7v5l4 2"/>'
};
const icon = name => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${iconPaths[name] || iconPaths.vault}</svg>`;
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const now = () => new Date().toISOString();
const clone = value => structuredClone(value);
const state = { view: 'home', recent: [], record: null, token: null, doc: null, create: null, selected: null, category: 'all', query: '', dirty: false, busy: false, generation: 0 };
let worker, calls = new Map(), toastTimer, clipTimer, copiedPassword, lastActivity = Date.now();
let driveController, driveIdentity, cloudCopies = [], oldVaults = [], oauthPending = false;
const syncSchedule = new SyncSchedule();
const collapsedCategories = new Set();
let draggedCategory = null;
let generatorOptions = { ...defaultGenerator };
const driveCache = new Map();
async function stopDrive() { driveController?.abort(); await disconnectGoogle(); driveIdentity = null; driveCache.clear(); }
function pauseDrive() { driveController?.abort(); cancelGoogleLogin(); }
async function driveTransport() {
  await ensureAccessToken();
  driveController = new AbortController();
  return new DriveTransport(accessToken(), { signal: driveController.signal, folder: state.record?.drive?.folder || null, cache: driveCache, vaultId: state.record?.blob ? inspect(state.record.blob).header.vault_id : null, vaultName: state.doc?.settings.vault_name || state.record?.name || 'Main' });
}

function startWorker() {
  if (worker) return;
  worker = new Worker(new URL('./vault-worker.js', import.meta.url), { type: 'module' });
  worker.onmessage = ({ data }) => { const call = calls.get(data.id); if (!call) return; calls.delete(data.id); data.error ? call.reject(new Error(data.error)) : call.resolve(data.result); };
  worker.onerror = () => { for (const call of calls.values()) call.reject(new Error('Не удалось запустить шифрование. Перезагрузите страницу.')); calls.clear(); };
}
function rpc(operation, args) { startWorker(); return new Promise((resolve, reject) => { const id = crypto.randomUUID(); calls.set(id, { resolve, reject }); worker.postMessage({ id, operation, args }); }); }
function stopWorker() { worker?.terminate(); worker = null; for (const call of calls.values()) call.reject(new Error('Хранилище заблокировано.')); calls.clear(); }
function toast(message, persistent = false) { const node = document.querySelector('#toast'); node.textContent = message; node.hidden = false; clearTimeout(toastTimer); if (!persistent) toastTimer = setTimeout(() => { node.hidden = true; node.textContent = ''; }, 6500); }
function error(message) { toast(message); const node = document.querySelector('#form-error'); if (node) { node.textContent = message; node.setAttribute('role', 'alert'); } else toast(message); }
function setBusy(value) { state.busy = value; document.body.classList.toggle('busy', value); document.body.setAttribute('aria-busy', String(value)); }
async function safe(action) {
  if (state.busy) return;
  try { setBusy(true); await action(); }
  catch (e) { if (e?.name !== 'AbortError') error(e instanceof Error ? e.message : 'Не удалось выполнить действие.'); }
  finally { setBusy(false); if (state.lockRequested && state.token) { state.lockRequested = false; void safe(lock); } }
}
function download(bytes, name, mime = 'application/octet-stream') {
  const url = URL.createObjectURL(new Blob([bytes], { type: mime })), a = document.createElement('a');
  a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function filename(name) { return name.replace(/[<>:"/\\|?*\x00-\x1f]/g, '_').replace(/[. ]+$/g, '').slice(0, 100) || 'vault'; }
async function refreshRecent() {
  state.recent = (await listVaults()).sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  try { oldVaults = await legacyVaults(); }
  catch { oldVaults = []; toast('Прежние хранилища браузера недоступны. Для их экспорта разрешите доступ к данным сайта. Файловый режим доступен.'); }
}
function initials(name) { return [...name.trim()].slice(0, 1).join('').toUpperCase() || 'Х'; }
function savedStatus() { return state.record?.cloudPending ? 'Есть изменения, не отправленные в Drive' : state.record?.drive ? 'Зашифрованная копия в Google Drive' : state.record?.filePending ? 'В памяти вкладки · сохраните файл' : 'Сохранено в файле на ПК'; }
const helpButton = `<button class="icon-button quiet" data-action="help" aria-label="Как это работает">${icon('help')}</button>`;
function brand() { return '<div class="brand"><img src="./icon.svg" alt=""><div>Password Manager<small>ЛИЧНОЕ ПРОСТРАНСТВО</small></div></div>'; }
function sidebar() {
  return `<aside class="sidebar">${brand()}<div class="sidebar-heading"><span class="kicker">Хранилища</span><button class="icon-button quiet small" data-action="new" aria-label="Добавить хранилище">${icon('plus')}</button></div><nav class="vault-list" aria-label="Ваши хранилища">${state.recent.map(v => `<div class="vault-item"><button class="vault-link ${state.record?.id === v.id ? 'active' : ''}" data-action="open-recent" data-id="${esc(v.id)}"><span class="vault-initial">${esc(initials(v.name))}</span><span><span class="vault-name">${esc(v.name)}</span><small>${v.fileHandle ? 'Файл на устройстве' : 'На этом устройстве'}</small></span></button><button class="danger vault-delete" data-action="delete-vault" data-id="${esc(v.id)}" aria-label="Удалить хранилище ${esc(v.name)}">${icon('trash')}</button></div>`).join('')}</nav>${!state.recent.length ? '<p class="sidebar-empty">Здесь появятся ваши хранилища.<br>Начнём с первого?</p>' : ''}<div class="side-bottom"><div class="footer-actions"><button class="icon-button quiet" data-action="theme" aria-label="Переключить тему">${icon(document.documentElement.dataset.theme === 'dark' ? 'sun' : 'moon')}</button><span class="version">WEB · 0.38</span>${helpButton}</div><p class="side-note">${icon('shield')}Шифрование на вашем устройстве.<br>Мастер-пароль остаётся у вас.</p></div></aside>`;
}
function shell(content, page = 'Хранилища') {
  app.innerHTML = `<div class="layout">${sidebar()}<main class="main"><header class="topbar"><div class="breadcrumb">${icon('vault')}<span>Ваше пространство</span><span>/</span><span>${esc(page)}</span></div><div class="top-status"><span class="status-dot"></span>Локальное шифрование</div></header>${content}<footer class="bottom-line"><span>Ваши пароли. Только ваш доступ.</span><span>Argon2id · AES-256-GCM</span></footer></main></div>`;
}
function home() {
  state.view = 'home'; state.create = null;
  document.title = 'Password Manager — Хранилища';
  shell(`<section class="welcome"><div class="welcome-mark">${icon('vault')}</div><h1>Пространство для ваших паролей</h1><p class="intro">Всё важное — в одном защищённом месте.<br>Создайте новое хранилище или откройте существующее.</p><div class="choices"><div class="choice"><div class="choice-leading">${icon('plus')}<div><h3>Создать новое хранилище</h3><p>Начните с чистого листа. Выберите имя и место<br class="desktop-break"> для вашего зашифрованного хранилища.</p></div></div><button class="primary" data-action="new">Создать</button></div><div class="choice"><div class="choice-leading">${icon('folder')}<div><h3>Открыть хранилище</h3><p>Уже есть файл? Откройте хранилище .pmvault,<br class="desktop-break"> в том числе из Windows-приложения.</p></div></div><button class="secondary" data-action="import">Открыть</button></div></div>${state.recent.length ? `<div class="mobile-recents"><p class="kicker">На этом устройстве</p>${state.recent.map(v => `<button class="vault-link" data-action="open-recent" data-id="${esc(v.id)}"><span class="vault-initial">${esc(initials(v.name))}</span><span class="vault-name">${esc(v.name)}</span>${icon('lock')}</button><button class="danger secondary" data-action="delete-vault" data-id="${esc(v.id)}">Удалить хранилище</button>`).join('')}</div>` : ''}<div class="choice"><div><h3>Google Drive</h3><p>Открыть зашифрованную облачную копию</p></div><button class="secondary" data-action="drive-settings">Подключить</button></div>${oldVaults.length ? `<div class="notice"><strong>Прежние хранилища браузера</strong><p>Скачайте копии перед удалением. Новые данные сюда не записываются.</p>${oldVaults.map((v,n) => `<div class="backup-row"><span>${esc(v.name)}</span><button data-action="legacy-export" data-index="${n}">Скачать</button><button class="danger" data-action="legacy-delete" data-index="${n}">Удалить</button></div>`).join('')}</div>` : ''}<p class="welcome-foot">${icon('lock')}Мастер-пароль не передаётся на сервер</p></section>`);
}
function steps(current) { return `<div class="steps"><${current === 1 ? 'b' : 'span'}>01 Хранилище</${current === 1 ? 'b' : 'span'}><i class="step-line"></i><${current === 2 ? 'b' : 'span'}>02 Защита</${current === 2 ? 'b' : 'span'}><i class="step-line"></i><${current === 3 ? 'b' : 'span'}>03 Восстановление</${current === 3 ? 'b' : 'span'}></div>`; }
function wizardHeader(step, title, intro) { return `<section class="wizard"><button class="back" data-action="wizard-back">${icon('back')}Назад</button>${steps(step)}<h1>${title}</h1><p class="intro">${intro}</p>`; }
function newVault() {
  if (!state.create) state.create = { name: '', location: 'memory', directory: null, step: 1 };
  state.view = 'create'; state.create.step = 1;
  shell(`${wizardHeader(1, 'Создать новое хранилище', 'Сначала создайте хранилище. Сохранить файл или подключить Google Drive можно после создания.')}<form id="create-location" class="form"><div class="field"><label for="vault-name">Название хранилища</label><input id="vault-name" name="name" placeholder="Например, Main" value="${esc(state.create.name)}" maxlength="100" autocomplete="off" required><small>До сохранения в файл или Google Drive хранилище существует в памяти вкладки.</small></div><p id="form-error" class="form-error"></p><div class="wizard-actions"><button type="button" class="secondary" data-action="import">Открыть существующее</button><button class="primary" type="submit">Продолжить${icon('arrow')}</button></div></form></section>`, 'Новое хранилище');
  document.querySelector('#vault-name').focus();
}
function protection() {
  state.view = 'create'; state.create.step = 2;
  shell(`${wizardHeader(2, 'Защитите ваше хранилище', `Придумайте мастер-пароль для «${esc(state.create.name)}». Он понадобится для каждого открытия.`)}<form id="create-password" class="form"><div class="field"><label for="master-password">Мастер-пароль</label><div class="password-input"><input id="master-password" name="password" type="password" placeholder="Не менее 8 символов" autocomplete="new-password" required><button type="button" class="icon-button quiet" data-action="reveal" data-target="master-password" aria-label="Показать мастер-пароль">${icon('eye')}</button></div><small>От 8 до 128 символов. Можно использовать пробелы и кириллицу.</small></div><div class="field"><label for="master-repeat">Повторите мастер-пароль</label><input id="master-repeat" name="repeat" type="password" placeholder="Введите пароль ещё раз" autocomplete="new-password" required></div><div class="password-hint">${icon('shield')}Шифрование происходит здесь, в вашем браузере.</div><p id="form-error" class="form-error"></p><div class="wizard-actions"><span class="hint">Шаг 2 из 3</span><button class="primary" type="submit">Продолжить${icon('arrow')}</button></div></form></section>`, 'Защита');
  document.querySelector('#master-password').focus();
}
function recovery() {
  state.create.step = 3;
  shell(`${wizardHeader(3, 'Ваш запасной ключ', 'Если вы забудете мастер-пароль, этот ключ поможет вернуть доступ. Сохраните его отдельно от хранилища.')}<div class="recovery-key" id="recovery-key" aria-label="Ключ восстановления">${esc(state.create.recovery)}</div><div class="inline-actions"><button data-action="copy-recovery">${icon('copy')}Копировать</button><button data-action="save-recovery">${icon('download')}Сохранить ключ</button></div><label class="confirmation"><input id="recovery-confirm" type="checkbox"><span>Я сохранил(а) ключ восстановления в отдельном безопасном месте.</span></label><p id="form-error" class="form-error"></p><div class="wizard-actions"><span class="hint">Шаг 3 из 3</span><button id="finish-create" class="primary" data-action="finish-create" disabled>Создать хранилище${icon('arrow')}</button></div></section>`, 'Восстановление');
}
function unlockScreen(record, mode = 'master') {
  state.record = record; state.view = 'unlock'; state.recoveryMode = mode === 'recovery';
  shell(`<section class="lock-card"><div class="welcome-mark">${icon('lock')}</div><h1>${esc(record.name)}</h1><p class="intro">${mode === 'recovery' ? 'Введите ключ восстановления и задайте новый мастер-пароль.' : 'Ваше хранилище заблокировано.<br>Введите мастер-пароль, чтобы продолжить.'}</p><form id="unlock-form" class="form"><div class="field"><label for="unlock-secret">${mode === 'recovery' ? 'Ключ восстановления' : 'Мастер-пароль'}</label><div class="password-input"><input id="unlock-secret" type="password" autocomplete="${mode === 'recovery' ? 'off' : 'current-password'}" placeholder="${mode === 'recovery' ? '52 символа ключа' : 'Введите мастер-пароль'}" required><button type="button" class="icon-button quiet" data-action="reveal" data-target="unlock-secret" aria-label="Показать секрет">${icon('eye')}</button></div></div>${mode === 'recovery' ? '<div class="field"><label for="recovery-password">Новый мастер-пароль</label><input id="recovery-password" type="password" autocomplete="new-password" placeholder="От 8 до 128 символов" required></div><div class="field"><label for="recovery-repeat">Повторите новый пароль</label><input id="recovery-repeat" type="password" autocomplete="new-password" required></div>' : ''}<p id="form-error" class="form-error"></p><button class="primary" type="submit">${mode === 'recovery' ? 'Восстановить доступ' : 'Разблокировать'}</button></form><button class="quiet" data-action="${mode === 'recovery' ? 'unlock-normal' : 'unlock-recovery'}">${mode === 'recovery' ? 'Вернуться к мастер-паролю' : 'Забыли мастер-пароль?'}</button><div><button class="quiet" data-action="home">Все хранилища</button></div></section>`, mode === 'recovery' ? 'Восстановление' : 'Хранилище заблокировано');
  document.querySelector('#unlock-secret').focus();
}
async function flushFile(record) {
  if (!record.fileHandle || !record.filePending) return record;
  try {
    const permission = await record.fileHandle.queryPermission({ mode: 'readwrite' });
    if (permission !== 'granted') return record;
    const current = new Uint8Array(await (await record.fileHandle.getFile()).arrayBuffer());
    if (record.fileHash && await hash(current) !== record.fileHash) { toast('Файл изменён другой программой. Изменения только в памяти вкладки; скачайте отдельную копию.'); return record; }
    if (!record.fileHash && current.byteLength) { toast('Файл уже содержит данные. Скачайте отдельную копию.'); return record; }
    const stream = await record.fileHandle.createWritable({ mode: 'exclusive' });
    try { await stream.write(record.blob); await stream.close(); } catch (e) { await stream.abort().catch(() => {}); throw e; }
    const updated = { ...record, fileHash: await hash(record.blob), filePending: false }; return await putVault(updated);
  } catch { toast('Файл не удалось обновить. Изменения только в памяти вкладки — скачайте копию перед закрытием.'); return record; }
}
async function hash(bytes) { return [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(v => v.toString(16).padStart(2, '0')).join(''); }
async function persist(document, metadataOnly = false) {
  const token = state.token, generation = state.generation;
  const staged = await rpc('update', { token, document });
  try {
    const saved = await saveSnapshot(state.record, staged.blob, metadataOnly);
    await rpc('commit', { token, stage: staged.stage });
    if (generation !== state.generation) return;
    state.record = await flushFile(saved); state.doc = staged.document;
    if (state.record.drive) state.record = await putVault({ ...state.record, cloudPending: true });
    else if (!metadataOnly && state.record.filePending && !state.record.memoryOnly) { download(state.record.blob, filename(state.record.name) + '-vault-export.pmvault'); }
  } catch (e) { if (worker) await rpc('discard', { token }).catch(() => {}); throw e; }
}
async function finishCreate() {
  if (!document.querySelector('#recovery-confirm').checked) throw new Error('Сначала подтвердите сохранение ключа.');
  const c = state.create, encoded = await rpc('encode', { token: c.token });
  let fileHandle;
  if (c.directory) {
    const name = filename(c.name) + '.pmvault';
    try { await c.directory.getFileHandle(name); throw new Error('В выбранной папке уже есть файл с таким именем. Измените имя хранилища.'); }
    catch (e) { if (e.name !== 'NotFoundError') throw e; }
    fileHandle = await c.directory.getFileHandle(name, { create: true });
  }
  const record = { id: crypto.randomUUID(), name: c.name, blob: encoded.blob, backups: [], updatedAt: now(), fileHandle: fileHandle || null, filePending: true, drive: null, memoryOnly: !fileHandle };
  const saved = await putVault(record);
  state.record = await flushFile(saved); state.doc = encoded.document; state.token = c.token; state.create = null; state.dirty = false;
  syncSchedule.reset(syncMinutes(state.doc.settings));
  await refreshRecent(); workspace();
  showModal('Хранилище создано', '<p>Выберите, куда сохранить зашифрованную копию. До сохранения не закрывайте вкладку.</p><div class="modal-actions"><button class="secondary" data-action="save-file">Сохранить файл</button><button class="primary" data-action="drive-settings">Сохранить в Google Drive</button></div>');
}
function visibleEntries() {
  return Object.values(state.doc.entries).filter(e => !!e.deleted_at === (state.category === 'trash') && (['all', 'trash'].includes(state.category) || (state.category === 'none' ? e.category === null : descendants(state.doc, state.category).has(e.category))) && ['title', 'site', 'username', 'email', 'note'].some(f => e[f].toLocaleLowerCase('ru').includes(state.query.toLocaleLowerCase('ru')))).sort((a, b) => a.title.localeCompare(b.title, 'ru'));
}
function workspaceSidebar() {
  const doc = state.doc, active = Object.values(doc.entries).filter(e => !e.deleted_at).length, trash = Object.values(doc.entries).filter(e => e.deleted_at).length;
  return `<aside class="sidebar">${brand()}<button class="vault-switch" data-action="switch-vault">${icon('vault')}<div><strong>${esc(state.record.name)}</strong><small>${state.record.drive ? 'Google Drive' : 'Файл на ПК'}</small></div>${icon('chevron')}</button><nav aria-label="Разделы хранилища"><button class="nav-link ${state.category === 'all' ? 'active' : ''}" data-action="filter" data-id="all" title="Все записи">${icon('key')}<span>Все записи</span><span class="count">${active}</span></button><button class="nav-link ${state.category === 'none' ? 'active' : ''}" data-action="filter" data-id="none" title="Без категории">${icon('folder')}<span>Без категории</span></button><div class="section-caption"><span>Категории</span><button class="icon-button quiet small" data-action="add-category" aria-label="Создать категорию">${icon('plus')}</button></div>${visibleCategoryRows(doc, collapsedCategories).map(({id, name, depth, path, hasChildren, collapsed}) => `<div class="category-row" draggable="true" data-category-id="${esc(id)}" data-category-depth="${depth}"><button class="nav-link ${state.category === id ? 'active' : ''}" data-action="filter" data-id="${esc(id)}" title="${esc(path)}"><i class="category-dot" data-category-color="${esc(doc.settings.category_colors?.[id] || '#9b87f5')}"></i><span>${depth ? '• ' : ''}${esc(name)}</span></button>${hasChildren ? `<button class="icon-button quiet small category-toggle" data-action="toggle-category" data-id="${esc(id)}" aria-expanded="${!collapsed}" aria-label="${collapsed ? 'Развернуть' : 'Свернуть'} подкатегории ${esc(name)}">${collapsed ? '▸' : '▾'}</button>` : ''}<button class="icon-button quiet small" data-action="manage-category" data-id="${esc(id)}" aria-label="Изменить категорию ${esc(name)}">${icon('settings')}</button></div>`).join('')}<button class="nav-link ${state.category === 'trash' ? 'active' : ''}" data-action="filter" data-id="trash" title="Корзина">${icon('trash')}<span>Корзина</span><span class="count">${trash}</span></button></nav><div class="side-bottom"><button class="nav-link" data-action="generator" title="Генератор">${icon('dice')}<span>Генератор паролей</span></button><button class="nav-link" data-action="settings" title="Настройки">${icon('settings')}<span>Настройки</span></button><div class="footer-actions"><button class="icon-button quiet" data-action="theme" aria-label="Переключить тему">${icon('sun')}</button><span class="version">WEB · 0.38</span><button class="icon-button quiet" data-action="lock" data-allow-busy aria-label="Заблокировать хранилище">${icon('lock')}</button></div></div></aside>`;
}
function recordList() {
  const entries = visibleEntries();
  return entries.length ? entries.map(e => {
    const category = state.doc.categories[e.category] || 'Без категории';
    const color = e.category ? state.doc.settings.category_colors?.[e.category] || '#9b87f5' : '';
    return `<button class="record ${e.id === state.selected ? 'active' : ''}" data-action="select-entry" data-id="${esc(e.id)}"><span class="record-badge">${esc(initials(e.title))}</span><span><strong ${color && state.category === 'all' ? `data-entry-color="${esc(color)}"` : ''}>${esc(e.title)}</strong><small>${esc(e.username || e.email || e.site || 'Без логина')}</small>${state.category === 'all' ? `<small class="record-category">${esc(category)}</small>` : ''}</span></button>`;
  }).join('') : `<div class="empty-state"><p>${state.query ? 'Ничего не найдено.<br>Попробуйте другой запрос.' : state.category === 'trash' ? 'В корзине пока пусто.' : 'Здесь пока нет записей.'}</p></div>`;
}
function applyEntryColors() {
  document.querySelectorAll('[data-entry-color]').forEach(node => { node.style.color = node.dataset.entryColor; });
}
function workspace() {
  state.view = 'workspace'; document.title = state.record.name + ' — Password Manager';
  app.innerHTML = `<div class="workspace ${state.selected || state.editingNew ? 'show-editor' : ''}">${workspaceSidebar()}<section class="entry-column"><div class="entry-toolbar"><div class="entry-toolbar-top"><h2>${state.category === 'trash' ? 'Корзина' : 'Записи'}</h2>${listActions()}<button class="icon-button quiet list-lock" data-action="lock" data-allow-busy aria-label="Заблокировать">${icon('lock')}</button></div><div class="search-wrap">${icon('search')}<input id="search" class="search" type="search" value="${esc(state.query)}" placeholder="Поиск по хранилищу" aria-label="Поиск по хранилищу"></div></div><div class="records" id="records">${recordList()}</div><div class="list-foot" id="list-foot">${visibleEntries().length} записей · Зашифровано на устройстве</div></section><main class="record-editor" id="record-editor"></main></div>`;
  document.querySelectorAll('[data-category-color]').forEach(node => { node.style.backgroundColor = node.dataset.categoryColor; });
  document.querySelectorAll('[data-category-depth]').forEach(node => { if (innerWidth > 760) node.style.paddingLeft = Math.min(Number(node.dataset.categoryDepth), 12) * 14 + 'px'; });
  applyEntryColors();
  renderEditor();
}
function listActions() {
  if (state.category !== 'trash') return `<button class="icon-button quiet" data-action="new-entry" aria-label="Новая запись">${icon('plus')}</button>`;
  const count = Object.values(state.doc.entries).filter(entry => entry.deleted_at).length;
  return `<button class="danger secondary small" data-action="empty-trash" ${count ? '' : 'disabled'}>Очистить корзину</button>`;
}
function renderEditor(draft) {
  const target = document.querySelector('#record-editor'); if (!target) return;
  const entry = draft || state.doc.entries[state.selected];
  if (!entry && !state.editingNew) { target.innerHTML = `<div class="editor-top"><span>${icon('lock')} Личное хранилище</span><div class="editor-actions"><button class="icon-button quiet" data-action="lock" data-allow-busy aria-label="Заблокировать">${icon('lock')}</button><button class="icon-button quiet" data-action="export" aria-label="Скачать зашифрованную копию">${icon('download')}</button></div></div><div class="empty-state">${icon('key')}<h2>Всё начинается с одной записи</h2><p>Сохраните первый аккаунт.<br>Название, логин и пароль — всё будет<br>зашифровано на вашем устройстве.</p><button class="primary" data-action="new-entry">Добавить запись</button></div>`; return; }
  const values = entry || Object.fromEntries([...FIELDS.map(f => [f, '']), ['category', state.category !== 'all' && state.category !== 'none' && state.category !== 'trash' ? state.category : null]]);
  const viewing = !!entry && !state.editingEntry;
  const labels = { title: 'Название', site: 'Сайт', username: 'Логин', email: 'Почта', phone: 'Телефон', password: 'Пароль', note: 'Заметка' };
  const input = (key, placeholder) => `<div class="field"><label for="entry-${key}">${labels[key]}</label><input id="entry-${key}" name="${key}" value="${esc(values[key])}" placeholder="${placeholder}" autocomplete="off" maxlength="100000" ${key === 'title' ? 'required' : ''}></div>`;
  target.innerHTML = `<header class="editor-top"><button class="mobile-menu" data-action="back-list">${icon('back')}Все записи</button><span class="save-state">${entry?.deleted_at ? 'В корзине' : savedStatus()}</span><div class="editor-actions"><button class="icon-button quiet" data-action="export" aria-label="Скачать зашифрованную копию">${icon('download')}</button><button class="icon-button quiet" data-action="lock" data-allow-busy aria-label="Заблокировать">${icon('lock')}</button></div></header><form id="entry-form" class="editor-content"><div class="editor-heading"><span class="record-badge">${entry ? esc(initials(entry.title)) : icon('plus')}</span><div><h1>${entry ? esc(entry.title) : 'Новая запись'}</h1><p>${entry ? esc(entry.site || 'Учётные данные') : 'Добавьте аккаунт в ваше хранилище'}</p></div></div>${input('title', 'Например, Почта')}${input('site', 'example.com')}<div class="field-grid">${input('username', 'Имя пользователя')}${input('email', 'you@example.com')}</div>${input('phone', 'Необязательно')}<div class="field"><label for="entry-password">Пароль</label><div class="password-input"><input id="entry-password" name="password" type="password" value="${esc(values.password)}" placeholder="Пароль аккаунта" autocomplete="new-password" maxlength="100000"><button type="button" class="icon-button quiet" data-action="reveal" data-target="entry-password" aria-label="Показать пароль">${icon('eye')}</button></div><div class="password-buttons"><button type="button" data-action="copy-password">${icon('copy')}Копировать</button><button type="button" data-action="generate-entry">${icon('dice')}Сгенерировать</button></div></div><div class="field"><label for="entry-category">Категория</label><select id="entry-category" name="category"><option value="">Без категории</option>${categoryRows(state.doc).map(({id, path: name}) => `<option value="${esc(id)}" ${values.category === id ? 'selected' : ''}>${esc(name)}</option>`).join('')}</select></div><div class="field"><label for="entry-note">Заметка</label><textarea id="entry-note" name="note" placeholder="Дополнительная информация" maxlength="100000">${esc(values.note)}</textarea></div><p id="form-error" class="form-error"></p><div class="editor-bottom">${entry?.deleted_at ? '<button class="quiet" type="button" data-action="restore-entry">Восстановить</button><button class="danger secondary" type="button" data-action="purge-entry">Удалить навсегда</button>' : `<button class="quiet ${entry ? 'danger' : ''}" type="button" data-action="${entry ? 'trash-entry' : 'cancel-entry'}">${entry ? 'В корзину' : 'Отмена'}</button><button class="primary" type="submit">Сохранить</button>`}</div></form>`;
  if (viewing || entry?.deleted_at) {
    target.querySelectorAll('.field').forEach(field => {
      const control = field.querySelector('input,textarea,select');
      field.hidden = !control.value.trim();
    });
    target.querySelectorAll('.field-grid').forEach(grid => { grid.hidden = [...grid.children].every(field => field.hidden); });
    target.querySelectorAll('input,textarea').forEach(node => { node.readOnly = true; });
    target.querySelectorAll('select').forEach(node => { node.disabled = true; });
    target.querySelector('[data-action="generate-entry"]').hidden = true;
    const save = target.querySelector('[type="submit"]');
    if (save) { save.type = 'button'; save.dataset.action = 'edit-entry'; save.textContent = 'Редактировать'; }
  }
  if (entry?.deleted_at) target.querySelectorAll('input,textarea,select').forEach(node => { node.disabled = true; });
  if (state.editingNew) document.querySelector('#entry-title').focus();
}
function editorValues() {
  const form = document.querySelector('#entry-form'); if (!form) return null;
  const data = new FormData(form), values = Object.fromEntries(FIELDS.map(f => [f, String(data.get(f) || '')])); values.category = data.get('category') || null; return values;
}
async function saveEntry() {
  if (state.selected && !state.editingEntry) return;
  const values = editorValues(); if (!values?.title.trim()) throw new Error('Укажите название записи.');
  const next = clone(state.doc), id = state.selected || crypto.randomUUID();
  next.entries[id] = { ...values, id, deleted_at: null, updated_at: now() }; next.drafts = {};
  await persist(next); state.selected = id; state.editingEntry = false; state.editingNew = false; state.dirty = false; workspace(); toast(state.record.drive ? 'Запись зашифрована · ожидает синхронизации' : 'Запись сохранена');
}
async function confirmLeave() {
  if (!state.dirty) return true;
  const choice = await ask('Сохранить изменения?', 'В записи есть несохранённые изменения.', [{ value: 'cancel', label: 'Остаться' }, { value: 'discard', label: 'Не сохранять' }, { value: 'save', label: 'Сохранить', primary: true }]);
  if (choice === 'cancel') return false;
  if (choice === 'save') await saveEntry(); else if (Object.keys(state.doc.drafts).length) { const next = clone(state.doc); next.drafts = {}; await persist(next, true); }
  state.dirty = false; return true;
}
function showModal(title, content) { modal.innerHTML = `<div class="modal-head"><h2>${title}</h2><button class="icon-button quiet" data-action="close-modal" aria-label="Закрыть">${icon('close')}</button></div>${content}`; modal.showModal(); }
function closeModal() { modal.close(); modal.replaceChildren(); }
function ask(title, message, buttons) {
  return new Promise(resolve => {
    showModal(title, `<p>${esc(message)}</p><div class="modal-actions">${buttons.map(b => `<button data-allow-busy data-choice="${b.value}" class="${b.primary ? 'primary' : 'secondary'}">${b.label}</button>`).join('')}</div>`);
    const finish = value => { modal.removeEventListener('click', onClick); modal.removeEventListener('cancel', onCancel); modal.removeEventListener('close', onClose); closeModal(); resolve(value); };
    const onClick = e => { const button = e.target.closest('[data-choice]'); if (button) finish(button.dataset.choice); else if (e.target.closest('[data-action="close-modal"]')) finish('cancel'); };
    const onCancel = e => { e.preventDefault(); finish('cancel'); };
    const onClose = () => { if (!modal.open) finish('cancel'); };
    modal.addEventListener('click', onClick); modal.addEventListener('cancel', onCancel); modal.addEventListener('close', onClose);
  });
}
async function copy(text, password = false) {
  try { await navigator.clipboard.writeText(text); }
  catch { throw new Error('Браузер не разрешил копирование. Выделите текст и скопируйте вручную.'); }
  if (password) { copiedPassword = text; clearTimeout(clipTimer); clipTimer = setTimeout(clearClipboard, 300000); }
  toast(password ? 'Пароль скопирован. Через 5 минут попробуем очистить текущий буфер.' : 'Скопировано');
}
async function clearClipboard() {
  clearTimeout(clipTimer); const previous = copiedPassword; copiedPassword = null;
  if (!previous) return;
  try { if (await navigator.clipboard.readText() === previous) await navigator.clipboard.writeText(''); } catch { /* Browser permissions may prohibit reading. Never clear unknown content. */ }
}
async function lock() {
  if (!state.token) return;
  // Requests stop on lock; the separate Google authorization remains in memory.
  // Drafts remain encrypted in session
  // memory if their destination is unavailable; the UI never claims disk persistence.
  const record = state.record, values = state.dirty ? editorValues() : null;
  state.view = 'locking';
  closeModal(); app.replaceChildren(); state.generation++;
  let failure = false;
  if (values) { const next = clone(state.doc); next.drafts[state.selected || 'new'] = values; try { await persist(next, true); } catch { failure = true; } }
  pauseDrive();
  if (state.record?.filePending || state.record?.cloudPending) failure = true;
  const locked = state.record || record;
  stopWorker(); state.token = null; state.doc = null; state.selected = null; state.editingNew = false; state.dirty = false;
  clearClipboard(); unlockScreen(locked); if (failure) toast('Есть изменения только в памяти вкладки. После разблокировки скачайте .pmvault или повторите запись в Drive. Не закрывайте вкладку до сохранения.');
}
async function openRecord(record) { state.generation++; stopWorker(); state.token = null; state.doc = null; state.dirty = false; state.selected = null; state.editingNew = false; unlockScreen(record); }
async function importFile(file) {
  if (!file) return; if (file.size > 16 * 1024 * 1024) throw new Error('Максимальный размер хранилища — 16 МиБ.');
  const blob = new Uint8Array(await file.arrayBuffer()); inspect(blob);
  const record = { id: crypto.randomUUID(), name: file.name.replace(/\.pmvault$/i, ''), blob, backups: [], updatedAt: now(), fileHandle: null, imported: true };
  await openRecord(record);
}
async function doUnlock() {
  const secret = document.querySelector('#unlock-secret').value, recoveryMode = state.recoveryMode;
  let newPassword;
  if (recoveryMode) { newPassword = document.querySelector('#recovery-password').value; validatePassword(newPassword); if (newPassword !== document.querySelector('#recovery-repeat').value) throw new Error('Мастер-пароли не совпадают.'); }
  const generation = state.generation;
  const result = await rpc('open', { blob: state.record.blob, secret, recovery: recoveryMode, newPassword, backups: state.record.backups || [], wire: !!state.record.wire, version: state.record.wire });
  if (generation !== state.generation) return;
  if (recoveryMode) {
    const encoded = await rpc('encode', { token: result.token });
    const recovered = { ...state.record, blob: encoded.blob, backups: result.backups, updatedAt: now(), filePending: !!state.record.fileHandle };
    state.record = await putVault(recovered);
  } else {
    const existing = await getVault(state.record.id);
    if (!existing) state.record = await putVault(state.record);
    else if ((existing.sequence || 0) !== (state.record.sequence || 0)) throw new Error('Хранилище обновлено в другой вкладке. Откройте его заново из списка.');
  }
  state.record = await flushFile(state.record);
  state.token = result.token; state.doc = result.document;
  if (state.doc.settings.vault_name) state.record = await putVault({ ...state.record, name: state.doc.settings.vault_name }); state.category = 'all'; state.query = ''; state.selected = null; state.editingNew = false; state.dirty = false; lastActivity = Date.now();
  if (state.record.drive && state.doc.sync?.pending) state.record = await putVault({ ...state.record, cloudPending: true });
  if (state.record.wire) {
    const encoded = await rpc('encode', { token: state.token });
    state.record = await putVault({ ...state.record, blob: encoded.blob, wire: null });
  }
  await refreshRecent(); workspace();
  syncSchedule.reset(syncMinutes(state.doc.settings));
  if (Object.keys(state.doc.drafts).length) {
    const choice = await ask('Продолжить черновик?', 'Перед блокировкой были сохранены незавершённые изменения.', [{ value: 'cancel', label: 'Позже' }, { value: 'resume', label: 'Продолжить', primary: true }]);
    if (choice === 'resume' && state.doc) { const [id, draft] = Object.entries(state.doc.drafts)[0]; state.selected = state.doc.entries[id] ? id : null; state.editingNew = !state.selected; workspace(); state.editingEntry = true; renderEditor(draft); state.dirty = true; }
  }
}
function generator(intoEditor = false) {
  const options = generatorOptions;
  showModal('Генератор паролей', `<form id="generator-form" class="form"><div class="field-grid"><div class="field"><label for="gen-length">Длина</label><input id="gen-length" name="length" type="number" min="8" max="128" value="${options.length}" required></div><div class="field"><label for="gen-count">Количество</label><input id="gen-count" name="count" type="number" min="1" max="100" value="${options.count}" required></div></div><div class="checkboxes">${[['lower', 'a–z'], ['upper', 'A–Z'], ['digits', '0–9'], ['symbols', '!@#'], ['exclude_similar', 'Без похожих символов']].map(([key, label]) => `<label><input type="checkbox" name="${key}" ${options[key] ? 'checked' : ''}> ${label}</label>`).join('')}</div><div class="field"><label for="gen-output">Результат</label><textarea id="gen-output" class="generator-output" readonly placeholder="Нажмите «Сгенерировать»"></textarea></div><p id="form-error" class="form-error"></p><div class="modal-actions">${intoEditor ? '<button type="button" class="secondary" data-action="use-generated">Вставить первый</button>' : ''}<button class="primary" type="submit">Сгенерировать</button></div></form>`);
}
function categoryDialog(id = '', defaultParent = '') {
  const name = state.doc.categories[id] || '';
  showModal(id ? 'Категория' : 'Новая категория', `<form id="category-form" class="form" data-id="${esc(id)}"><div class="field"><label for="category-name">Название</label><input id="category-name" name="name" value="${esc(name)}" maxlength="256" required></div><div class="field"><label for="category-parent">Родительская категория</label><select id="category-parent"><option value="">Без родителя</option>${categoryRows(state.doc).filter(row => !id || !descendants(state.doc, id).has(row.id)).map(row => `<option value="${esc(row.id)}" ${(state.doc.category_parents?.[id] || defaultParent) === row.id ? 'selected' : ''}>${esc(row.path)}</option>`).join('')}</select></div><div class="field"><label for="category-color">Цвет</label><input id="category-color" type="color" value="${esc(state.doc.settings.category_colors?.[id] || '#9b87f5')}"></div><p id="form-error" class="form-error"></p><div class="modal-actions">${id ? `<button type="button" class="secondary" data-action="add-subcategory" data-id="${esc(id)}">Создать подкатегорию</button><button type="button" class="danger secondary" data-action="delete-category" data-id="${esc(id)}">Удалить категорию</button>` : ''}<button class="primary" type="submit">${id ? 'Сохранить' : 'Создать категорию'}</button></div></form>`);
  document.querySelector('#category-name').focus();
}
function syncSettingsFields() {
  const minutes = syncMinutes(state.doc.settings);
  return `<div class="field"><label class="sync-toggle" for="sync-auto"><span>Автоматическая синхронизация Google Drive</span><input id="sync-auto" type="checkbox" ${minutes ? 'checked' : ''}></label><label for="sync-minutes">Интервал в минутах</label><input id="sync-minutes" type="number" min="1" max="1440" step="1" value="${minutes || 5}" ${minutes ? '' : 'disabled'}><small>По умолчанию — 5 минут. Отключите автоматическую синхронизацию для режима «Только вручную». До отправки изменения Drive остаются в памяти вкладки.</small></div>`;
}
function settings() {
  const status = !connected() || !state.record.drive ? ['не подключен', 'disconnected'] : state.record.cloudPending || state.doc.sync?.pending ? ['Требует синхронизации', 'pending'] : ['Подключен', 'connected'];
  showModal('Настройки хранилища', `<form id="settings-form" class="form"><div class="field"><label for="settings-theme">Тема</label><select id="settings-theme" name="theme">${[['system','Системная'],['light','Светлая'],['dark','Тёмная']].map(([key,label]) => `<option value="${key}" ${state.doc.settings.theme === key ? 'selected' : ''}>${label}</option>`).join('')}</select></div><div class="field"><label for="lock-minutes">Автоблокировка, минут</label><input id="lock-minutes" type="number" name="lock_minutes" min="1" max="1440" value="${state.doc.settings.lock_minutes}"></div><hr class="settings-separator"><div class="field"><label for="settings-vault-name">Имя хранилища</label><input id="settings-vault-name" name="vault_name" maxlength="100" value="${esc(state.record.name)}" required></div><hr class="settings-separator"><button type="button" class="secondary settings-single" data-action="drive-settings">Google Drive — Действия</button><p id="drive-connection-status" class="drive-status ${status[1]}">Google Drive — ${status[0]}</p><button type="button" class="secondary settings-single" data-action="drive-sync" ${connected() ? '' : 'disabled'}>Синхронизировать сейчас</button>${syncSettingsFields()}<hr class="settings-separator"><button type="button" class="secondary settings-single" data-action="export">Скачать зашифрованный экспорт</button><button type="button" class="secondary settings-single" data-action="save-file">Сохранить файл на ПК</button><button type="button" class="secondary settings-single" data-action="backups">Резервные состояния</button><hr class="settings-separator"><button type="button" class="danger secondary settings-single" data-action="delete-vault" data-id="${esc(state.record.id)}">Удалить хранилище</button><p class="storage-summary">До сохранения в файл или Google Drive данные существуют в памяти вкладки.</p><div class="modal-actions"><button class="primary" type="submit">Сохранить</button></div></form>`);
}
async function commitSyncStage(staged) {
  try {
    const saved = await saveSnapshot(state.record, staged.blob, true);
    await rpc('commit', { token: state.token, stage: staged.stage });
    state.record = saved; state.doc = staged.document;
  } catch (e) { await rpc('discard', { token: state.token }).catch(() => {}); throw e; }
}
async function syncDrive() {
  if (!state.doc) throw new Error('Сначала откройте хранилище.');
  toast('Синхронизация..', true);
  syncSchedule.reset(syncMinutes(state.doc.settings));
  const transport = await driveTransport(), identity = driveIdentity || await transport.identity();
  if (state.record.drive?.id && state.record.drive.id !== identity.id) throw new Error('Выбран другой Google-аккаунт. Подключите прежний аккаунт.');
  // A complete remote listing precedes any publication; incompatible access stops it.
  const pendingLocal = !!state.record.cloudPending;
  const before = new TextDecoder().decode(canonical({ ...state.doc, revision: 0 }));
  let remote = await transport.fetch();
  state.record = await putVault({ ...state.record, drive: { ...identity, folder: transport.folder }, cloudPending: true });
  let finished = false, checkpointSaved = false;
  const vaultId = inspect(state.record.blob).header.vault_id;
  for (let pass = 0; pass < 4; pass++) {
    await commitSyncStage(await rpc('sync-prepare', { token: state.token, remote }));
    const pending = state.doc.sync.pending;
    if (!pending) { finished = true; break; }
    // Save the immutable queue first; drain both a retry and any later edits.
    await transport.checkpoint(vaultId, state.record.blob);
    checkpointSaved = true;
    const { unb64 } = await import('./core.js');
    const confirmed = await transport.publish(pending.id, unb64(pending.blob));
    await commitSyncStage(await rpc('sync-ack', { token: state.token, id: pending.id, blob: confirmed }));
    remote = await transport.fetch();
  }
  if (!finished) throw new Error('Появляются новые облачные изменения. Повторите обмен; очередь сохранена.');
  const changed = before !== new TextDecoder().decode(canonical({ ...state.doc, revision: 0 }));
  // The pre-publication checkpoint already contains all user data and an exact
  // retryable queue. A second copy solely to clear its pending flag is redundant.
  if (!checkpointSaved && (pendingLocal || changed)) await transport.checkpoint(vaultId, state.record.blob);
  state.record = await putVault({ ...state.record, cloudPending: false, filePending: false });
  const count = Object.keys(conflicts(state.doc.sync.state)).length;
  toast(count ? `Синхронизация выполнена! Конфликтов: ${count}. Выберите варианты в Google Drive → Конфликты.` : 'Синхронизация выполнена!');
  if (state.view === 'workspace') { const values = state.dirty ? editorValues() : null; workspace(); if (values) { renderEditor(values); state.dirty = true; } }
}
function driveDialog() {
  showModal('Google Drive', `<p>Google получает только зашифрованные файлы. Мастер-пароль и ключ восстановления остаются здесь.</p>
    ${!connected() ? `<p>Войдите в Google и разрешите доступ к файлам приложения.</p><button id="google-connect" class="primary" data-action="drive-connect" disabled>Подготовка входа…</button>` : `<p>${esc(driveIdentity?.email || state.record?.drive?.email || 'Google подключён')}</p><div class="inline-actions">${state.doc ? '<button class="primary" data-action="drive-sync">Сохранить и синхронизировать</button><button class="secondary" data-action="drive-conflicts">Конфликты</button>' : '<button class="primary" data-action="drive-list">Открыть из Drive</button>'}<button class="quiet" data-action="drive-disconnect">Отключить Google</button></div>`}
    <p id="form-error" class="form-error"></p><p class="notice">${persistentSessionEnabled() ? 'Подключение Google запоминается на срок до 30 дней и восстанавливается после перезагрузки. Отключение Google завершает сохранённую сессию.' : 'Длительный вход на этом сайте пока недоступен. Подключение сохраняется при блокировке хранилища; после перезагрузки или истечения доступа Google может запросить повторный вход.'} При ошибке сети скачайте .pmvault перед закрытием.</p>`);
  const control = document.querySelector('#google-connect');
  if (control) void loadGoogle().then(() => {
    if (modal.contains(control)) { control.textContent = 'Войти в Google'; control.disabled = false; }
  }).catch(e => {
    if (modal.contains(control)) { control.textContent = 'Повторить подготовку'; control.dataset.action = 'drive-settings'; control.disabled = false; error(e.message); }
  });
}
async function connectDrive() {
  oauthPending = true;
  try {
    await authorize(GOOGLE_WEB_CLIENT_ID);
    driveCache.clear();
    driveIdentity = await (await driveTransport()).identity();
    if (state.doc) { closeModal(); await syncDrive(); driveDialog(); }
    else driveDialog();
  } finally { oauthPending = false; }
}
async function listCloud() {
  const transport = await driveTransport(); cloudCopies = await transport.checkpoints();
  showModal('Копии в Google Drive', `<p>Последние копии показаны первыми. Название содержит имя хранилища и время сохранения (UTC).</p>${cloudCopies.length ? cloudCopies.map((copy, n) => `<div class="backup-row"><small>${esc(copy.name)}</small><button class="secondary small" data-action="drive-open" data-index="${n}">Открыть</button><button class="danger secondary small" data-action="drive-delete" data-index="${n}">Удалить хранилище</button></div>`).join('') : '<p>Сохранённых веб-копий пока нет. Хранилище Windows сначала откройте через экспорт .pmvault, затем подключите тот же Google Cloud проект.</p>'}<p id="form-error" class="form-error"></p>`);
}
function showConflicts() {
  const all = state.doc.sync ? conflicts(state.doc.sync.state) : {};
  showModal('Конфликты', Object.keys(all).length ? Object.entries(all).map(([key, variants]) => `<div class="notice"><strong>${esc(key.startsWith('category_color:') ? 'Цвет категории: ' + (state.doc.categories[key.split(':')[1]] || 'Удалённая категория') : key)}</strong>${Object.entries(variants).map(([dot, value], n) => {
    const hiddenId = 'conflict-' + dot.replaceAll(':', '-');
    return `<div class="backup-row"><div><p>${esc(typeof value === 'string' ? value : value === null ? (key.startsWith('category_color:') ? 'Цвет по умолчанию' : 'Категория удалена') : value.purged_at ? 'Запись удалена навсегда' : `${value.title}${value.deleted_at ? ' · В корзине' : ''}`)}</p>${value?.password !== undefined ? `<p>${esc(value.site)}<br>${esc(value.username)} · ${esc(value.email)}<br>${esc(value.phone)}<br>${esc(value.note)}<br>${esc(value.updated_at)}</p><div class="password-input"><input id="${hiddenId}" type="password" value="${esc(value.password)}" readonly><button class="icon-button" data-action="reveal" data-target="${hiddenId}" aria-label="Показать пароль">${icon('eye')}</button></div>` : ''}</div><button class="secondary small" data-action="drive-resolve" data-key="${esc(key)}" data-dot="${esc(dot)}">Выбрать ${n + 1}</button></div>`;
  }).join('')}</div>`).join('') : '<p>Конфликтов нет.</p>');
}
function help() { showModal('Ваше личное пространство', '<p>Создайте хранилище, задайте мастер-пароль и сохраните запасной ключ. Все поля шифруются на вашем устройстве; сайт не получает содержимое записей.</p><p class="notice">Для обмена с Windows используйте .pmvault. Google Drive подключается через настройки хранилища. На этом этапе используйте вымышленные данные.</p><p>Выберите файл на ПК или Google Drive. В базе браузера новые хранилища не сохраняются. Без прямого доступа к файлу используйте скачивание .pmvault.</p><div class="modal-actions"><button class="primary" data-action="close-modal">Понятно</button></div>'); }

async function deleteVault(id) {
  const record = await getVault(id); if (!record) return;
  const cloud = record.drive && connected();
  const choice = await ask('Удалить хранилище «' + record.name + '»?', 'Удаление уберёт хранилище и его историю из этой вкладки. Скачанные файлы на ПК сохранятся.' + (record.drive ? ' Облачные копии удаляются только отдельным действием.' : ''), [{ value: 'cancel', label: 'Отмена' }, { value: 'local', label: 'Удалить с сайта' }, ...(cloud ? [{ value: 'cloud', label: 'Удалить с сайта и из Drive' }] : [])]);
  if (!['local', 'cloud'].includes(choice)) return;
  if (choice === 'cloud') {
    const transport = await driveTransport();
    await transport.deleteVault(inspect(record.blob).header.vault_id);
  }
  if (state.record?.id === id) { pauseDrive(); stopWorker(); state.generation++; state.token = null; state.doc = null; state.record = null; state.dirty = false; state.selected = null; await clearClipboard(); }
  await forgetVault(id); await refreshRecent(); closeModal(); home(); toast('Хранилище удалено');
}
async function deleteCloudVault(copy) {
  if (!copy) return;
  if (await ask('Удалить хранилище из Google Drive?', 'Будут удалены все служебные версии выбранного хранилища, включая резервные копии. Файлы на ПК и другие хранилища сохранятся. Подключённые устройства могут загрузить свою копию снова.', [{ value: 'cancel', label: 'Отмена' }, { value: 'delete', label: 'Удалить', primary: true }]) !== 'delete') return;
  const transport = await driveTransport(), blob = await transport.readCheckpoint(copy.id), id = inspect(blob).header.vault_id;
  await transport.deleteVault(id);
  // Detach every open copy of this vault to prevent its background re-upload.
  for (const record of await listVaults()) if (inspect(record.blob).header.vault_id === id) {
    const saved = await putVault({ ...record, drive: null, cloudPending: false, filePending: true, memoryOnly: true });
    if (state.record?.id === saved.id) state.record = saved;
  }
  await refreshRecent(); await listCloud(); toast('Облачное хранилище удалено');
}

const actions = {
  'drive-settings': async () => { closeModal(); driveDialog(); },
  'delete-vault': async node => deleteVault(node.dataset.id),
  'drive-delete': async node => deleteCloudVault(cloudCopies[Number(node.dataset.index)]),
  'drive-connect': connectDrive,
  'drive-list': listCloud,
  'drive-sync': async () => { if (!await confirmLeave()) return; closeModal(); await syncDrive(); },
  'drive-conflicts': async () => showConflicts(),
  'drive-resolve': async node => { await commitSyncStage(await rpc('sync-resolve', { token: state.token, key: node.dataset.key, dot: node.dataset.dot })); state.record = await putVault({ ...state.record, cloudPending: true }); showConflicts(); toast('Вариант выбран · ожидает синхронизации'); },
  'drive-disconnect': async () => {
    await stopDrive();
    if (state.record?.drive) {
      download(state.record.blob, filename(state.record.name) + '-vault-export.pmvault');
      state.record = await putVault({ ...state.record, drive: null, fileHandle: null, filePending: true, cloudPending: false });
    }
    driveDialog();
  },
  'drive-open': async node => {
    const copy = cloudCopies[Number(node.dataset.index)]; if (!copy) return;
    const transport = await driveTransport(), blob = await transport.readCheckpoint(copy.id); inspect(blob);
    closeModal(); await openRecord({ id: crypto.randomUUID(), name: copy.vaultName || 'Хранилище Google Drive', blob, wire: copy.version, backups: [], updatedAt: now(), drive: { ...driveIdentity, folder: transport.folder }, filePending: false });
  },
  'legacy-export': async node => { const old = oldVaults[Number(node.dataset.index)]; if (old) download(old.blob, filename(old.name) + '.pmvault'); },
  'legacy-delete': async node => {
    const old = oldVaults[Number(node.dataset.index)]; if (!old) return;
    if (await ask('Удалить прежнюю браузерную копию?', 'Продолжайте только после сохранения и проверки файла .pmvault. Это удалит также прежнюю историю этой копии.', [{ value: 'cancel', label: 'Отмена' }, { value: 'delete', label: 'Файл сохранён — удалить', primary: true }]) !== 'delete') return;
    await removeLegacy(old.id); await refreshRecent(); home();
  },
  home: async () => { if (state.token) { if (!await confirmLeave()) return; await lock(); } state.record = null; state.create = null; stopWorker(); await refreshRecent(); home(); },
  new: async () => { state.create = null; state.record = null; stopWorker(); newVault(); },
  'wizard-back': async () => { if (state.create.step === 1) { state.create = null; home(); } else if (state.create.step === 2) newVault(); else { stopWorker(); state.create.token = null; state.create.recovery = null; protection(); } },
  'choose-folder': async () => { if (!(typeof window.showDirectoryPicker === 'function')) { toast('Выбор папки недоступен. После создания вы сможете скачать файл.'); return; } state.create.directory = await window.showDirectoryPicker({ mode: 'readwrite', id: 'password-manager-vaults' }); document.querySelector('#vault-path').value = state.create.directory.name; },
  'finish-create': finishCreate,
  'save-file': async () => {
    if (!state.record || !await confirmLeave()) return;
    if (typeof window.showSaveFilePicker !== 'function') { download(state.record.blob, filename(state.record.name) + '-vault-export.pmvault'); closeModal(); return; }
    const handle = await window.showSaveFilePicker({ suggestedName: filename(state.record.name) + '.pmvault', types: [{ description: 'Хранилище', accept: { 'application/octet-stream': ['.pmvault'] } }] });
    // Selecting a nonempty destination requires its native overwrite confirmation.
    const previous = new Uint8Array(await (await handle.getFile()).arrayBuffer());
    const fileHash = previous.length ? await hash(previous) : null;
    const saved = await putVault({ ...state.record, fileHandle: handle, fileHash, filePending: true, memoryOnly: false });
    state.record = await flushFile(saved); closeModal(); await refreshRecent(); workspace();
  },
  'copy-recovery': () => copy(state.create.recovery),
  'save-recovery': async () => { download(state.create.recovery + '\n', filename(state.create.name) + '-recovery-key.txt', 'text/plain;charset=utf-8'); toast('Сохраните ключ отдельно от хранилища'); },
  import: async () => {
    if (typeof window.showOpenFilePicker !== 'function') { document.querySelector('#file-input').click(); return; }
    const [handle] = await window.showOpenFilePicker({ types: [{ description: 'Хранилище', accept: { 'application/octet-stream': ['.pmvault'] } }], multiple: false });
    const file = await handle.getFile();
    if (file.size > 16 * 1024 * 1024) throw new Error('Максимальный размер — 16 МиБ.');
    const blob = new Uint8Array(await file.arrayBuffer()); inspect(blob);
    if (await handle.requestPermission({ mode: 'readwrite' }) !== 'granted') throw new Error('Для сохранения в этот файл нужен доступ на запись.');
    await openRecord({ id: crypto.randomUUID(), name: file.name.replace(/\.pmvault$/i, ''), blob, backups: [], updatedAt: now(), fileHandle: handle, fileHash: await hash(blob), filePending: false });
  },
  'open-recent': async node => { const record = await getVault(node.dataset.id); if (!record) throw new Error('Хранилище не найдено на этом устройстве.'); await openRecord(record); },
  'unlock-recovery': async () => unlockScreen(state.record, 'recovery'), 'unlock-normal': async () => unlockScreen(state.record),
  reveal: async node => { const input = document.getElementById(node.dataset.target); input.type = input.type === 'password' ? 'text' : 'password'; node.setAttribute('aria-label', input.type === 'password' ? 'Показать пароль' : 'Скрыть пароль'); },
  theme: async () => { const dark = document.documentElement.dataset.theme !== 'dark'; document.documentElement.dataset.theme = dark ? 'dark' : 'light'; if (state.doc) { const next = clone(state.doc); next.settings.theme = dark ? 'dark' : 'light'; await persist(next, true); } },
  help: async () => help(), 'close-modal': async () => closeModal(),
  lock,
  'switch-vault': async () => { if (!await confirmLeave()) return; await lock(); state.record = null; home(); },
  'edit-entry': async () => { state.editingEntry = true; renderEditor(); },
  'toggle-category': async node => {
    const id = node.dataset.id;
    const hidingSelected = !collapsedCategories.has(id) && state.category !== id && descendants(state.doc, id).has(state.category);
    if (hidingSelected && !await confirmLeave()) return;
    if (collapsedCategories.has(id)) collapsedCategories.delete(id); else collapsedCategories.add(id);
    if (hidingSelected) { state.category = id; state.selected = null; state.editingNew = false; }
    const draft = state.dirty ? editorValues() : null;
    workspace();
    if (draft) { renderEditor(draft); state.dirty = true; }
  },
  'add-subcategory': async node => categoryDialog('', node.dataset.id),
  'manage-category': async node => { if (await confirmLeave()) categoryDialog(node.dataset.id); },
  'delete-category': async node => {
    const id = node.dataset.id;
    if (!Object.hasOwn(state.doc.categories, id)) return;
    if (await ask('Удалить категорию?', 'Записи останутся без категории. Подкатегории сохранятся на уровень выше.', [{value:'cancel', label:'Отмена'}, {value:'delete', label:'Удалить', primary:true}]) !== 'delete') return;
    const next = clone(state.doc); removeCategory(next, id);
    for (const entry of Object.values(next.entries)) if (entry.category === id) { entry.category = null; entry.updated_at = now(); }
    for (const draft of Object.values(next.drafts)) if (draft.category === id) draft.category = null;
    await persist(next); state.category = 'all'; state.selected = null; state.editingNew = false; workspace(); toast('Категория удалена');
  },
  'new-entry': async () => { if (!await confirmLeave()) return; state.selected = null; state.editingNew = true; state.dirty = false; workspace(); },
  'cancel-entry': async () => { if (!await confirmLeave()) return; state.selected = null; state.editingNew = false; workspace(); },
  'select-entry': async node => { if (!await confirmLeave()) return; state.selected = node.dataset.id; state.editingEntry = false; state.editingNew = false; state.dirty = false; workspace(); },
  filter: async node => { if (!await confirmLeave()) return; state.category = node.dataset.id; state.selected = null; state.editingNew = false; workspace(); },
  'back-list': async () => { if (!await confirmLeave()) return; state.selected = null; state.editingNew = false; workspace(); },
  export: async () => { if (state.dirty) toast('Экспорт содержит последнее сохранённое состояние.'); download(state.record.blob, filename(state.record.name) + '-vault-export.pmvault'); },
  'copy-password': () => copy(document.querySelector('#entry-password').value, true),
  'generate-entry': async () => generator(true), generator: async () => generator(false),
  'use-generated': async () => { const first = document.querySelector('#gen-output').value.split('\n')[0]; if (!first) return; closeModal(); document.querySelector('#entry-password').value = first; state.dirty = true; },
  'add-category': async () => { if (await confirmLeave()) categoryDialog(); },
  'trash-entry': async () => { const next = clone(state.doc); next.entries[state.selected].deleted_at = now(); next.entries[state.selected].updated_at = now(); delete next.drafts[state.selected]; await persist(next); state.selected = null; state.dirty = false; workspace(); },
  'restore-entry': async () => { const next = clone(state.doc); next.entries[state.selected].deleted_at = null; next.entries[state.selected].updated_at = now(); await persist(next); state.selected = null; state.dirty = false; workspace(); },
  'purge-entry': async () => { const choice = await ask('Удалить запись навсегда?', 'Запись исчезнет из актуального состояния. Прежние копии могут её содержать.', [{ value: 'cancel', label: 'Отмена' }, { value: 'delete', label: 'Удалить', primary: true }]); if (choice !== 'delete' || !state.doc) return; const next = clone(state.doc); delete next.entries[state.selected]; delete next.drafts[state.selected]; next.tombstones[state.selected] = now(); await persist(next); state.selected = null; state.dirty = false; workspace(); },
  'empty-trash': async () => {
    if (!await confirmLeave()) return;
    const ids = Object.values(state.doc.entries).filter(entry => entry.deleted_at).map(entry => entry.id);
    if (!ids.length) return;
    const choice = await ask('Очистить всю корзину?', `Удалить навсегда все записи из корзины (${ids.length})? Поиск не ограничивает очистку. Прежние резервные копии и экспорты могут содержать эти записи.`, [{ value: 'cancel', label: 'Отмена' }, { value: 'delete', label: 'Очистить корзину', primary: true }]);
    if (choice !== 'delete' || !state.doc) return;
    const next = clone(state.doc), time = now();
    for (const id of ids) { delete next.entries[id]; delete next.drafts[id]; next.tombstones[id] = time; }
    await persist(next); state.selected = null; state.editingNew = false; state.dirty = false; workspace(); toast('Корзина очищена');
  },
  settings: async () => settings(),
  backups: async () => { closeModal(); const all = [state.record.blob, ...(state.record.backups || [])]; showModal('Резервные состояния', `<p>Скачайте зашифрованное состояние и откройте его как отдельную копию. Актуальное хранилище останется на месте.</p>${all.map((_, index) => `<div class="backup-row"><div><strong>${index ? 'Предыдущее состояние ' + index : 'Актуальное состояние'}</strong><small>${index ? 'Файл сохранит прежние значения записей' : 'Последняя успешная запись'}</small></div><button class="secondary small" data-action="download-backup" data-index="${index}">Скачать</button></div>`).join('')}`); },
  'download-backup': async node => { const blob = [state.record.blob, ...(state.record.backups || [])][Number(node.dataset.index)]; if (blob) download(blob, filename(state.record.name) + '-state-' + node.dataset.index + '.pmvault'); }
};
function categoryDropTarget(event) {
  const row = event.target.closest('[data-category-id]');
  if (row) return row.dataset.categoryId;
  return event.target.closest('[data-action=filter][data-id=all]') ? null : undefined;
}
function validCategoryDrop(parent) {
  return state.doc && draggedCategory && parent !== undefined && !descendants(state.doc, draggedCategory).has(parent);
}
document.addEventListener('dragstart', event => {
  const row = event.target.closest('[data-category-id]');
  if (!row || !state.doc || state.busy) { event.preventDefault(); return; }
  draggedCategory = row.dataset.categoryId;
  event.dataTransfer.setData('application/x-password-manager-category', draggedCategory);
  event.dataTransfer.effectAllowed = 'move';
});
document.addEventListener('dragover', event => {
  if (!validCategoryDrop(categoryDropTarget(event))) return;
  event.preventDefault(); event.dataTransfer.dropEffect = 'move';
});
document.addEventListener('drop', event => {
  const parent = categoryDropTarget(event), source = draggedCategory, generation = state.generation;
  if (!validCategoryDrop(parent)) return;
  event.preventDefault(); draggedCategory = null;
  void safe(async () => {
    if (!await confirmLeave() || generation !== state.generation || !state.doc) return;
    const next = clone(state.doc); moveCategory(next, source, parent);
    await persist(next); collapsedCategories.delete(parent); state.category = source;
    state.selected = null; state.editingNew = false; workspace();
  });
});
document.addEventListener('dragend', () => { draggedCategory = null; });

document.addEventListener('click', e => {
  const node = e.target.closest('[data-action]'); if (!node || node.disabled) return;
  if (node.dataset.action === 'lock' && state.busy) { pauseDrive(); state.lockRequested = true; if (modal.open) closeModal(); return; }
  if (node.dataset.action === 'close-modal' && modal.querySelector('[data-choice]')) return;
  const action = actions[node.dataset.action]; if (action) { e.preventDefault(); safe(() => action(node)); }
});
document.addEventListener('change', e => {
  if (e.target.id === 'sync-auto') document.querySelector('#sync-minutes').disabled = !e.target.checked;
  if (e.target.name === 'location') { state.create.location = e.target.value; document.querySelector('#folder-options').hidden = e.target.value !== 'folder'; }
  if (e.target.id === 'recovery-confirm') document.querySelector('#finish-create').disabled = !e.target.checked;
});
document.addEventListener('input', e => {
  if (e.target.closest('#entry-form')) { state.dirty = true; const label = document.querySelector('.save-state'); if (label) label.textContent = 'Есть несохранённые изменения'; }
  if (e.target.id === 'search') { state.query = e.target.value; document.querySelector('#records').innerHTML = recordList(); applyEntryColors(); document.querySelector('#list-foot').textContent = visibleEntries().length + ' записей · Зашифровано на устройстве'; }
});
document.addEventListener('submit', e => {
  e.preventDefault(); const form = e.target;
  safe(async () => {
    if (form.id === 'create-location') { state.create.name = vaultName(document.querySelector('#vault-name').value); protection(); }
    else if (form.id === 'create-password') { const password = document.querySelector('#master-password').value; validatePassword(password); if (password !== document.querySelector('#master-repeat').value) throw new Error('Мастер-пароли не совпадают.'); const prepared = await rpc('prepare', { password, name: state.create.name }); state.create.token = prepared.token; state.create.recovery = prepared.recovery; recovery(); }
    else if (form.id === 'unlock-form') await doUnlock();
    else if (form.id === 'entry-form') await saveEntry();
    else if (form.id === 'category-form') {
      const name = document.querySelector('#category-name').value.trim(), id = form.dataset.id || crypto.randomUUID();
      if (!name) throw new Error('Введите название категории.');
      if (Object.entries(state.doc.categories).some(([key, value]) => key !== id && value === name)) throw new Error('Такая категория уже существует.');
      const next = clone(state.doc); next.categories[id] = name; next.category_parents ??= {};
      const parent = document.querySelector('#category-parent').value;
      if (parent) next.category_parents[id] = parent; else delete next.category_parents[id];
      validateParents(next);
      next.settings.category_colors ??= {}; next.settings.category_colors[id] = document.querySelector('#category-color').value;
      await persist(next); closeModal(); workspace();
    }
    else if (form.id === 'generator-form') { const data = new FormData(form), options = { length: Number(data.get('length')), count: Number(data.get('count')), ...Object.fromEntries(['lower', 'upper', 'digits', 'symbols', 'exclude_similar'].map(k => [k, data.has(k)])) }; const passwords = generate(options); generatorOptions = options; document.querySelector('#gen-output').value = passwords.join('\n'); }
    else if (form.id === 'settings-form') {
      const next = clone(state.doc), previousInterval = syncMinutes(next.settings);
      next.settings.lock_minutes = Number(new FormData(form).get('lock_minutes'));
      next.settings.vault_name = vaultName(new FormData(form).get('vault_name'));
      next.settings.theme = new FormData(form).get('theme');
      next.settings.sync_minutes = document.querySelector('#sync-auto').checked ? Number(document.querySelector('#sync-minutes').value) : 0;
      if (!Number.isInteger(next.settings.sync_minutes) || next.settings.sync_minutes < (document.querySelector('#sync-auto').checked ? 1 : 0) || next.settings.sync_minutes > 1440) throw new Error('Интервал синхронизации: от 1 до 1440 минут, либо только вручную.');
      await persist(next, true);
      if (previousInterval !== next.settings.sync_minutes) syncSchedule.reset(next.settings.sync_minutes);
      state.record = await putVault({ ...state.record, name: next.settings.vault_name });
      document.documentElement.dataset.theme = next.settings.theme === 'system' ? (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light') : next.settings.theme;
      await refreshRecent(); closeModal(); workspace(); toast('Настройки сохранены');
    }
  });
});
document.querySelector('#file-input').addEventListener('change', e => { const file = e.target.files[0]; e.target.value = ''; safe(() => importFile(file)); });
function checkIdle() {
  if (!state.doc || state.view === 'locking' || state.lockRequested || Date.now() - lastActivity < state.doc.settings.lock_minutes * 60000) return;
  if (state.busy) { pauseDrive(); state.lockRequested = true; if (modal.open) closeModal(); }
  else void safe(lock);
}
for (const name of ['pointerdown', 'keydown', 'wheel']) document.addEventListener(name, () => {
  // Check the deadline before resetting activity, including after background throttling.
  checkIdle(); lastActivity = Date.now();
}, { passive: true });
window.addEventListener('beforeunload', e => { if (state.dirty || state.busy || state.record?.filePending || state.record?.cloudPending) { e.preventDefault(); e.returnValue = ''; } });
setInterval(checkIdle, 1000);
function checkAutoSync() {
  if (!state.doc || !state.record?.drive || !connected() || state.busy || state.dirty || modal.open || state.view !== 'workspace') return;
  if (syncSchedule.due(syncMinutes(state.doc.settings))) void safe(syncDrive);
}
setInterval(checkAutoSync, 1000);
// Returning to the tab checks elapsed inactivity; hiding it never locks immediately.
document.addEventListener('visibilitychange', () => { if (!document.hidden && !oauthPending) checkIdle(); });
document.addEventListener('keydown', e => { if (e.key.toLowerCase() === 'l' && (e.ctrlKey || e.metaKey) && e.shiftKey && state.token) { e.preventDefault(); safe(lock); } });
try { if (!crypto.subtle) throw new Error('Для шифрования нужен HTTPS или localhost.'); await initializeGoogleSession(GOOGLE_WEB_CLIENT_ID); await refreshRecent(); if (!state.recent.length && !oldVaults.length && !connected()) newVault(); else home(); }
catch (e) { shell(`<section class="welcome"><h1>Не удалось открыть пространство</h1><p class="intro">${esc(e.message)}</p><button class="secondary" data-action="help">Как это работает</button></section>`); }
