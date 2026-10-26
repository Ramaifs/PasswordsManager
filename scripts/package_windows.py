"""Build portable ZIP and an offline per-user Setup.exe using the local compiler."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile
from password_manager import __version__ as version

root = Path(__file__).resolve().parents[1]
bundle = root / 'dist' / version / 'PasswordManager'
out = root / 'releases' / version
out.mkdir(parents=True, exist_ok=True)
build = root / 'build' / ('setup-' + version)
build.mkdir(parents=True, exist_ok=True)
files = {p.relative_to(bundle).as_posix(): p for p in bundle.rglob('*') if p.is_file()}
for name in ['USER_GUIDE.md', 'LICENSE.txt', 'THIRD_PARTY_NOTICES.md', 'CHANGELOG.md']:
    files[name] = root / name
for name in ['google-setup.md', 'release-' + version + '.md']:
    files['docs/' + name] = root / 'docs' / name
for folder, target in [('release-materials/licenses', 'licenses'), ('release-materials/library-sources', 'library-sources')]:
    for p in (root / folder).rglob('*'):
        if p.is_file(): files[target + '/' + p.relative_to(root / folder).as_posix()] = p
hashes = {name: hashlib.sha256(p.read_bytes()).hexdigest() for name,p in sorted(files.items())}
with zipfile.ZipFile(build / 'payload.zip', 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for name,p in sorted(files.items()): archive.write(p, name)
(build / 'payload.sha256').write_text('\n'.join(digest + '  ' + name for name,digest in hashes.items()), encoding='utf-8')
with zipfile.ZipFile(out / f'PasswordManager-{version}-portable.zip', 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for name,p in sorted(files.items()): archive.write(p, 'PasswordManager/' + name)
    archive.writestr('PasswordManager/portable.flag', 'Portable data lives in ./data.\n')
    archive.writestr('PasswordManager/PORTABLE.txt', 'Запустите PasswordManager.exe. Данные хранятся в папке data рядом с EXE.\nДля переноса прежнего хранилища откройте его зашифрованный экспорт .pmvault.\nGoogle нужно подключать отдельно на каждом компьютере (защита DPAPI Windows).\n', compress_type=zipfile.ZIP_DEFLATED)
    archive.writestr('PasswordManager/SHA256SUMS.json', json.dumps(hashes, indent=2))
compiler = Path(os.environ['WINDIR']) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
version_info = build / 'VersionInfo.cs'
numeric_version = version + '.0' * (4 - len(version.split('.')))
version_info.write_text('using System.Reflection;\n[assembly: AssemblyVersion("' + numeric_version + '")]\n[assembly: AssemblyFileVersion("' + numeric_version + '")]\n[assembly: AssemblyInformationalVersion("' + version + '")]\n', encoding='utf-8')
common = [str(compiler), '/nologo', '/win32icon:' + str(root / 'src/password_manager/assets/app.ico'), '/target:winexe', '/platform:x64', '/reference:System.Windows.Forms.dll', '/reference:System.IO.Compression.dll', '/reference:System.IO.Compression.FileSystem.dll']
uninstall = build / 'Uninstall.exe'
subprocess.run([*common, '/define:UNINSTALLER', '/out:' + str(uninstall), str(root / 'scripts/Setup.cs'), str(version_info)], check=True)
setup = out / 'PasswordsManager.exe'
subprocess.run([*common, '/out:' + str(setup), '/resource:' + str(build / 'payload.zip') + ',payload.zip', '/resource:' + str(build / 'payload.sha256') + ',payload.sha256', '/resource:' + str(uninstall) + ',uninstall.exe', str(root / 'scripts/Setup.cs'), str(version_info)], check=True)
release_files = [setup, out / f'PasswordManager-{version}-portable.zip']
setup_inputs = [root/'scripts/Setup.cs', root/'scripts/package_windows.py', root/'src/password_manager/assets/app.ico']
manifest = {'version': version, 'installed': False, 'published': False, 'setup_inputs': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in setup_inputs}, 'files': {p.name: {'bytes':p.stat().st_size, 'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in release_files}}
(out / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(json.dumps(manifest, indent=2))
