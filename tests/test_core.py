from copy import deepcopy
from datetime import datetime, timezone, timedelta
import json
import string

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from password_manager import model
from password_manager.crypto import Access, unlock, canonical, MAX_FILE
from password_manager.errors import InvalidVault, VaultError, StorageError
from password_manager.generator import generate, GeneratorOptions
from password_manager.importer import preview_legacy
from password_manager.storage import Store, read_bounded

PASSWORD = "Вымышленная парольная фраза 123"
NEW_PASSWORD = "Другая тестовая парольная фраза"


@pytest.fixture
def store(tmp_path):
    instance = Store(tmp_path / "data")
    yield instance
    instance.close()


@pytest.fixture
def created(store):
    return store.create(PASSWORD)


@pytest.mark.parametrize("length", [8, 20, 128])
def test_generator(length):
    for password in generate(GeneratorOptions(length=length, count=20)):
        assert len(password) == length
        for group in (string.ascii_lowercase, string.ascii_uppercase, string.digits, "!@#$%^&*()-_=+[]{};:,.?/"):
            assert any(c in group for c in password)
        assert set(password) <= set(string.ascii_letters + string.digits + "!@#$%^&*()-_=+[]{};:,.?/")


@pytest.mark.parametrize("options", [GeneratorOptions(length=7), GeneratorOptions(length=129), GeneratorOptions(count=0),
    GeneratorOptions(count=101), GeneratorOptions(lower=False, upper=False, digits=False, symbols=False)])
def test_bad_generator(options):
    with pytest.raises(VaultError):
        generate(options)


def test_similar_exclusion():
    assert not set("Il1O0o|") & set("".join(generate(GeneratorOptions(count=50, exclude_similar=True))))


@pytest.mark.parametrize("password", ["x" * 8, "x" * 14, "x" * 15, "x" * 128, PASSWORD, " " * 8, "абвгдеёж"])
def test_password_boundaries(password):
    access, recovery = Access.create(password)
    doc = model.new_document()
    blob = access.encode(doc)
    assert unlock(blob, password)[1] == doc
    assert unlock(blob, recovery, recovery=True)[1] == doc


@pytest.mark.parametrize("password", ["", "x" * 7, "x" * 129])
def test_invalid_password(password):
    with pytest.raises(VaultError):
        Access.create(password)


def test_eight_character_password_change_and_recovery(store):
    access, doc, recovery = store.create("абвгдеёж")
    eid = model.save_entry(doc, {"title": "Short master fixture", "password": "FICTIONAL-ENTRY"})
    store.commit(access, doc)
    store.change_password(access, doc, "абвгдеёж", "12345678")
    for index in range(len(store.snapshots())):
        store.open("12345678", index=index)
    store.recover(recovery, "восемь12")
    assert store.open("восемь12")[1]["entries"][eid]["password"] == "FICTIONAL-ENTRY"
    with pytest.raises(InvalidVault):
        store.open("12345678")


def test_persistence_and_no_plaintext(store, created):
    access, doc, recovery = created
    cid = model.category(doc, "CATEGORY-UNIQUE-MARKER")
    eid = model.save_entry(doc, {"title": "TITLE-UNIQUE-MARKER", "password": "PASSWORD-UNIQUE-MARKER", "category": cid})
    doc["drafts"][eid] = {**{f: "" for f in model.FIELDS}, "category": None, "password": "DRAFT-UNIQUE-MARKER"}
    store.commit(access, doc)
    assert store.open(PASSWORD)[1] == doc
    assert store.open(recovery, recovery=True)[1] == doc
    store.close()
    for file in store.root.rglob("*"):
        if file.is_file():
            raw = file.read_bytes()
            for marker in [b"CATEGORY-UNIQUE-MARKER", b"TITLE-UNIQUE-MARKER", b"PASSWORD-UNIQUE-MARKER", b"DRAFT-UNIQUE-MARKER", recovery.encode(), PASSWORD.encode()]:
                assert marker not in raw


