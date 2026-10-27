from copy import deepcopy
import uuid

from . import model
from .errors import VaultError


class Session:
    def __init__(self, store):
        self.store = store
        self.access = None
        self.document = None
        self.actor = str(uuid.uuid4())

    @property
    def unlocked(self):
        return self.access is not None

    def open(self, password):
        access, doc = self.store.open(password)
        # Expiry is an explicit new persisted state, never a read-time disappearance.
        expired = deepcopy(doc)
        model.expire_trash(expired)
        model.migrate_old_passwords(expired)
        if expired != doc:
            from .sync_state import track
            track(doc, expired, self.actor)
            expired["revision"] += 1
            self.store.commit(access, expired)
            doc = expired
        self.access, self.document = access, doc

    def mutate(self, operation):
        if not self.unlocked:
            raise VaultError("Хранилище заблокировано.")
        updated = deepcopy(self.document)
        result = operation(updated)
        from .sync_state import track
        track(self.document, updated, self.actor)
        updated["revision"] += 1
        self.store.commit(self.access, updated)
        self.document = updated
        return result

    def lock(self):
        self.access = None
        self.document = None
