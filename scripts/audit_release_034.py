"""Read-only final archive/source audit. Never installs or launches the app."""
from pathlib import Path
import hashlib
import json
import zipfile

root = Path(__file__).resolve().parents[1]
out = root / 'releases/0.3.4'
receipt = json.loads((root / 'artifacts/build-034.json').read_text(encoding='utf-8'))
for name,digest in receipt['inputs'].items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, name
exe = root / 'dist/PasswordManager-0.3.4/PasswordManager.exe'
assert hashlib.sha256(exe.read_bytes()).hexdigest() == receipt['exe_sha256']
checks = ['frozen-exe-matches-current-source-receipt']
manifest = json.loads((out / 'manifest.json').read_text(encoding='utf-8'))
for name,meta in manifest['files'].items():
    p = out / name
    assert p.stat().st_size == meta['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest() == meta['sha256']
checks.append('all-release-sha256-and-lengths-match')
with zipfile.ZipFile(out / 'PasswordManager-0.3.4-portable.zip') as archive:
    assert archive.testzip() is None
    names = archive.namelist()
    assert 'PasswordManager/portable.flag' in names
    assert archive.read('PasswordManager/PasswordManager.exe') == exe.read_bytes()
    sums = json.loads(archive.read('PasswordManager/SHA256SUMS.json'))
    for name,digest in sums.items():
        assert hashlib.sha256(archive.read('PasswordManager/' + name)).hexdigest() == digest
    assert not any('/data/' in name or name.endswith(('.pmvault','.dpapi')) for name in names)
checks.extend(['portable-flag-exe-and-full-payload-hashes', 'no-user-vault-or-token-in-portable'])
with zipfile.ZipFile(root / 'build/setup-034/payload.zip') as archive:
    assert archive.testzip() is None
    assert 'portable.flag' not in archive.namelist()
    assert archive.read('PasswordManager.exe') == exe.read_bytes()
    assert not any(name.endswith(('.pmvault','.dpapi')) for name in archive.namelist())
checks.append('installed-payload-uses-appdata-no-portable-marker-or-user-data')
with zipfile.ZipFile(out / 'PasswordManager-web-0.3.4.zip') as archive:
    assert archive.testzip() is None
    for name in archive.namelist():
        assert archive.read(name) == (root / 'web/password-manager/dist' / name).read_bytes()
    assert not any('google-desktop' in name for name in archive.namelist())
checks.append('web-archive-matches-tested-assets-no-desktop-oauth-json')
for name in ['artifacts/frozen-034/smoke-result.json', 'artifacts/verification-034.json', 'web/password-manager/artifacts/browser/result.json']:
    assert json.loads((root / name).read_text(encoding='utf-8'))['success'], name
checks.append('source-desktop-browser-and-frozen-reports-successful')
report = {'version':'0.3.4', 'success':True, 'checks':checks, 'installed':False, 'published':False, 'real_google_login_verified':False}
(root / 'artifacts/release-034-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
