// Session cache only. New vault bytes are never persisted in IndexedDB.
const records = new Map();
export const listVaults = async () => [...records.values()].map(v => ({ ...v }));
export const getVault = async id => records.get(id);
export async function putVault(record) {
  const current = records.get(record.id);
  if (current && (current.sequence || 0) !== (record.sequence || 0)) throw new Error('Хранилище уже обновлено. Откройте актуальную версию.');
  const saved = { ...record, sequence: (current?.sequence || 0) + 1 };
  records.set(saved.id, saved); return saved;
}
export const forgetVault = async id => records.delete(id);
export async function saveSnapshot(record, blob, metadataOnly = false) {
  return putVault({ ...record, blob, updatedAt: new Date().toISOString(), filePending: !record.drive,
    backups: metadataOnly ? record.backups || [] : [record.blob, ...(record.backups || [])].filter(Boolean).slice(0, 7) });
}
