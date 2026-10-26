from copy import deepcopy
import itertools
import uuid

import pytest

from password_manager import model, sync_state
from password_manager.crypto import Access, canonical, unb64
from password_manager.errors import InvalidVault, VaultError
from password_manager.session import Session
from password_manager.storage import Store
from password_manager.sync import SyncEngine, AccessConflict, SyncError

PASSWORD = "fictional sync master phrase"


class MemoryDrive:
    """Immutable server; duplicate id retries return the same exact encrypted bytes."""
    def __init__(self):
        self.files = {}
        self.fail_after_publish = False
    def fetch(self): return dict(self.files)
    def publish(self, version, blob):
        if version in self.files and self.files[version] != blob:
            raise SyncError("immutable collision")
        self.files[version] = blob
        if self.fail_after_publish:
            self.fail_after_publish = False
            raise SyncError("network acknowledgement lost")
        return self.files[version]
    def delete(self, version): self.files.pop(version, None)


@pytest.fixture
def clients(tmp_path):
    access, _ = Access.create(PASSWORD)
    base = model.new_document()
    eid = model.save_entry(base, {"title": "base record", "password": "FICTIONAL-SYNC-SECRET"})
    sessions = []
    for name in ("a", "b", "c"):
        store = Store(tmp_path / name)
        store.commit(access, deepcopy(base))
        session = Session(store)
        session.open(PASSWORD)
        sessions.append(session)
    yield sessions, eid
    for s in sessions: s.store.close()


def align(sessions, drive):
    for _ in range(2):
        for s in sessions:
            SyncEngine(s).exchange(drive)


def test_two_clients_independent_edits_and_local_only_fields(clients):
    (a, b, _), eid = clients
    drive = MemoryDrive()
    align([a, b], drive)
    a.mutate(lambda doc: model.save_entry(doc, {"title": "one", "email": "one@example.invalid"}))
    b.mutate(lambda doc: model.save_entry(doc, {"title": "two", "phone": "FICTIONAL-PHONE"}))
    a.mutate(lambda doc: doc["drafts"].update({"new": {**{f: "" for f in model.FIELDS}, "category": None, "password": "LOCAL-DRAFT-MARKER"}}))
    a.mutate(lambda doc: doc["settings"].update(theme="dark"))
    align([a, b], drive)
    assert len(a.document["entries"]) == len(b.document["entries"]) == 3
    assert a.document["sync"]["state"] == b.document["sync"]["state"]
    for blob in drive.files.values():
        payload = a.access.decode(blob)
        wire = canonical(payload)
        assert b"LOCAL-DRAFT-MARKER" not in wire and b"settings" not in wire and b"drafts" not in wire
        assert b"FICTIONAL-SYNC-SECRET" not in blob
    assert b.document["settings"]["theme"] == "system"


def test_category_and_subcategory_colors_roundtrip_drive(clients):
    (a, b, _), _ = clients
    drive = MemoryDrive()
    align([a, b], drive)
    root = a.mutate(lambda doc: model.category(doc, 'Work'))
    child = a.mutate(lambda doc: model.category(doc, 'Mail', parent_id=root))
    a.mutate(lambda doc: doc['settings'].update(category_colors={root: '#123456', child: '#abcdef'}))
    align([a, b], drive)
    assert b.document['settings'].get('category_colors') == {root: '#123456', child: '#abcdef'}
    assert b.document['category_parents'][child] == root
    b.mutate(lambda doc: doc['settings']['category_colors'].update({child: '#654321'}))
    align([b, a], drive)
    assert a.document['settings']['category_colors'][child] == '#654321'
    a.mutate(lambda doc: doc['settings']['category_colors'].pop(child))
    align([a, b], drive)
    assert child not in b.document['settings']['category_colors']


def test_existing_local_colors_migrate_without_reselection(clients):
    (a, b, _), _ = clients
    drive = MemoryDrive()
    root = a.mutate(lambda doc: model.category(doc, 'Work'))
    align([a, b], drive)
    # A pre-update vault already has sync state, but its colors were local-only.
    legacy = deepcopy(a.document)
    legacy['settings']['category_colors'] = {root: '#112233'}
    a.store.commit(a.access, legacy)
    a.document = legacy
    align([a, b], drive)
    assert b.document['settings'].get('category_colors') == {root: '#112233'}


