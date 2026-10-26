"""Audit versioned release archives, their manifest and source build receipt."""
from pathlib import Path
import hashlib
import json
import zipfile
from password_manager import __version__ as version

root = Path(__file__).resolve().parents[1]
out = root / 'releases' / version
receipt = json.loads((root/'artifacts/build-receipt.json').read_text(encoding='utf-8'))
for name, digest in receipt['inputs'].items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest() == digest, name
exe = root/'dist'/version/'PasswordManager/PasswordManager.exe'
assert hashlib.sha256(exe.read_bytes()).hexdigest() == receipt['exe_sha256']
manifest = json.loads((out/'manifest.json').read_text(encoding='utf-8'))
for name, details in manifest['files'].items():
    data=(out/name).read_bytes()
    assert len(data)==details['bytes'] and hashlib.sha256(data).hexdigest()==details['sha256'],name
with zipfile.ZipFile(out/f'PasswordManager-{version}-portable.zip') as archive:
    assert archive.testzip() is None
    assert 'PasswordManager/portable.flag' in archive.namelist()
    assert archive.read('PasswordManager/PasswordManager.exe')==exe.read_bytes()
    hashes=json.loads(archive.read('PasswordManager/SHA256SUMS.json'))
    for name,digest in hashes.items():
        assert hashlib.sha256(archive.read('PasswordManager/'+name)).hexdigest()==digest,name
    assert not any(name.endswith(('.pmvault','.dpapi')) for name in archive.namelist())
with zipfile.ZipFile(root/'build'/('setup-'+version)/'payload.zip') as archive:
    assert archive.testzip() is None and 'portable.flag' not in archive.namelist()
    assert archive.read('PasswordManager.exe')==exe.read_bytes()
with zipfile.ZipFile(out/f'PasswordManager-web-{version}.zip') as archive:
    assert archive.testzip() is None
    for name in archive.namelist():
        assert archive.read(name)==(root/'web/password-manager/dist'/name).read_bytes(),name
for file in ['artifacts/frozen-smoke/smoke-result.json','web/password-manager/artifacts/browser/result.json']:
    assert json.loads((root/file).read_text(encoding='utf-8'))['success']
report={'version':version,'success':True,'source_receipt_matches':True,'archives_and_hashes_valid':True,'user_vaults_and_tokens_excluded':True,'installed':False,'website_deployed':False}
(root/'artifacts'/('release-'+version+'-audit.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
