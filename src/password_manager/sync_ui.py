"""GUI orchestration: worker threads receive only ciphertext, never vault access."""
from threading import Event
from time import monotonic

from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtWidgets import QFileDialog, QMessageBox, QInputDialog, QDialog

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

    def connection_status(self):
        if not self.connection.exists:
            return "Google Drive — не подключен", "#d94a59"
        from .sync import state_id
        metadata = self.window.session.document.get("sync")
        pending = (not metadata or metadata["pending"] is not None or metadata["published"] != state_id(self.window.session.access, metadata["state"]))
        if pending or self.busy:
            return "Google Drive — Требует синхронизации", "#c98313"
        return "Google Drive — Подключен", "#2a9d59"

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
        choices = (["Все копии Google Drive", "Синхронизировать", "Отключить Google", "Создать папку заново", "Удалить облачные версии"]
                   if self.connection.exists else ["Подключить Google"])
        choice, ok = QInputDialog.getItem(window, "Google Drive", "Действие", choices, editable=False)
        if not ok: return
        if choice == "Все копии Google Drive":
            self.browse_copies()
        elif choice == "Подключить Google":
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
                transport.vault_id = self.window.session.access.header["vault_id"]
                transport.vault_name = self.window.session.document["settings"].get("vault_name", "Main")
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
        self.browse_copies()

    def browse_copies(self):
        if self.busy:
            return
        if self.window.session.unlocked and not self.window.leave_editor():
            return
        self.cancel = Event()
        def fetch_copies(_=None):
            transport = self.transport_factory(self.connection, self.cancel)
            self._start(transport.checkpoints, lambda copies: self.show_copies(transport, copies), allow_locked=True)
        if self.connection.exists:
            fetch_copies()
            return
        path = Path(__file__).with_name("google-desktop.json")
        if not path.exists():
            selected, _ = QFileDialog.getOpenFileName(self.window, "OAuth JSON типа Desktop app", "", "JSON (*.json)")
            if not selected:
                return
            path = Path(selected)
        client = config(path)
        def connected(value):
            self.connection.save(value)
            fetch_copies()
        self._start(lambda: authorize(client, self.cancel), connected, allow_locked=True)

    def show_copies(self, transport, copies):
        from .cloud_browser import CloudCopiesDialog
        dialog = CloudCopiesDialog(self.window, copies, self.window.preferences.last_opened_vault)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        copy = dialog.selected_copy
        dialog.deleteLater()
        if accepted and copy:
            self._start(lambda: transport.read_checkpoint(copy), lambda blob: self.preview_copy(copy, blob), allow_locked=True)

    def preview_copy(self, copy, blob):
        from .crypto import unlock
        from . import model, sync_state
        from .sync import version_payload
        from .cloud_browser import CloudPreviewDialog
        secret = self.window.ask_password("Мастер-пароль выбранной копии")
        if secret is None:
            return
        access, payload = unlock(blob, secret)
        if copy.get("version"):
            payload = version_payload(blob, access, copy["version"])
            document = model.new_document()
            document["sync"] = {"state": payload["state"], "pending": None, "published": None, "seen": {}}
            document = sync_state.project(document, payload["state"])
            if copy.get("vaultName"):
                from .vault_names import validate_name
                document["settings"]["vault_name"] = validate_name(copy["vaultName"])
        else:
            document = model.validate(payload)
        try:
            self.window.preferences.save_last_opened_vault(access.header["vault_id"])
        except OSError:
            self.window.toast("Не удалось запомнить последнее открытое хранилище")
        dialog = CloudPreviewDialog(self.window, copy, access, document)
        self.window.last_activity = monotonic()
        dialog.exec()
        switch = dialog.switch_requested
        dialog.clear()
        dialog.deleteLater()
        if switch:
            self.switch_to_copy(access, document)

    def switch_to_copy(self, access, document):
        from .session import Session
        if self.window.session.unlocked and not self.window.leave_editor():
            return
        if self.window.session.store.exists:
            answer = QMessageBox.question(self.window, "Переключить хранилище?", "Выбранная копия станет рабочим хранилищем. Прежнее хранилище и все его локальные резервные состояния будут сохранены в зашифрованном архиве. Продолжить?")
            if answer != QMessageBox.StandardButton.Yes:
                return
        archive = self.window.session.store.switch_to_copy(access, document)
        self.window.lock_vault()
        self.window.session = Session(self.window.session.store)
        self.window.session.access, self.window.session.document = access, document
        self.window.selected_id = None
        self.window.dirty = False
        self.window.master.clear()
        self.reset_schedule()
        self.window.build_editor()
        self.window.toast("Рабочее хранилище переключено" + (". Прежние копии: " + str(archive) if archive else ""))

    def browse_archive(self):
        from .storage import read_bounded
        path, _ = QFileDialog.getOpenFileName(self.window, "Архив прежних хранилищ", str(self.window.session.store.root / "switched-vaults"), "Хранилище (*.pmvault)")
        if path:
            self.preview_copy({"id": "local-archive", "name": Path(path).name, "version": None}, read_bounded(path))

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
        transport.vault_id = self.window.session.access.header["vault_id"]
        transport.vault_name = self.window.session.document["settings"].get("vault_name", "Main")
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