def test_wrong_secrets_and_tampering(store, created):
    original = read_bounded(store.snapshots()[0])
    for secret, recovery in [("wrong password long enough", False), ("A" * 52, True)]:
        with pytest.raises(InvalidVault):
            unlock(original, secret, recovery=recovery)
    for field in ["vault_id", "salt", "master", "recovery"]:
        obj = json.loads(original)
        obj["header"][field] = "tampered"
        with pytest.raises(InvalidVault):
            unlock(canonical(obj), PASSWORD)
    obj = json.loads(original)
    obj["payload"]["ciphertext"] = "A" * 100
    with pytest.raises(InvalidVault):
        unlock(canonical(obj), PASSWORD)
    assert read_bounded(store.snapshots()[0]) == original


def test_limits_before_kdf(store, created, monkeypatch):
    raw = read_bounded(store.snapshots()[0])
    obj = json.loads(raw)
    def forbidden(*args):
        pytest.fail("Untrusted parameters reached KDF")
    monkeypatch.setattr("password_manager.crypto.derive", forbidden)
    for key, value in [("version", 999), ("kdf", {"memory": 2**50})]:
        changed = deepcopy(obj)
        changed["header"][key] = value
        with pytest.raises(InvalidVault):
            unlock(canonical(changed), PASSWORD)
    for malformed in [b"{}", b"[]", raw[:100], b"x" * (MAX_FILE + 1), b'{"header":1,"header":2}']:
        with pytest.raises(InvalidVault):
            unlock(malformed, PASSWORD)


def test_aes_gcm_known_vector():
    # NIST SP800-38D, empty plaintext/AAD, 256-bit zero key and 96-bit zero IV.
    assert AESGCM(bytes(32)).encrypt(bytes(12), b"", b"").hex() == "530f8afbc74536b9a963b4f1c4cb738b"


def test_fresh_nonces(created):
    access, doc, _ = created
    nonces = [json.loads(access.encode(doc))["payload"]["nonce"] for _ in range(200)]
    assert len(set(nonces)) == len(nonces)


def test_backups_and_rotation(store, created):
    access, doc, recovery = created
    for i in range(10):
        doc["revision"] = i + 1
        store.commit(access, doc)
    assert [store.open(PASSWORD, index=i)[1]["revision"] for i in range(8)] == list(range(10, 2, -1))
    export = store.root.parent / "export.pmvault"
    store.export(export)
    exported = export.read_bytes()
    access = store.change_password(access, doc, PASSWORD, NEW_PASSWORD)
    for i in range(8):
        assert store.open(NEW_PASSWORD, index=i)[1]["revision"] == 10 - i
        store.open(recovery, recovery=True, index=i)
        with pytest.raises(InvalidVault):
            store.open(PASSWORD, index=i)
    assert export.read_bytes() == exported
    unlock(exported, PASSWORD)
    from password_manager.crypto import recovery_secret
    new_recovery = recovery_secret()
    previous_key = access.key
    access = store.rotate_recovery(access, doc, NEW_PASSWORD, new_recovery)
    assert access.key != previous_key and access.header["epoch"] == 2
    for i in range(8):
        store.open(new_recovery, recovery=True, index=i)
        with pytest.raises(InvalidVault):
            store.open(recovery, recovery=True, index=i)
    assert len(list(store.root.glob("*/0.pmvault"))) == 1


def test_recovery(store, created):
    _, doc, recovery = created
    store.recover(recovery, NEW_PASSWORD)
    assert store.open(NEW_PASSWORD)[1] == doc
    store.open(recovery, recovery=True)


@pytest.mark.parametrize("rotate", [False, True])
def test_failed_commit_preserves_previous(store, created, monkeypatch, rotate):
    access, doc, recovery = created
    before = (store.root / "CURRENT").read_bytes()
    doc["revision"] += 1
    def fail(*args):
        raise OSError("simulated write failure")
    monkeypatch.setattr("password_manager.storage.os.replace", fail)
    with pytest.raises(StorageError):
        if rotate:
            store.change_password(access, doc, PASSWORD, NEW_PASSWORD)
        else:
            store.commit(access, doc)
    assert (store.root / "CURRENT").read_bytes() == before
    assert store.open(PASSWORD)[1]["revision"] == 0
    store.open(recovery, recovery=True)


def test_exclusive_lock(store):
    with pytest.raises(VaultError):
        Store(store.root)


