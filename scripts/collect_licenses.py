"""Collect actual dependency notices and matching LGPL sources for the portable bundle."""
from pathlib import Path
import hashlib
import importlib.metadata
import json
import shutil
import ssl
import sys
import tarfile
import urllib.request

root = Path(__file__).resolve().parents[1]
destination = root / "release-materials" / "licenses"
sources = root / "release-materials" / "library-sources"
destination.mkdir(parents=True, exist_ok=True)
sources.mkdir(parents=True, exist_ok=True)
packages = ["cryptography", "argon2-cffi", "argon2-cffi-bindings", "cffi", "pycparser", "PySide6", "PySide6_Essentials", "shiboken6", "pyinstaller"]
inventory = []
for package in packages:
    dist = importlib.metadata.distribution(package)
    folder = destination / package
    folder.mkdir(exist_ok=True)
    for file in dist.files or []:
        if ".dist-info/licenses/" in str(file).replace("\\", "/"):
            source = Path(dist.locate_file(file))
            if source.is_file():
                shutil.copyfile(source, folder / source.name)
    inventory.append({"name": dist.metadata["Name"], "version": dist.version,
                      "license": dist.metadata.get("License-Expression") or dist.metadata.get("License"),
                      "project_urls": dist.metadata.get_all("Project-URL") or []})
python_license = Path(sys.base_prefix) / "LICENSE.txt"
if python_license.exists(): shutil.copyfile(python_license, destination / "PYTHON-LICENSE.txt")

downloads = [
    ("qtbase-everywhere-src-6.12.0.tar.xz", "https://download.qt.io/official_releases/qt/6.12/6.12.0/submodules/qtbase-everywhere-src-6.12.0.tar.xz"),
    ("pyside-setup-everywhere-src-6.12.0.tar.xz", "https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.12.0-src/pyside-setup-everywhere-src-6.12.0.tar.xz"),
    ("qttranslations-everywhere-src-6.12.0.tar.xz", "https://download.qt.io/official_releases/qt/6.12/6.12.0/submodules/qttranslations-everywhere-src-6.12.0.tar.xz"),
]
records = []
for name, url in downloads:
    target = sources / name
    if not target.exists():
        temporary = target.with_suffix(".partial")
        try:
            with urllib.request.urlopen(url, timeout=60) as response, temporary.open("wb") as output:
                total = 0
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > 150 * 1024 * 1024: raise RuntimeError("Source archive exceeds limit")
                    output.write(chunk)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    # Read licence/attribution files only; never extract paths from an untrusted archive.
    found = 0
    with tarfile.open(target, "r:xz") as archive:
        for member in archive:
            relative = Path(member.name)
            if member.isfile() and ("LICENSES" in relative.parts or relative.name.startswith(("LICENSE", "COPYING", "NOTICE"))) and member.size < 512 * 1024:
                stream = archive.extractfile(member)
                if stream:
                    data = stream.read()
                    filename = hashlib.sha256(member.name.encode()).hexdigest()[:12] + "-" + relative.name
                    (destination / filename).write_bytes(data)
                    found += 1
    records.append({"name": name, "url": url, "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "notice_files": found})
    print(name, "downloaded and inspected", flush=True)
(destination / "DEPENDENCIES.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
(sources / "SOURCE-MANIFEST.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
