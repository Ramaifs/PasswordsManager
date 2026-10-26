"""Build portable ZIP and an offline per-user Setup.exe using the local compiler."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile

root = Path(__file__).resolve().parents[1]
bundle = root / 'dist/PasswordManager-0.3.4'
out = root / 'releases/0.3.4'
out.mkdir(parents=True, exist_ok=True)
build = root / 'build/setup-034'
build.mkdir(parents=True, exist_ok=True)
files = {p.relative_to(bundle).as_posix(): p for p in bundle.rglob('*') if p.is_file()}
for name in ['USER_GUIDE.md', 'LICENSE.txt', 'THIRD_PARTY_NOTICES.md', 'CHANGELOG.md']:
    files[name] = root / name
for name in ['google-setup.md', 'release-0.3.4.md']:
    files['docs/' + name] = root / 'docs' / name
for folder, target in [('release-materials/licenses', 'licenses'), ('release-materials/library-sources', 'library-sources')]:
    for p in (root / folder).rglob('*'):
        if p.is_file(): files[target + '/' + p.relative_to(root / folder).as_posix()] = p
hashes = {name: hashlib.sha256(p.read_bytes()).hexdigest() for name,p in sorted(files.items())}
with zipfile.ZipFile(build / 'payload.zip', 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for name,p in sorted(files.items()): archive.write(p, name)
(build / 'payload.sha256').write_text('\n'.join(digest + '  ' + name for name,digest in hashes.items()), encoding='utf-8')
with zipfile.ZipFile(out / 'PasswordManager-0.3.4-portable.zip', 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for name,p in sorted(files.items()): archive.write(p, 'PasswordManager/' + name)
    archive.writestr('PasswordManager/portable.flag', 'Portable data lives in ./data.\n')
    archive.writestr('PasswordManager/PORTABLE.txt', 'Запустите PasswordManager.exe. Данные хранятся в папке data рядом с EXE.\nДля переноса прежнего хранилища откройте его зашифрованный экспорт .pmvault.\nGoogle нужно подключать отдельно на каждом компьютере (защита DPAPI Windows).\n', compress_type=zipfile.ZIP_DEFLATED)
    archive.writestr('PasswordManager/SHA256SUMS.json', json.dumps(hashes, indent=2))
with zipfile.ZipFile(out / 'PasswordManager-web-0.3.4.zip', 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for p in sorted((root / 'web/password-manager/dist').rglob('*')):
        if p.is_file(): archive.write(p, p.relative_to(root / 'web/password-manager/dist').as_posix())
compiler = Path(os.environ['WINDIR']) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
common = [str(compiler), '/nologo', '/target:winexe', '/platform:x64', '/reference:System.Windows.Forms.dll', '/reference:System.IO.Compression.dll', '/reference:System.IO.Compression.FileSystem.dll']
uninstall = build / 'Uninstall.exe'
subprocess.run([*common, '/define:UNINSTALLER', '/out:' + str(uninstall), str(root / 'scripts/Setup.cs')], check=True)
setup = out / 'PasswordsManager.exe'
subprocess.run([*common, '/out:' + str(setup), '/resource:' + str(build / 'payload.zip') + ',payload.zip', '/resource:' + str(build / 'payload.sha256') + ',payload.sha256', '/resource:' + str(uninstall) + ',uninstall.exe', str(root / 'scripts/Setup.cs')], check=True)
release_files = [setup, out / 'PasswordManager-0.3.4-portable.zip', out / 'PasswordManager-web-0.3.4.zip']
manifest = {'version': '0.3.4', 'installed': False, 'published': False, 'files': {p.name: {'bytes':p.stat().st_size, 'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in release_files}}
(out / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(json.dumps(manifest, indent=2))
