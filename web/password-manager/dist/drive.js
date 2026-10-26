// Transport receives encrypted bytes only. No vault keys or record fields.
import { parseStrict, canonical } from './core.js';
import { inspect } from './core.js';
import { backupName, nameFromBackup } from './vault-names.js';
import { orderedCopies } from './cloud-backups.js';
const API = 'https://www.googleapis.com/drive/v3/files';
const APP = 'personal-password-manager-v1', FOLDER = 'application/vnd.google-apps.folder';
const MAX = 4 * 1024 * 1024;
const id = value => { if (typeof value !== 'string' || !/^[A-Za-z0-9_-]{1,200}$/.test(value)) throw new Error('Некорректный идентификатор Google Drive.'); return value; };
const owned = m => m.appProperties?.pm_app === APP && m.appProperties?.pm_object === m.id;
const equal = (a, b) => a.length === b.length && a.every((v, i) => v === b[i]);
export class DriveTransport {
  constructor(token, { signal, fetcher = globalThis.fetch, folder = null, cache = new Map(), vaultId = null, vaultName = 'Main' } = {}) {
    this.token = token; this.signal = signal;
    // Browser fetch is a Window/Worker method; transport must not become its receiver.
    this.fetcher = fetcher.bind(globalThis); this.folder = folder; this.cache = cache;
    this.folderIds = null; this.remote = null; this.vaultId = vaultId; this.vaultName = vaultName;
  }
  async call(method, url, { body, type, binary = false, limit = 2 * 1024 * 1024 } = {}) {
    const controller = new AbortController(), onAbort = () => controller.abort();
    this.signal?.addEventListener('abort', onAbort, { once: true });
    const timeout = setTimeout(() => controller.abort(), 30000);
    try {
      if (this.signal?.aborted) throw new DOMException('Обмен остановлен', 'AbortError');
      const response = await this.fetcher(url, { method, headers: { Authorization: 'Bearer ' + this.token, ...(type ? { 'Content-Type': type } : {}) }, body, signal: controller.signal, credentials: 'omit', redirect: 'error', cache: 'no-store', referrerPolicy: 'no-referrer' });
      if (!response.ok) {
        if (response.status === 401) throw new Error('Срок входа в Google истёк. Подключитесь заново.');
        throw new Error(`Google Drive: запрос не выполнен (${response.status}). Локальные данные сохранены.`);
      }
      if (Number(response.headers.get('content-length')) > limit) throw new Error('Ответ Drive слишком большой.');
      const reader = response.body.getReader(); const chunks = []; let size = 0;
      try {
        while (true) { const { done, value } = await reader.read(); if (done) break; size += value.length; if (size > limit) throw new Error('Ответ Drive превышает безопасный предел.'); chunks.push(value); }
      } finally { await reader.cancel().catch(() => {}); }
      const bytes = new Uint8Array(size); let offset = 0; for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
      if (this.signal?.aborted) throw new DOMException('Обмен остановлен', 'AbortError');
      return binary ? bytes : parseStrict(bytes);
    } finally { clearTimeout(timeout); this.signal?.removeEventListener('abort', onAbort); }
  }
  async list(q) {
    const files = [], pages = new Set(); let page;
    for (let n = 0; n < 100; n++) {
      const params = new URLSearchParams({ q, pageSize: '1000', fields: 'nextPageToken,incompleteSearch,files(id,name,mimeType,appProperties,size,parents,version,md5Checksum,modifiedTime,createdTime)' });
      if (page) params.set('pageToken', page);
      const value = await this.call('GET', API + '?' + params);
      if (value.incompleteSearch || !Array.isArray(value.files)) throw new Error('Drive не подтвердил полный список файлов.');
      files.push(...value.files); if (files.length > 2000) throw new Error('История Drive слишком большая.');
      if (!value.nextPageToken) return files;
      page = value.nextPageToken; if (typeof page !== 'string' || pages.has(page)) throw new Error('Некорректное продолжение списка Drive.'); pages.add(page);
    }
    throw new Error('Список Drive прочитан не полностью.');
  }
  async identity() {
    const data = await this.call('GET', 'https://www.googleapis.com/drive/v3/about?fields=user(permissionId,emailAddress)');
    return { id: id(data.user?.permissionId), email: typeof data.user.emailAddress === 'string' ? data.user.emailAddress : '' };
  }
  async generateId() { const data = await this.call('GET', API + '/generateIds?count=1&space=drive&type=files'); if (!Array.isArray(data.ids) || data.ids.length !== 1) throw new Error('Drive не выдал ID.'); return id(data.ids[0]); }
  async folders() {
    if (this.folderIds) return this.folderIds;
    const found = await this.list(`trashed = false and mimeType = '${FOLDER}' and appProperties has { key='pm_app' and value='${APP}' }`);
    let folders = found.filter(m => owned(m) && m.mimeType === FOLDER).map(m => id(m.id)).sort();
    if (this.folder && !folders.includes(this.folder)) throw new Error('Папка Drive удалена или недоступна. Автоматическая повторная загрузка остановлена.');
    if (!folders.length) {
      const identity = await this.generateId(), metadata = { id: identity, name: 'Менеджер паролей', mimeType: FOLDER, appProperties: { pm_app: APP, pm_object: identity } };
      const result = await this.call('POST', API + '?fields=id', { body: canonical(metadata), type: 'application/json' });
      if (result.id !== identity) throw new Error('Создание папки не подтверждено.'); folders = [identity];
    }
    this.folder = folders[0]; this.folderIds = folders; return folders;
  }
  async fetch() {
    this.remote = null;
    const remote = new Map(), plans = [], active = new Set(); let total = 0;
    for (const folder of await this.folders()) {
      for (const m of await this.list(`trashed = false and '${folder}' in parents and appProperties has { key='pm_app' and value='${APP}' }`)) {
        if (!owned(m)) continue;
        const version = m.appProperties.pm_version;
        if (version === undefined) continue;
        if (typeof version !== 'string' || !/^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(version)) throw new Error('Некорректный номер облачной версии.');
        if (this.vaultId && m.appProperties.pm_vault && m.appProperties.pm_vault !== this.vaultId) continue;
        const size = Number(m.size); if (!Number.isSafeInteger(size) || size <= 0 || size > MAX) throw new Error('Недопустимый размер версии Drive.');
        total += size; if (total > 64 * 1024 * 1024 || remote.size >= 1000) throw new Error('История Drive превышает безопасный предел.');
        const identity = id(m.id); active.add(identity);
        plans.push({ m, version, size, identity });
        if (plans.length > 1000) throw new Error('История Drive превышает безопасный предел.');
      }
    }
    let cursor = 0, failure;
    // Four bounded downloads overlap network latency; cached encrypted bytes are
    // reused only while Google's monotonically increasing file revision matches.
    await Promise.all(Array.from({ length: Math.min(4, plans.length) }, async () => {
      while (cursor < plans.length && !failure) {
        const { m, version, size, identity } = plans[cursor++];
        try {
          const revision = typeof m.version === 'string' && /^[0-9]+$/.test(m.version) ? `${m.version}:${size}:${m.md5Checksum || ''}` : null;
          const cached = this.cache.get(identity);
          const blob = revision && cached?.revision === revision ? cached.blob : await this.call('GET', API + '/' + identity + '?alt=media', { binary: true, limit: MAX });
          if (blob.length !== size) throw new Error('Передача версии не завершена.');
          if (this.vaultId && inspect(blob).header.vault_id !== this.vaultId) continue;
          if (remote.has(version) && !equal(remote.get(version), blob)) throw new Error('Разные данные с одним номером облачной версии.');
          remote.set(version, blob);
          if (revision) this.cache.set(identity, { revision, blob }); else this.cache.delete(identity);
        } catch (error) { failure = error; }
      }
    }));
    if (failure) { this.remote = null; throw failure; }
    for (const identity of this.cache.keys()) if (!active.has(identity)) this.cache.delete(identity);
    this.remote = [...remote].map(([id, blob]) => ({ id, blob })); return this.remote;
  }
  async publish(version, blob) {
    if (!/^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(version) || !blob.length || blob.length > MAX) throw new Error('Некорректная публикация.');
    const remote = this.remote ?? await this.fetch(), previous = remote.find(v => v.id === version);
    if (previous) { if (!equal(previous.blob, blob)) throw new Error('Облачная версия отличается от локальной очереди.'); return previous.blob; }
    const identity = await this.generateId(), boundary = 'pm_' + crypto.randomUUID().replaceAll('-', '');
    const metadata = { id: identity, name: backupName(this.vaultName), parents: [this.folder], mimeType: 'application/octet-stream', appProperties: { pm_app: APP, pm_object: identity, pm_version: version, ...(this.vaultId ? { pm_vault: this.vaultId } : {}) } };
    const body = new Blob([`--${boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n`, canonical(metadata), `\r\n--${boundary}\r\nContent-Type: application/octet-stream\r\n\r\n`, blob, `\r\n--${boundary}--\r\n`]);
    const result = await this.call('POST', 'https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id', { body, type: 'multipart/related; boundary=' + boundary });
    if (result.id !== identity) throw new Error('Публикация Drive не подтверждена.');
    const confirmed = await this.call('GET', API + '/' + identity + '?alt=media', { binary: true, limit: MAX });
    if (!equal(confirmed, blob)) throw new Error('Прочитанные из Drive байты не совпадают с очередью.');
    this.remote.push({ id: version, blob: confirmed }); return confirmed;
  }
  async checkpoints() {
    const result = [];
    for (const folder of await this.folders()) {
      const files = await this.list(`trashed = false and '${folder}' in parents and appProperties has { key='pm_app' and value='${APP}' }`);
      for (const m of files) if (owned(m) && (m.appProperties.pm_checkpoint === '1' || m.appProperties.pm_version)) {
        const size = Number(m.size);
        if (!Number.isSafeInteger(size) || size < 1 || size > 16 * 1024 * 1024) throw new Error('Недопустимый размер копии Drive.');
        result.push({ id: id(m.id), name: m.name, vaultName: nameFromBackup(m.name), vaultId: m.appProperties.pm_vault || null, size, version: m.appProperties.pm_version || null, modifiedAt: m.modifiedTime || '', createdAt: m.createdTime || '' });
      }
    }
    return orderedCopies(result);
  }
  async readCheckpoint(identity) { return this.call('GET', API + '/' + id(identity) + '?alt=media', { binary: true, limit: 16 * 1024 * 1024 }); }
  async checkpoint(vaultId, blob) {
    if (!blob.length || blob.length > 16 * 1024 * 1024) throw new Error('Копия Drive превышает 16 МиБ.');
    await this.folders();
    const identity = await this.generateId(), boundary = 'pm_' + crypto.randomUUID().replaceAll('-', '');
    const metadata = { id: identity, name: backupName(this.vaultName), parents: [this.folder], mimeType: 'application/octet-stream', appProperties: { pm_app: APP, pm_object: identity, pm_checkpoint: '1', pm_vault: vaultId } };
    const body = new Blob([`--${boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n`, canonical(metadata), `\r\n--${boundary}\r\nContent-Type: application/octet-stream\r\n\r\n`, blob, `\r\n--${boundary}--\r\n`]);
    const result = await this.call('POST', 'https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id', { body, type: 'multipart/related; boundary=' + boundary });
    if (result.id !== identity || !equal(await this.readCheckpoint(identity), blob)) throw new Error('Drive не подтвердил зашифрованную копию.');
    return identity;
  }
  async deleteVault(vaultId) {
    if (!/^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(vaultId)) throw new Error('Некорректный ID хранилища.');
    // Build and validate the complete plan before deleting anything. Copied files
    // lose the object-ID binding and are never part of this plan.
    const copies = await this.checkpoints(), targets = [];
    for (const copy of copies) {
      if (copy.vaultId && copy.vaultId !== vaultId) continue;
      const blob = await this.readCheckpoint(copy.id);
      if (inspect(blob).header.vault_id === vaultId) targets.push(copy.id);
    }
    for (const identity of targets) {
      const current = await this.call('GET', API + '/' + identity + '?fields=id,appProperties');
      if (!owned(current) || (current.appProperties.pm_vault && current.appProperties.pm_vault !== vaultId)) throw new Error('Облачная копия изменилась. Повторите удаление.');
      await this.call('DELETE', API + '/' + identity, { binary: true });
      this.cache.delete(identity);
    }
    this.remote = null;
    return targets.length;
  }
}
