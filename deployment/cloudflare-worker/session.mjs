// OAuth sessions contain Google credentials only; vault data never reaches this handler.
const SCOPE = 'https://www.googleapis.com/auth/drive.file';
const COOKIE = '__Host-pm-google';
const FLOW_COOKIE = '__Host-pm-oauth';
const LIFETIME = 30 * 86400;
const encoder = new TextEncoder();
const decoder = new TextDecoder();
const b64 = bytes => btoa(String.fromCharCode(...bytes)).replaceAll('+', '-').replaceAll('/', '_').replace(/=+$/, '');
const unb64 = value => Uint8Array.from(atob(value.replaceAll('-', '+').replaceAll('_', '/')), c => c.charCodeAt(0));

function reply(value, status = 200, cookie) {
  const headers = { 'Content-Type': 'application/json', 'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer', 'X-Content-Type-Options': 'nosniff' };
  if (cookie) headers['Set-Cookie'] = cookie;
  return new Response(JSON.stringify(value), { status, headers });
}
const cookie = (id, age = LIFETIME) => `${COOKIE}=${id}; Path=/; Max-Age=${age}; Secure; HttpOnly; SameSite=Strict`;
const sessionId = request => request.headers.get('Cookie')?.split(';').map(s => s.trim()).find(s => s.startsWith(COOKIE + '='))?.slice(COOKIE.length + 1);
const flowCookie = (value, age = 600) => `${FLOW_COOKIE}=${value}; Path=/; Max-Age=${age}; Secure; HttpOnly; SameSite=Lax`;
const readCookie = (request, name) => request.headers.get('Cookie')?.split(';').map(s => s.trim()).find(s => s.startsWith(name + '='))?.slice(name.length + 1);
const configured = env => !!(env.GOOGLE_SESSIONS && env.GOOGLE_CLIENT_ID && env.GOOGLE_CLIENT_SECRET && env.SESSION_ENCRYPTION_KEY && env.SITE_ORIGIN);
class SessionError extends Error {
  constructor(code, status = 503) { super(code); this.code = code; this.status = status; }
}
function validSessionKey(env) {
  try { return typeof env.SESSION_ENCRYPTION_KEY === 'string' && unb64(env.SESSION_ENCRYPTION_KEY.trim()).length === 32; }
  catch { return false; }
}
async function key(env) {
  const bytes = unb64(env.SESSION_ENCRYPTION_KEY.trim());
  if (bytes.length !== 32) throw new Error('Invalid session key');
  return crypto.subtle.importKey('raw', bytes, 'AES-GCM', false, ['encrypt', 'decrypt']);
}
async function seal(value, env, id) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const encrypted = await crypto.subtle.encrypt({ name: 'AES-GCM', iv, additionalData: encoder.encode(id) }, await key(env), encoder.encode(JSON.stringify(value)));
  return JSON.stringify({ iv: b64(iv), data: b64(new Uint8Array(encrypted)) });
}
async function unseal(stored, env, id) {
  const box = JSON.parse(stored);
  const raw = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: unb64(box.iv), additionalData: encoder.encode(id) }, await key(env), unb64(box.data));
  return JSON.parse(decoder.decode(raw));
}
async function newSession(tokens, env, kind = 'web') {
  const id = b64(crypto.getRandomValues(new Uint8Array(32)));
  const sealed = await seal({ refresh: tokens.refresh_token, expires: Date.now() + LIFETIME * 1000, origin: env.SITE_ORIGIN, client: env.GOOGLE_CLIENT_ID, kind }, env, id);
  await env.GOOGLE_SESSIONS.put(id, sealed, { expirationTtl: LIFETIME });
  return id;
}
function returnToSite(env, result, id) {
  const headers = new Headers({ Location: env.SITE_ORIGIN + '/?google=' + result, 'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer' });
  headers.append('Set-Cookie', flowCookie('', 0));
  if (id) headers.append('Set-Cookie', cookie(id));
  return new Response(null, { status: 303, headers });
}
async function redirectCallback(request, env, url) {
  let flow;
  try {
    const stored = readCookie(request, FLOW_COOKIE);
    if (!stored || stored.length > 4096) return returnToSite(env, 'invalid_state');
    flow = await unseal(decoder.decode(unb64(stored)), env, 'oauth-flow');
    if (flow.expires <= Date.now() || flow.origin !== env.SITE_ORIGIN || flow.client !== env.GOOGLE_CLIENT_ID || !flow.state || flow.state !== url.searchParams.get('state')) return returnToSite(env, 'invalid_state');
  } catch { return returnToSite(env, 'invalid_state'); }
  if (url.searchParams.has('error')) return returnToSite(env, 'denied');
  const code = url.searchParams.get('code');
  if (!code || code.length > 4096) return returnToSite(env, 'denied');
  try {
    const tokens = await googleToken({ code, grant_type: 'authorization_code', redirect_uri: env.SITE_ORIGIN + '/', code_verifier: flow.verifier }, env);
    if (!tokens?.refresh_token) return returnToSite(env, 'offline_access_missing');
    const id = await newSession(tokens, env, flow.android ? 'android' : 'web');
    if (flow.android) {
      // The public state is only a lookup key. Redemption needs the app's
      // 256-bit verifier; credentials never appear in the browser URL or HTML.
      const pairKey = 'android-pair:' + flow.android.state;
      await env.GOOGLE_SESSIONS.put(pairKey, await seal({
        session: id, challenge: flow.android.challenge, expires: Date.now() + 300000
      }, env, pairKey), { expirationTtl: 300 });
      return new Response('<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Google подключён</title><body><h1>Google подключён</h1><p>Вернитесь в Password Manager для Android.</p><a href="passwordmanager://google">Вернуться в приложение</a></body></html>', {
        headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer',
          'Set-Cookie': flowCookie('', 0), 'Content-Security-Policy': "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'" }
      });
    }
    return returnToSite(env, 'connected', id);
  } catch (error) { return returnToSite(env, error instanceof SessionError ? error.code : 'google_exchange_unavailable'); }
}
async function readSession(request, env, native = false) {
  const id = native ? request.headers.get('Authorization')?.replace(/^Bearer /, '') : sessionId(request);
  if (!id || !/^[A-Za-z0-9_-]{43}$/.test(id)) return null;
  const stored = await env.GOOGLE_SESSIONS.get(id);
  if (!stored) return null;
  try {
    const box = JSON.parse(stored);
    const raw = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: unb64(box.iv), additionalData: encoder.encode(id) }, await key(env), unb64(box.data));
    const value = JSON.parse(decoder.decode(raw));
    if (value.expires <= Date.now() || value.origin !== env.SITE_ORIGIN || value.client !== env.GOOGLE_CLIENT_ID || (native ? value.kind !== 'android' : value.kind === 'android')) return null;
    return { id, ...value };
  } catch { return null; }
}
async function googleToken(parameters, env) {
  let response;
  try { response = await (env.OAUTH_FETCH || fetch)('https://oauth2.googleapis.com/token', {
    method: 'POST', body: new URLSearchParams({ client_id: env.GOOGLE_CLIENT_ID, client_secret: env.GOOGLE_CLIENT_SECRET.trim(), ...parameters }),
    // workerd supports manual/follow only. Manual also prevents forwarding secrets.
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, redirect: 'manual', signal: AbortSignal.timeout(20000)
  }); } catch {
    throw new SessionError('google_network_unavailable');
  }
  if (!response.ok) {
    if (response.status >= 300 && response.status < 400) throw new SessionError('google_unavailable');
    const details = await response.json().catch(() => ({}));
    if (details.error === 'invalid_client' || details.error === 'unauthorized_client') throw new SessionError('oauth_invalid_client');
    if (details.error === 'redirect_uri_mismatch') throw new SessionError('oauth_redirect_mismatch');
    if (details.error === 'invalid_grant') throw new SessionError('oauth_invalid_grant', 401);
    throw new SessionError('google_unavailable');
  }
  let value;
  try { value = await response.json(); }
  catch { throw new SessionError('google_response_invalid'); }
  if (typeof value.access_token !== 'string' || !value.access_token || !Number.isFinite(Number(value.expires_in)) || Number(value.expires_in) <= 0) return null;
  if (value.scope && !value.scope.split(' ').includes(SCOPE)) return null;
  return value;
}
async function codeBody(request) {
  if (Number(request.headers.get('Content-Length')) > 8192) return null;
  const reader = request.body?.getReader();
  if (!reader) return null;
  const chunks = []; let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read(); if (done) break;
      size += value.length; if (size > 8192) return null;
      chunks.push(value);
    }
  } finally { await reader.cancel().catch(() => {}); }
  const bytes = new Uint8Array(size); let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  return decoder.decode(bytes);
}

