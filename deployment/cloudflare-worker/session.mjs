// OAuth sessions contain Google credentials only; vault data never reaches this handler.
const SCOPE = 'https://www.googleapis.com/auth/drive.file';
const COOKIE = '__Host-pm-google';
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
const configured = env => !!(env.GOOGLE_SESSIONS && env.GOOGLE_CLIENT_ID && env.GOOGLE_CLIENT_SECRET && env.SESSION_ENCRYPTION_KEY && env.SITE_ORIGIN);
async function key(env) {
  const bytes = unb64(env.SESSION_ENCRYPTION_KEY);
  if (bytes.length !== 32) throw new Error('Invalid session key');
  return crypto.subtle.importKey('raw', bytes, 'AES-GCM', false, ['encrypt', 'decrypt']);
}
async function seal(value, env, id) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const encrypted = await crypto.subtle.encrypt({ name: 'AES-GCM', iv, additionalData: encoder.encode(id) }, await key(env), encoder.encode(JSON.stringify(value)));
  return JSON.stringify({ iv: b64(iv), data: b64(new Uint8Array(encrypted)) });
}
async function readSession(request, env) {
  const id = sessionId(request);
  if (!id || !/^[A-Za-z0-9_-]{43}$/.test(id)) return null;
  const stored = await env.GOOGLE_SESSIONS.get(id);
  if (!stored) return null;
  try {
    const box = JSON.parse(stored);
    const raw = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: unb64(box.iv), additionalData: encoder.encode(id) }, await key(env), unb64(box.data));
    const value = JSON.parse(decoder.decode(raw));
    if (value.expires <= Date.now() || value.origin !== env.SITE_ORIGIN || value.client !== env.GOOGLE_CLIENT_ID) return null;
    return { id, ...value };
  } catch { return null; }
}
async function googleToken(parameters, env) {
  const response = await (env.OAUTH_FETCH || fetch)('https://oauth2.googleapis.com/token', {
    method: 'POST', body: new URLSearchParams({ client_id: env.GOOGLE_CLIENT_ID, client_secret: env.GOOGLE_CLIENT_SECRET, ...parameters }),
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, redirect: 'error', signal: AbortSignal.timeout(20000)
  });
  if (!response.ok) return null;
  const value = await response.json();
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

export async function handleSession(request, env) {
  const url = new URL(request.url), path = url.pathname;
  if (path === '/api/google/config' && request.method === 'GET') return reply({ enabled: configured(env), clientId: configured(env) ? env.GOOGLE_CLIENT_ID : null });
  if (!configured(env)) return reply({ error: 'Google session service is not configured' }, 503);
  if (url.origin !== env.SITE_ORIGIN || request.headers.get('Origin') !== env.SITE_ORIGIN || request.headers.get('X-Requested-With') !== 'XMLHttpRequest') return reply({ error: 'Invalid request origin' }, 403);
  if (request.method !== 'POST') return reply({ error: 'Method not allowed' }, 405);
  try {
    if (path === '/api/google/exchange') {
      if (!request.headers.get('Content-Type')?.startsWith('application/json')) return reply({ error: 'Invalid request format' }, 400);
      const body = await codeBody(request);
      if (body === null) return reply({ error: 'Request too large or empty' }, 413);
      let code;
      try { ({ code } = JSON.parse(body)); } catch { return reply({ error: 'Invalid request format' }, 400); }
      if (typeof code !== 'string' || !code || code.length > 4096) return reply({ error: 'Invalid authorization code' }, 400);
      const tokens = await googleToken({ code, grant_type: 'authorization_code', redirect_uri: env.SITE_ORIGIN }, env);
      if (!tokens || typeof tokens.refresh_token !== 'string' || !tokens.refresh_token) return reply({ error: 'Google did not grant offline access. Reconnect Google.' }, 401);
      const id = b64(crypto.getRandomValues(new Uint8Array(32)));
      await env.GOOGLE_SESSIONS.put(id, await seal({ refresh: tokens.refresh_token, expires: Date.now() + LIFETIME * 1000, origin: env.SITE_ORIGIN, client: env.GOOGLE_CLIENT_ID }, env, id), { expirationTtl: LIFETIME });
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
      const tokens = await googleToken({ grant_type: 'refresh_token', refresh_token: session.refresh }, env);
      if (!tokens) return reply({ error: 'Reconnect Google to continue' }, 401);
      return reply({ access_token: tokens.access_token, expires_in: tokens.expires_in });
    }
    return reply({ error: 'Not found' }, 404);
  } catch {
    // Provider errors, codes and tokens must never enter application logs or responses.
    return reply({ error: 'Google session service is unavailable. Try again.' }, 502);
  }
}

export default {
  async fetch(request, env) {
    if (new URL(request.url).pathname.startsWith('/api/google/')) return handleSession(request, env);
    return env.ASSETS.fetch(request);
  }
};
