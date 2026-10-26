"""Offline fallback: rebuild the existing PyInstaller archive with edited sources.

Uses only the existing bundled CPython runtime, no downloaded interpreter.
The original bootloader and dependencies are retained; all app modules are replaced.
"""
import __main__ as recovery
import hashlib
import json
import marshal
import os
from pathlib import Path
import zlib

root = Path(__file__).resolve().parents[1]
base = root / 'dist/PasswordManager'
output = root / 'dist/PasswordManager-0.3.4'
output.mkdir(exist_ok=True)
# Copy dependencies without importing shutil (it is not needed by the old bundle).
for folder, dirs, files in os.walk(base / '_internal'):
    relative = Path(folder).relative_to(base)
    (output / relative).mkdir(parents=True, exist_ok=True)
    for name in files:
        (output / relative / name).write_bytes((Path(folder) / name).read_bytes())
exe, start, cookie = recovery.exe, recovery.start, recovery.cookie
pyz, toc = recovery.pyz, recovery.toc
data = bytearray(pyz[:12])
new_toc = []
for name, (kind, offset, length) in toc.items():
    if name == 'password_manager' or name.startswith('password_manager.'):
        continue
    chunk = pyz[offset:offset + length]
    new_toc.append((name, (kind, len(data), len(chunk))))
    data.extend(chunk)
hashes = {}
for source in sorted((root / 'src/password_manager').glob('*.py')):
    name = 'password_manager' if source.stem == '__init__' else 'password_manager.' + source.stem
    kind = int(source.stem == '__init__')
    content = source.read_bytes()
    hashes[source.relative_to(root).as_posix()] = hashlib.sha256(content).hexdigest()
    chunk = zlib.compress(marshal.dumps(compile(content, name.replace('.', '/') + '.py', 'exec')), 6)
    new_toc.append((name, (kind, len(data), len(chunk))))
    data.extend(chunk)
data[8:12] = len(data).to_bytes(4, 'big')
data.extend(marshal.dumps(new_toc))

number = recovery.number
offset = start + number(exe[cookie+12:cookie+16])
end = offset + number(exe[cookie+16:cookie+20])
archive, records = bytearray(), bytearray()
while offset < end:
    length = number(exe[offset:offset+4])
    entry = bytearray(exe[offset:offset+length])
    pos, size = number(entry[4:8]), number(entry[8:12])
    chunk = exe[start+pos:start+pos+size]
    if entry[17:18] == b'z':
        chunk = bytes(data)
        entry[12:16] = len(chunk).to_bytes(4, 'big')
        entry[16] = 0
    entry[4:8] = len(archive).to_bytes(4, 'big')
    entry[8:12] = len(chunk).to_bytes(4, 'big')
    archive.extend(chunk)
    records.extend(entry)
    offset += length
new_cookie = bytearray(exe[cookie:cookie+88])
new_cookie[8:12] = (len(archive)+len(records)+88).to_bytes(4, 'big')
new_cookie[12:16] = len(archive).to_bytes(4, 'big')
new_cookie[16:20] = len(records).to_bytes(4, 'big')
target = output / 'PasswordManager.exe'
target.write_bytes(exe[:start] + archive + records + new_cookie)
config = root / 'src/password_manager/google-desktop.json'
dest = output / '_internal/password_manager/google-desktop.json'
dest.parent.mkdir(exist_ok=True)
dest.write_bytes(config.read_bytes())
hashes[config.relative_to(root).as_posix()] = hashlib.sha256(config.read_bytes()).hexdigest()
receipt = {'version': '0.3.4', 'method': 'existing-pyinstaller-archive-rebuilt-with-bundled-cpython',
           'base_exe_sha256': hashlib.sha256(exe).hexdigest(), 'inputs': hashes,
           'exe_sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'installed': False}
(root / 'artifacts/build-034.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
print('Rebuilt', target)