async function startFlow(env, android) {
  const state = b64(crypto.getRandomValues(new Uint8Array(32)));
  const verifier = b64(crypto.getRandomValues(new Uint8Array(32)));
  const challenge = b64(new Uint8Array(await crypto.subtle.digest('SHA-256', encoder.encode(verifier))));
  const flow = await seal({ state, verifier, expires: Date.now() + 600000, origin: env.SITE_ORIGIN, client: env.GOOGLE_CLIENT_ID, ...(android ? { android } : {}) }, env, 'oauth-flow');
  const auth = new URL('https://accounts.google.com/o/oauth2/v2/auth');
  auth.search = new URLSearchParams({ client_id: env.GOOGLE_CLIENT_ID, redirect_uri: env.SITE_ORIGIN + '/', response_type: 'code', scope: SCOPE, state, code_challenge: challenge, code_challenge_method: 'S256', access_type: 'offline', prompt: 'consent' });
  return { url: auth.href, cookie: flowCookie(b64(encoder.encode(flow))) };
}
async function handleAndroid(request, env, url) {
  // Native clients cannot supply browser Origin. No CORS headers are emitted;
  // browser callers cannot read native bearer credentials across origins.
  if (request.headers.has('Origin') || request.headers.get('Sec-Fetch-Site') === 'cross-site') return reply({ error: 'Invalid native request' }, 403);
  if (url.pathname === '/api/android/connect' && request.method === 'GET') {
    const state = url.searchParams.get('state'), challenge = url.searchParams.get('challenge');
    if (!/^[A-Za-z0-9_-]{43}$/.test(state || '') || !/^[A-Za-z0-9_-]{43}$/.test(challenge || '')) return reply({ error: 'Invalid pairing request' }, 400);
    const flow = await startFlow(env, { state, challenge });
    return new Response(null, { status: 303, headers: { Location: flow.url, 'Set-Cookie': flow.cookie, 'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer' } });
  }
  if (request.method !== 'POST') return reply({ error: 'Method not allowed' }, 405);
  if (url.pathname === '/api/android/pair') {
    if (!request.headers.get('Content-Type')?.startsWith('application/json')) return reply({ error: 'Invalid request format' }, 400);
    const source = await codeBody(request);
    let body; try { body = JSON.parse(source); } catch { return reply({ error: 'Invalid pairing request' }, 400); }
    if (!body || !/^[A-Za-z0-9_-]{43}$/.test(body.state || '') || !/^[A-Za-z0-9_-]{43}$/.test(body.verifier || '')) return reply({ error: 'Invalid pairing request' }, 400);
    const pairKey = 'android-pair:' + body.state, stored = await env.GOOGLE_SESSIONS.get(pairKey);
    if (!stored) return reply({ pending: true });
    const pair = await unseal(stored, env, pairKey);
    const challenge = b64(new Uint8Array(await crypto.subtle.digest('SHA-256', encoder.encode(body.verifier))));
    if (pair.expires <= Date.now() || pair.challenge !== challenge) return reply({ error: 'Pairing expired or invalid' }, 403);
    // Idempotent for five minutes, allowing recovery if a response is lost.
    // Each retry requires the same secret verifier, which never leaves the app.
    return reply({ session: pair.session });
  }
  if (!['/api/android/token', '/api/android/logout'].includes(url.pathname)) return reply({ error: 'Not found' }, 404);
  const session = await readSession(request, env, true);
  if (!session) return reply({ error: 'Google session expired' }, 401);
  if (url.pathname === '/api/android/logout') {
    await env.GOOGLE_SESSIONS.delete(session.id); return reply({ success: true });
  }
  const tokens = await googleToken({ grant_type: 'refresh_token', refresh_token: session.refresh }, env);
  if (!tokens) return reply({ error: 'Reconnect Google to continue' }, 401);
  return reply({ access_token: tokens.access_token, expires_in: tokens.expires_in });
}

