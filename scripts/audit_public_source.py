"""Inspect the staged public snapshot without printing credential contents."""
from pathlib import Path
import json
import re
import subprocess

root = Path(__file__).resolve().parents[1]
git = ['git', '-c', 'safe.directory=' + root.as_posix()]
def command(*args):
    return subprocess.check_output([*git, *args], cwd=root)

entries = command('ls-files', '--stage', '-z').split(b'\0')
paths = []
pattern = re.compile(rb'(?:GOCSPX-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{24,}|AKIA[A-Z0-9]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
for entry in entries:
    if not entry:
        continue
    metadata, raw_path = entry.split(b'\t', 1)
    name = raw_path.decode('utf-8')
    assert metadata.split()[0] != b'160000', 'Embedded Git repository: ' + name
    assert not name.endswith(('.pmvault','.dpapi','.exe','.dll','.pyc')), name
    assert not any(part in {'.venv','artifacts','build','releases','node_modules','.openai','.git'} for part in Path(name).parts), name
    assert name != 'src/password_manager/google-desktop.json', name
    content = command('show', ':' + name)
    assert not pattern.search(content), 'Credential-like content in ' + name
    paths.append(name)
assert 'web/password-manager/dist/categories.js' in paths
assert 'All Rights Reserved' in command('show', ':LICENSE.txt').decode('utf-8')
print(json.dumps({'success':True,'files':len(paths),'arr_license':True,'embedded_repositories':False,'credential_scan':'passed'}))
