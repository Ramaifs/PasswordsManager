"""GitHub Releases metadata only; updates are never installed automatically."""
import re
from threading import Event
from PySide6.QtCore import QObject, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox
from . import __version__
from .crypto import parse
from .http_client import request, HttpError
from .errors import VaultError
from .sync_ui import IOThread

REPOSITORY = "Ramaifs/PasswordsManager"
API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r"v?\d{1,5}\.\d{1,5}\.\d{1,5}", value):
        raise VaultError("GitHub вернул неподдерживаемый номер версии.")
    return tuple(int(part) for part in value.removeprefix('v').split('.'))


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
        worker = IOThread(lambda: latest_release(cancel=self.cancel), self.cancel, self)
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
            elif result['available']:
                if self.window.session.unlocked and QMessageBox.question(self.window, "Доступно обновление", f"Доступна версия {result['version']}. Открыть страницу загрузки? Текущее приложение: {__version__}.") == QMessageBox.StandardButton.Yes:
                    QDesktopServices.openUrl(QUrl(result['url']))
            elif manual:
                self.window.toast("Релизы пока не опубликованы" if result.get('unpublished') else "Установлена актуальная версия")
        worker.finished.connect(finished)
        worker.start()