export async function handleSession(request, env) {
  const url = new URL(request.url), path = url.pathname;
  if (path === '/api/google/config' && request.method === 'GET') return reply({ enabled: configured(env), clientId: configured(env) ? env.GOOGLE_CLIENT_ID : null });
  if (!configured(env)) return reply({ error: 'Google session service is not configured' }, 503);
  if (!validSessionKey(env)) return reply({ error: 'session_key_invalid' }, 503);
  if (url.origin === env.SITE_ORIGIN && path.startsWith('/api/android/')) {
    try { return await handleAndroid(request, env, url); }
    catch (error) { return reply({ error: error instanceof SessionError ? error.code : 'android_session_unavailable' }, error instanceof SessionError ? error.status : 502); }
  }
  if (url.origin === env.SITE_ORIGIN && path === '/' && request.method === 'GET' && (url.searchParams.has('code') || url.searchParams.has('error'))) return redirectCallback(request, env, url);
  if (url.origin !== env.SITE_ORIGIN || request.headers.get('Origin') !== env.SITE_ORIGIN || request.headers.get('X-Requested-With') !== 'XMLHttpRequest') return reply({ error: 'Invalid request origin' }, 403);
  if (request.method !== 'POST') return reply({ error: 'Method not allowed' }, 405);
  let stage = 'session_storage_unavailable';
  try {
    if (path === '/api/google/start') {
      const flow = await startFlow(env);
      return reply({ authorization_url: flow.url }, 200, flow.cookie);
    }
    if (path === '/api/google/exchange') {
      if (!request.headers.get('Content-Type')?.startsWith('application/json')) return reply({ error: 'Invalid request format' }, 400);
      stage = 'request_body_unavailable';
      const body = await codeBody(request);
      if (body === null) return reply({ error: 'Request too large or empty' }, 413);
      let code;
      try { ({ code } = JSON.parse(body)); } catch { return reply({ error: 'Invalid request format' }, 400); }
      if (typeof code !== 'string' || !code || code.length > 4096) return reply({ error: 'Invalid authorization code' }, 400);
      stage = 'google_exchange_unavailable';
      const tokens = await googleToken({ code, grant_type: 'authorization_code', redirect_uri: env.SITE_ORIGIN }, env);
      if (!tokens || typeof tokens.refresh_token !== 'string' || !tokens.refresh_token) return reply({ error: 'offline_access_missing' }, 401);
      stage = 'session_crypto_unavailable';
      const id = b64(crypto.getRandomValues(new Uint8Array(32)));
      const sealed = await seal({ refresh: tokens.refresh_token, expires: Date.now() + LIFETIME * 1000, origin: env.SITE_ORIGIN, client: env.GOOGLE_CLIENT_ID }, env, id);
      stage = 'session_storage_unavailable';
      await env.GOOGLE_SESSIONS.put(id, sealed, { expirationTtl: LIFETIME });
      const previous = sessionId(request);
      if (previous && /^[A-Za-z0-9_-]{43}$/.test(previous)) await env.GOOGLE_SESSIONS.delete(previous);
      return reply({ access_token: tokens.access_token, expires_in: tokens.expires_in }, 200, cookie(id));
    }
    if (path === '/api/google/logout') {
      const id = sessionId(request);
      if (id && /^[A-Za-z0-9_-]{43}$/.test(id)) await env.GOOGLE_SESSIONS.delete(id);
      return reply({ success: true }, 200, cookie('', 0));
    }
    if (path === '/api/google/token') {
      const session = await readSession(request, env);
      if (!session) return reply({ error: 'Google session expired' }, 401, cookie('', 0));
      stage = 'google_exchange_unavailable';
      const tokens = await googleToken({ grant_type: 'refresh_token', refresh_token: session.refresh }, env);
      if (!tokens) return reply({ error: 'Reconnect Google to continue' }, 401);
      return reply({ access_token: tokens.access_token, expires_in: tokens.expires_in });
    }
    return reply({ error: 'Not found' }, 404);
  } catch (error) {
    // Provider errors, codes and tokens must never enter application logs or responses.
    if (error instanceof SessionError) return reply({ error: error.code }, error.status);
    return reply({ error: stage }, 502);
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname.startsWith('/api/google/') || url.pathname.startsWith('/api/android/') || (url.pathname === '/' && (url.searchParams.has('code') || url.searchParams.has('error')))) return handleSession(request, env);
    return env.ASSETS.fetch(request);
  }
};
