import os
from pathlib import Path
import subprocess
import sys

import pytest

from password_manager.storage import Store
from password_manager.crypto import unlock

PASSWORD = "interruption fictional phrase"


@pytest.mark.parametrize("point", ["snapshot", "pointer", "after_commit"])
def test_process_interruption(tmp_path, point):
    root = tmp_path / "crash-fixture"
    store = Store(root)
    access, doc, _ = store.create(PASSWORD)
    store.close()
    script = '''
import os, sys
from password_manager.storage import Store
import password_manager.storage as storage
store = Store(sys.argv[1])
access, doc = store.open("interruption fictional phrase")
doc["revision"] = 42
point = sys.argv[2]
original = storage.write_fsynced
def write(path, data):
    original(path, data)
    if (point == "snapshot" and path.name == "0.pmvault") or (point == "pointer" and path.suffix == ".tmp"):
        os._exit(73)
storage.write_fsynced = write
if point == "after_commit":
    store.cleanup = lambda: os._exit(73)
store.commit(access, doc)
'''
    env = dict(os.environ, PYTHONPATH=str(Path("src").resolve()))
    result = subprocess.run([sys.executable, "-c", script, str(root), point], env=env, capture_output=True, timeout=20)
    assert result.returncode == 73
    store = Store(root)
    try:
        assert store.open(PASSWORD)[1]["revision"] == (42 if point == "after_commit" else 0)
        store.cleanup()
        assert len(list(root.glob("*/0.pmvault"))) == 1
    finally:
        store.close()


def test_mid_rotation_write_failure(tmp_path, monkeypatch):
    import password_manager.storage as storage
    store = Store(tmp_path / "rotation")
    try:
        access, doc, recovery = store.create(PASSWORD)
        for i in range(7):
            doc["revision"] = i + 1
            store.commit(access, doc)
        original = storage.write_fsynced
        def write(path, data):
            if path.name == "4.pmvault":
                raise OSError("simulated full disk")
            original(path, data)
        monkeypatch.setattr(storage, "write_fsynced", write)
        from password_manager.errors import StorageError
        with pytest.raises(StorageError):
            store.change_password(access, doc, PASSWORD, "replacement fictional phrase")
        for index in range(8):
            assert store.open(PASSWORD, index=index)[1]["revision"] == 7 - index
            store.open(recovery, recovery=True, index=index)
    finally:
        store.close()


@pytest.mark.parametrize("kind", ["master", "recovery"])
@pytest.mark.parametrize("point", ["pointer", "after_commit"])
def test_process_interruption_during_rekey(tmp_path, kind, point):
    import base64
    from password_manager.errors import InvalidVault
    new_recovery = base64.b32encode(bytes([1]) * 32).decode().rstrip("=")
    root = tmp_path / "key-crash-fixture"
    store = Store(root)
    access, doc, old_recovery = store.create(PASSWORD)
    for i in range(7):
        doc["revision"] = i + 1
        store.commit(access, doc)
    store.close()
    script = '''
import os, sys, base64
from password_manager.storage import Store
import password_manager.storage as storage
store = Store(sys.argv[1])
access, doc = store.open("interruption fictional phrase")
original = storage.write_fsynced
def write(path, data):
    original(path, data)
    if sys.argv[3] == "pointer" and path.suffix == ".tmp":
        os._exit(73)
storage.write_fsynced = write
if sys.argv[3] == "after_commit":
    store.cleanup = lambda: os._exit(73)
if sys.argv[2] == "master":
    store.change_password(access, doc, "interruption fictional phrase", "replacement fictional phrase")
else:
    recovery = base64.b32encode(bytes([1]) * 32).decode().rstrip("=")
    store.rotate_recovery(access, doc, "interruption fictional phrase", recovery)
'''
    env = dict(os.environ, PYTHONPATH=str(Path("src").resolve()))
    result = subprocess.run([sys.executable, "-c", script, str(root), kind, point], env=env, capture_output=True, timeout=20)
    assert result.returncode == 73
    store = Store(root)
    try:
        committed = point == "after_commit"
        password = "replacement fictional phrase" if kind == "master" and committed else PASSWORD
        recovery = new_recovery if kind == "recovery" and committed else old_recovery
        for index in range(8):
            assert store.open(password, index=index)[1]["revision"] == 7 - index
            store.open(recovery, recovery=True, index=index)
        if committed:
            with pytest.raises(InvalidVault):
                store.open(PASSWORD if kind == "master" else old_recovery, recovery=kind == "recovery")
        store.cleanup()
        assert len(list(root.glob("*/0.pmvault"))) == 1
    finally:
        store.close()
