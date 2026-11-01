"""Build and verify the browser-backed APK using an existing Android SDK/JDK.

No downloads, installation, emulator launch or publication. The signing identity is
reused across builds; its password is DPAPI-protected for the current Windows user.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import uuid
import xml.etree.ElementTree as ET
import zipfile

from password_manager.protected import _dpapi

ROOT = Path(__file__).resolve().parents[1]
UNITY = Path("C:/Program Files/Unity/Hub/Editor/2022.3.22f1/Editor/Data/PlaybackEngines/AndroidPlayer")
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--sdk', type=Path, default=os.environ.get('ANDROID_HOME', UNITY / 'SDK'))
parser.add_argument('--jdk', type=Path, default=os.environ.get('JAVA_HOME', UNITY / 'OpenJDK'))
parser.add_argument('--platform', default='android-32')
parser.add_argument('--build-tools', default='32.0.0')
args = parser.parse_args()
tools = args.sdk / 'build-tools' / args.build_tools
platform = args.sdk / 'platforms' / args.platform / 'android.jar'
java, javac, keytool = [args.jdk / 'bin' / (name + '.exe') for name in ('java', 'javac', 'keytool')]
for required in (java, javac, keytool, platform, tools / 'aapt.exe', tools / 'lib/d8.jar', tools / 'lib/apksigner.jar', tools / 'zipalign.exe'):
    if not required.is_file():
        raise SystemExit(f'Missing existing Android build tool: {required}')

namespace = '{http://schemas.android.com/apk/res/android}'
manifest = ROOT / 'android/AndroidManifest.xml'
version = ET.parse(manifest).getroot().get(namespace + 'versionName')
work = ROOT / 'build' / ('android-' + uuid.uuid4().hex)
for name in ('gen', 'classes', 'dex'):
    (work / name).mkdir(parents=True)
out = ROOT / 'releases' / version
out.mkdir(parents=True, exist_ok=True)
environment = os.environ.copy()

def run(*command):
    result = subprocess.run([str(v) for v in command], env=environment, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode:
        # Arguments never contain the signing password.
        raise RuntimeError(f'{Path(str(command[0])).name} exited {result.returncode}\n{result.stdout}\n{result.stderr}')
    return result.stdout

run(tools / 'aapt.exe', 'package', '-f', '-M', manifest, '-S', ROOT / 'android/res', '-I', platform, '-F', work / 'resources.apk', '-J', work / 'gen')
sources = sorted((ROOT / 'android/src').rglob('*.java')) + sorted((work / 'gen').rglob('*.java'))
run(javac, '-encoding', 'UTF-8', '--release', '8', '-classpath', platform, '-d', work / 'classes', *sources)
run(java, '-cp', tools / 'lib/d8.jar', 'com.android.tools.r8.D8', '--lib', platform, '--min-api', '23', '--output', work / 'dex', *sorted((work / 'classes').rglob('*.class')))
with zipfile.ZipFile(work / 'resources.apk', 'a', zipfile.ZIP_DEFLATED) as archive:
    archive.write(work / 'dex/classes.dex', 'classes.dex')
run(tools / 'zipalign.exe', '-f', '4', work / 'resources.apk', work / 'aligned.apk')

identity = ROOT / 'deployment/android-signing'
identity.mkdir(parents=True, exist_ok=True)
keystore, password_file = identity / 'release.keystore', identity / 'password.dpapi'
if keystore.exists() != password_file.exists():
    raise SystemExit('Incomplete signing identity. Restore the matching keystore and DPAPI password; do not regenerate it.')
if not keystore.exists():
    password_file.write_bytes(_dpapi(secrets.token_urlsafe(48).encode('ascii')))
    environment['PM_ANDROID_SIGNING_PASSWORD'] = _dpapi(password_file.read_bytes(), decrypt=True).decode('ascii')
    run(keytool, '-genkeypair', '-keystore', keystore, '-storetype', 'PKCS12', '-alias', 'release', '-keyalg', 'RSA', '-keysize', '3072', '-validity', '10000', '-dname', 'CN=Password Manager,OU=Android,O=Ramaifs', '-storepass:env', 'PM_ANDROID_SIGNING_PASSWORD', '-keypass:env', 'PM_ANDROID_SIGNING_PASSWORD')
else:
    environment['PM_ANDROID_SIGNING_PASSWORD'] = _dpapi(password_file.read_bytes(), decrypt=True).decode('ascii')
apk = out / f'PasswordManager-{version}-android.apk'
run(java, '-jar', tools / 'lib/apksigner.jar', 'sign', '--ks', keystore, '--ks-key-alias', 'release', '--ks-pass', 'env:PM_ANDROID_SIGNING_PASSWORD', '--key-pass', 'env:PM_ANDROID_SIGNING_PASSWORD', '--out', apk, work / 'aligned.apk')
verification = run(java, '-jar', tools / 'lib/apksigner.jar', 'verify', '--verbose', '--print-certs', apk)
run(tools / 'zipalign.exe', '-c', '4', apk)
badging = run(tools / 'aapt.exe', 'dump', 'badging', apk)
with zipfile.ZipFile(apk) as archive:
    assert archive.testzip() is None
    assert {'AndroidManifest.xml', 'classes.dex', 'resources.arsc'} <= set(archive.namelist())
report = {
    'version': version, 'package': 'com.ramaifs.passwordmanager', 'kind': 'browser-backed Android client (Custom Tabs, HTTPS site)',
    'apk': apk.relative_to(ROOT).as_posix(), 'bytes': apk.stat().st_size,
    'sha256': hashlib.sha256(apk.read_bytes()).hexdigest(),
    'signature_verification': verification, 'badging': badging,
    'input_hashes': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT / 'android').rglob('*')) if p.is_file()},
    'device_tested': False, 'published': False,
}
(out / 'android-manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: report[k] for k in ('version', 'apk', 'bytes', 'sha256', 'device_tested')}, indent=2))
print(verification)
