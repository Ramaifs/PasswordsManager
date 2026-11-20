package com.ramaifs.passwordmanager;
import android.app.*;
import android.content.*;
import android.net.Uri;
import android.os.Bundle;
import android.security.keystore.*;
import android.util.*;
import android.view.WindowManager;
import android.webkit.*;
import org.json.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.util.concurrent.*;
import javax.crypto.*;
import javax.crypto.spec.GCMParameterSpec;

/** Offline packaged interface. Vault keys never cross the JavaScript storage bridge. */
public final class MainActivity extends Activity {
 private static final String ORIGIN="https://appassets.androidplatform.net", SERVICE="https://password-manager-vault.masaoyhs.workers.dev";
 private static final String RELEASES = "https://github.com/Ramaifs/PasswordsManager/releases";
 private WebView web; private boolean ready; private ValueCallback<Uri[]> chooser; private byte[] exporting;
 private final ExecutorService network=Executors.newSingleThreadExecutor();
 @Override public void onCreate(Bundle saved) {
  super.onCreate(saved);
  getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
  getWindow().setStatusBarColor(0xff1e1e24);getWindow().setNavigationBarColor(0xff1e1e24);
  web=new WebView(this);WebSettings settings=web.getSettings();
  settings.setJavaScriptEnabled(true);settings.setDomStorageEnabled(true);
  settings.setAllowFileAccess(false);settings.setAllowContentAccess(false);settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
  android.webkit.CookieManager.getInstance().setAcceptThirdPartyCookies(web,false);
  web.addJavascriptInterface(new Bridge(),"AndroidVault");
  web.setWebViewClient(new WebViewClient(){
   @Override public WebResourceResponse shouldInterceptRequest(WebView v,WebResourceRequest req){
    Uri u=req.getUrl();
    if(!"https".equals(u.getScheme()))return denied();
    if(!"appassets.androidplatform.net".equals(u.getHost()))return "www.googleapis.com".equals(u.getHost())?null:denied();
    String path=u.getPath();if(path==null||path.contains("..")||!"GET".equals(req.getMethod()))return denied();if(path.equals("/"))path="/index.html";
    try {
     String mime=path.endsWith(".js")?"text/javascript":path.endsWith(".css")?"text/css":path.endsWith(".svg")?"image/svg+xml":path.endsWith(".html")?"text/html":path.endsWith(".wasm")?"application/wasm":"application/octet-stream";
     WebResourceResponse result=new WebResourceResponse(mime,"UTF-8",getAssets().open("ui"+path));
     java.util.Map<String,String> h=new java.util.HashMap<>();h.put("Cache-Control","no-store");h.put("X-Content-Type-Options","nosniff");result.setResponseHeaders(h);return result;
    }catch(IOException e){return denied();}
   }
   @Override public boolean shouldOverrideUrlLoading(WebView v,WebResourceRequest r){return !r.getUrl().toString().startsWith(ORIGIN+"/");}
   @Override public void onPageFinished(WebView v,String url){ready=true;}
  });
  web.setWebChromeClient(new WebChromeClient(){
   @Override public boolean onShowFileChooser(WebView v,ValueCallback<Uri[]> callback,FileChooserParams params){
    if(chooser!=null)chooser.onReceiveValue(null);chooser=callback;
    try{startActivityForResult(new Intent(Intent.ACTION_GET_CONTENT).setType("*/*").addCategory(Intent.CATEGORY_OPENABLE),10);}
    catch(Exception e){chooser.onReceiveValue(null);chooser=null;}return true;
   }
  });
  setContentView(web);web.loadUrl(ORIGIN+"/index.html");
 }
 private WebResourceResponse denied(){return new WebResourceResponse("text/plain","UTF-8",403,"Forbidden",java.util.Collections.emptyMap(),new ByteArrayInputStream(new byte[0]));}
 private void event(String name){if(ready)web.evaluateJavascript("window.dispatchEvent(new Event("+JSONObject.quote(name)+"))",null);}
 @Override protected void onPause(){event("pm-background");super.onPause();}
 @Override protected void onResume(){super.onResume();if(web!=null)event("pm-resume");}
 @Override public void onBackPressed(){event("pm-back");}
 @Override protected void onDestroy(){network.shutdownNow();if(web!=null){web.removeJavascriptInterface("AndroidVault");web.destroy();}super.onDestroy();}
 @Override protected void onActivityResult(int req,int result,Intent data){
  super.onActivityResult(req,result,data);
  if(req==10&&chooser!=null){chooser.onReceiveValue(result==RESULT_OK&&data!=null?new Uri[]{data.getData()}:null);chooser=null;}
  if(req==11){byte[] bytes=exporting;exporting=null;if(result==RESULT_OK&&data!=null&&bytes!=null)network.execute(()->{
   try(OutputStream out=getContentResolver().openOutputStream(data.getData(),"wt")){out.write(bytes);}
   catch(Exception e){runOnUiThread(()->new AlertDialog.Builder(this).setMessage("Экспорт не записан. Локальное сохранение осталось на телефоне.").setPositiveButton("OK",null).show());}
  });}
 }
 private byte[] read(InputStream source,int limit)throws IOException{
  try(InputStream in=source;ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] b=new byte[8192];int n;while((n=in.read(b))!=-1){if(out.size()+n>limit)throw new IOException("Size limit");out.write(b,0,n);}return out.toByteArray();}
 }
 private synchronized void atomic(String name,byte[] bytes)throws IOException{
  AtomicFile file=new AtomicFile(new File(getFilesDir(),name));FileOutputStream out=null;
  try{out=file.startWrite();out.write(bytes);file.finishWrite(out);}catch(IOException e){if(out!=null)file.failWrite(out);throw e;}
 }
 private SecretKey sessionKey()throws Exception{
  KeyStore store=KeyStore.getInstance("AndroidKeyStore");store.load(null);
  if(!store.containsAlias("google-session")){KeyGenerator gen=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");gen.init(new KeyGenParameterSpec.Builder("google-session",KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());gen.generateKey();}
  return(SecretKey)store.getKey("google-session",null);
 }
 private synchronized void saveSession(String session)throws Exception{
  Cipher c=Cipher.getInstance("AES/GCM/NoPadding");c.init(Cipher.ENCRYPT_MODE,sessionKey());
  JSONObject box=new JSONObject().put("iv",Base64.encodeToString(c.getIV(),Base64.NO_WRAP)).put("data",Base64.encodeToString(c.doFinal(session.getBytes(StandardCharsets.UTF_8)),Base64.NO_WRAP));atomic("google-session.json",box.toString().getBytes(StandardCharsets.UTF_8));
 }
 private synchronized String session()throws Exception{
  File file=new File(getFilesDir(),"google-session.json");if(!file.exists())return "";
  JSONObject box=new JSONObject(new String(read(new AtomicFile(file).openRead(),8192),StandardCharsets.UTF_8));Cipher c=Cipher.getInstance("AES/GCM/NoPadding");c.init(Cipher.DECRYPT_MODE,sessionKey(),new GCMParameterSpec(128,Base64.decode(box.getString("iv"),Base64.NO_WRAP)));return new String(c.doFinal(Base64.decode(box.getString("data"),Base64.NO_WRAP)),StandardCharsets.UTF_8);
 }
 private static final class AuthFailure extends IOException {
  final String code;
  AuthFailure(String code, String message) { super(message); this.code = code; }
 }
 private AuthFailure authHttpFailure(String path, HttpURLConnection connection, int status) {
  String detail = "";
  try {
   InputStream error = connection.getErrorStream();
   if (error != null) detail = new JSONObject(new String(read(error, 8192), StandardCharsets.UTF_8)).optString("error");
  } catch (IOException | JSONException ignored) {
   // Display only the HTTP status if the server response is not a supported JSON error.
  }
  if (status == 401) {
   if ("oauth_invalid_grant".equals(detail) || "Reconnect Google to continue".equals(detail)) {
    return new AuthFailure("access_revoked", "Google отозвал доступ. Подключите Google Drive заново [TOKEN-REVOKED].");
   }
   if ("Google session expired".equals(detail)) {
    return new AuthFailure("session_expired", "Сессия Google Drive недоступна. Подключите Google Drive заново [TOKEN-401].");
   }
  }
  if ("oauth_invalid_client".equals(detail)) {
   return new AuthFailure("service_config", "Сервис Google Drive отклонил настройки входа [" + path.toUpperCase(java.util.Locale.ROOT) + "-CONFIG].");
  }
  return new AuthFailure("http_error", "Сервис подключения Google Drive вернул ошибку [" + path.toUpperCase(java.util.Locale.ROOT) + "-HTTP-" + status + "].");
 }
 private JSONObject auth(String path, String body) throws Exception {
  if (!path.equals("pair") && !path.equals("token") && !path.equals("logout")) throw new IOException("Invalid route");
  String sessionId = "";
  if (!path.equals("pair")) {
   try {
    sessionId = session();
   } catch (Exception error) {
    throw new AuthFailure("session_read", "Не удалось прочитать защищённую сессию. Подключите Google Drive заново [SESSION-READ].");
   }
  }
  HttpURLConnection connection = (HttpURLConnection) new URL(SERVICE + "/api/android/" + path).openConnection();
  try {
   connection.setConnectTimeout(15000);
   connection.setReadTimeout(25000);
   connection.setInstanceFollowRedirects(false);
   connection.setRequestMethod("POST");
   connection.setRequestProperty("Content-Type", "application/json");
   if (!sessionId.isEmpty()) connection.setRequestProperty("Authorization", "Bearer " + sessionId);
   connection.setDoOutput(true);
   try (OutputStream output = connection.getOutputStream()) {
    output.write(body.getBytes(StandardCharsets.UTF_8));
   }
   int status = connection.getResponseCode();
   if (path.equals("logout") && (status == 200 || status == 401)) {
    new AtomicFile(new File(getFilesDir(), "google-session.json")).delete();
    return new JSONObject().put("success", true);
   }
   if (status != 200) throw authHttpFailure(path, connection, status);
   JSONObject value = new JSONObject(new String(read(connection.getInputStream(), 65536), StandardCharsets.UTF_8));
   if (path.equals("pair") && value.has("session")) {
    try {
     saveSession(value.getString("session"));
    } catch (Exception error) {
     throw new AuthFailure("session_write", "Android не смог сохранить защищённую сессию Google Drive [SESSION-WRITE].");
    }
    value.remove("session");
    value.put("paired", true);
   }
   return value;
  } finally {
   connection.disconnect();
  }
 }
 private JSONObject latestRelease() throws AuthFailure {
  HttpURLConnection connection = null;
  try {
   connection = (HttpURLConnection) new URL(RELEASES + "/latest/download/manifest.json").openConnection();
   connection.setConnectTimeout(10000);
   connection.setReadTimeout(10000);
   if (connection.getResponseCode() != 200 || !"https".equals(connection.getURL().getProtocol())) throw new IOException();
   JSONObject manifest = new JSONObject(new String(read(connection.getInputStream(), 32768), StandardCharsets.UTF_8));
   String version = manifest.getString("version");
   if (!version.matches("[0-9]{1,4}\\.[0-9]{1,4}(\\.[0-9]{1,4})?")) throw new IOException();
   return new JSONObject().put("version", version);
  } catch (IOException | JSONException error) {
   throw new AuthFailure("update_check", "Не удалось проверить обновления на GitHub.");
  } finally {
   if (connection != null) connection.disconnect();
  }
 }
 private final class Bridge{
  @JavascriptInterface public synchronized String readVaults(){try{File f=new File(getFilesDir(),"vaults.json");return f.exists()?new String(read(new AtomicFile(f).openRead(),64*1024*1024),StandardCharsets.UTF_8):"[]";}catch(Exception e){return "{\"error\":\"Не удалось прочитать сохранение. Исходные данные не перезаписаны.\"}";}}
  @JavascriptInterface public synchronized String writeVaults(String encrypted){try{byte[] bytes=encrypted.getBytes(StandardCharsets.UTF_8);if(bytes.length>64*1024*1024)throw new IOException();new JSONArray(encrypted);atomic("vaults.json",bytes);return "{}";}catch(Exception e){return "{\"error\":\"Не удалось сохранить хранилище. Освободите место и повторите.\"}";}}
  @JavascriptInterface public void authRequest(String id, String path, String body) {
   if (!id.matches("[0-9a-f-]{36}") || body.length() > 4096) return;
   if (!path.equals("pair") && !path.equals("token") && !path.equals("logout") && !path.equals("release")) return;
   network.execute(() -> {
    JSONObject result = new JSONObject();
    try {
     try {
      result.put("value", path.equals("release") ? latestRelease() : auth(path, body));
     } catch (AuthFailure error) {
      result.put("error", error.getMessage()).put("code", error.code);
     } catch (Exception error) {
      String step = path.toUpperCase(java.util.Locale.ROOT);
      String kind;
      String description;
      if (error instanceof UnknownHostException) {
       kind = "DNS";
       description = "Не удалось найти сервер подключения Google Drive";
      } else if (error instanceof javax.net.ssl.SSLException) {
       kind = "TLS";
       description = "Не удалось установить защищённое соединение с сервером Google Drive";
      } else if (error instanceof SocketTimeoutException) {
       kind = "TIMEOUT";
       description = "Сервер подключения Google Drive не ответил вовремя";
      } else if (error instanceof SocketException || error instanceof EOFException) {
       kind = "SOCKET";
       description = "Соединение с сервером подключения Google Drive оборвалось";
      } else if (error instanceof JSONException) {
       kind = "RESPONSE";
       description = "Сервис подключения Google Drive прислал некорректный ответ";
      } else {
       kind = "NETWORK";
       description = "Не удалось подключиться к серверу Google Drive";
      }
      result.put("error", description + " [" + step + "-" + kind + "].");
      if (kind.equals("DNS")) result.put("code", "transport_dns");
      else if (kind.equals("TIMEOUT") || kind.equals("SOCKET")) result.put("code", "transport_retry");
     }
    } catch (JSONException ignored) {
     return;
    }
    String script = "window.pmAuthResult(" + JSONObject.quote(id) + "," + result + ")";
    runOnUiThread(() -> { if (!isFinishing() && !isDestroyed()) web.evaluateJavascript(script, null); });
   });
  }
  @JavascriptInterface public boolean hasSession(){return new File(getFilesDir(),"google-session.json").exists();}
  @JavascriptInterface public void openReleases() {
   runOnUiThread(() -> {
    try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(RELEASES))); }
    catch (ActivityNotFoundException error) { new AlertDialog.Builder(MainActivity.this).setMessage("Для просмотра версий нужен браузер.").setPositiveButton("OK", null).show(); }
   });
  }
  @JavascriptInterface public void connect(String state,String challenge){if(!state.matches("[A-Za-z0-9_-]{43}")||!challenge.matches("[A-Za-z0-9_-]{43}"))return;runOnUiThread(()->{try{startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse(SERVICE+"/api/android/connect?state="+state+"&challenge="+challenge)));}catch(Exception e){new AlertDialog.Builder(MainActivity.this).setMessage("Для подключения Google нужен системный браузер.").setPositiveButton("OK",null).show();}});}
  @JavascriptInterface public void exportFile(String encoded,String name){if(encoded.length()>24*1024*1024)return;byte[] bytes=Base64.decode(encoded,Base64.DEFAULT);runOnUiThread(()->{if(exporting!=null)return;exporting=bytes;startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("application/octet-stream").addCategory(Intent.CATEGORY_OPENABLE).putExtra(Intent.EXTRA_TITLE,name.replaceAll("[/\\\\]","_")),11);});}
  @JavascriptInterface public void copyText(String text){((ClipboardManager)getSystemService(CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("Password Manager",text));}
  @JavascriptInterface public String readClipboard(){ClipboardManager cb=(ClipboardManager)getSystemService(CLIPBOARD_SERVICE);return cb.hasPrimaryClip()?cb.getPrimaryClip().getItemAt(0).coerceToText(MainActivity.this).toString():"";}
  @JavascriptInterface public void clearClipboard(String expected){if(readClipboard().equals(expected))copyText("");}
  @JavascriptInterface public void uninstall(){runOnUiThread(()->startActivity(new Intent(Intent.ACTION_DELETE,Uri.parse("package:"+getPackageName()))));}
  @JavascriptInterface public void closeApp(){runOnUiThread(()->finish());}
 }
}
