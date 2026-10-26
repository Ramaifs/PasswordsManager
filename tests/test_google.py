import base64
import hashlib
import os
from threading import Event
import time
import urllib.parse
import uuid

import pytest

from password_manager.crypto import canonical
from password_manager.drive import DriveTransport, APP, FOLDER_MIME, FolderMissing
from password_manager.errors import VaultError
from password_manager.oauth import verifier_pair, exchange_code, config, SCOPE, AUTH, TOKEN
from password_manager.protected import ProtectedConnection
from password_manager.sync import SyncError


class Connection:
    def __init__(self):
        self.value = {"access_token": "FICTIONAL-ACCESS-TOKEN", "expires_at": time.time() + 10000, "folder": "folderA"}
    def load(self): return dict(self.value)
    def save(self, value): self.value = dict(value)


class FakeAPI:
    def __init__(self):
        self.calls = []
        self.data = {}
        self.manual = b"USER-COPY"
        self.folder_exists = True
        self.next = 0
    def metadata(self, identity, version, blob):
        return {"id": identity, "name": f"version-{version}.pmvault", "size": str(len(blob)),
                "appProperties": {"pm_app": APP, "pm_object": identity, "pm_version": version},
                "md5Checksum": hashlib.md5(blob).hexdigest()}
    def __call__(self, method, url, *, headers, body, limit, cancel):
        self.calls.append((method, url))
        assert headers["Authorization"] == "Bearer FICTIONAL-ACCESS-TOKEN"
        parsed = urllib.parse.urlsplit(url)
        query = urllib.parse.parse_qs(parsed.query)
        if "generateIds" in parsed.path:
            self.next += 1
            return canonical({"ids": [f"generated{self.next}"]})
        if method == "GET" and "q" in query:
            if "mimeType" in query["q"][0]:
                folders = [{"id": "folderA", "mimeType": FOLDER_MIME,
                    "appProperties": {"pm_app": APP, "pm_object": "folderA"}}] if self.folder_exists else []
                return canonical({"files": folders})
            files = [self.metadata(identity, version, blob) for identity, (version, blob) in self.data.items()]
            # A user's copied file preserves metadata but gets a new object ID: do not ingest/delete it.
            manual = self.metadata("originalObject", str(uuid.UUID(int=1)), self.manual)
            manual["id"] = "manualCopy"
            return canonical({"files": [*files, manual]})
        if method == "POST" and "uploadType" in query:
            import json
            boundary = headers["Content-Type"].split("boundary=")[1].encode()
            pieces = body.split(b"--" + boundary)
            metadata = json.loads(pieces[1].split(b"\r\n\r\n", 1)[1].rstrip(b"\r\n"))
            blob = pieces[2].split(b"\r\n\r\n", 1)[1][:-2]
            self.data[metadata["id"]] = (metadata["appProperties"]["pm_version"], blob)
            return canonical({"id": metadata["id"]})
        identity = parsed.path.rsplit("/", 1)[-1]
        if method == "GET" and query.get("alt") == ["media"]:
            return self.data[identity][1]
        if method == "DELETE":
            assert identity != "manualCopy"
            self.data.pop(identity, None)
            return b""
        raise AssertionError("Unexpected fake API call")


def test_drive_upload_readback_retry_and_safe_delete():
    api = FakeAPI()
    drive = DriveTransport(Connection(), Event(), request=api)
    version = str(uuid.uuid4())
    blob = b"FICTIONAL-ENCRYPTED-BYTES"
    assert drive.publish(version, blob) == blob
    assert drive.publish(version, blob) == blob
    assert len(api.data) == 1
    assert drive.fetch() == {version: blob}
    drive.delete(version)
    assert not api.data and api.manual == b"USER-COPY"


def test_deleted_folder_never_silently_recreated():
    api = FakeAPI()
    api.folder_exists = False
    drive = DriveTransport(Connection(), Event(), request=api)
    with pytest.raises(FolderMissing): drive.fetch()
    assert all(method == "GET" for method, _ in api.calls)


def test_incomplete_listing_stops_processing():
    connection = Connection()
    def fake(*args, **kwargs): return canonical({"files": [], "incompleteSearch": True})
    with pytest.raises(SyncError): DriveTransport(connection, Event(), request=fake).fetch()


def test_cancel_prevents_api_calls():
    cancel = Event()
    cancel.set()
    api = FakeAPI()
    with pytest.raises(SyncError): DriveTransport(Connection(), cancel, request=api).fetch()
    assert not api.calls


def test_pkce_and_code_exchange_without_live_google():
    verifier, challenge = verifier_pair()
    assert len(verifier) >= 43
    assert challenge == base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    def fake(method, url, **kwargs):
        params = urllib.parse.parse_qs(kwargs["body"].decode())
        assert url == TOKEN and params["code_verifier"] == [verifier]
        assert params["redirect_uri"] == ["http://127.0.0.1:12345/callback"]
        return {"access_token": "FICTIONAL-ACCESS", "refresh_token": "FICTIONAL-REFRESH", "scope": SCOPE}
    value = exchange_code({"client_id": "test.apps.googleusercontent.com", "client_secret": "FICTIONAL-CLIENT"},
                          "FICTIONAL-CODE", verifier, "http://127.0.0.1:12345/callback", request=fake)
    assert value["refresh_token"] == "FICTIONAL-REFRESH"


def test_oauth_config_rejects_foreign_endpoint(tmp_path):
    source = tmp_path / "client.json"
    source.write_bytes(canonical({"installed": {"client_id": "test.apps.googleusercontent.com", "client_secret": "fake", "auth_uri": "https://evil.invalid/", "token_uri": TOKEN}}))
    with pytest.raises(VaultError): config(source)
    source.write_bytes(canonical({"installed": {"client_id": "test.apps.googleusercontent.com", "client_secret": "fake", "auth_uri": AUTH, "token_uri": TOKEN}}))
    assert config(source)["client_id"] == "test.apps.googleusercontent.com"
    # Match real Desktop JSON exported by Google, without trusting its URL for I/O.
    source.write_bytes(canonical({"installed": {"client_id": "test.apps.googleusercontent.com", "client_secret": "fake", "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": TOKEN}}))
    assert config(source)["client_id"] == "test.apps.googleusercontent.com"
    source.write_bytes(canonical({"installed": {"client_id": "test.apps.googleusercontent.com", "client_secret": "fake", "auth_uri": "https://accounts.google.com.evil.invalid/o/oauth2/auth", "token_uri": TOKEN}}))
    with pytest.raises(VaultError): config(source)


@pytest.mark.skipif(os.name != "nt", reason="Windows DPAPI only")
def test_actual_windows_dpapi_protection_and_disconnect(tmp_path):
    connection = ProtectedConnection(tmp_path)
    secret = {"refresh_token": "FICTIONAL-UNIQUE-TOKEN-MARKER", "folder": "fixture"}
    connection.save(secret)
    assert b"FICTIONAL-UNIQUE-TOKEN-MARKER" not in connection.path.read_bytes()
    assert connection.load() == secret
    connection.disconnect()
    assert not connection.exists
