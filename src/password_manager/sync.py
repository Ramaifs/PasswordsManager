"""Durable, retryable encrypted version exchange. Transport never receives a DEK."""
from copy import deepcopy
import hashlib
import re
import uuid

from .crypto import b64, unb64, canonical, checked_envelope
from .errors import InvalidVault, VaultError
from . import sync_state

MAX_CLOUD = 4 * 1024 * 1024
MAX_VERSIONS = 1000


class SyncError(VaultError):
    pass


class AccessConflict(SyncError):
    def __init__(self):
        super().__init__("Обнаружена версия с другим доступом или другое хранилище. Локальные изменения сохранены, публикация остановлена. Для переноса разблокируйте обе версии и подтвердите объединение.")


def digest(value):
    return hashlib.sha256(value).hexdigest()


def header_id(access):
    return digest(canonical(access.header))


def state_id(access, state):
    return digest(canonical([access.header, state]))


def validate_metadata(metadata):
    if not isinstance(metadata, dict) or set(metadata) != {"state", "pending", "published", "seen"}:
        raise InvalidVault()
    sync_state.validate(metadata["state"])
    if not isinstance(metadata["seen"], dict) or len(metadata["seen"]) > 10_000:
        raise InvalidVault()
    for version, observed in metadata["seen"].items():
        sync_state.identifier(version)
        if not isinstance(observed, dict) or set(observed) != {"digest", "vector"}:
            raise InvalidVault()
        fingerprint = observed["digest"]
        if not isinstance(fingerprint, str) or not re.fullmatch("[0-9a-f]{64}", fingerprint):
            raise InvalidVault()
        sync_state.validate({"vector": observed["vector"], "registers": {}})
    if metadata["published"] is not None and (not isinstance(metadata["published"], str) or not re.fullmatch("[0-9a-f]{64}", metadata["published"])):
        raise InvalidVault()
    pending = metadata["pending"]
    if pending is not None:
        if not isinstance(pending, dict) or set(pending) != {"id", "blob", "state_id"}:
            raise InvalidVault()
        sync_state.identifier(pending["id"])
        if len(unb64(pending["blob"])) > MAX_CLOUD:
            raise InvalidVault()
        if not isinstance(pending["state_id"], str) or not re.fullmatch("[0-9a-f]{64}", pending["state_id"]):
            raise InvalidVault()


def version_payload(blob, access, version_id):
    if len(blob) > MAX_CLOUD:
        raise InvalidVault()
    payload = access.decode(blob)
    if set(payload) != {"protocol", "id", "state"} or type(payload["protocol"]) is not int or payload["protocol"] != 1 or payload["id"] != version_id:
        raise InvalidVault()
    sync_state.identifier(version_id)
    sync_state.validate(payload["state"])
    return payload


