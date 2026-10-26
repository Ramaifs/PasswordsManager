export function vaultName(value) {
  if (typeof value !== 'string' || !value.trim() || [...value].length > 100 || /[\x00-\x1f]/.test(value)) throw new Error('Название хранилища: от 1 до 100 символов без управляющих знаков.');
  return value.trim();
}
export function backupName(name, date = new Date()) {
  return `${vaultName(name).replace(/[<>:"/\\|?*]/g, '_')}-Backup-${date.toISOString().slice(0, 19).replace('T', '-')}.pmvault`;
}
export function nameFromBackup(name) {
  return typeof name === 'string' && /^.+-Backup-\d{4}-\d\d-\d\d-\d\d:\d\d:\d\d\.pmvault$/.test(name) ? name.slice(0, name.lastIndexOf('-Backup-')) : null;
}
