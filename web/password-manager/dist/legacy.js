// Read/export old browser vaults. No new vaults are written to this database.
const NAME = 'personal-password-manager-v1';
async function existingDatabase() {
  if (!globalThis.indexedDB) return null;
  if (indexedDB.databases && !(await indexedDB.databases()).some(db => db.name === NAME)) return null;
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(NAME);
    let absent = false;
    request.onupgradeneeded = () => { absent = true; request.transaction.abort(); };
    request.onerror = () => absent ? resolve(null) : reject(new Error('Не удалось прочитать прежние хранилища браузера.'));
    request.onsuccess = () => resolve(request.result);
  });
}
export async function legacyVaults() {
  const db = await existingDatabase(); if (!db) return [];
  try {
    if (!db.objectStoreNames.contains('vaults')) return [];
    return await new Promise((resolve, reject) => {
      const request = db.transaction('vaults').objectStore('vaults').getAll();
      request.onsuccess = () => resolve(request.result); request.onerror = () => reject(new Error('Ошибка чтения прежних хранилищ.'));
    });
  } finally { db.close(); }
}
export async function removeLegacy(id) {
  const db = await existingDatabase(); if (!db) return;
  try { await new Promise((resolve, reject) => {
    const tx = db.transaction('vaults', 'readwrite'); tx.objectStore('vaults').delete(id);
    tx.oncomplete = resolve; tx.onerror = tx.onabort = () => reject(new Error('Не удалось удалить прежнюю браузерную копию.'));
  }); } finally { db.close(); }
}
