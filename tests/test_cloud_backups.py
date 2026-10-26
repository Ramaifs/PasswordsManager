from copy import deepcopy
from threading import Event
import hashlib
import uuid

import pytest

from password_manager import model
from password_manager.cloud_backups import ordered_copies, group_copies
from password_manager.crypto import Access, unlock
from password_manager.drive import DriveTransport, APP
from password_manager.errors import StorageError, InvalidVault
from password_manager.storage import Store, read_bounded
from password_manager.preferences import Preferences
from password_manager.sync import SyncError


def test_time_order_and_last_opened_group_are_independent_of_copy_type():
    copies = [
        {'id': 'old-full', 'vaultId': 'a', 'modifiedAt': '2026-10-26T10:00:00Z'},
        {'id': 'new-wire', 'vaultId': 'a', 'version': 'wire', 'modifiedAt': '2026-10-26T12:00:00Z'},
        {'id': 'newest-other', 'vaultId': 'b', 'modifiedAt': '2026-10-26T14:00:00+01:00'},
        {'id': 'fallback', 'name': 'Main-Backup-2026-10-26-11:00:00.pmvault'},
        {'id': 'unknown', 'modifiedAt': 'invalid'},
    ]
    assert [c['id'] for c in ordered_copies(copies)] == ['newest-other', 'new-wire', 'fallback', 'old-full', 'unknown']
    latest, others = group_copies(copies, 'a')
    assert latest['id'] == 'new-wire'
    assert [c['id'] for c in others] == ['newest-other', 'fallback', 'old-full', 'unknown']
    assert len(others) + 1 == len(copies)
    assert group_copies(copies, 'missing')[0] is None


def test_drive_lists_all_vaults_and_checks_ciphertext_before_open(monkeypatch):
    access, _ = Access.create('Fictional cloud copy password')
    blob = access.encode(model.new_document())
    vault = access.header['vault_id']
    version = str(uuid.uuid4())
    metadata = [
        {'id': 'old', 'name': 'Main-Backup-2026-10-26-10:00:00.pmvault', 'size': str(len(blob)), 'modifiedTime': '2026-10-26T10:00:00Z', 'appProperties': {'pm_app': APP, 'pm_object': 'old', 'pm_checkpoint': '1', 'pm_vault': vault}},
        {'id': 'new', 'name': 'Other-Backup-2026-10-26-11:00:00.pmvault', 'size': str(len(blob)), 'modifiedTime': '2026-10-26T11:00:00Z', 'md5Checksum': hashlib.md5(blob).hexdigest(), 'appProperties': {'pm_app': APP, 'pm_object': 'new', 'pm_version': version, 'pm_vault': vault}},
        {'id': 'manual-copy', 'size': str(len(blob)), 'appProperties': {'pm_app': APP, 'pm_object': 'old', 'pm_checkpoint': '1'}},
    ]
    transport = DriveTransport(None, Event())
    transport.vault_id = str(uuid.uuid4())  # browser must include other vaults too
    monkeypatch.setattr(transport, 'folders', lambda: ['folder'])
    monkeypatch.setattr(transport, '_list', lambda query: metadata)
    copies = transport.checkpoints()
    assert [c['id'] for c in copies] == ['new', 'old']
    assert copies[0]['vaultName'] == 'Other'
    monkeypatch.setattr(transport, '_call', lambda *args, **kwargs: blob)
    assert transport.read_checkpoint(copies[0]) == blob
    changed = {**copies[0], 'size': len(blob) + 1}
    with pytest.raises(SyncError):
        transport.read_checkpoint(changed)
    with pytest.raises(SyncError):
        transport.read_checkpoint({**copies[0], 'vaultId': str(uuid.uuid4())})


def test_last_opened_preference_survives_other_preferences(tmp_path):
    prefs = Preferences(tmp_path)
    identity = str(uuid.uuid4())
    prefs.save_last_opened_vault(identity)
    prefs.save_close_action('tray')
    prefs.save_window_mode('maximized')
    restored = Preferences(tmp_path)
    assert restored.last_opened_vault == identity
    assert restored.close_action == 'tray' and restored.window_mode == 'maximized'


def test_switch_archives_every_old_snapshot_before_changing_access(tmp_path):
    store = Store(tmp_path)
    try:
        old_access, doc, _ = store.create('Original fictional password')
        model.save_entry(doc, {'title': 'Original record'})
        store.commit(old_access, doc)
        original = [read_bounded(path) for path in store.snapshots()]
        access, _ = Access.create('Different fictional password')
        new = model.new_document()
        model.save_entry(new, {'title': 'Cloud record'})
        archive = store.switch_to_copy(access, new)
        assert [read_bounded(archive / f'{i}.pmvault') for i in range(len(original))] == original
        assert store.open('Different fictional password')[1] == new
        assert unlock(read_bounded(archive / '0.pmvault'), 'Original fictional password')[1] == doc
        with pytest.raises(InvalidVault):
            store.open('Original fictional password')
        assert len(store.snapshots()) == 1
    finally:
        store.close()


def test_failed_switch_preserves_current_and_archived_ciphertext(tmp_path, monkeypatch):
    store = Store(tmp_path)
    try:
        access, doc, _ = store.create('Original fictional password')
        original = read_bounded(store.snapshots()[0])
        def fail(blobs):
            raise StorageError()
        monkeypatch.setattr(store, '_publish', fail)
        with pytest.raises(StorageError):
            store.switch_to_copy(access, deepcopy(doc))
        assert read_bounded(store.snapshots()[0]) == original
        assert next((tmp_path / 'switched-vaults').glob('*/0.pmvault')).read_bytes() == original
    finally:
        store.close()


def test_archive_write_failure_never_changes_current(tmp_path, monkeypatch):
    import password_manager.storage as storage
    store = Store(tmp_path)
    try:
        access, doc, _ = store.create('Original fictional password')
        original = read_bounded(store.snapshots()[0])
        real_write = storage.write_fsynced
        def fail_archive(path, data):
            if 'switched-vaults' in path.parts:
                raise OSError('Fixture disk failure')
            real_write(path, data)
        monkeypatch.setattr(storage, 'write_fsynced', fail_archive)
        with pytest.raises(StorageError):
            store.switch_to_copy(access, doc)
        assert read_bounded(store.snapshots()[0]) == original
    finally:
        store.close()
