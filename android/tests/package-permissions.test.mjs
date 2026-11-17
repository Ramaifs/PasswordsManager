import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=fileURLToPath(new URL('../../',import.meta.url));
const sdk=process.env.ANDROID_HOME || 'D:/Programs/UnityHub/Editor/2022.3.22f1/Editor/Data/PlaybackEngines/AndroidPlayer/SDK';
test('offline Android client declares the normal Internet permission needed after browser consent',()=>{
 const manifest=readFileSync(path.join(root,'android/AndroidManifest.xml'),'utf8');
 assert.match(manifest,/<uses-permission\b[^>]*android:name="android\.permission\.INTERNET"/,'Browser consent works in Chrome, but the APK cannot redeem or renew Google access without INTERNET');
});
test('signed distributable APK actually requests Internet access',()=>{
 const { version } = JSON.parse(readFileSync(path.join(root, 'android/package.json'), 'utf8'));
 const apk = path.join(root, 'releases', version, 'PasswordManager-' + version + '-android.apk');
 const result=spawnSync(path.join(sdk,'build-tools/32.0.0/aapt.exe'),['dump','permissions',apk],{encoding:'utf8'});
 assert.equal(result.status,0,result.stderr);
 assert.match(result.stdout,/android\.permission\.INTERNET/,'Signed APK cannot perform native OAuth/Drive network requests');
});
