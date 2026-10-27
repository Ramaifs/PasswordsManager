export const EXTRA_FIELDS = ['email', 'phone', 'username', 'site', 'password', 'second_password'];
export const FIELD_LABELS = {title:'Название', site:'Сайт', username:'Логин', email:'Почта', phone:'Телефон', password:'Пароль', second_password:'Второй пароль (2FA)', note:'Заметка'};
export function additionalFields(record) {
  const result = structuredClone(record.additional_fields || {});
  if (record.old_passwords) (result.password ||= []).unshift(record.old_passwords);
  return result;
}
export function migrateOldPasswords(doc) {
  for (const record of [...Object.values(doc.entries), ...Object.values(doc.drafts)]) {
    if (record.old_passwords) { record.additional_fields = additionalFields(record); record.old_passwords = ''; }
  }
  return doc;
}
export function splitPasswords(text) {
  const values = text.split(/\r\n|[\r\n]/).filter(value => value.length);
  if (!values.length) throw new Error('В буфере обмена нет паролей.');
  if (values.length > 1000 || values.some(value => [...value].length > 100000)) throw new Error('Можно вставить до 1000 паролей, каждый до 100000 символов.');
  return values;
}

export function nextPasswordNumber(doc) {
  const values = Object.values(doc.entries).filter(entry => entry.entry_type === 'password' && !entry.deleted_at)
    .map(entry => entry.note.trim()).filter(note => /^[0-9]{1,15}$/.test(note)).map(Number);
  return values.reduce((maximum, value) => Math.max(maximum, value), 0) + 1;
}
