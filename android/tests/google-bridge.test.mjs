import test from 'node:test';
import assert from 'node:assert/strict';
globalThis.window=globalThis;
let saved=true,opened,requests=[];
globalThis.AndroidVault={hasSession:()=>saved,connect:(state,challenge)=>{opened={state,challenge};},authRequest:(id,path,body)=>{
 requests.push({path,body:JSON.parse(body)});
 queueMicrotask(()=>window.pmAuthResult(id,{value:path==='pair'?{paired:true}:path==='token'?{access_token:'FICTIONAL',expires_in:3600}:{success:true}}));
}};
const google=await import('../assets/ui/google.js');
test('saved native session renews without browser, new pairing uses secret verifier, disconnect clears access',async()=>{
 assert(google.connected());assert.equal(await google.ensureAccessToken(),'FICTIONAL');assert.equal(opened,undefined);
 await google.authorize();assert.match(opened.state,/^[A-Za-z0-9_-]{43}$/);assert.match(opened.challenge,/^[A-Za-z0-9_-]{43}$/);
 const pair=requests.find(r=>r.path==='pair');assert(pair);assert.equal(pair.body.state,opened.state);assert.notEqual(pair.body.verifier,opened.challenge);
 const expected=Buffer.from(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(pair.body.verifier))).toString('base64url');assert.equal(opened.challenge,expected);
 await google.disconnectGoogle();assert(!google.connected());assert.throws(()=>google.accessToken());
});
