"""Prepare a Cloudflare-specific copy of the tested Site, without account mutations."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
import subprocess
import zipfile

root = Path(__file__).resolve().parents[1]
site = root / "web" / "password-manager"
source = site / "dist"
artifacts = root / "artifacts"
artifacts.mkdir(exist_ok=True)

commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=site, text=True).strip()
if subprocess.check_output(["git", "status", "--porcelain", "--", "dist"], cwd=site).strip():
    raise SystemExit("Site assets changed since the tested commit; verify them before packaging")
if not (source / "index.html").is_file():
    raise SystemExit("Site index.html is missing")

files = {}
for path in sorted(source.rglob("*")):
    if not path.is_file():
        continue
    if path.is_symlink() or not path.resolve().is_relative_to(source.resolve()):
        raise SystemExit("Refusing an asset outside the intended Site directory")
    relative = path.relative_to(source)
    if any(part.startswith(".") for part in relative.parts):
        continue  # Sites-specific hosting metadata is not a Cloudflare asset.
    if path.suffix.lower() not in {".html", ".js", ".css", ".svg", ".wasm", ".license"}:
        raise SystemExit("Unexpected asset type; inspect before uploading: " + relative.as_posix())
    files[relative.as_posix()] = path.read_bytes()

headers = (root / "deployment" / "cloudflare-pages" / "_headers").read_bytes()
files["_headers"] = headers
files["LICENSE.txt"] = (site / "LICENSE.txt").read_bytes()
html = files["index.html"].decode("utf-8")
meta = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)"', html)
if not meta or meta.group(1) not in headers.decode("utf-8"):
    raise SystemExit("Cloudflare and HTML content security policies differ")
for expected in ("app.js", "core.js", "storage.js", "vault-worker.js", "sync.js", "sync-schedule.js", "drive.js", "google.js", "legacy.js", "vendor/hash-wasm.js", "vendor/hash-wasm.LICENSE"):
    if expected not in files:
        raise SystemExit("Required asset is missing: " + expected)

target = artifacts / "cloudflare-workers-upload.zip"
temporary = target.with_suffix(".partial")
try:
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(name, data)
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip() is not None:
            raise SystemExit("ZIP integrity validation failed")
        if set(archive.namelist()) != set(files):
            raise SystemExit("ZIP entries do not match the prepared files")
        for name, data in files.items():
            if hashlib.sha256(archive.read(name)).digest() != hashlib.sha256(data).digest():
                raise SystemExit("ZIP asset hash mismatch")
    temporary.replace(target)
finally:
    temporary.unlink(missing_ok=True)
# Keep the previously shared local link pointing to this same current package.
(artifacts / "cloudflare-pages-upload.zip").write_bytes(target.read_bytes())

report = {
    "prepared_utc": datetime.now(timezone.utc).isoformat(),
    "source_commit": commit,
    "archive": target.name,
    "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
    "bytes": target.stat().st_size,
    "files": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())},
    "uploaded": False,
    "new_hostname": None,
    "target_hostname": "password-manager-vault.masaoyhs.workers.dev",
    "audience": "public: explicitly requested by user; Access deferred",
    "compatibility_archive": "cloudflare-pages-upload.zip",
    "account_access": "not available: no connected provider, CLI login, or environment credentials found",
    "required_before_cutover": ["upload current ZIP in existing Cloudflare Worker", "export .pmvault from the old origin", "verify actual deployment URL and HTTPS"],
    "existing_site_changed": False,
}
placeholder_path = artifacts / "cloudflare-placeholder.zip"
with zipfile.ZipFile(placeholder_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    archive.write(root / "deployment" / "cloudflare-pages" / "placeholder" / "index.html", "index.html")
    archive.writestr("_headers", headers)
with zipfile.ZipFile(placeholder_path) as archive:
    if archive.testzip() is not None or set(archive.namelist()) != {"index.html", "_headers"}:
        raise SystemExit("Placeholder ZIP validation failed")
report["placeholder_archive"] = placeholder_path.name
report["placeholder_sha256"] = hashlib.sha256(placeholder_path.read_bytes()).hexdigest()
(artifacts / "cloudflare-pages-preparation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({key: report[key] for key in ["source_commit", "archive", "bytes", "sha256", "uploaded", "new_hostname", "existing_site_changed"]}, indent=2))
