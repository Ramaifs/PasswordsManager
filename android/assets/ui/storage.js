// Disk contains only authenticated encrypted envelopes and their encrypted history.
import { inspect, b64, unb64 } from './core.js';
const records = new Map();
let startupError;
try {
const disk = JSON.parse(AndroidVault.readVaults());
if (!Array.isArray(disk)) throw new Error(disk.error || 'Локальное сохранение повреждено.');
for (const item of disk) {
  const blob = unb64(item.blob); inspect(blob);
  records.set(item.id, {...item, blob, backups:(item.backups || []).map(value => unb64(value))});
}
} catch(error) { startupError = error; }
function requireStorage() { if (startupError) throw startupError; }
function flush(next) {
  requireStorage();
  const serialized = [...next.values()].map(record => ({
    id:record.id, name:record.name, blob:b64(record.blob), backups:(record.backups || []).map(b64),
    updatedAt:record.updatedAt, sequence:record.sequence, drive:record.drive || null,
    cloudPending:!!record.cloudPending, filePending:false, memoryOnly:false, wire:record.wire || null
  }));
  const result = JSON.parse(AndroidVault.writeVaults(JSON.stringify(serialized)));
  if (result.error) throw new Error(result.error);
}
export const listVaults = async () => { requireStorage(); return [...records.values()].map(v => ({...v})); };
export const getVault = async id => records.get(id);
export async function putVault(record) {
  const current = records.get(record.id);
  if (current && (current.sequence || 0) !== (record.sequence || 0)) throw new Error('Хранилище обновлено. Откройте актуальную версию.');
  inspect(record.blob);
  const saved = {...record, sequence:(current?.sequence || 0)+1, filePending:false, memoryOnly:false};
  const next = new Map(records); next.set(saved.id,saved); flush(next); records.set(saved.id,saved); return saved;
}
export async function forgetVault(id) { const next=new Map(records);next.delete(id);flush(next);records.delete(id); }
export async function saveSnapshot(record,blob,metadataOnly=false) {
  return putVault({...record,blob,updatedAt:new Date().toISOString(),cloudPending:!!record.drive,
    backups:metadataOnly?record.backups || []:[record.blob,...record.backups || []].filter(Boolean).slice(0,7)});
}
