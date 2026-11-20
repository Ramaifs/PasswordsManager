// OAuth consent runs in the system browser. The bearer session stays in Android Keystore.
export const SCOPE='https://www.googleapis.com/auth/drive.file';
let token=null, expiry=0, epoch=0, paired=AndroidVault.hasSession(), renewing;
const pending=new Map();
window.pmAuthResult = (id, result) => {
 const request = pending.get(id);
 if (!request) return;
 pending.delete(id);
 clearTimeout(request.timer);
 if (result.error) request.reject(Object.assign(new Error(result.error), {code: result.code}));
 else request.resolve(result.value);
};
function call(path, body = {}) {
 return new Promise((resolve, reject) => {
  const id = crypto.randomUUID();
  const timer = setTimeout(() => {
   pending.delete(id);
   reject(new Error('Нет ответа от сервиса подключения Google Drive (' + path + ').'));
  }, 45000);
  pending.set(id, {resolve, reject, timer});
  try {
   AndroidVault.authRequest(id, path, JSON.stringify(body));
  } catch (error) {
   pending.delete(id);
   clearTimeout(timer);
   reject(error);
  }
 });
}
function accept(value) {
 const seconds = Number(value.expires_in);
 if (typeof value.access_token !== 'string' || !value.access_token || !Number.isFinite(seconds) || seconds <= 0) {
  throw new Error('Google не подтвердил доступ.');
 }
 token = value.access_token;
 expiry = Date.now() + seconds * 1000 - Math.min(30000, seconds * 500);
 paired = true;
 return token;
}
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
async function requestAccess(generation, waitForNewSession = false) {
 const deadline = waitForNewSession ? Date.now() + 75000 : 0;
 let delay = 1500;
 while (generation === epoch) {
  try {
   const result = await call('token');
   if (generation !== epoch) break;
   return accept(result);
  } catch (error) {
   if (generation !== epoch) break;
   if (error.code === 'session_expired' && Date.now() + delay < deadline) {
    await wait(delay);
    delay = Math.min(delay * 2, 10000);
    continue;
   }
   if (['session_expired', 'access_revoked', 'session_read'].includes(error.code)) {
    paired = false;
    token = null;
    expiry = 0;
   }
   throw error;
  }
 }
 throw new Error('Обмен остановлен.');
}
export async function initializeGoogleSession(){return connected();}
export const persistentSessionEnabled=()=>true;
export const redirectPreferred=()=>false;
export const validClientId=value=>typeof value==='string'&&value.endsWith('.apps.googleusercontent.com');
export const loadGoogle=async()=>{};
export async function ensureAccessToken(){
 if(token&&Date.now()<expiry)return token;
 if(!paired)throw new Error('Подключите Google Drive.');
 if (!renewing) renewing = requestAccess(epoch).finally(() => { renewing = null; });
 return renewing;
}
export function accessToken(){if(!token||Date.now()>=expiry)throw new Error('Обновите подключение Google Drive.');return token;}
export const connected=()=>paired;
export function clearGoogle(){token=null;expiry=0;cancelGoogleLogin();}
export function cancelGoogleLogin(){epoch++;}
export async function disconnectGoogle(){clearGoogle();paired=false;await call('logout');}
export async function authorize(){
 const generation=++epoch;
 const bytes=()=>crypto.getRandomValues(new Uint8Array(32));
 const url64=b=>btoa(String.fromCharCode(...b)).replaceAll('+','-').replaceAll('/','_').replaceAll('=','');
 const state=url64(bytes()), verifier=url64(bytes());
 const challenge=url64(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(verifier))));
 AndroidVault.connect(state,challenge);
 const deadline=Date.now()+180000;
 let consecutiveNetworkErrors = 0;
 while(Date.now()<deadline&&epoch===generation){
  await wait(1500);
  if (epoch !== generation) break;
  let result;
  try {
   result = await call('pair', {state, verifier});
   consecutiveNetworkErrors = 0;
  } catch (error) {
   if (epoch !== generation) break;
   if (!['transport_retry', 'transport_dns'].includes(error.code) || ++consecutiveNetworkErrors >= 3 || Date.now() >= deadline) throw error;
   await wait(1000 * consecutiveNetworkErrors);
   continue;
  }
  if(epoch!==generation)throw new Error('Вход отменён.');
  if (result.paired) {
   token = null;
   expiry = 0;
   paired = true;
   return requestAccess(generation, true);
  }
 }
 throw new Error('Вход Google не завершён. Повторите подключение.');
}
export const authorizeRedirect=authorize;
export const latestAndroidRelease = () => call('release');
