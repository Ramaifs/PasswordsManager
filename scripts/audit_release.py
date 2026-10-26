"""Audit versioned release archives, their manifest and source build receipt."""
from pathlib import Path
import hashlib
import json
import zipfile
import struct
import pefile
from password_manager import __version__ as version

root = Path(__file__).resolve().parents[1]
out = root / 'releases' / version
receipt = json.loads((root/'artifacts/build-receipt.json').read_text(encoding='utf-8'))
for name, digest in receipt['inputs'].items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest() == digest, name
exe = root/'dist'/version/'PasswordManager/PasswordManager.exe'
assert hashlib.sha256(exe.read_bytes()).hexdigest() == receipt['exe_sha256']
icon = (root/'src/password_manager/assets/app.ico').read_bytes()
expected_frames = set()
for i in range(struct.unpack_from('<H', icon, 4)[0]):
    size, offset = struct.unpack_from('<II', icon, 6 + 16 * i + 8)
    expected_frames.add(hashlib.sha256(icon[offset:offset+size]).hexdigest())
for binary in [exe, out/'PasswordsManager.exe', root/'build'/('setup-'+version)/'Uninstall.exe']:
    pe = pefile.PE(str(binary), fast_load=True)
    pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_RESOURCE']])
    frames = set()
    for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        if entry.id == 3:
            for item in entry.directory.entries:
                for language in item.directory.entries:
                    data = language.data.struct
                    frames.add(hashlib.sha256(pe.get_data(data.OffsetToData, data.Size)).hexdigest())
    assert expected_frames <= frames, 'Application icon frames missing: ' + str(binary)
    pe.close()
manifest = json.loads((out/'manifest.json').read_text(encoding='utf-8'))
for name, digest in manifest.get('setup_inputs', {}).items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest() == digest, name
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
web_manifest = out/'web-manifest.json'
if web_manifest.exists():
    web = json.loads(web_manifest.read_text(encoding='utf-8'))
    assert web['version'] == version and web['published'] is False and web['publish_to_github'] is False
    archive_path = out/web['archive']
    assert archive_path.resolve().is_relative_to(out.resolve())
    assert hashlib.sha256(archive_path.read_bytes()).hexdigest() == web['sha256']
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.testzip() is None and set(archive.namelist()) == set(web['files'])
        for name, item in web['files'].items():
            data = archive.read(name)
            assert hashlib.sha256(data).hexdigest() == item['sha256']
            assert (root/item['source']).read_bytes() == data
for file in ['artifacts/frozen-smoke/smoke-result.json','web/password-manager/artifacts/browser/result.json']:
    assert json.loads((root/file).read_text(encoding='utf-8'))['success']
report={'version':version,'success':True,'source_receipt_matches':True,'archives_and_hashes_valid':True,'application_and_installer_icon_frames_verified':len(expected_frames),'user_vaults_and_tokens_excluded':True,'installed':False,'website_deployed':False}
(root/'artifacts'/('release-'+version+'-audit.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
