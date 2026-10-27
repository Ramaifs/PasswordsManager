"""Explicit release selection and bounded, hash-verified GitHub downloads."""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request
import urllib.error
from urllib.parse import urlsplit
import uuid
from threading import Event
from PySide6.QtCore import QObject, QTimer, QThread, Signal
from PySide6.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton, QProgressBar
from . import __version__
from .crypto import parse
from .http_client import request, HttpError
from .errors import VaultError
from .sync_ui import IOThread

REPOSITORY = "Ramaifs/PasswordsManager"
API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
RELEASES_API = f"https://api.github.com/repos/{REPOSITORY}/releases?per_page=100"
MAX_INSTALLER = 512 * 1024 * 1024


def release_versions(*, cancel=None, fetch=request):
    try:
        releases = parse(fetch("GET", RELEASES_API, headers={"Accept": "application/vnd.github+json", "User-Agent": "PasswordsManager/" + __version__}, limit=4 * 1024 * 1024, cancel=cancel))
    except HttpError:
        raise VaultError("Не удалось получить список версий с GitHub.") from None
    if not isinstance(releases, list):
        raise VaultError("GitHub вернул некорректный список версий.")
    result = []
    for release in releases:
        if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
            continue
        tag = release.get("tag_name")
        try:
            version_tuple(tag)
        except VaultError:
            continue
        assets = release.get("assets", [])
        if not isinstance(assets, list):
            continue
        if {"PasswordsManager.exe", "manifest.json"} <= {a.get("name") for a in assets if isinstance(a, dict)}:
            result.append({"version": tag.removeprefix("v"), "tag": tag})
    return sorted(result, key=lambda item: version_tuple(item["version"]), reverse=True)


def github_asset(url, *, cancel, limit):
    """Yield bounded chunks; follow only HTTPS GitHub release asset redirects."""
    class Redirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            host = urlsplit(newurl)
            if host.scheme != "https" or host.hostname not in ("github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com") or host.username or host.password or host.port not in (None, 443):
                raise VaultError("GitHub перенаправил загрузку на неизвестный сервер.")
            return super().redirect_request(req, fp, code, msg, headers, newurl)
    try:
        request_ = urllib.request.Request(url, headers={"User-Agent": "PasswordsManager/" + __version__})
        with urllib.request.build_opener(Redirect).open(request_, timeout=30) as response:
            size = 0
            while True:
                if cancel.is_set():
                    raise VaultError("Загрузка отменена.")
                chunk = response.read(min(256 * 1024, limit + 1 - size))
                if not chunk:
                    break
                size += len(chunk)
                if size > limit:
                    raise VaultError("Файл обновления превышает допустимый размер.")
                yield chunk
    except (OSError, ValueError, urllib.error.URLError):
        raise VaultError("Не удалось скачать обновление с GitHub. Повторите загрузку.") from None


def download_release(release, root, *, cancel, progress=lambda done, total: None, stream=github_asset):
    tag = release["tag"]
    version_tuple(tag)
    base = f"https://github.com/{REPOSITORY}/releases/download/{tag}/"
    manifest = parse(b"".join(stream(base + "manifest.json", cancel=cancel, limit=256 * 1024)))
    try:
        asset = manifest["files"]["PasswordsManager.exe"]
        expected, size = asset["sha256"], asset["bytes"]
        if manifest["version"] != tag.removeprefix("v") or not isinstance(expected, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected) or type(size) is not int or not 1 <= size <= MAX_INSTALLER:
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise VaultError("В релизе нет корректного манифеста установщика.") from None
    directory = Path(root) / "updates"
    directory.mkdir(parents=True, exist_ok=True)
    temporary = directory / ("download-" + uuid.uuid4().hex + ".partial")
    target = directory / ("PasswordsManager-" + tag.removeprefix("v") + ".exe")
    digest, done = hashlib.sha256(), 0
    try:
        with temporary.open("xb") as output:
            for chunk in stream(base + "PasswordsManager.exe", cancel=cancel, limit=size):
                if cancel.is_set():
                    raise VaultError("Загрузка отменена.")
                done += len(chunk)
                if done > size:
                    raise VaultError("Неверный размер установщика.")
                digest.update(chunk)
                output.write(chunk)
                progress(done, size)
            output.flush()
            os.fsync(output.fileno())
        if done != size or digest.hexdigest() != expected.lower() or cancel.is_set():
            raise VaultError("Проверка SHA-256 обновления не пройдена или загрузка отменена.")
        os.replace(temporary, target)
        return {"path": target, "sha256": expected.lower(), "version": tag.removeprefix("v")}
    finally:
        temporary.unlink(missing_ok=True)


