"""Pure domain operations. Deletions retain permanent IDs for future sync."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import uuid
import re

from .errors import VaultError, InvalidVault

FIELDS = ("title", "site", "username", "email", "phone", "password", "second_password", "old_passwords", "note")
OPTIONAL_FIELDS = {"second_password", "old_passwords"}
SECRET_FIELDS = {"password", *OPTIONAL_FIELDS}
SUGGESTION_FIELDS = ("email", "phone", "username", "site")
EXTRA_FIELDS = (*SUGGESTION_FIELDS, "password", "second_password")


def valid_additional(value):
    return (isinstance(value, dict) and not set(value) - set(EXTRA_FIELDS)
            and all(isinstance(items, list) and len(items) <= 100
                    and all(isinstance(item, str) and len(item) <= 100_000 for item in items)
                    for items in value.values()))


def additional_fields(record):
    """Project legacy secrets without modifying immutable sync register values."""
    result = deepcopy(record.get("additional_fields", {}))
    if record.get("old_passwords"):
        # A legacy value may contain punctuation or newlines belonging to the secret.
        result.setdefault("password", []).insert(0, record["old_passwords"])
    return result


def migrate_old_passwords(doc):
    for record in [*doc["entries"].values(), *doc["drafts"].values()]:
        if record.get("old_passwords"):
            record["additional_fields"] = additional_fields(record)
            record["old_passwords"] = ""


def display_fields(record, labels):
    extra = additional_fields(record)
    for key, label in labels.items():
        yield key, label, record.get(key, "")
        for index, value in enumerate(extra.get(key, []), 2):
            yield key, f"{label} №{index}", value


def paste_passwords(doc, text):
    passwords = [line for line in re.split(r"\r\n|[\r\n]", text) if line]
    if not passwords:
        raise VaultError("В буфере обмена нет паролей.")
    if len(passwords) > 1000 or any(len(value) > 100_000 for value in passwords):
        raise VaultError("Можно вставить до 1000 паролей, каждый до 100000 символов.")
    return [save_entry(doc, {"entry_type": "password", "password": value}) for value in passwords]


def suggestions(doc, field):
    if field not in SUGGESTION_FIELDS:
        return []
    values = {}
    for entry in doc["entries"].values():
        for value in [entry[field], *additional_fields(entry).get(field, [])]:
            if not entry["deleted_at"] and value.strip():
                values.setdefault(value.casefold(), value)
    return sorted(values.values(), key=str.casefold)


def valid_fields(record, extra):
    """Accept legacy records without changing immutable causal register values."""
    required = (set(FIELDS) - OPTIONAL_FIELDS) | set(extra)
    return (isinstance(record, dict) and required <= set(record) <= required | OPTIONAL_FIELDS | {"entry_type", "additional_fields"}
            and valid_additional(record.get("additional_fields", {}))
            and record.get("entry_type", "account") in ("account", "password")
            and all(isinstance(record.get(f, ""), str) and len(record.get(f, "")) <= 100_000 for f in FIELDS)
            and (record.get("entry_type") != "password" or
                 (record["category"] is None and not any(record.get("additional_fields", {}).values()) and not any(record.get(f, "") for f in FIELDS if f not in ("title", "password", "note"))
                  and ("id" not in extra or bool(record["password"])))))


def password_title(note):
    return next((line.strip()[:80] for line in note.splitlines() if line.strip()), "Пароль")


def now():
    return datetime.now(timezone.utc).isoformat()


def new_document():
    return {"schema": 1, "entries": {}, "categories": {}, "category_parents": {}, "tombstones": {}, "drafts": {},
            "settings": {"theme": "system", "lock_minutes": 30}, "revision": 0, "sync": None}


def validate(document):
    try:
        if isinstance(document, dict) and "sync" not in document:
            document["sync"] = None  # Backward-compatible local 0.1 documents.
        if isinstance(document, dict) and "category_parents" not in document:
            document["category_parents"] = {}
        if not isinstance(document, dict) or set(document) != set(new_document()) or type(document["schema"]) is not int or document["schema"] != 1:
            raise InvalidVault()
        if type(document["revision"]) is not int or document["revision"] < 0:
            raise InvalidVault()
        for key in ("entries", "categories", "tombstones", "drafts", "settings"):
            if not isinstance(document[key], dict):
                raise InvalidVault()
        for cid, name in document["categories"].items():
            if str(uuid.UUID(cid)) != cid or not isinstance(name, str) or not name.strip() or len(name) > 256:
                raise InvalidVault()
        parents = document["category_parents"]
        if not isinstance(parents, dict):
            raise InvalidVault()
        for cid, parent in parents.items():
            if cid not in document["categories"] or parent not in document["categories"]:
                raise InvalidVault()
            visited = {cid}
            while parent is not None:
                if parent in visited:
                    raise InvalidVault()
                visited.add(parent)
                parent = parents.get(parent)
        for eid, record in document["entries"].items():
            if str(uuid.UUID(eid)) != eid or not isinstance(record, dict):
                raise InvalidVault()
            if not valid_fields(record, {"id", "category", "deleted_at", "updated_at"}) or record["id"] != eid:
                raise InvalidVault()
            if not record["title"].strip():
                raise InvalidVault()
            if record["category"] is not None and record["category"] not in document["categories"]:
                raise InvalidVault()
            for f in ("updated_at", "deleted_at"):
                if record[f] is not None and datetime.fromisoformat(record[f]).tzinfo is None:
                    raise InvalidVault()
        if document["entries"].keys() & document["tombstones"].keys():
            raise InvalidVault()
        for eid, timestamp in document["tombstones"].items():
            if str(uuid.UUID(eid)) != eid or datetime.fromisoformat(timestamp).tzinfo is None:
                raise InvalidVault()
        settings = document["settings"]
        if set(settings) - {"theme", "accent_color", "lock_minutes", "generator", "sync_minutes", "category_colors", "check_updates", "vault_name"}:
            raise InvalidVault()
        if "accent_color" in settings and (not isinstance(settings["accent_color"], str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", settings["accent_color"])):
            raise InvalidVault()
        if "vault_name" in settings:
            from .vault_names import validate_name
            try:
                validate_name(settings["vault_name"])
            except VaultError:
                raise InvalidVault() from None
        if "check_updates" in settings and type(settings["check_updates"]) is not bool:
            raise InvalidVault()
        colors = settings.get("category_colors", {})
        if not isinstance(colors, dict) or any(str(uuid.UUID(cid)) != cid or not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color) for cid, color in colors.items()):
            raise InvalidVault()
        if settings.get("theme") not in ("system", "light", "dark") or type(settings.get("lock_minutes")) is not int or not 1 <= settings["lock_minutes"] <= 1440:
            raise InvalidVault()
        if "sync_minutes" in settings and (type(settings["sync_minutes"]) is not int or not 0 <= settings["sync_minutes"] <= 1440):
            raise InvalidVault()
        if "generator" in settings:
            g = settings["generator"]
            if not isinstance(g, dict) or set(g) != {"length", "count", "lower", "upper", "digits", "symbols", "exclude_similar"}:
                raise InvalidVault()
            if type(g["length"]) is not int or not 8 <= g["length"] <= 128 or type(g["count"]) is not int or not 1 <= g["count"] <= 100:
                raise InvalidVault()
            if any(type(g[k]) is not bool for k in ("lower", "upper", "digits", "symbols", "exclude_similar")) or not any(g[k] for k in ("lower", "upper", "digits", "symbols")):
                raise InvalidVault()
        for key, draft in document["drafts"].items():
            if key != "new":
                if str(uuid.UUID(key)) != key:
                    raise InvalidVault()
            if not valid_fields(draft, {"category"}):
                raise InvalidVault()
            if draft["category"] is not None and not isinstance(draft["category"], str):
                raise InvalidVault()
        if document["sync"] is not None:
            from .sync import validate_metadata
            validate_metadata(document["sync"])
        return document
    except (KeyError, TypeError, ValueError, AttributeError):
        raise InvalidVault() from None


def save_entry(doc, values, entry_id=None):
    values = dict(values)
    if values.get("entry_type") == "password":
        if not isinstance(values.get("password"), str) or not values["password"]:
            raise VaultError("Укажите пароль.")
        if not isinstance(values.get("note", ""), str):
            raise VaultError("Недопустимая заметка.")
        values["title"] = password_title(values.get("note", ""))
    if not isinstance(values.get("title"), str) or not values["title"].strip():
        raise VaultError("Укажите название записи.")
    if set(values) - (set(FIELDS) | {"category", "entry_type", "additional_fields"}):
        raise VaultError("Неизвестные поля записи.")
    if any(not isinstance(values.get(f, ""), str) or len(values.get(f, "")) > 100_000 for f in FIELDS):
        raise VaultError("Недопустимые поля записи.")
    category = values.get("category")
    if category is not None and category not in doc["categories"]:
        raise VaultError("Категория не найдена.")
    if entry_id is not None and entry_id not in doc["entries"]:
        raise VaultError("Запись не найдена.")
    entry_id = entry_id or str(uuid.uuid4())
    record = {f: values.get(f, "") for f in FIELDS}
    if "additional_fields" in values:
        record["additional_fields"] = deepcopy(values["additional_fields"])
    record.update(id=entry_id, category=category, deleted_at=None, updated_at=now())
    if "entry_type" in values:
        record["entry_type"] = values["entry_type"]
    if not valid_fields(record, {"id", "category", "deleted_at", "updated_at"}):
        raise VaultError("Недопустимые поля записи.")
    doc["entries"][entry_id] = record
    doc["drafts"].pop(entry_id, None)
    return entry_id


def category(doc, name, category_id=None, *, parent_id=None):
    if not isinstance(name, str) or not name.strip() or len(name) > 256:
        raise VaultError("Название категории должно содержать от 1 до 256 символов.")
    if name in doc["categories"].values() and doc["categories"].get(category_id) != name:
        raise VaultError("Такая категория уже существует.")
    cid = category_id or str(uuid.uuid4())
    if parent_id is not None and (parent_id not in doc["categories"] or parent_id in category_descendants(doc, cid)):
        raise VaultError("Категорию нельзя поместить внутрь неё самой или её подкатегории.")
    doc["categories"][cid] = name
    if parent_id is not None:
        doc.setdefault("category_parents", {})[cid] = parent_id
    return cid


def category_descendants(doc, cid):
    result, pending, children = {cid}, [cid], {}
    for child, parent in doc.get("category_parents", {}).items():
        children.setdefault(parent, []).append(child)
    while pending:
        for child in children.get(pending.pop(), []):
            if child not in result:
                result.add(child)
                pending.append(child)
    return result


def move_category(doc, cid, parent_id=None):
    if cid not in doc["categories"] or (parent_id is not None and parent_id not in doc["categories"]):
        raise VaultError("Категория не найдена.")
    if parent_id in category_descendants(doc, cid):
        raise VaultError("Категорию нельзя поместить внутрь неё самой или её подкатегории.")
    parents = doc.setdefault("category_parents", {})
    if parent_id is None:
        parents.pop(cid, None)
    else:
        parents[cid] = parent_id


def category_rows(doc):
    children = {}
    for cid in doc["categories"]:
        children.setdefault(doc.get("category_parents", {}).get(cid), []).append(cid)
    result, pending = [], [(cid, 0) for cid in reversed(children.get(None, []))]
    while pending:
        cid, depth = pending.pop()
        result.append((cid, doc["categories"][cid], depth))
        pending.extend((child, depth + 1) for child in reversed(children.get(cid, [])))
    return result


def category_path(doc, cid):
    names, seen = [], set()
    while cid in doc["categories"] and cid not in seen:
        seen.add(cid)
        names.append(doc["categories"][cid])
        cid = doc.get("category_parents", {}).get(cid)
    return " / ".join(reversed(names))


def normalize_category_parents(doc):
    parents = {cid: parent for cid, parent in doc.get("category_parents", {}).items()
               if cid in doc["categories"] and parent in doc["categories"] and cid != parent}
    cyclic = set()
    for cid in sorted(parents):
        chain, positions = [], {}
        while cid in parents:
            if cid in positions:
                cyclic.update(chain[positions[cid]:])
                break
            positions[cid] = len(chain)
            chain.append(cid)
            cid = parents[cid]
    doc["category_parents"] = {cid: parent for cid, parent in parents.items() if cid not in cyclic}
    return doc


def delete_category(doc, cid):
    parents = doc.setdefault("category_parents", {})
    parent = parents.pop(cid, None)
    for child in list(parents):
        if parents[child] == cid:
            if parent is None:
                del parents[child]
            else:
                parents[child] = parent
    doc["categories"].pop(cid)
    doc["settings"].get("category_colors", {}).pop(cid, None)
    for draft in doc["drafts"].values():
        if draft["category"] == cid:
            draft["category"] = None
    for entry in doc["entries"].values():
        if entry["category"] == cid:
            entry.update(category=None, updated_at=now())


def trash(doc, entry_id):
    doc["entries"][entry_id].update(deleted_at=now(), updated_at=now())
    doc["drafts"].pop(entry_id, None)


def restore(doc, entry_id):
    doc["entries"][entry_id].update(deleted_at=None, updated_at=now())


def purge(doc, entry_id):
    doc["entries"].pop(entry_id)
    doc["drafts"].pop(entry_id, None)
    doc["tombstones"][entry_id] = now()


def empty_trash(doc):
    ids = [eid for eid, entry in doc["entries"].items() if entry["deleted_at"]]
    for eid in ids:
        purge(doc, eid)
    return len(ids)


def expire_trash(doc, at=None):
    cutoff = (at or datetime.now(timezone.utc)) - timedelta(days=30)
    for eid, entry in list(doc["entries"].items()):
        if entry["deleted_at"] and datetime.fromisoformat(entry["deleted_at"]) <= cutoff:
            purge(doc, eid)


def search(doc, query="", category_id="all", deleted=False):
    query = query.strip().casefold()
    phone_query = re.sub(r"[^0-9]", "", query) if re.fullmatch(r"\+?[0-9\s().-]+", query) else ""
    def matches(entry):
        values = [entry.get(f, "") for f in FIELDS] + [v for items in additional_fields(entry).values() for v in items]
        return (any(query in value.casefold() for value in values)
                or bool(phone_query and any(phone_query in re.sub(r"[^0-9]", "", number)
                    for value in values for number in re.findall(r"\+?[0-9][0-9\s().-]*", value))))

    selected = category_descendants(doc, category_id)
    return [deepcopy(e) for e in doc["entries"].values()
            if bool(e["deleted_at"]) == deleted and (category_id == "all" or (e.get("entry_type") != "password" and e["category"] in selected)
                or (category_id == "other-passwords" and e.get("entry_type") == "password"))
            and matches(e)]


def backup_diff(current, previous):
    a, b = current["entries"], previous["entries"]
    return {"added": len(b.keys() - a.keys()), "removed": len(a.keys() - b.keys()),
            "changed": sum(a[k] != b[k] for k in a.keys() & b.keys()),
            "categories_changed": current["categories"] != previous["categories"]}
