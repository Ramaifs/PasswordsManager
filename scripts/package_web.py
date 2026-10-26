"""Build a local-only static website ZIP; never uploads or deploys it."""
from pathlib import Path
import hashlib
import json
import zipfile
from password_manager import __version__ as version

root = Path(__file__).resolve().parents[1]
source = root / "web/password-manager/dist"
out = root / "releases" / version
out.mkdir(parents=True, exist_ok=True)
inputs = {}
for path in sorted(source.rglob("*")):
    if not path.is_file():
        continue
    if path.is_symlink() or not path.resolve().is_relative_to(source.resolve()):
        raise ValueError("Website assets must remain within dist")
    relative = path.relative_to(source)
    if any(part.startswith(".") for part in relative.parts):
        continue
    if path.suffix.lower() not in {".html", ".js", ".css", ".svg", ".wasm", ".license", ".png", ".ico"}:
        raise ValueError("Unexpected website asset: " + relative.as_posix())
    inputs[relative.as_posix()] = path
inputs["_headers"] = root / "deployment/cloudflare-pages/_headers"
inputs["LICENSE.txt"] = root / "web/password-manager/LICENSE.txt"
files = {name: path.read_bytes() for name, path in inputs.items()}
assert "index.html" in files and "app.js" in files and "vault-worker.js" in files
archive_path = out / f"PasswordManager-web-{version}.zip"
with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for name, data in sorted(files.items()):
        archive.writestr(name, data)
with zipfile.ZipFile(archive_path) as archive:
    assert archive.testzip() is None and set(archive.namelist()) == set(files)
    for name, data in files.items():
        assert archive.read(name) == data == inputs[name].read_bytes(), name
manifest = {
    "version": version, "archive": archive_path.name,
    "bytes": archive_path.stat().st_size,
    "sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
    "published": False, "publish_to_github": False, "deployed": False,
    "files": {name: {"source": path.relative_to(root).as_posix(), "sha256": hashlib.sha256(files[name]).hexdigest()} for name, path in inputs.items()},
}
(out / "web-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(json.dumps({key: value for key, value in manifest.items() if key != "files"}, indent=2))
