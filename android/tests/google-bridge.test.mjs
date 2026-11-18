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

test('fresh pairing retries a briefly unavailable session and replaces the old account token', async () => {
 const calls = [];
 let tokenRequests = 0;
 AndroidVault.authRequest = (id, path) => {
  calls.push(path);
  if (path === 'pair') return queueMicrotask(() => window.pmAuthResult(id, {value:{paired:true}}));
  const count = ++tokenRequests;
  queueMicrotask(() => window.pmAuthResult(id, count === 2
    ? {error:'Session not visible yet',code:'session_expired'}
    : {value:{access_token:count === 1 ? 'OLD' : 'NEW',expires_in:3600}}));
 };
 const client = await import('../assets/ui/google.js?fresh-pairing');
 assert.equal(await client.ensureAccessToken(),'OLD');
 assert.equal(await client.authorize(),'NEW');
 assert.deepEqual(calls,['token','pair','token','token']);
});

test('a revoked saved Google session allows sign-in again without retrying the rejected token', async () => {
 let calls = 0;
 AndroidVault.authRequest = id => {
  calls++;
  queueMicrotask(() => window.pmAuthResult(id,{error:'Reconnect Google',code:'access_revoked'}));
 };
 const client = await import('../assets/ui/google.js?revoked');
 await assert.rejects(client.ensureAccessToken(),{code:'access_revoked'});
 assert.equal(client.connected(), false);
 await assert.rejects(client.ensureAccessToken(),/Подключите Google Drive/);
 assert.equal(calls,1);
});

test('a temporary network interruption during pairing retries without reopening Google', async () => {
 let browserOpens = 0;
 let pairRequests = 0;
 AndroidVault.connect = () => { browserOpens++; };
 AndroidVault.authRequest = (id, path) => {
  const result = path === 'token' ? {value:{access_token:'RECOVERED',expires_in:3600}}
   : ++pairRequests === 1 ? {error:'Connection reset',code:'transport_retry'}
   : {value:{paired:true}};
  queueMicrotask(() => window.pmAuthResult(id,result));
 };
 const client = await import('../assets/ui/google.js?pair-interrupted');
 assert.equal(await client.authorize(),'RECOVERED');
 assert.equal(browserOpens,1);
 assert.equal(pairRequests,2);
});
