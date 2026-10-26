"""Read-only public asset comparison; no account or provider mutations."""
from pathlib import Path
import hashlib
import json
from datetime import datetime, timezone
import urllib.request

root = Path(__file__).resolve().parents[1]
base = 'https://password-manager-vault.masaoyhs.workers.dev'
report = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'url': base, 'assets': {}, 'account_changed': False}
for asset in ('index.html', 'app.js', 'storage.js'):
    try:
        request = urllib.request.Request(base + '/' + asset, headers={'User-Agent': 'PasswordManagerDeploymentCheck/1.0'})
        with urllib.request.urlopen(request, timeout=15) as response:
            data = response.read(2 * 1024 * 1024 + 1)
            if len(data) > 2 * 1024 * 1024:
                raise ValueError('oversized asset')
            fingerprint = hashlib.sha256(data).hexdigest()
            local = root / 'web' / 'password-manager' / 'dist' / asset
            report['assets'][asset] = {'status': response.status, 'sha256': fingerprint,
                'matches_current_source': fingerprint == hashlib.sha256(local.read_bytes()).hexdigest()}
    except Exception as error:
        report['assets'][asset] = {'verified': False, 'error_type': type(error).__name__}
report['current_version_verified'] = all(value.get('matches_current_source') for value in report['assets'].values())
(root / 'artifacts' / 'cloudflare-public-check.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