def test_concurrent_color_changes_resolve_without_resurrection(clients):
    (a, b, _), _ = clients
    drive = MemoryDrive()
    root = a.mutate(lambda doc: model.category(doc, 'Work'))
    a.mutate(lambda doc: doc['settings'].update(category_colors={root: '#112233'}))
    align([a, b], drive)
    a.mutate(lambda doc: doc['settings']['category_colors'].update({root: '#445566'}))
    b.mutate(lambda doc: doc['settings']['category_colors'].pop(root))
    align([a, b], drive)
    key = 'category_color:' + root
    variants = sync_state.conflicts(a.document['sync']['state'])[key]
    assert set(variants.values()) == {None, '#445566'}
    reset = next(dot for dot, value in variants.items() if value is None)
    SyncEngine(a).resolve(key, reset)
    align([a, b], drive)
    assert all(root not in s.document['settings']['category_colors'] for s in (a, b))
    a.mutate(lambda doc: model.delete_category(doc, root))
    align([a, b], drive)
    assert root not in b.document['categories']


@pytest.mark.parametrize('value', ['red', '#abc', '#1234567', 123, {'color': '#112233'}])
def test_wire_category_color_validation(value):
    state = sync_state.empty()
    with pytest.raises(InvalidVault):
        sync_state.write(state, str(uuid.uuid4()), 'category_color:' + str(uuid.uuid4()), value)


def test_conflict_requires_explicit_choice(clients):
    (a, b, _), eid = clients
    drive = MemoryDrive()
    align([a, b], drive)
    a.mutate(lambda doc: model.save_entry(doc, {"title": "changed A", "password": "A-SECRET"}, eid))
    b.mutate(lambda doc: model.save_entry(doc, {"title": "changed B", "password": "B-SECRET"}, eid))
    align([a, b], drive)
    key = f"entry:{eid}"
    variants = sync_state.conflicts(a.document["sync"]["state"])[key]
    assert {v["password"] for v in variants.values()} == {"A-SECRET", "B-SECRET"}
    with pytest.raises(VaultError):
        a.mutate(lambda doc: model.save_entry(doc, {"title": "implicit overwrite"}, eid))
    choice = next(dot for dot, value in variants.items() if value["password"] == "B-SECRET")
    SyncEngine(a).resolve(key, choice)
    align([a, b], drive)
    assert not sync_state.conflicts(a.document["sync"]["state"])
    assert a.document["entries"][eid]["password"] == b.document["entries"][eid]["password"] == "B-SECRET"


@pytest.mark.parametrize("purge", [False, True])
def test_delete_edit_conflict(clients, purge):
    (a, b, _), eid = clients
    drive = MemoryDrive()
    align([a, b], drive)
    a.mutate(lambda doc: model.purge(doc, eid) if purge else model.trash(doc, eid))
    b.mutate(lambda doc: model.save_entry(doc, {"title": "offline edited"}, eid))
    align([a, b], drive)
    assert len(sync_state.conflicts(a.document["sync"]["state"])[f"entry:{eid}"]) == 2


def test_old_offline_state_does_not_resurrect_purge_after_compaction(clients):
    (a, b, c), eid = clients
    drive = MemoryDrive()
    align([a, b, c], drive)
    stale = deepcopy(c.document)
    a.mutate(lambda doc: model.purge(doc, eid))
    SyncEngine(a).exchange(drive)
    for i in range(12):
        a.mutate(lambda doc: model.save_entry(doc, {"title": f"new-{i}"}))
        SyncEngine(a).exchange(drive)
    assert len(drive.files) == 8
    c.document = stale
    SyncEngine(c).exchange(drive)
    assert eid not in c.document["entries"] and eid in c.document["tombstones"]


