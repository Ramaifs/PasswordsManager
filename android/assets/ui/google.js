// OAuth consent runs in the system browser. The bearer session stays in Android Keystore.
export const SCOPE='https://www.googleapis.com/auth/drive.file';
let token=null, expiry=0, epoch=0, paired=AndroidVault.hasSession(), renewing;
const pending=new Map();
window.pmAuthResult=(id,result)=>{const call=pending.get(id);if(!call)return;pending.delete(id);clearTimeout(call.timer);result.error?call.reject(new Error(result.error)):call.resolve(result.value);};
function call(path,body={}) {
 return new Promise((resolve,reject)=>{const id=crypto.randomUUID();const timer=setTimeout(()=>{pending.delete(id);reject(new Error('Google не отвечает. Повторите подключение.'));},45000);pending.set(id,{resolve,reject,timer});AndroidVault.authRequest(id,path,JSON.stringify(body));});
}
function accept(value){if(typeof value.access_token!=='string'||!Number.isFinite(Number(value.expires_in)))throw new Error('Google не подтвердил доступ.');token=value.access_token;expiry=Date.now()+Number(value.expires_in)*1000-30000;paired=true;return token;}
export async function initializeGoogleSession(){return connected();}
export const persistentSessionEnabled=()=>true;
export const redirectPreferred=()=>false;
export const validClientId=value=>typeof value==='string'&&value.endsWith('.apps.googleusercontent.com');
export const loadGoogle=async()=>{};
export async function ensureAccessToken(){
 if(token&&Date.now()<expiry)return token;
 if(!paired)throw new Error('Подключите Google Drive.');
 if(!renewing){const generation=epoch;renewing=call('token').then(value=>{if(epoch!==generation)throw new Error('Обмен остановлен.');return accept(value);}).finally(()=>{renewing=null;});}
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
 while(Date.now()<deadline&&epoch===generation){
  await new Promise(resolve=>setTimeout(resolve,1500));
  const result=await call('pair',{state,verifier});
  if(epoch!==generation)throw new Error('Вход отменён.');
  if(result.paired){paired=true;return ensureAccessToken();}
 }
 throw new Error('Вход Google не завершён. Повторите подключение.');
}
export const authorizeRedirect=authorize;
