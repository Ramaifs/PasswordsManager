// Access token stays in memory until expiry, explicit disconnect or page reload.
export const SCOPE = 'https://www.googleapis.com/auth/drive.file';
let loading, token = null, expiry = 0, epoch = 0, cancelLogin;
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
export function connected() { return !!token && Date.now() < expiry; }
export function cancelGoogleLogin() { epoch++; cancelLogin?.(); }
export function clearGoogle() { token = null; expiry = 0; cancelGoogleLogin(); }
