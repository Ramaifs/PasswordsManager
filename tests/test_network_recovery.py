import pytest
from password_manager import updates, oauth
from password_manager.crypto import canonical
from password_manager.errors import VaultError
from password_manager.http_client import HttpError


def test_update_check_and_version_picker_survive_github_api_rate_limit(monkeypatch):
    manifest = canonical({"version": "0.41", "files": {
        "PasswordsManager.exe": {"bytes": 100, "sha256": "a" * 64}}})
    calls = []
    def limited(*args, **kwargs):
        raise HttpError(403)
    def asset(url, **kwargs):
        calls.append(url)
        yield manifest
    monkeypatch.setattr(updates, "github_asset", asset)
    assert updates.latest_release(current="0.40", fetch=limited)["version"] == "0.41"
    assert updates.release_versions(fetch=limited) == [{"version": "0.41", "tag": "v0.41"}]
    assert all(url == "https://github.com/Ramaifs/PasswordsManager/releases/latest/download/manifest.json" for url in calls)


def test_update_fallback_rejects_invalid_installer_metadata(monkeypatch):
    monkeypatch.setattr(updates, "github_asset", lambda *a, **k: iter([canonical({
        "version": "../bad", "files": {"PasswordsManager.exe": {"bytes": 1, "sha256": "a"*64}}
    })]))
    with pytest.raises(VaultError):
        updates.latest_release(fetch=lambda *a, **k: (_ for _ in ()).throw(HttpError(403)))


def test_expired_google_grant_requires_reconnect_without_deleting_connection():
    class Connection:
        saved = False
        def load(self):
            return {"expires_at": 0, "client_id": "fixture", "client_secret": "fixture", "refresh_token": "fixture"}
        def save(self, value):
            self.saved = True
    connection = Connection()
    with pytest.raises(VaultError, match="Подключите Google заново"):
        oauth.bearer(connection, request=lambda *a, **k: (_ for _ in ()).throw(HttpError(400)))
    assert not connection.saved
