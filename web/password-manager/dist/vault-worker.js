import * as core from './core.js';
import * as sync from './sync.js';
const sessions = new Map();
self.onmessage = async ({ data }) => {
  const { id, operation, args } = data;
  try {
    if (operation === 'prepare') {
      const prepared = await core.createVault(args.password), token = crypto.randomUUID();
      sessions.set(token, { access: prepared.access, document: prepared.document, actor: crypto.randomUUID() });
      self.postMessage({ id, result: { token, recovery: prepared.recovery, document: prepared.document } }); return;
    }
    if (operation === 'open') {
      const opened = await (args.wire ? core.unlockPayload : core.unlockVault)(new Uint8Array(args.blob), args.secret, !!args.recovery);
      if (args.wire) {
        const payload = opened.document;
        if (payload.protocol !== 1 || payload.id !== args.version || Object.keys(payload).sort().join(',') !== 'id,protocol,state') throw new Error('Некорректная облачная версия.');
        sync.validateState(payload.state);
        const doc = core.newDocument(); doc.sync = { state: payload.state, pending: null, published: null, seen: {} };
        opened.document = sync.project(doc, payload.state);
      }
      let backups;
      if (args.recovery) {
        if (!Array.isArray(args.backups) || args.backups.length > 7) throw new Error('Некорректная история хранилища.');
        const previous = opened.access;
        const updated = await core.changePassword(previous, args.newPassword);
        backups = [];
        for (const blob of args.backups) backups.push(await core.encodeVault(updated, await core.decodeVault(previous, new Uint8Array(blob))));
        opened.access = updated;
      }
      const token = crypto.randomUUID(); sessions.set(token, { ...opened, actor: crypto.randomUUID() });
      self.postMessage({ id, result: { token, document: opened.document, backups } }); return;
    }
    const session = sessions.get(args.token); if (!session) throw new Error('Хранилище заблокировано.');
    if (operation === 'commit') {
      if (!session.pending || session.pending.stage !== args.stage) throw new Error('Изменения уже отменены.');
      session.document = session.pending.document; session.pending = null;
      self.postMessage({ id, result: true }); return;
    }
    if (operation === 'discard') { session.pending = null; self.postMessage({ id, result: true }); return; }
    if (operation === 'encode') {
      self.postMessage({ id, result: { blob: await core.encodeVault(session.access, session.document), document: session.document } }); return;
    }
    if (operation === 'update') {
      const next = structuredClone(args.document);
      core.trackChanges(session.document, next, session.actor);
      next.revision = session.document.revision + 1;
      core.validateDocument(next);
      const blob = await core.encodeVault(session.access, next);
      const stage = crypto.randomUUID(); session.pending = { stage, document: next };
      self.postMessage({ id, result: { blob, document: next, stage } }); return;
    }
    if (['sync-prepare', 'sync-ack', 'sync-resolve'].includes(operation)) {
      let next;
      if (operation === 'sync-prepare') next = await sync.prepare(session.access, session.document, session.actor, args.remote);
      if (operation === 'sync-ack') next = await sync.acknowledge(session.access, session.document, args.id, new Uint8Array(args.blob));
      if (operation === 'sync-resolve') next = sync.resolve(session.document, session.actor, args.key, args.dot);
      next.revision = session.document.revision + 1;
      const blob = await core.encodeVault(session.access, next), stage = crypto.randomUUID();
      session.pending = { stage, document: next };
      self.postMessage({ id, result: { blob, document: next, stage } }); return;
    }
    throw new Error('Неизвестная операция.');
  } catch (error) { self.postMessage({ id, error: error instanceof Error ? error.message : 'Операция не выполнена.' }); }
};
