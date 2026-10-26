"""GUI orchestration: worker threads receive only ciphertext, never vault access."""
from threading import Event
from time import monotonic

from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtWidgets import QFileDialog, QMessageBox, QInputDialog

from .crypto import unb64
from .drive import DriveTransport, FolderMissing
from .errors import VaultError
from .oauth import authorize, config
from .protected import ProtectedConnection
from .sync import SyncEngine
from .sync_state import conflicts
from pathlib import Path


class IOThread(QThread):
    result = Signal(object)

    def __init__(self, operation, cancel, parent=None):
        super().__init__(parent)
        self.operation, self.cancel = operation, cancel

    def run(self):
        try:
            result = self.operation()
        except Exception as error:
            result = error if isinstance(error, VaultError) else VaultError("Операция Google не выполнена. Локальные данные сохранены.")
        self.operation = None
        self.result.emit(result)


class SyncUI(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.connection = ProtectedConnection(window.session.store.root)
        self.cancel = Event()
        self.worker = None
        self.run_id = 0
        self.status = "Локальное хранилище"
        self.last_sync_attempt = monotonic()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.auto_sync)
        self.timer.start(1000)
        self.transport_factory = DriveTransport

    @property
    def busy(self): return self.worker is not None

    def set_status(self, text):
        self.status = text
        if self.window.session.unlocked and hasattr(self.window, "status"):
            self.window.status.setText(text)

    def pause(self):
        self.cancel.set()
        self.run_id += 1

    def _start(self, operation, callback, *, allow_locked=False):
        if self.busy:
            return
        cancel = self.cancel
        current_run = self.run_id
        worker = IOThread(operation, cancel, self)
        self.worker = worker
        def delivered(result):
            self.worker = None
            worker.deleteLater()
            if cancel.is_set() or current_run != self.run_id or (not allow_locked and not self.window.session.unlocked):
                return
            if isinstance(result, Exception):
                self.set_status(str(result))
                self.window.toast(str(result))
                return
            try:
                callback(result)
            except (VaultError, OSError) as error:
                self.set_status(str(error) if isinstance(error, VaultError) else "Не удалось сохранить результат синхронизации.")
                self.window.toast(self.status)
        # finished rather than result ensures the thread has completely stopped before disposal.
        result_box = []
        worker.result.connect(lambda result: result_box.append(result))
        worker.finished.connect(lambda: delivered(result_box[0] if result_box else VaultError("Обмен прерван.")))
        worker.start()

    def auto_sync(self):
        if not self.window.session.unlocked:
            return
        minutes = self.window.session.document["settings"].get("sync_minutes", 5)
        if minutes == 0 or monotonic() - self.last_sync_attempt < minutes * 60:
            return
        if self.window.session.unlocked and self.connection.exists and not self.busy and not self.window.dirty:
            # Do not navigate away from an open modal editor or settings window.
            from PySide6.QtWidgets import QApplication
            if QApplication.activeModalWidget() is None:
                self.sync()

    def reset_schedule(self):
        self.last_sync_attempt = monotonic()

    def menu(self):
        window = self.window
        if not window.leave_editor() or self.busy:
            return
        if not self.connection.exists:
            self.connect()
            return
        choices = (["Синхронизировать", "Отключить Google", "Создать папку заново", "Удалить облачные версии"]
                   if self.connection.exists else ["Подключить Google"])
        choice, ok = QInputDialog.getItem(window, "Google Drive", "Действие", choices, editable=False)
        if not ok: return
        if choice == "Подключить Google":
            self.connect()
        elif choice == "Синхронизировать":
            self.sync()
        elif choice == "Отключить Google":
            self.pause()
            self.connection.disconnect()
            self.set_status("Google отключён. Локальные и облачные файлы сохранены.")
        elif choice == "Создать папку заново":
            if QMessageBox.question(window, "Повторная загрузка", "Создать папку и повторно отправить локальные данные? Утраченные облачные изменения этим не восстанавливаются.") == QMessageBox.StandardButton.Yes:
                self.cancel = Event()
                transport = self.transport_factory(self.connection, self.cancel)
                self._start(lambda: transport.folders(recreate=True), lambda _: self.sync())
        elif choice == "Удалить облачные версии":
            if QMessageBox.question(window, "Удаление из Drive", "Удалить служебные версии и отключить Google на этом компьютере? Ручные копии и локальное хранилище сохранятся.") == QMessageBox.StandardButton.Yes:
                self.cancel = Event()
                transport = self.transport_factory(self.connection, self.cancel)
                def deleted(_):
                    self.connection.disconnect()
                    self.set_status("Служебные версии удалены; Google отключён. Другие подключённые компьютеры могут загрузить свои версии снова.")
                self._start(transport.delete_cloud, deleted)

    def connect(self):
        if self.busy or not self.window.session.unlocked:
            return
        path = Path(__file__).with_name("google-desktop.json")
        if not path.exists():
            selected, _ = QFileDialog.getOpenFileName(self.window, "OAuth JSON типа Desktop app", "", "JSON (*.json)")
            if not selected:
                return
            path = Path(selected)
        client = config(path)
        self.cancel = Event()
        self.set_status("Ожидание разрешения Google в системном браузере…")
        def connected(value):
            self.connection.save(value)
            self.set_status("Google подключён")
            self.sync()
        self._start(lambda: authorize(client, self.cancel), connected)

    def open_from_drive(self):
        """Restore an existing encrypted vault; Google never replaces its master password."""
        if self.busy or self.window.session.store.exists:
            return
        self.cancel = Event()
        def fetch_versions(_=None):
            transport = self.transport_factory(self.connection, self.cancel)
            self.window.toast("Синхронизация..", persistent=True)
            self._start(transport.fetch, open_version, allow_locked=True)
        def open_version(remote):
            if not remote:
                self.window.toast("В Google Drive пока нет хранилища. Создайте его на этом устройстве.")
                return
            versions = sorted(remote)
            version = versions[0]
            if len(versions) > 1:
                version, ok = QInputDialog.getItem(self.window, "Google Drive", "Выберите версию для открытия. После разблокировки остальные изменения будут объединены.", versions, editable=False)
                if not ok:
                    self.window.toast("Открытие отменено")
                    return
            from .crypto import unlock
            from . import model, sync_state
            from .sync import version_payload
            secret = self.window.master.text() or self.window.ask_password("Мастер-пароль облачного хранилища")
            if secret is None:
                self.window.toast("Открытие отменено")
                return
            access, _ = unlock(remote[version], secret)
            payload = version_payload(remote[version], access, version)
            doc = model.new_document()
            doc["sync"] = {"state": payload["state"], "pending": None, "published": None, "seen": {}}
            doc = sync_state.project(doc, payload["state"])
            # A new profile may have been created while authorization was pending.
            if self.window.session.store.exists or self.window.session.unlocked:
                raise VaultError("Локальное хранилище уже существует. Разблокируйте его для синхронизации.")
            self.window.session.store.commit(access, doc)
            self.window.session.access, self.window.session.document = access, doc
            self.window.master.clear()
            self.window.build_editor()
            self.sync()
        if self.connection.exists:
            fetch_versions()
        else:
            path = Path(__file__).with_name("google-desktop.json")
            if not path.exists():
                selected, _ = QFileDialog.getOpenFileName(self.window, "OAuth JSON типа Desktop app", "", "JSON (*.json)")
                if not selected:
                    return
                path = Path(selected)
            client = config(path)
            def connected(value):
                self.connection.save(value)
                fetch_versions()
            self._start(lambda: authorize(client, self.cancel), connected, allow_locked=True)

    def sync(self):
        if self.busy or not self.window.session.unlocked or not self.connection.exists:
            return
        if self.window.dirty:
            self.set_status("Перед синхронизацией сохраните или отмените редактирование.")
            return
        self.reset_schedule()
        self.window.toast("Синхронизация..", persistent=True)
        self.cancel = Event()
        transport = self.transport_factory(self.connection, self.cancel)
        self.set_status("Получение зашифрованных версий…")
        self._start(transport.fetch, lambda remote: self._received(transport, remote))

    def _received(self, transport, remote):
        if self.window.dirty:
            self.set_status("Получение завершено; применение отложено до сохранения редактора.")
            self.window.toast(self.status)
            return
        engine = SyncEngine(self.window.session)
        pending = engine.prepare(remote)
        self.refresh_view()
        if pending:
            self.set_status("Отправка зашифрованной версии…")
            blob = unb64(pending["blob"])
            self._start(lambda: transport.publish(pending["id"], blob),
                        lambda confirmed: self._published(transport, pending["id"], confirmed))
        else:
            candidates = engine.cleanup_candidates(remote)
            if candidates:
                self._start(lambda: [transport.delete(v) for v in candidates], lambda _: self.complete())
            else:
                self.complete()

    def _published(self, transport, version, confirmed):
        SyncEngine(self.window.session).acknowledge(version, confirmed)
        self._start(transport.fetch, lambda remote: self._received(transport, remote))

    def complete(self):
        metadata = self.window.session.document["sync"]
        count = len(conflicts(metadata["state"])) if metadata else 0
        self.set_status(f"Синхронизация завершена. Конфликтов: {count}" if count else "Синхронизация завершена")
        self.window.toast(f"Синхронизация выполнена! Конфликтов: {count}" if count else "Синхронизация выполнена!")

    def refresh_view(self):
        self.window.refresh_categories()
        self.window.clear_editor()
        self.window.refresh_entries()