def test_repeated_password_change_preserves_recovery(store, created):
    access, doc, recovery = created
    access = store.change_password(access, doc, PASSWORD, NEW_PASSWORD)
    store.change_password(access, doc, NEW_PASSWORD, PASSWORD)
    assert store.open(PASSWORD)[1] == doc
    assert store.open(recovery, recovery=True)[1] == doc


def test_restore_keeps_current_and_creates_tombstones(store, created):
    access, doc, _ = created
    eid = model.save_entry(doc, {"title": "Will be removed by restore"})
    doc["revision"] = 1
    store.commit(access, doc)
    restored = store.restore_backup(access, doc, 1)
    assert restored["revision"] == 2
    assert eid in restored["tombstones"]
    assert eid in store.open(PASSWORD, index=1)[1]["entries"]


def test_damaged_recovery_preserves_source(store, created):
    access, doc, _ = created
    doc["revision"] = 1
    store.commit(access, doc)
    corrupted = b"DAMAGED-BY-FIXTURE"
    store.snapshots()[0].write_bytes(corrupted)
    with pytest.raises(InvalidVault):
        store.open(PASSWORD)
    access, restored = store.recover_damaged(PASSWORD, 1)
    assert store.open(PASSWORD)[1] == restored
    assert next(store.root.glob("damaged-*/0.pmvault")).read_bytes() == corrupted


def test_cleanup_failure_does_not_report_failed_commit(store, created, monkeypatch):
    access, doc, _ = created
    def fail(): raise OSError("cleanup failure after commit")
    monkeypatch.setattr(store, "cleanup", fail)
    doc["revision"] = 1
    store.commit(access, doc)
    assert store.open(PASSWORD)[1]["revision"] == 1 and store.cleanup_pending


def test_manifest_path_traversal_rejected(store, created):
    (store.root / "CURRENT").write_bytes(canonical({"generation": "../../outside", "count": 1}))
    with pytest.raises(InvalidVault):
        store.open(PASSWORD)


def test_export_failure_is_not_published(store, created, monkeypatch):
    destination = store.root.parent / "failed-export.pmvault"
    from password_manager import storage
    original = storage.write_fsynced
    def fail(path, data):
        original(path, data[:64])
        raise OSError("simulated failed export")
    monkeypatch.setattr(storage, "write_fsynced", fail)
    with pytest.raises(StorageError):
        store.export(destination)
    assert not destination.exists()
    assert not list(destination.parent.glob(".*.tmp"))


def test_domain_and_independent_objects():
    doc = model.new_document()
    first = model.save_entry(doc, {"title": "Same", "email": "one@example.invalid"})
    second = model.save_entry(doc, {"title": "Same", "email": "two@example.invalid"})
    category = model.category(doc, "Test")
    model.save_entry(doc, {"title": "Updated", "category": category}, first)
    assert doc["entries"][second]["email"] == "two@example.invalid"
    assert [e["id"] for e in model.search(doc, "two@example")] == [second]
    model.delete_category(doc, category)
    assert doc["entries"][first]["category"] is None
    model.trash(doc, first)
    assert len(model.search(doc, deleted=True)) == 1
    model.restore(doc, first)
    assert len(model.search(doc)) == 2
    model.trash(doc, first)
    model.expire_trash(doc, datetime.now(timezone.utc) + timedelta(days=31))
    assert first not in doc["entries"] and first in doc["tombstones"]
    assert model.validate(doc) == doc


def test_import_fixture():
    from pathlib import Path
    data = Path("examples/legacy-demo.json").read_bytes()
    rows = preview_legacy(data)
    assert len(rows) == 2
    assert rows[0]["username"] == "fictional-user"
    assert rows[0]["email"] == "demo@example.invalid"
    assert rows[0]["phone"] == "+0 000 000 00 00"
    assert rows[0]["password"] == "FICTIONAL-EXAMPLE-ONLY"
    assert rows[0]["category"] is None


@pytest.mark.parametrize("data", [b"[]", b"{", b'{"site":[{"Unknown":"SECRET"}]}', b'{"site":[{"Phone":123}]}',
    b'{"site":[{}],"site":[{}]}', b'{"site":[]}'])
def test_bad_import_does_not_leak(data):
    with pytest.raises(VaultError) as caught:
        preview_legacy(data)
    assert "SECRET" not in str(caught.value)
