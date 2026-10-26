"""Drive v3 immutable objects. Object ID binding excludes user-created copies."""
import hashlib
import re
import uuid
import urllib.parse

from . import http_client
from .crypto import canonical, parse
from .oauth import bearer
from .sync import SyncError, MAX_CLOUD, MAX_VERSIONS

API = "https://www.googleapis.com/drive/v3/files"
UPLOAD = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
APP = "personal-password-manager-v1"
FOLDER_MIME = "application/vnd.google-apps.folder"


class FolderMissing(SyncError):
    def __init__(self):
        super().__init__("Папка приложения удалена или недоступна. Локальные данные сохранены. Для повторной загрузки подтвердите создание папки в настройках Google.")


def file_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", value):
        raise SyncError("Google вернул некорректные метаданные файла.")
    return value


class DriveTransport:
    def __init__(self, connection, cancel, *, request=http_client.request):
        self.connection, self.cancel, self.request = connection, cancel, request
        self.objects = {}

    def _call(self, method, url, *, body=None, headers=None, json=True, limit=5 * 1024 * 1024):
        if self.cancel.is_set():
            raise SyncError("Синхронизация приостановлена.")
        for attempt in range(2):
            token = bearer(self.connection)
            try:
                result = self.request(method, url, headers={**(headers or {}), "Authorization": f"Bearer {token}"},
                                      body=body, limit=limit, cancel=self.cancel)
                break
            except http_client.HttpError as error:
                if error.status != 401 or attempt:
                    raise
                value = self.connection.load()
                value["expires_at"] = 0
                self.connection.save(value)
        if self.cancel.is_set():
            raise SyncError("Синхронизация приостановлена.")
        if not json:
            return result
        value = parse(result)
        if not isinstance(value, dict):
            raise SyncError("Некорректный ответ Google Drive.")
        return value

    def _list(self, query):
        page, files = None, []
        tokens = set()
        for _ in range(100):
            params = {"q": query, "pageSize": "1000", "fields": "nextPageToken,incompleteSearch,files(id,name,mimeType,appProperties,size,md5Checksum,parents)"}
            if page: params["pageToken"] = page
            result = self._call("GET", API + "?" + urllib.parse.urlencode(params), limit=2 * 1024 * 1024)
            if result.get("incompleteSearch") or not isinstance(result.get("files"), list):
                raise SyncError("Google не подтвердил полное чтение списка версий.")
            files.extend(result["files"])
            if len(files) > MAX_VERSIONS * 2:
                raise SyncError("Облачная история слишком велика для безопасной обработки.")
            page = result.get("nextPageToken")
            if not page: return files
            if not isinstance(page, str) or page in tokens:
                raise SyncError("Некорректное продолжение списка Google Drive.")
            tokens.add(page)
        raise SyncError("Список Google Drive не был прочитан полностью.")

    def _generate_id(self):
        result = self._call("GET", API + "/generateIds?count=1&space=drive&type=files")
        ids = result.get("ids")
        if not isinstance(ids, list) or len(ids) != 1:
            raise SyncError("Google не выдал идентификатор файла.")
        return file_id(ids[0])

    def folders(self, *, recreate=False):
        query = f"trashed = false and mimeType = '{FOLDER_MIME}' and appProperties has {{ key='pm_app' and value='{APP}' }}"
        found = self._list(query)
        ids = sorted(file_id(f["id"]) for f in found if self._owned(f) and f.get("mimeType") == FOLDER_MIME)
        value = self.connection.load()
        pinned = value.get("folder")
        if pinned and pinned not in ids and not recreate:
            raise FolderMissing()
        if not ids:
            identity = self._generate_id()
            metadata = {"id": identity, "name": "Менеджер паролей", "mimeType": FOLDER_MIME,
                        "appProperties": {"pm_app": APP, "pm_object": identity}}
            result = self._call("POST", API + "?fields=id", body=canonical(metadata), headers={"Content-Type": "application/json"})
            if result.get("id") != identity:
                raise SyncError("Google не подтвердил создание папки.")
            ids = [identity]
        if value.get("folder") != ids[0]:
            value["folder"] = ids[0]
            self.connection.save(value)
        return ids

    @staticmethod
    def _owned(metadata):
        props = metadata.get("appProperties", {})
        return isinstance(props, dict) and props.get("pm_app") == APP and props.get("pm_object") == metadata.get("id")

    def fetch(self):
        folders = self.folders()
        remote, objects = {}, {}
        total = 0
        for folder in folders:
            query = f"trashed = false and '{folder}' in parents and appProperties has {{ key='pm_app' and value='{APP}' }}"
            for metadata in self._list(query):
                if not self._owned(metadata):
                    continue
                version = metadata["appProperties"].get("pm_version")
                if not isinstance(version, str): continue
                try:
                    if str(uuid.UUID(version)) != version: raise ValueError()
                except ValueError:
                    raise SyncError("Некорректная версия в папке приложения.") from None
                if metadata.get("name") != f"version-{version}.pmvault":
                    continue
                identity = file_id(metadata["id"])
                try:
                    size = int(metadata.get("size", -1))
                except (ValueError, TypeError):
                    size = -1
                if not 0 < size <= MAX_CLOUD:
                    raise SyncError("Недопустимый размер облачной версии.")
                total += size
                if total > 64 * 1024 * 1024 or len(remote) >= MAX_VERSIONS:
                    raise SyncError("Облачная история превышает безопасный предел загрузки.")
                blob = self._call("GET", API + f"/{identity}?alt=media", json=False, limit=MAX_CLOUD)
                if len(blob) != size or (metadata.get("md5Checksum") and hashlib.md5(blob).hexdigest() != metadata["md5Checksum"]):
                    raise SyncError("Google не подтвердил целостность передачи файла.")
                if version in remote and remote[version] != blob:
                    raise SyncError("Обнаружены разные файлы с одним идентификатором версии.")
                remote[version] = blob
                objects.setdefault(version, []).append(identity)
        self.objects = objects
        return remote

    def publish(self, version, blob):
        if str(uuid.UUID(version)) != version or not 0 < len(blob) <= MAX_CLOUD:
            raise SyncError("Некорректная публикация.")
        existing = self.fetch()
        if version in existing:
            if existing[version] != blob:
                raise SyncError("Облачная версия не совпадает с очередью.")
            return existing[version]
        identity = self._generate_id()
        folder = self.connection.load()["folder"]
        metadata = {"id": identity, "name": f"version-{version}.pmvault", "parents": [folder],
                    "mimeType": "application/octet-stream", "appProperties": {"pm_app": APP, "pm_object": identity, "pm_version": version}}
        boundary = "pm_" + uuid.uuid4().hex
        body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode() + canonical(metadata)
                + f"\r\n--{boundary}\r\nContent-Type: application/octet-stream\r\n\r\n".encode() + blob + f"\r\n--{boundary}--\r\n".encode())
        result = self._call("POST", UPLOAD + "&fields=id", body=body, headers={"Content-Type": f"multipart/related; boundary={boundary}"})
        if result.get("id") != identity:
            raise SyncError("Публикация не подтверждена Google Drive.")
        # A create response alone does not acknowledge bytes; read them back.
        confirmed = self._call("GET", API + f"/{identity}?alt=media", json=False, limit=MAX_CLOUD)
        if confirmed != blob:
            raise SyncError("Опубликованные данные не совпадают с локальной очередью.")
        return confirmed

    def delete(self, version):
        # Only IDs from the complete validated owned-object listing can be removed.
        for identity in self.objects.get(version, []):
            try:
                self._call("DELETE", API + "/" + file_id(identity), json=False)
            except http_client.HttpError as error:
                if error.status != 404:
                    raise

    def delete_cloud(self):
        # Explicit user action; remove only owned version objects, never whole folders/manual copies.
        remote = self.fetch()
        for version in remote: self.delete(version)
