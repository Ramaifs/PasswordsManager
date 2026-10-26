// Only the last opened vault UUID is persisted; vault data and Google tokens stay out.
const KEY = 'pm-last-opened-vault';
const uuid = value => typeof value === 'string' && /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(value);
let lastVault = null;
export function lastOpenedVault() {
  if (lastVault) return lastVault;
  try { const saved = globalThis.localStorage?.getItem(KEY); if (uuid(saved)) lastVault = saved; } catch {}
  return lastVault;
}
export function rememberOpenedVault(value) {
  if (!uuid(value)) return;
  lastVault = value;
  try { globalThis.localStorage?.setItem(KEY, value); } catch {}
}
export function backupTime(copy) {
  for (const value of [copy.modifiedAt, copy.createdAt]) {
    if (typeof value !== 'string' || !/(Z|[+-]\d\d:\d\d)$/.test(value)) continue;
    const time = Date.parse(value); if (Number.isFinite(time)) return time;
  }
  const match = /-Backup-(\d{4}-\d\d-\d\d)-(\d\d:\d\d:\d\d)\.pmvault$/.exec(copy.name || '');
  if (match) { const stamp = match[1] + 'T' + match[2]; const time = Date.parse(stamp + 'Z'); if (Number.isFinite(time) && new Date(time).toISOString().slice(0,19) === stamp) return time; }
  return -Infinity;
}
export function orderedCopies(copies) {
  const compare = (a, b) => a < b ? -1 : a > b ? 1 : 0;
  return [...copies].sort((a, b) => {
    const left = backupTime(a), right = backupTime(b);
    return (left === right ? 0 : left > right ? -1 : 1) || compare(a.name || '', b.name || '') || compare(a.id, b.id);
  });
}
export function groupCopies(copies, lastVault) {
  const ordered = orderedCopies(copies);
  const latest = ordered.find(copy => lastVault && copy.vaultId === lastVault) || null;
  return { latest, others: ordered.filter(copy => copy.id !== latest?.id) };
}
export function displayTime(copy) {
  const time = backupTime(copy);
  return time === -Infinity ? 'Время неизвестно' : new Date(time).toISOString().slice(0, 19).replace('T', ' ') + ' UTC';
}
