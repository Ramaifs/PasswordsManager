"""Copy-on-write generations; CURRENT is the single atomic commit point.

The caller holds Store's interprocess lock for the entire unlocked session.
All files in a generation are encrypted before its manifest can be published.
"""
from pathlib import Path
from copy import deepcopy
import os
import shutil
import uuid

from .crypto import Access, MAX_FILE, canonical, parse, unlock
from .errors import InvalidVault, StorageError, VaultError
from . import model


def read_bounded(path, limit=MAX_FILE):
    with Path(path).open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise InvalidVault()
    return data


def write_fsynced(path, data):
    with Path(path).open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def export_blob(destination, blob):
    destination = Path(destination)
    if destination.exists():
        raise VaultError("Для экспорта выберите новое имя файла.")
    temporary = destination.with_name(f".{uuid.uuid4()}.tmp")
    try:
        write_fsynced(temporary, blob)
        if os.name == "nt":
            os.rename(temporary, destination)
        else:
            os.link(temporary, destination)
    except OSError:
        raise StorageError() from None
    finally:
        temporary.unlink(missing_ok=True)


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = None
        self.cleanup_pending = False
        self.acquire()

    def acquire(self):
        self._lock = (self.root / "session.lock").open("a+b")
        try:
            self._lock.seek(0)
            if self._lock.read(1) == b"":
                self._lock.write(b"0")
                self._lock.flush()
            self._lock.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self._lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._lock.close()
            self._lock = None
            raise VaultError("Хранилище уже открыто другим экземпляром приложения.") from None

    def close(self):
        if self._lock:
            self._lock.close()
            self._lock = None

    @property
    def exists(self):
        return (self.root / "CURRENT").exists()

    def generation(self):
        manifest = parse(read_bounded(self.root / "CURRENT", 256))
        if not isinstance(manifest, dict) or set(manifest) != {"generation", "count"}:
            raise InvalidVault()
        name = manifest["generation"]
        try:
            if str(uuid.UUID(name)) != name or type(manifest["count"]) is not int or not 1 <= manifest["count"] <= 8:
                raise InvalidVault()
        except (ValueError, TypeError, AttributeError):
            raise InvalidVault() from None
        return self.root / name, manifest["count"]

    def snapshots(self):
        folder, count = self.generation()
        return [folder / f"{i}.pmvault" for i in range(count)]

    def open(self, secret, *, recovery=False, index=0):
        paths = self.snapshots()
        access, document = unlock(read_bounded(paths[index]), secret, recovery=recovery)
        return access, model.validate(document)

    def create(self, password):
        if self.exists:
            raise VaultError("Хранилище уже существует.")
        access, recovery = Access.create(password)
        document = model.new_document()
        self.commit(access, document)
        return access, document, recovery

    def commit(self, access, document, *, previous_access=None, replace_current=False):
        """Preserve up to 7 previous successful states, re-encrypting on key changes."""
        model.validate(document)
        blobs = [access.encode(document)]
        if self.exists:
            previous = self.snapshots()[1:] if previous_access or replace_current else self.snapshots()[:7]
            for path in previous:
                blob = read_bounded(path)
                if previous_access:
                    blob = access.encode(model.validate(previous_access.decode(blob)))
                blobs.append(blob)
        self._publish(blobs)

    def switch_to_copy(self, access, document):
        """Archive every current ciphertext before selecting an independent vault."""
        model.validate(document)
        encoded = access.encode(document)
        archive = None
        if self.exists:
            archive = self.root / "switched-vaults" / str(uuid.uuid4())
            try:
                archive.mkdir(parents=True)
                for index, source in enumerate(self.snapshots()):
                    blob = read_bounded(source)
                    target = archive / f"{index}.pmvault"
                    write_fsynced(target, blob)
                    if read_bounded(target) != blob:
                        raise StorageError()
            except OSError:
                raise StorageError() from None
        self._publish([encoded])
        return archive

    def _publish(self, blobs):
        folder = self.root / str(uuid.uuid4())
        pointer = self.root / f"pointer-{uuid.uuid4()}.tmp"
        try:
            folder.mkdir()
            for i, blob in enumerate(blobs):
                write_fsynced(folder / f"{i}.pmvault", blob)
            write_fsynced(pointer, canonical({"generation": folder.name, "count": len(blobs)}))
            os.replace(pointer, self.root / "CURRENT")
        except OSError:
            # Do not touch CURRENT or previous generations on any pre-commit failure.
            shutil.rmtree(folder, ignore_errors=True)
            pointer.unlink(missing_ok=True)
            raise StorageError() from None
        try:
            self.cleanup_pending = bool(self.cleanup())
        except OSError:
            # Commit has already succeeded: caller must update its in-memory state.
            self.cleanup_pending = True

    def cleanup(self):
        """Delete only UUID directories owned by this repository; never follow links."""
        current, _ = self.generation()
        pending = []
        for path in self.root.iterdir():
            try:
                owned = str(uuid.UUID(path.name)) == path.name
            except ValueError:
                owned = False
            if owned and path != current and path.is_dir() and not path.is_symlink() and not path.is_junction():
                try:
                    shutil.rmtree(path)
                except OSError:
                    pending.append(path.name)
        return pending

    def export(self, destination):
        blob = read_bounded(self.snapshots()[0])
        export_blob(destination, blob)

    def restore_backup(self, access, current, index):
        if not 1 <= index < len(self.snapshots()):
            raise VaultError("Резервное состояние не найдено.")
        previous = model.validate(access.decode(read_bounded(self.snapshots()[index])))
        # Keep tombstones and explicitly tombstone entries removed by restore.
        previous["tombstones"].update(current["tombstones"])
        for eid in current["entries"].keys() - previous["entries"].keys():
            previous["tombstones"][eid] = model.now()
        for eid in previous["entries"]:
            previous["tombstones"].pop(eid, None)
        previous["revision"] = current["revision"] + 1
        previous["drafts"] = current["drafts"]
        previous["sync"] = deepcopy(current["sync"])
        from .sync_state import track
        track(current, previous, str(uuid.uuid4()))
        self.commit(access, previous)
        return previous

    def recover_damaged(self, secret, index):
        """Explicit recovery only: preserve every source byte in a quarantine directory."""
        access, doc = self.open(secret, index=index)
        paths = self.snapshots()
        quarantine = self.root / f"damaged-{uuid.uuid4()}"
        quarantine.mkdir()
        valid = []
        try:
            for path in paths:
                blob = read_bounded(path)
                write_fsynced(quarantine / path.name, blob)
                try:
                    previous = model.validate(access.decode(blob))
                    valid.append((previous, blob))
                except InvalidVault:
                    pass
            doc["revision"] = max([state["revision"] for state, _ in valid] + [doc["revision"]]) + 1
            self._publish([access.encode(doc), *[blob for _, blob in valid[:7]]])
        except OSError:
            raise StorageError() from None
        return access, doc

    def change_password(self, access, doc, current_password, new_password):
        checked, _ = self.open(current_password)
        if checked.key != access.key:
            raise InvalidVault()
        updated = access.change_password(new_password)
        self.commit(updated, doc, previous_access=access)
        return updated

    def rotate_recovery(self, access, doc, current_password, new_recovery):
        checked, _ = self.open(current_password)
        if checked.key != access.key:
            raise InvalidVault()
        updated, _ = Access.create(current_password, new_recovery, access.header["vault_id"], access.header["epoch"] + 1)
        self.commit(updated, doc, previous_access=access)
        return updated

    def recover(self, recovery_key, new_password):
        access, doc = self.open(recovery_key, recovery=True)
        updated = access.change_password(new_password)
        self.commit(updated, doc, previous_access=access)
        return updated, doc