def test_uncertain_publish_retries_same_blob_after_restart(clients):
    (a, _, _), eid = clients
    drive = MemoryDrive()
    drive.fail_after_publish = True
    with pytest.raises(SyncError): SyncEngine(a).exchange(drive)
    pending = deepcopy(a.document["sync"]["pending"])
    assert drive.files[pending["id"]] == unb64(pending["blob"])
    a.lock()
    a.open(PASSWORD)
    SyncEngine(a).exchange(drive)
    assert a.document["sync"]["pending"] is None
    assert len(drive.files) == 1


def test_failed_confirmation_never_marks_published(clients):
    (a, _, _), _ = clients
    pending = SyncEngine(a).prepare({})
    with pytest.raises(SyncError): SyncEngine(a).acknowledge(pending["id"], b"wrong")
    assert a.document["sync"]["published"] is None
    a.lock()
    with pytest.raises(SyncError): SyncEngine(a).prepare({})


def test_old_key_client_is_blocked_and_local_data_preserved(clients):
    (a, b, _), eid = clients
    drive = MemoryDrive()
    align([a, b], drive)
    a.access = a.store.change_password(a.access, a.document, PASSWORD, "new fictional access phrase")
    SyncEngine(a).exchange(drive)
    b.mutate(lambda doc: model.save_entry(doc, {"title": "unsent old key edit"}, eid))
    before = deepcopy(drive.files)
    with pytest.raises(AccessConflict): SyncEngine(b).exchange(drive)
    assert drive.files == before
    assert b.document["entries"][eid]["title"] == "unsent old key edit"
    assert len(list((b.store.root / "sync-blocked").glob("*.pmvault"))) >= 2


def test_other_vault_stops_all_publication(clients):
    (a, _, _), _ = clients
    other, _ = Access.create(PASSWORD)
    version = str(uuid.uuid4())
    blob = other.encode({"protocol": 1, "id": version, "state": sync_state.empty()})
    drive = MemoryDrive()
    drive.files[version] = blob
    with pytest.raises(AccessConflict): SyncEngine(a).exchange(drive)
    assert len(drive.files) == 1


def test_crdt_merge_laws_and_causal_resolution(clients):
    (a, b, c), eid = clients
    actor = str(uuid.uuid4())
    base = sync_state.seed(a.document, actor)
    branches = []
    for i, session in enumerate((a, b, c)):
        state = deepcopy(base)
        value = deepcopy(a.document["entries"][eid])
        value["password"] = f"branch-{i}"
        sync_state.write(state, session.actor, f"entry:{eid}", value)
        branches.append(state)
    left, right, third = branches
    assert sync_state.merge(left, left) == left
    assert sync_state.merge(left, right) == sync_state.merge(right, left)
    expected = sync_state.merge(sync_state.merge(left, right), third)
    for order in itertools.permutations(branches):
        assert sync_state.merge(order[0], sync_state.merge(order[1], order[2])) == expected
    assert len(expected["registers"][f"entry:{eid}"]) == 3


def test_cleanup_does_not_remove_unresolved_contributors(clients):
    (a, b, _), eid = clients
    drive = MemoryDrive()
    align([a, b], drive)
    a.mutate(lambda doc: model.save_entry(doc, {"title": "A"}, eid))
    b.mutate(lambda doc: model.save_entry(doc, {"title": "B"}, eid))
    align([a, b], drive)
    protected = dict(drive.files)
    for i in range(9):
        a.mutate(lambda doc: model.save_entry(doc, {"title": f"other-{i}"}))
        SyncEngine(a).exchange(drive)
    assert all(v in drive.files for v in protected)


def test_dot_collision_rejected(clients):
    (a, _, _), eid = clients
    base = sync_state.seed(a.document, str(uuid.uuid4()))
    changed = deepcopy(base)
    dot = next(iter(changed["registers"][f"entry:{eid}"]))
    changed["registers"][f"entry:{eid}"][dot]["password"] = "forged value"
    with pytest.raises(InvalidVault): sync_state.merge(base, changed)


