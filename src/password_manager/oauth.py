"""Desktop OAuth: system browser, PKCE-S256, state, loopback-only callback."""
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import secrets
import time
import urllib.parse
import webbrowser

from .crypto import canonical, parse
from .errors import VaultError
from .http_client import json_request
from .storage import read_bounded

SCOPE = "https://www.googleapis.com/auth/drive.file"
AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
# Google-generated Desktop JSON still uses this official legacy discovery URL.
# Actual authorization always uses AUTH above, never a URL supplied by the file.
CONFIG_AUTH_URIS = {AUTH, "https://accounts.google.com/o/oauth2/auth"}
TOKEN = "https://oauth2.googleapis.com/token"


def config(path):
    try:
        value = parse(read_bounded(path, 65536))["installed"]
        client_id, client_secret = value["client_id"], value["client_secret"]
        if not isinstance(client_id, str) or not client_id.endswith(".apps.googleusercontent.com") or not isinstance(client_secret, str) or not client_secret or len(client_secret) > 1024:
            raise ValueError()
        if value.get("auth_uri") not in CONFIG_AUTH_URIS or value.get("token_uri") != TOKEN:
            raise ValueError()
        return {"client_id": client_id, "client_secret": client_secret}
    except (KeyError, TypeError, ValueError):
        raise VaultError("Нужен JSON OAuth-клиента Google типа Desktop app с официальными адресами Google.") from None


def verifier_pair():
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode().rstrip("=")
    return verifier, challenge


def exchange_code(client, code, verifier, redirect, *, request=json_request):
    payload = {**client, "code": code, "code_verifier": verifier, "redirect_uri": redirect, "grant_type": "authorization_code"}
    token = request("POST", TOKEN, headers={"Content-Type": "application/x-www-form-urlencoded"},
                    body=urllib.parse.urlencode(payload).encode(), limit=65536)
    validate_token(token)
    if not token.get("refresh_token"):
        raise VaultError("Google не выдал токен для автономного доступа. Повторите подключение.")
    return {**client, "refresh_token": token["refresh_token"], "access_token": token["access_token"],
            "expires_at": time.time() + int(token.get("expires_in", 3600)) - 60, "folder": None}


def validate_token(token):
    if not isinstance(token.get("access_token"), str) or not token["access_token"] or token.get("token_type", "Bearer").lower() != "bearer":
        raise VaultError("Google не подтвердил подключение.")
    if "scope" in token and SCOPE not in token["scope"].split():
        raise VaultError("Не предоставлен доступ к файлам приложения Google Drive.")


def authorize(client, cancel, *, browser=webbrowser.open, request=json_request):
    verifier, challenge = verifier_pair()
    state = secrets.token_urlsafe(32)
    result = {}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            parsed = urllib.parse.urlsplit(self.path)
            params = urllib.parse.parse_qs(parsed.query, strict_parsing=False)
            valid = (parsed.path == "/callback" and params.get("state") == [state]
                     and self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}")
            if not valid:
                self.send_response(400)
                self.end_headers()
                return
            if len(params.get("code", [])) == 1 and not params.get("error"):
                result["code"] = params["code"][0]
            else:
                result["denied"] = True
            message = "Можно закрыть эту вкладку и вернуться в приложение.".encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(message)))
            self.end_headers()
            self.wfile.write(message)
    class LocalServer(HTTPServer):
        def get_request(self):
            sock, address = super().get_request()
            sock.settimeout(1)
            return sock, address
    with LocalServer(("127.0.0.1", 0), Handler) as server:
        server.timeout = 0.3
        redirect = f"http://127.0.0.1:{server.server_port}/callback"
        url = AUTH + "?" + urllib.parse.urlencode({"client_id": client["client_id"], "redirect_uri": redirect,
            "response_type": "code", "scope": SCOPE, "state": state, "code_challenge": challenge,
            "code_challenge_method": "S256", "access_type": "offline", "prompt": "consent"})
        if not browser(url):
            raise VaultError("Не удалось открыть системный браузер.")
        deadline = time.monotonic() + 180
        while not result and not cancel.is_set() and time.monotonic() < deadline:
            server.handle_request()
    if cancel.is_set() or not result.get("code"):
        raise VaultError("Подключение Google отменено или время ожидания истекло.")
    return exchange_code(client, result["code"], verifier, redirect, request=request)


def bearer(connection, *, request=json_request):
    value = connection.load()
    if value.get("expires_at", 0) <= time.time():
        payload = {"client_id": value["client_id"], "client_secret": value["client_secret"],
                   "refresh_token": value["refresh_token"], "grant_type": "refresh_token"}
        token = request("POST", TOKEN, headers={"Content-Type": "application/x-www-form-urlencoded"},
                        body=urllib.parse.urlencode(payload).encode(), limit=65536)
        validate_token(token)
        value["access_token"] = token["access_token"]
        value["expires_at"] = time.time() + int(token.get("expires_in", 3600)) - 60
        connection.save(value)
    return value["access_token"]
