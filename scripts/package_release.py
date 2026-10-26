"""Create a local reviewable portable ZIP. Never uploads or installs anything."""
from pathlib import Path
import hashlib
import json
import os
import zipfile

from password_manager import __version__

root = Path(__file__).resolve().parents[1]
bundle = root / "dist" / "PasswordManager"
assert (bundle / "PasswordManager.exe").exists()
output = root / "releases"
output.mkdir(exist_ok=True)
target = output / f"PasswordManager-{__version__}-windows-x64.zip"
files = {}
def add(source, relative):
    if relative in files: raise RuntimeError("Duplicate archive target")
    files[relative] = source
for path in bundle.rglob("*"):
    if path.is_file(): add(path, path.relative_to(bundle).as_posix())
for name in ("USER_GUIDE.md", "LICENSE.txt", "THIRD_PARTY_NOTICES.md", "CHANGELOG.md", "README.md", "PLAN.md", "GLOSSARY.md", "requirements-lock.txt", "pyproject.toml"):
    add(root / name, name)
for folder, archive_name in [(root / "docs", "docs"), (root / "examples", "examples"),
    (root / "src", "src"), (root / "scripts", "scripts"), (root / "tests", "tests"),
    (root / "release-materials" / "licenses", "licenses"),
    (root / "release-materials" / "library-sources", "library-sources")]:
    for path in folder.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts and not any(p.endswith(".egg-info") for p in path.parts):
            add(path, archive_name + "/" + path.relative_to(folder).as_posix())
for name in ["bundle-audit.json", "tests.xml", "frozen-smoke/smoke-result.json", "source-smoke/desktop-demo.png", "source-manifest.json", "build-receipt.json"]:
    path = root / "artifacts" / name
    if path.exists(): add(path, "artifacts/" + name)
hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in sorted(files.items())}
temporary = target.with_suffix(".partial")
try:
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, path in sorted(files.items()):
            archive.write(path, "PasswordManager/" + name)
        archive.writestr("PasswordManager/SHA256SUMS.json", json.dumps(hashes, indent=2))
    with zipfile.ZipFile(temporary) as archive:
        assert archive.testzip() is None
    os.replace(temporary, target)
finally:
    temporary.unlink(missing_ok=True)
manifest = {"version": __version__, "archive": target.name, "bytes": target.stat().st_size,
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "files": len(files), "published": False}
(output / "release-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(json.dumps(manifest, indent=2))
