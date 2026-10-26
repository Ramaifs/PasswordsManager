"""Build a separate portable directory; never installs/launches the user application."""
from pathlib import Path
import json
import hashlib
from datetime import datetime, timezone
import pefile
import subprocess
import sys
from password_manager import __version__

root = Path(__file__).resolve().parents[1]
for directory in (root / "dist", root / "build"):
    if not directory.resolve().is_relative_to(root.resolve()):
        raise RuntimeError("Build output resolves outside the intended workspace")
artifacts = root / "artifacts"
artifacts.mkdir(exist_ok=True)
assets = root / "src/password_manager/assets"
inputs = [*sorted((root / "src").rglob("*.py")), *sorted(assets.glob("*")), root / "scripts" / "desktop_entry.py", root / "scripts" / "build.py", root / "pyproject.toml"]
oauth_config = root / "src" / "password_manager" / "google-desktop.json"
if oauth_config.exists():
    inputs.append(oauth_config)
before = {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onedir", "--windowed",
           "--name", "PasswordManager", "--icon", str(assets / "app.ico"), "--add-data", str(assets) + ";password_manager/assets", "--paths", str(root / "src"),
           *(["--add-data", str(oauth_config) + ";password_manager"] if oauth_config.exists() else []),
           "--distpath", str(root / "dist" / __version__), "--workpath", str(root / "build" / "pyinstaller"),
           "--specpath", str(root / "build"), str(root / "scripts" / "desktop_entry.py")]
with (artifacts / "build.log").open("w", encoding="utf-8") as log:
    result = subprocess.run(command, cwd=root, stdout=log, stderr=subprocess.STDOUT)
print(f"PyInstaller exit: {result.returncode}")
if result.returncode:
    raise SystemExit(result.returncode)

bundle = (root / "dist" / __version__ / "PasswordManager").resolve()
qt = bundle / "_internal" / "PySide6"
allowed = {"platforms/qwindows.dll", "platforms/qoffscreen.dll", "styles/qmodernwindowsstyle.dll",
           "imageformats/qico.dll", "imageformats/qjpeg.dll", "imageformats/qgif.dll"}
removed = []
def remove_owned(path):
    checked = path.resolve()
    if not checked.is_relative_to(bundle) or path.is_symlink():
        raise RuntimeError("Refusing to remove a path outside this build")
    path.unlink()
    removed.append(path.relative_to(bundle).as_posix())

for plugin in (qt / "plugins").rglob("*.dll"):
    if plugin.relative_to(qt / "plugins").as_posix() not in allowed:
        remove_owned(plugin)

roots = [qt / name for name in ["QtCore.pyd", "QtGui.pyd", "QtWidgets.pyd", "QtNetwork.pyd", "QtSvg.pyd", "pyside6.abi3.dll"]]
roots.extend((qt / "plugins").rglob("*.dll"))
needed = set()
queue = list(roots)
checked = set()
while queue:
    binary = queue.pop()
    if binary in checked: continue
    checked.add(binary)
    pe = pefile.PE(str(binary))
    dependencies = list(getattr(pe, "DIRECTORY_ENTRY_IMPORT", [])) + list(getattr(pe, "DIRECTORY_ENTRY_DELAY_IMPORT", []))
    for entry in dependencies:
        name = entry.dll.decode("ascii")
        if name.lower().startswith("qt6"):
            needed.add(name.lower())
            queue.append(qt / name)
    pe.close()
for binary in qt.glob("Qt6*.dll"):
    if binary.name.lower() not in needed:
        remove_owned(binary)
if (qt / "opengl32sw.dll").exists():
    remove_owned(qt / "opengl32sw.dll")
for translation in (qt / "translations").glob("*.qm"):
    if translation.name != "qtbase_ru.qm": remove_owned(translation)
audit = {"qt_dlls": sorted(needed), "plugins": sorted(allowed), "removed": removed}
(artifacts / "bundle-audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
after = {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
if before != after:
    raise RuntimeError("Sources changed while building: rebuild required")
receipt = {"finished_utc": datetime.now(timezone.utc).isoformat(), "exit_code": 0, "inputs": before,
           "exe_sha256": hashlib.sha256((bundle / "PasswordManager.exe").read_bytes()).hexdigest()}
(artifacts / "build-receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
print("Qt dependency closure:", ", ".join(sorted(needed)))
