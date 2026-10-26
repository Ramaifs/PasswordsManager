from pathlib import Path
import json
import os
import subprocess
import sys
from password_manager import __version__

root = Path(__file__).resolve().parents[1]
exe = root / "dist" / __version__ / "PasswordManager" / "PasswordManager.exe"
output = root / "artifacts" / "frozen-smoke"
env = dict(os.environ)
for key in ["PYTHONPATH", "PYTHONHOME", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"]:
    env.pop(key, None)
env["PATH"] = str(Path(os.environ["WINDIR"]) / "System32")
env["QT_QPA_PLATFORM"] = "offscreen"
result = subprocess.run([str(exe), "--self-test", str(output)], env=env, cwd=exe.parent, timeout=90)
if result.returncode:
    raise SystemExit(result.returncode)
report = json.loads((output / "smoke-result.json").read_text(encoding="utf-8"))
assert report["success"] and report["frozen"]
assert "dependencies-from-bundle" in report["checks"]
print("Frozen smoke passed; non-admin:", report.get("non_admin"))
