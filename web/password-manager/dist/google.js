// Access token stays in memory until expiry, explicit disconnect or page reload.
export const SCOPE = 'https://www.googleapis.com/auth/drive.file';
let loading, token = null, expiry = 0, epoch = 0, cancelLogin;
let persistent = false, serverSession = false, renewing;
async function sessionRequest(path, body = {}, fetcher = globalThis.fetch) {
  const response = await fetcher('/api/google/' + path, { method: 'POST', credentials: 'same-origin', cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(25000), headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }, body: JSON.stringify(body) });
  if (!response.ok) { const error = new Error('Подключите Google заново: сессия завершена или сервер недоступен.'); error.status = response.status; throw error; }
  return response.json();
}
function acceptToken(response) {
  const seconds = Number(response.expires_in);
  if (typeof response.access_token !== 'string' || !response.access_token || !Number.isFinite(seconds) || seconds <= 0) throw new Error('Google не подтвердил срок доступа.');
  token = response.access_token; expiry = Date.now() + seconds * 1000 - 30000;
  return token;
}
export async function initializeGoogleSession(clientId, fetcher = globalThis.fetch) {
  try {
    const response = await fetcher('/api/google/config', { credentials: 'same-origin', cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(5000) });
    if (!response.ok) return false;
    const config = await response.json();
    persistent = config.enabled === true && config.clientId === clientId;
    if (!persistent) return false;
    try { acceptToken(await sessionRequest('token', {}, fetcher)); serverSession = true; }
    catch { serverSession = false; }
  } catch { persistent = false; }
  return connected();
}
export async function ensureAccessToken() {
  if (token && Date.now() < expiry) return token;
  if (!persistent || !serverSession) return accessToken();
  if (!renewing) {
    const generation = epoch;
    renewing = sessionRequest('token').then(response => {
      if (generation !== epoch) throw new Error('Обмен остановлен.');
      return acceptToken(response);
    }).catch(error => { if (generation === epoch && error.status === 401) { token = null; expiry = 0; serverSession = false; } throw error; }).finally(() => { renewing = null; });
  }
  return renewing;
}
export async function disconnectGoogle() {
  clearGoogle(); serverSession = false;
  if (persistent) await sessionRequest('logout');
}
export function persistentSessionEnabled() { return persistent; }
export function validClientId(value) { return typeof value === 'string' && /^[0-9]+-[a-zA-Z0-9_-]+\.apps\.googleusercontent\.com$/.test(value); }
export function loadGoogle() {
  if (globalThis.google?.accounts?.oauth2) return Promise.resolve();
  if (loading) return loading;
  loading = new Promise((resolve, reject) => {
    const script = document.createElement('script'); script.src = 'https://accounts.google.com/gsi/client'; script.async = true; script.referrerPolicy = 'strict-origin-when-cross-origin';
    const timer = setTimeout(() => { script.remove(); loading = null; reject(new Error('Google не отвечает. Повторите подключение.')); }, 20000);
    script.onload = () => { clearTimeout(timer); resolve(); };
    script.onerror = () => { clearTimeout(timer); loading = null; script.remove(); reject(new Error('Не удалось загрузить вход Google. Проверьте подключение.')); };
    document.head.append(script);
  }); return loading;
}
export function authorize(clientId) {
  if (!validClientId(clientId) || !globalThis.google?.accounts?.oauth2) return Promise.reject(new Error('Сначала настройте Web client ID и подготовьте вход Google.'));
  const generation = epoch;
  return new Promise((resolve, reject) => {
    let settled = false;
    const timer = setTimeout(() => finish(new Error('Вход Google не завершён. Повторите подключение.')), 120000);
    const cancel = () => finish(new Error('Вход отменён: хранилище заблокировано.'));
    function finish(error, value) { if (settled) return; settled = true; clearTimeout(timer); if (cancelLogin === cancel) cancelLogin = null; error ? reject(error) : resolve(value); }
    cancelLogin = cancel;
    if (persistent) {
      const client = google.accounts.oauth2.initCodeClient({ client_id: clientId, scope: SCOPE, include_granted_scopes: false, ux_mode: 'popup',
        callback: async response => {
          if (settled || generation !== epoch) return finish(new Error('Вход отменён.'));
          if (response.error || !response.code) return finish(new Error('Доступ Google не предоставлен.'));
          try {
            const result = await sessionRequest('exchange', { code: response.code });
            if (settled || generation !== epoch) return finish(new Error('Вход отменён.'));
            serverSession = true; finish(null, acceptToken(result));
          } catch (error) { finish(error); }
        }, error_callback: () => finish(new Error('Окно входа закрыто или заблокировано браузером.')) });
      try { client.requestCode(); } catch { finish(new Error('Не удалось открыть окно Google.')); }
      return;
    }
    const client = google.accounts.oauth2.initTokenClient({ client_id: clientId, scope: SCOPE, include_granted_scopes: false,
      callback: response => {
        if (settled || generation !== epoch) return finish(new Error('Вход отменён.'));
        if (response.error || !response.access_token || !google.accounts.oauth2.hasGrantedAllScopes(response, SCOPE)) return finish(new Error('Доступ к файлам приложения не предоставлен.'));
        const seconds = Number(response.expires_in);
        if (!Number.isFinite(seconds) || seconds <= 0) return finish(new Error('Google не подтвердил срок доступа.'));
        token = response.access_token; expiry = Date.now() + seconds * 1000 - 30000; finish(null, token);
      }, error_callback: () => finish(new Error('Окно входа закрыто или заблокировано браузером. Повторите вход.')) });
    // Reuse the existing Google session instead of forcing account selection each time.
    try { client.requestAccessToken({ prompt: '' }); }
    catch { finish(new Error('Не удалось открыть окно Google. Повторите подключение.')); }
  });
}
export function accessToken() { if (!token || Date.now() >= expiry) { clearGoogle(); throw new Error('Подключитесь к Google заново.'); } return token; }
export function connected() { return (!!token && Date.now() < expiry) || (persistent && serverSession); }
export function cancelGoogleLogin() { epoch++; cancelLogin?.(); }
export function clearGoogle() { token = null; expiry = 0; cancelGoogleLogin(); }