class DownloadThread(QThread):
    result = Signal(object)
    progress = Signal(int)

    def __init__(self, release, root, cancel, parent):
        super().__init__(parent)
        self.release, self.root, self.cancel = release, root, cancel

    def run(self):
        try:
            value = download_release(self.release, self.root, cancel=self.cancel, progress=lambda done, total: self.progress.emit(done * 100 // total))
        except Exception as error:
            value = error if isinstance(error, VaultError) else VaultError("Не удалось сохранить обновление. Проверьте свободное место и доступ к папке.")
        self.result.emit(value)


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r"v?\d{1,5}\.\d{1,5}(?:\.\d{1,5})?", value):
        raise VaultError("GitHub вернул неподдерживаемый номер версии.")
    parts = tuple(int(part) for part in value.removeprefix('v').split('.'))
    return parts + (0,) if len(parts) == 2 else parts


def latest_release(*, current=__version__, cancel=None, fetch=request):
    try:
        data = fetch("GET", API, headers={"Accept": "application/vnd.github+json", "User-Agent": "PasswordsManager/" + current}, limit=256 * 1024, cancel=cancel)
    except HttpError as error:
        if error.status == 404:
            return {"available": False, "unpublished": True}
        raise VaultError("Не удалось проверить обновления. Проверьте подключение к интернету.") from None
    release = parse(data)
    if not isinstance(release, dict) or release.get('draft') or release.get('prerelease'):
        raise VaultError("Не удалось проверить стабильную версию приложения.")
    tag = release.get('tag_name')
    available = version_tuple(tag) > version_tuple(current)
    return {"available": available, "version": tag.removeprefix('v'), "url": f"https://github.com/{REPOSITORY}/releases/tag/{tag}"}


class UpdateChecker(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window, self.worker, self.cancel = window, None, Event()
        self.scheduled = False
        self.dialog = None
        self.downloaded = None

    @property
    def busy(self):
        return self.worker is not None

    def schedule(self):
        if not self.scheduled and self.window.session.document['settings'].get('check_updates', True):
            self.scheduled = True
            QTimer.singleShot(3000, lambda: self.check() if self.window.session.unlocked and self.window.session.document['settings'].get('check_updates', True) else None)

    def check(self, manual=False):
        if self.busy:
            return
        self.cancel = Event()
        worker = IOThread(lambda: release_versions(cancel=self.cancel) if manual else latest_release(cancel=self.cancel), self.cancel, self)
        self.worker = worker
        results = []
        worker.result.connect(results.append)
        def finished():
            self.worker = None
            worker.deleteLater()
            if self.cancel.is_set():
                return
            result = results[0] if results else VaultError("Проверка обновлений прервана.")
            if isinstance(result, Exception):
                if manual:
                    self.window.toast(str(result))
            elif manual:
                self.show_versions(result)
            elif result['available']:
                if self.window.session.unlocked and QMessageBox.question(self.window, "Доступно обновление", f"Доступна версия {result['version']}. Открыть выбор версии и загрузку? Текущее приложение: {__version__}.") == QMessageBox.StandardButton.Yes:
                    self.check(manual=True)
        worker.finished.connect(finished)
        worker.start()

    def show_versions(self, releases):
        if not self.window.session.unlocked:
            return
        if not releases:
            self.window.toast("На GitHub пока нет версий с установщиком и манифестом проверки.")
            return
        dialog = QDialog(self.window)
        self.dialog = dialog
        self.downloaded = None
        dialog.setWindowTitle("Скачать и установить версию")
        dialog.setMinimumWidth(470)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(f"Установлена версия {__version__}. Источник: GitHub {REPOSITORY}"))
        versions = QComboBox()
        versions.setObjectName("updateVersions")
        for release in releases:
            versions.addItem(release["version"] + (" (текущая)" if version_tuple(release["version"]) == version_tuple(__version__) else ""), release)
        layout.addWidget(versions)
        status = QLabel("Выберите версию. Загрузка выполняется прямо в приложении.")
        status.setWordWrap(True)
        layout.addWidget(status)
        bar = QProgressBar()
        bar.setObjectName("updateProgress")
        layout.addWidget(bar)
        download = QPushButton("Скачать")
        download.setObjectName("primary")
        install = QPushButton("Установить")
        install.setObjectName("installUpdate")
        install.setEnabled(False)
        cancel = QPushButton("Закрыть")
        for control in (download, install, cancel):
            layout.addWidget(control)
        def changed():
            self.downloaded = None
            install.setEnabled(False)
            bar.setValue(0)
        versions.currentIndexChanged.connect(changed)
        def start():
            release = versions.currentData()
            if version_tuple(release["version"]) < version_tuple(__version__):
                if QMessageBox.question(dialog, "Предыдущая версия", "Старая версия может не поддерживать новые поля хранилища. Скачать выбранную версию?") != QMessageBox.StandardButton.Yes:
                    return
            self.cancel = Event()
            changed()
            download.setEnabled(False)
            versions.setEnabled(False)
            cancel.setText("Отменить загрузку")
            status.setText("Скачивание с GitHub…")
            worker = DownloadThread(release, self.window.session.store.root, self.cancel, self)
            self.worker = worker
            results = []
            worker.result.connect(results.append)
            worker.progress.connect(bar.setValue)
            def finished():
                self.worker = None
                worker.deleteLater()
                if not dialog.isVisible() or self.cancel.is_set():
                    return
                versions.setEnabled(True)
                download.setEnabled(True)
                cancel.setText("Закрыть")
                result = results[0] if results else VaultError("Отменить загрузку.")
                if isinstance(result, Exception):
                    status.setText(str(result))
                else:
                    self.downloaded = result
                    status.setText("Скачано. SHA-256 проверен. Нажмите «Установить»: приложение закроется, откроется установщик.")
                    install.setEnabled(True)
            worker.finished.connect(finished)
            worker.start()
        download.clicked.connect(start)
        install.clicked.connect(lambda: self.window.safe(self.install_downloaded))
        cancel.clicked.connect(dialog.reject)
        dialog.finished.connect(lambda _: self.cancel.set())
        dialog.exec()

    def install_downloaded(self):
        downloaded = self.downloaded
        if not downloaded or self.busy or not self.window.leave_editor():
            return
        if self.window.cloud.busy:
            raise VaultError("Дождитесь завершения синхронизации перед установкой.")
        path = downloaded["path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != downloaded["sha256"]:
            raise VaultError("Установщик изменился после загрузки. Скачайте его повторно.")
        # The installer waits for this process before touching installed binaries.
        args = [str(path)]
        if version_tuple(downloaded["version"]) >= version_tuple("0.41"):
            args += ["--wait-pid", str(os.getpid())]
        subprocess.Popen(args, close_fds=True)
        self.window.lock_vault()
        self.window.quit_application()
