import { additionalFields } from './additional-fields.js';

export const SPACE_MESSAGE = 'Знак пробела запрещено писать в записях (доступно только через продвинутые настройки)';
export const CREDENTIAL_FIELDS = ['email', 'phone', 'username', 'site', 'password', 'second_password', 'old_passwords'];
export const FIELD_NAMES = {
  title: 'название', site: 'сайт', username: 'логин', email: 'почта', phone: 'телефон',
  password: 'пароль', second_password: 'второй пароль', old_passwords: 'старые пароли',
  note: 'заметка', category: 'категория', color: 'цвет', entry_type: 'тип записи', allow_spaces: 'разрешение пробелов'
};
export const hasSpace = value => /[\s\u0085]/u.test(value);
const clean = value => value.replace(/[\s\u0085]/gu, '');
export function spaceFields(entry) {
  if (entry.allow_spaces) return [];
  return CREDENTIAL_FIELDS.filter(field => [entry[field] || '', ...(entry.additional_fields?.[field] || [])].some(hasSpace));
}
export function spaceProblems(doc) {
  return Object.values(doc.entries).map(entry => ({entry, fields: spaceFields(entry)})).filter(item => item.fields.length);
}
export function repairSpaces(doc) {
  for (const {entry, fields} of spaceProblems(doc)) {
    if (entry.entry_type === 'password' && !clean(entry.password)) continue;
    for (const field of fields) {
      if (Object.hasOwn(entry, field)) entry[field] = clean(entry[field]);
      if (entry.additional_fields?.[field]) entry.additional_fields[field] = entry.additional_fields[field].map(clean);
    }
    entry.updated_at = new Date().toISOString();
  }
}

function categoryPath(doc, id) {
  const names = [];
  while (id) {
    names.unshift(doc.categories[id]);
    id = doc.category_parents?.[id];
  }
  return names.join(' / ');
}

export function entryChanges(before, after) {
  const changes = [];
  const ids = new Set([...Object.keys(before.entries), ...Object.keys(after.entries), ...Object.keys(after.tombstones)]);
  for (const id of ids) {
    const a = before.entries[id], b = after.entries[id], fields = [];
    if (!b) {
      if (a || !Object.hasOwn(before.tombstones, id)) fields.push(Object.hasOwn(after.tombstones, id) ? 'Удалена окончательно' : 'Отсутствует в версии');
    } else if (!a) {
      fields.push(b.deleted_at ? 'Добавлена в корзину' : 'Добавлена');
    } else {
      if (!!a.deleted_at !== !!b.deleted_at) fields.push(b.deleted_at ? 'В корзине' : 'Восстановлена из корзины');
      const extraA = additionalFields(a), extraB = additionalFields(b);
      for (const [key, label] of Object.entries(FIELD_NAMES)) {
        if ((a[key] ?? '') !== (b[key] ?? '') || JSON.stringify(extraA[key] || []) !== JSON.stringify(extraB[key] || []))
          fields.push('Изменено поле «' + label + '»');
      }
      if (a.category && a.category === b.category && categoryPath(before, a.category) !== categoryPath(after, b.category)) fields.push('Изменён путь категории');
    }
    if (fields.length) changes.push({ id, title: b?.title || a?.title || id, fields });
  }
  return changes.sort((a, b) => a.title.localeCompare(b.title, 'ru') || a.id.localeCompare(b.id));
}