def test_explicit_old_key_migration_preserves_both_edits(clients):
    (a, b, _), eid = clients
    drive = MemoryDrive()
    align([a, b], drive)
    a.access = a.store.change_password(a.access, a.document, PASSWORD, "new fictional access phrase")
    a.mutate(lambda doc: model.save_entry(doc, {"title": "new access edit"}, eid))
    SyncEngine(a).exchange(drive)
    b.mutate(lambda doc: model.save_entry(doc, {"title": "old access edit"}, eid))
    version, blob = next((v, blob) for v, blob in drive.files.items() if __import__('json').loads(blob)["header"] == a.access.header)
    from password_manager.crypto import unlock
    source_access, payload = unlock(blob, "new fictional access phrase")
    SyncEngine(b).import_unlocked(blob, source_access, payload, adopt_access=True)
    assert b.store.open("new fictional access phrase")[1] == b.document
    values = sync_state.conflicts(b.document["sync"]["state"])[f"entry:{eid}"].values()
    assert {v["title"] for v in values} == {"new access edit", "old access edit"}
    for i in range(len(b.store.snapshots())):
        b.store.open("new fictional access phrase", index=i)


def test_other_vault_import_is_additive_and_keeps_access(clients):
    (a, _, _), eid = clients
    other, _ = Access.create("other fictional master phrase")
    doc = model.new_document()
    # Deliberately reuse the same UUID in an unrelated vault: namespace must not collide.
    doc["entries"][eid] = deepcopy(a.document["entries"][eid])
    doc["entries"][eid]["title"] = "unrelated imported account"
    blob = other.encode(doc)
    SyncEngine(a).import_unlocked(blob, other, doc)
    assert len(a.document["entries"]) == 2
    assert a.document["entries"][eid]["title"] == "base record"
    assert a.store.open(PASSWORD)[1] == a.document


def test_empty_remote_after_explicit_recreation_is_republished(clients):
    (a, _, _), _ = clients
    drive = MemoryDrive()
    SyncEngine(a).exchange(drive)
    drive.files.clear()
    SyncEngine(a).exchange(drive)
    assert len(drive.files) == 1


def test_old_access_versions_retained_then_compacted_safely(clients):
    (a, _, _), _ = clients
    drive = MemoryDrive()
    SyncEngine(a).exchange(drive)
    old_versions = set(drive.files)
    a.access = a.store.change_password(a.access, a.document, PASSWORD, "new fictional access phrase")
    SyncEngine(a).exchange(drive)
    assert old_versions <= drive.files.keys()
    for i in range(9):
        a.mutate(lambda doc: model.save_entry(doc, {"title": f"after-key-{i}"}))
        SyncEngine(a).exchange(drive)
    assert not old_versions & drive.files.keys()
    assert len(drive.files) == 8


def test_concurrent_cleanup_views_keep_eight_covering_states(clients):
    (a, b, _), _ = clients
    drive = MemoryDrive()
    align([a, b], drive)
    for i in range(11):
        a.mutate(lambda doc: model.save_entry(doc, {"title": f"history-{i}"}))
        pending = SyncEngine(a).prepare(drive.fetch())
        if pending:
            blob = unb64(pending["blob"])
            SyncEngine(a).acknowledge(pending["id"], drive.publish(pending["id"], blob))
    stale_view = drive.fetch()
    SyncEngine(b).prepare(stale_view)
    candidates_a = SyncEngine(a).cleanup_candidates(stale_view)
    candidates_b = SyncEngine(b).cleanup_candidates(stale_view)
    for version in candidates_a: drive.delete(version)
    for version in candidates_b: drive.delete(version)
    assert len(drive.files) >= 8
    SyncEngine(b).exchange(drive)
    assert len(b.document["entries"]) == 12


def test_noop_sync_does_not_consume_local_history(clients):
    (a, _, _), _ = clients
    drive = MemoryDrive()
    engine = SyncEngine(a)
    engine.exchange(drive)
    before = deepcopy(a.document)
    count = len(a.store.snapshots())
    engine.exchange(drive)
    assert a.document == before and len(a.store.snapshots()) == count
