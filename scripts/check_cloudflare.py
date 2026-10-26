"""Read-only public asset comparison; no account or provider mutations."""
from pathlib import Path
import hashlib
import json
from datetime import datetime, timezone
import subprocess
from concurrent.futures import ThreadPoolExecutor
from password_manager import __version__

root = Path(__file__).resolve().parents[1]
base = 'https://password-manager-vault.masaoyhs.workers.dev'
source = root / 'web/password-manager/dist'
report = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'version': __version__, 'url': base, 'assets': {}, 'account_changed': False}
assets = sorted(path.relative_to(source).as_posix() for path in source.rglob('*')
                if path.is_file() and not any(part.startswith('.') for part in path.relative_to(source).parts))
fetch_script = """
const response = await fetch(process.argv[1], {
  signal: AbortSignal.timeout(15000), headers: {'Cache-Control': 'no-cache'}
});
if (response.status !== 200) throw new Error('Unexpected HTTP status');
const chunks = []; let length = 0;
for await (const chunk of response.body) {
  length += chunk.length;
  if (length > 2 * 1024 * 1024) throw new Error('Oversized asset');
  chunks.push(chunk);
}
process.stdout.write(Buffer.concat(chunks));
"""


def check_asset(asset):
    try:
        # Node uses the same working HTTPS transport as Wrangler on this host.
        result = subprocess.run(['node', '--input-type=module', '-e', fetch_script, base + '/' + asset],
                                capture_output=True, check=True, timeout=20)
        fingerprint = hashlib.sha256(result.stdout).hexdigest()
        local = source / asset
        return asset, {'status': 200, 'sha256': fingerprint,
                       'matches_current_source': fingerprint == hashlib.sha256(local.read_bytes()).hexdigest()}
    except Exception as error:
        return asset, {'verified': False, 'error_type': type(error).__name__}


with ThreadPoolExecutor(max_workers=4) as executor:
    report['assets'] = dict(executor.map(check_asset, assets))
report['current_version_verified'] = bool(assets) and all(value.get('matches_current_source') for value in report['assets'].values())
(root / 'artifacts' / 'cloudflare-public-check.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
raise SystemExit(0 if report['current_version_verified'] else 1)