class SyncEngine:
    def __init__(self, session):
        self.session = session

    def _require(self):
        if not self.session.unlocked:
            raise SyncError("Синхронизация приостановлена: хранилище заблокировано.")

    def _save(self, document):
        self._require()
        if document == self.session.document:
            return
        shared_changed = sync_state.shared(document) != sync_state.shared(self.session.document)
        document["revision"] = self.session.document["revision"] + 1
        self.session.store.commit(self.session.access, document, replace_current=not shared_changed)
        self.session.document = document

    def initialize(self):
        self._require()
        doc = deepcopy(self.session.document)
        if self.session.document["sync"] is None:
            doc["sync"] = {"state": sync_state.seed(doc, self.session.actor), "pending": None,
                           "published": None, "seen": {}}
        else:
            sync_state.migrate_category_colors(doc, self.session.actor)
        self._save(doc)

    def prepare(self, remote):
        """Consume a complete bounded listing. Persist merge + immutable queue before I/O."""
        self.initialize()
        if not isinstance(remote, dict) or len(remote) > MAX_VERSIONS:
            raise SyncError("Слишком много облачных версий; требуется проверка истории.")
        if any(not isinstance(blob, bytes) or len(blob) > MAX_CLOUD for blob in remote.values()) or sum(len(blob) for blob in remote.values()) > 64 * 1024 * 1024:
            raise SyncError("Облачная история превышает безопасный предел загрузки.")
        doc = deepcopy(self.session.document)
        metadata = doc["sync"]
        access = self.session.access
        if metadata["pending"] is not None and checked_envelope(unb64(metadata["pending"]["blob"]))["header"] != access.header:
            old_pending = metadata["pending"]
            old_blob = unb64(old_pending["blob"])
            self._preserve(old_blob)
            # It was authored and saved locally before rekey; current state causally covers it.
            metadata["seen"][old_pending["id"]] = {"digest": digest(old_blob), "vector": deepcopy(metadata["state"]["vector"])}
            metadata["pending"] = None
        state = metadata["state"]
        parsed = {}
        blocked = False
        for version, blob in remote.items():
            sync_state.identifier(version)
            envelope = checked_envelope(blob)
            if envelope["header"] != access.header:
                if metadata["seen"].get(version, {}).get("digest") != digest(blob):
                    self._preserve(blob)
                    blocked = True
                continue
            payload = version_payload(blob, access, version)
            state = sync_state.merge(state, payload["state"])
            parsed[version] = payload
            metadata["seen"][version] = {"digest": digest(blob), "vector": deepcopy(payload["state"]["vector"])}
        if blocked:
            # An encrypted copy of local unsent state remains separate for manual migration.
            self._preserve(access.encode(self.session.document))
            raise AccessConflict()
        metadata["state"] = state
        doc = sync_state.project(doc, state)
        pending = metadata["pending"]
        # First retry the exact existing version. Later edits are published on the next pass.
        represented = any(payload["state"] == state for payload in parsed.values())
        if pending is None and (metadata["published"] != state_id(access, state) or not represented):
            version = str(uuid.uuid4())
            blob = access.encode({"protocol": 1, "id": version, "state": state})
            if len(blob) > MAX_CLOUD:
                raise SyncError("Облачная версия превышает 4 МиБ; локальные данные сохранены.")
            metadata["pending"] = {"id": version, "blob": b64(blob), "state_id": state_id(access, state)}
        # project made a copy; attach the final metadata, including pending/seen.
        doc["sync"] = metadata
        self._save(doc)
        return deepcopy(metadata["pending"])

    def _preserve(self, blob):
        from .storage import write_fsynced
        folder = self.session.store.root / "sync-blocked"
        folder.mkdir(exist_ok=True)
        path = folder / (digest(blob) + ".pmvault")
        if not path.exists():
            write_fsynced(path, blob)

    def acknowledge(self, version, blob):
        self._require()
        doc = deepcopy(self.session.document)
        meta = doc["sync"]
        pending = meta["pending"]
        if pending is None or pending["id"] != version or unb64(pending["blob"]) != blob:
            raise SyncError("Публикация не подтверждена: облачная версия не совпадает с очередью.")
        payload = version_payload(blob, self.session.access, version)
        meta["seen"][version] = {"digest": digest(blob), "vector": deepcopy(payload["state"]["vector"])}
        meta["published"] = pending["state_id"]
        meta["pending"] = None
        self._save(doc)

    def resolve(self, key, dot):
        self.initialize()
        doc = deepcopy(self.session.document)
        state = doc["sync"]["state"]
        variants = sync_state.conflicts(state).get(key, {})
        if dot not in variants:
            raise SyncError("Выбранный вариант конфликта уже изменился.")
        sync_state.write(state, self.session.actor, key, variants[dot])
        self._save(sync_state.project(doc, state))

    def import_unlocked(self, blob, foreign_access, payload, *, adopt_access=False):
        """Called only after explicit GUI confirmation and independent source unlock."""
        from . import model
        self.initialize()
        self._preserve(blob)
        self._preserve(self.session.access.encode(self.session.document))
        doc = deepcopy(self.session.document)
        same_vault = foreign_access.header["vault_id"] == self.session.access.header["vault_id"]
        if payload.get("protocol") == 1:
            source = version_payload(blob, foreign_access, payload.get("id"))
            foreign_state = source["state"]
        else:
            model.validate(payload)
            foreign_state = payload["sync"]["state"] if payload["sync"] else sync_state.seed(payload, str(uuid.uuid4()))
        if same_vault:
            state = sync_state.merge(doc["sync"]["state"], foreign_state)
            doc = sync_state.project(doc, state)
            if payload.get("protocol") == 1:
                doc["sync"]["seen"][payload["id"]] = {"digest": digest(blob), "vector": deepcopy(payload["state"]["vector"])}
        else:
            # Different namespaces: preserve every source variant as a separate imported record.
            categories = {}
            for key, variants in foreign_state["registers"].items():
                kind, eid = key.split(":")
                if kind == "category":
                    names = sorted({v for v in variants.values() if v is not None})
                    for name in names:
                        existing = next((cid for cid, label in doc["categories"].items() if label == name), None)
                        cid = existing or model.category(doc, name)
                        categories.setdefault(eid, cid)
            before = deepcopy(doc)
            for key, variants in foreign_state["registers"].items():
                if not key.startswith("entry:"): continue
                for value in {canonical(v): v for v in variants.values()}.values():
                    if "purged_at" in value: continue
                    values = {f: value[f] for f in model.FIELDS}
                    values["category"] = categories.get(value["category"])
                    eid = model.save_entry(doc, values)
                    if value["deleted_at"]:
                        doc["entries"][eid]["deleted_at"] = value["deleted_at"]
            # Include newly imported categories in causal changes too.
            before["categories"] = deepcopy(self.session.document["categories"])
            sync_state.track(before, doc, self.session.actor)
            if adopt_access:
                raise SyncError("Другое хранилище импортируется с сохранением текущего доступа.")
        pending = doc["sync"]["pending"]
        if pending:
            self._preserve(unb64(pending["blob"]))
        doc["sync"]["pending"] = None
        doc["sync"]["published"] = None
        target = foreign_access if adopt_access else self.session.access
        doc["revision"] += 1
        self.session.store.commit(target, doc, previous_access=self.session.access if adopt_access else None)
        self.session.access, self.session.document = target, doc

    def cleanup_candidates(self, remote):
        self._require()
        current = self.session.document["sync"]["state"]
        protected = {dot for variants in sync_state.conflicts(current).values() for dot in variants}
        states = {}
        for version, blob in remote.items():
            if checked_envelope(blob)["header"] == self.session.access.header:
                states[version] = version_payload(blob, self.session.access, version)["state"]
        def rank(item):
            version, state = item
            return sum(state["vector"].values()), version
        ordered = sorted(states.items(), key=rank)
        result = []
        for i, (version, state) in enumerate(ordered):
            dots = {dot for variants in state["registers"].values() for dot in variants}
            if dots & protected:
                continue
            # Eight distinct immutable later witnesses must each causally cover this state.
            witnesses = [other for other, newer in ordered[i + 1:]
                         if sync_state.merge(state, newer) == newer and not sync_state.conflicts(newer)]
            if len(witnesses) >= 8:
                result.append(version)
        # An old-access file is eligible only when its exact bytes were authenticated and
        # causally integrated before the access change, and eight current-access states
        # each cover that recorded causal context. Unresolved current conflicts retain it.
        if not sync_state.conflicts(current):
            seen = self.session.document["sync"]["seen"]
            for version, blob in remote.items():
                if version in states or seen.get(version, {}).get("digest") != digest(blob):
                    continue
                vector = seen[version]["vector"]
                witnesses = [newer for other, newer in ordered if (sum(newer["vector"].values()), other) > (sum(vector.values()), version)
                             and not sync_state.conflicts(newer)
                             and all(newer["vector"].get(actor, 0) >= counter for actor, counter in vector.items())]
                if len(witnesses) >= 8:
                    result.append(version)
        return result

    def exchange(self, transport):
        """Synchronous orchestration for tests/CLI; GUI splits I/O into cancellable workers."""
        self._require()
        for _ in range(4):
            remote = transport.fetch()
            pending = self.prepare(remote)
            if pending is None:
                break
            blob = unb64(pending["blob"])
            confirmed = transport.publish(pending["id"], blob)
            self.acknowledge(pending["id"], confirmed)
        latest = transport.fetch()
        self.prepare(latest)
        for version in self.cleanup_candidates(latest):
            transport.delete(version)
        return len(sync_state.conflicts(self.session.document["sync"]["state"]))
