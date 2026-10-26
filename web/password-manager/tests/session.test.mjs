import test from 'node:test';
import assert from 'node:assert/strict';
import { handleSession } from '../../../deployment/cloudflare-worker/session.mjs';

const origin = 'https://vault.example.invalid';
function fixture() {
  const values = new Map(), grants = [];
  const env = {
    SITE_ORIGIN: origin, GOOGLE_CLIENT_ID: '123-test.apps.googleusercontent.com', GOOGLE_CLIENT_SECRET: 'FICTIONAL-SECRET',
    SESSION_ENCRYPTION_KEY: Buffer.alloc(32, 7).toString('base64url'),
    GOOGLE_SESSIONS: { get: async id => values.get(id), put: async (id, value) => values.set(id, value), delete: async id => values.delete(id) },
    OAUTH_FETCH: async (url, options) => {
      assert.equal(url, 'https://oauth2.googleapis.com/token');
      grants.push(Object.fromEntries(options.body));
      return Response.json({ access_token: 'FICTIONAL-ACCESS', expires_in: 3600, scope: 'https://www.googleapis.com/auth/drive.file', ...(options.body.get('grant_type') === 'authorization_code' ? { refresh_token: 'FICTIONAL-REFRESH' } : {}) });
    }
  };
  const request = (path, cookie = '', body = {}) => new Request(origin + '/api/google/' + path, { method: 'POST', headers: { Origin: origin, 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest', Cookie: cookie }, body: JSON.stringify(body) });
  return { env, values, grants, request };
}

test('OAuth session survives reload, refreshes, encrypts credentials and logout revokes it', async () => {
  const { env, values, grants, request } = fixture();
  const login = await handleSession(request('exchange', '', { code: 'FICTIONAL-CODE' }), env);
  assert.equal(login.status, 200);
  const cookie = login.headers.get('Set-Cookie');
  for (const flag of ['__Host-pm-google=', 'Secure', 'HttpOnly', 'SameSite=Strict', 'Max-Age=2592000']) assert.ok(cookie.includes(flag));
  assert.equal(login.headers.get('Cache-Control'), 'no-store');
  const response = await login.json();
  assert.equal(response.access_token, 'FICTIONAL-ACCESS');
  assert.ok(!JSON.stringify(response).includes('REFRESH'));
  assert.ok(!JSON.stringify([...values.values()]).includes('FICTIONAL-REFRESH'));
  const restored = await handleSession(request('token', cookie.split(';')[0]), env);
  assert.equal(restored.status, 200);
  assert.equal((await restored.json()).access_token, 'FICTIONAL-ACCESS');
  assert.equal(grants[1].grant_type, 'refresh_token');
  assert.equal(grants[0].redirect_uri, origin);
  assert.equal((await handleSession(request('logout', cookie.split(';')[0]), env)).status, 200);
  assert.equal(values.size, 0);
  assert.equal((await handleSession(request('token', cookie.split(';')[0]), env)).status, 401);
});

test('OAuth rejects cross-origin, missing CSRF header, malformed codes and unconfigured service', async () => {
  const { env, request, grants } = fixture();
  const foreign = request('exchange', '', { code: 'CODE' }); foreign.headers.set('Origin', 'https://evil.invalid');
  assert.equal((await handleSession(foreign, env)).status, 403);
  const noHeader = request('exchange'); noHeader.headers.delete('X-Requested-With');
  assert.equal((await handleSession(noHeader, env)).status, 403);
  assert.equal((await handleSession(request('exchange', '', { code: '' }), env)).status, 400);
  assert.equal((await handleSession(request('exchange', '', { code: 'CODE' }), {})).status, 503);
  assert.equal(grants.length, 0);
});

test('OAuth encrypted sessions reject corruption, another site or client, and provider denial', async () => {
  const { env, request, values } = fixture();
  const login = await handleSession(request('exchange', '', { code: 'CODE' }), env);
  const cookie = login.headers.get('Set-Cookie').split(';')[0];
  const [id, original] = [...values][0];
  values.set(id, original.replace(/"data":"./, '"data":"!'));
  assert.equal((await handleSession(request('token', cookie), env)).status, 401);
  values.set(id, original);
  assert.equal((await handleSession(request('token', cookie), { ...env, GOOGLE_CLIENT_ID: 'OTHER' })).status, 401);
  env.OAUTH_FETCH = async () => Response.json({ error: 'invalid_grant', error_description: 'SECRET-PROVIDER-CONTENT' }, { status: 400 });
  const denied = await handleSession(request('token', cookie), env);
  assert.equal(denied.status, 401); assert.ok(!(await denied.text()).includes('SECRET-PROVIDER'));
});

test('browser restores server session, renews after expiry and never stores tokens in browser databases', async () => {
  const client = await import('../dist/google.js?persistent-test');
  const savedFetch = globalThis.fetch, realNow = Date.now;
  let tokens = 0, logout = false;
  globalThis.fetch = async (url, options) => {
    assert.equal(options.credentials, 'same-origin');
    if (url.endsWith('/config')) return Response.json({ enabled: true, clientId: '123-test.apps.googleusercontent.com' });
    assert.equal(options.headers['X-Requested-With'], 'XMLHttpRequest');
    if (url.endsWith('/logout')) { logout = true; return Response.json({ success: true }); }
    tokens++; return Response.json({ access_token: 'TOKEN-' + tokens, expires_in: 3600 });
  };
  try {
    assert.ok(await client.initializeGoogleSession('123-test.apps.googleusercontent.com'));
    assert.equal(client.accessToken(), 'TOKEN-1');
    const initial = realNow(); Date.now = () => initial + 3600000;
    assert.ok(client.connected());
    assert.equal(await client.ensureAccessToken(), 'TOKEN-2');
    client.cancelGoogleLogin(); assert.ok(client.connected());
    await client.disconnectGoogle(); assert.ok(logout); assert.ok(!client.connected());
  } finally { globalThis.fetch = savedFetch; Date.now = realNow; }
});

test('browser code login and a fresh page share the Worker session without another Google popup', async () => {
  const { env, values } = fixture();
  const originalFetch = globalThis.fetch, originalGoogle = globalThis.google;
  let cookie = '', popups = 0;
  globalThis.fetch = async (path, options) => {
    const response = await handleSession(new Request(origin + path, { ...options, headers: { ...options.headers, Origin: origin, Cookie: cookie } }), env);
    if (response.headers.has('Set-Cookie')) cookie = response.headers.get('Set-Cookie').split(';')[0];
    return response;
  };
  globalThis.google = { accounts: { oauth2: { initCodeClient: config => ({ requestCode() { popups++; queueMicrotask(() => config.callback({ code: 'FICTIONAL-CODE' })); } }) } } };
  try {
    const first = await import('../dist/google.js?first-page');
    assert.equal(await first.initializeGoogleSession(env.GOOGLE_CLIENT_ID), false);
    await first.authorize(env.GOOGLE_CLIENT_ID);
    assert.ok(first.connected()); assert.equal(popups, 1); assert.equal(values.size, 1);
    const reloaded = await import('../dist/google.js?reloaded-page');
    assert.equal(await reloaded.initializeGoogleSession(env.GOOGLE_CLIENT_ID), true);
    assert.equal(reloaded.accessToken(), 'FICTIONAL-ACCESS'); assert.equal(popups, 1);
    await reloaded.disconnectGoogle(); assert.equal(values.size, 0);
  } finally { globalThis.fetch = originalFetch; globalThis.google = originalGoogle; }
});

test('Google client and session-key configuration failures are specific and redact provider details', async () => {
  const { env, request } = fixture();
  env.OAUTH_FETCH = async () => Response.json({ error: 'invalid_client', error_description: 'SECRET-PROVIDER-CONTENT' }, { status: 401 });
  const invalidClient = await handleSession(request('exchange', '', { code: 'CODE' }), env);
  assert.equal(invalidClient.status, 503);
  const clientError = await invalidClient.text();
  assert.ok(clientError.includes('oauth_invalid_client'));
  assert.ok(!clientError.includes('SECRET-PROVIDER'));
  env.SESSION_ENCRYPTION_KEY = 'not-a-session-key';
  const invalidKey = await handleSession(request('exchange', '', { code: 'CODE' }), env);
  assert.equal(invalidKey.status, 503);
  assert.equal((await invalidKey.json()).error, 'session_key_invalid');
});

test('Worker token exchange uses supported manual redirects and never follows credentials', async () => {
  const { env, request } = fixture();
  env.OAUTH_FETCH = async (url, options) => {
    // workerd rejects redirect:error before making any HTTP request.
    assert.equal(options.redirect, 'manual');
    return new Response(null, { status: 302, headers: { Location: 'https://other.invalid/' } });
  };
  const response = await handleSession(request('exchange', '', { code: 'CODE' }), env);
  assert.equal(response.status, 503);
  assert.equal((await response.json()).error, 'google_unavailable');
});
