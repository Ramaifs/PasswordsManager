"""Capture repeatable checks and hash reviewable inputs; excludes user data/.venv."""
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
from password_manager import __version__

root = Path(__file__).resolve().parents[1]
artifacts = root / "artifacts"
artifacts.mkdir(exist_ok=True)
results = []
def test_inputs():
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for base in (root / "src", root / "tests") for path in sorted(base.rglob("*.py"))}
inputs_before = test_inputs()
reuse = "--metadata-only" in sys.argv
if reuse:
    previous = json.loads((artifacts / "test-inputs.json").read_text(encoding="utf-8"))
    if previous != inputs_before:
        raise SystemExit("Source/test inputs changed: run full verification first")
    results.append({"check": "pytest", "exit_code": 0, "reused": "identical source and test hashes"})
for name, command in [
    ("pytest", [sys.executable, "-m", "pytest", "-q", "--junitxml=artifacts/tests.xml"]),
    ("pip-check", [sys.executable, "-m", "pip", "check"]),
]:
    if reuse and name == "pytest": continue
    completed = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    (artifacts / f"{name}.txt").write_text(completed.stdout + completed.stderr, encoding="utf-8")
    results.append({"check": name, "exit_code": completed.returncode})
    print(f"{name}: exit {completed.returncode}")
    if name == "pytest" and completed.returncode == 0:
        if inputs_before != test_inputs():
            raise SystemExit("Inputs changed during tests: rerun required")
        (artifacts / "test-inputs.json").write_text(json.dumps(inputs_before, indent=2), encoding="utf-8")

paths = [path for base in [root / "src", root / "tests", root / "scripts", root / "docs", root / "examples"]
         for path in base.rglob("*") if path.is_file() and not {"__pycache__"}.intersection(path.parts) and not any(p.endswith(".egg-info") for p in path.parts)]
paths.extend(path for path in root.iterdir() if path.is_file())
missing = []
links = 0
for path in paths:
    if path.suffix == ".md":
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            target = target.strip("<>").split("#")[0]
            if not target or re.match(r"[a-z]+://|mailto:", target):
                continue
            links += 1
            resolved = (path.parent / target).resolve()
            # This exact output is written below after link results are available.
            if resolved != artifacts / "source-manifest.json" and not resolved.exists():
                missing.append({"source": str(path.relative_to(root)), "target": target})
results.append({"check": "markdown-links", "exit_code": int(bool(missing)), "count": links, "missing": missing})
print(f"markdown-links: {links} checked; {len(missing)} missing")

pin_errors = []
for line in (root / "requirements-lock.txt").read_text().splitlines():
    if "==" in line and not line.startswith("#"):
        name, expected = line.split("==")
        actual = importlib.metadata.version(name)
        if actual != expected:
            pin_errors.append(name)
results.append({"check": "dependency-pins", "exit_code": int(bool(pin_errors)), "mismatched": pin_errors})

manifest = {"created_utc": datetime.now(timezone.utc).isoformat(), "application_version": __version__,
            "python": sys.version, "platform": platform.platform(), "checks": results,
            "files": [{"path": path.relative_to(root).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                      for path in sorted(set(paths))]}
(artifacts / "source-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
raise SystemExit(int(any(r["exit_code"] for r in results)))
