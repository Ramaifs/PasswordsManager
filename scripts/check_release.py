"""Audit the exact ZIP and run its unpacked EXE on fictional temporary data."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import subprocess
import uuid
import zipfile

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "releases" / "release-manifest.json").read_text(encoding="utf-8"))
archive_path = root / "releases" / manifest["archive"]
assert archive_path.resolve().is_relative_to((root / "releases").resolve())
archive_hash = hashlib.sha256(archive_path.read_bytes()).hexdigest()
assert archive_hash == manifest["sha256"]
destination = root / "build" / ("unpacked-release-" + str(uuid.uuid4()))
assert destination.resolve().is_relative_to((root / "build").resolve())
destination.mkdir(parents=True)
with zipfile.ZipFile(archive_path) as archive:
    names = archive.namelist()
    assert len(names) == len(set(names))
    hashes = json.loads(archive.read("PasswordManager/SHA256SUMS.json"))
    assert len(hashes) == manifest["files"]
    for name in names:
        safe = PurePosixPath(name)
        assert not safe.is_absolute() and ".." not in safe.parts and "\\" not in name and ":" not in name
        assert safe.parts[0] == "PasswordManager"
        assert not {"CURRENT", "session.lock", "google-connection.dpapi", ".venv"}.intersection(safe.parts)
        if name != "PasswordManager/SHA256SUMS.json":
            relative = name.removeprefix("PasswordManager/")
            assert hashlib.sha256(archive.read(name)).hexdigest() == hashes[relative]
    archive.extractall(destination)
exe = destination / "PasswordManager" / "PasswordManager.exe"
env = dict(os.environ)
for key in ["PYTHONPATH", "PYTHONHOME", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"]:
    env.pop(key, None)
env["PATH"] = str(Path(os.environ["WINDIR"]) / "System32")
output = root / "artifacts" / "release-smoke"
result = subprocess.run([str(exe), "--self-test", str(output)], env=env, cwd=exe.parent, timeout=90)
assert result.returncode == 0
smoke = json.loads((output / "smoke-result.json").read_text(encoding="utf-8"))
assert smoke["success"] and smoke["frozen"]
report = {"archive": manifest["archive"], "sha256": archive_hash, "files_verified": len(hashes),
          "frozen_smoke": True, "non_admin": smoke.get("non_admin"), "success": True}
(root / "artifacts" / "release-audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
