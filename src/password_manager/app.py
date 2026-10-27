"""Russian desktop UI. No stdout, traceback dialogs or content logging."""
from copy import deepcopy
from dataclasses import asdict
import os
from pathlib import Path
import sys
import time

from PySide6.QtCore import QEvent, Qt, QTimer, QAbstractNativeEventFilter, QTranslator, QLibraryInfo, QSize, QCollator, QLocale
from PySide6.QtGui import QGuiApplication, QColor, QIcon
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QLineEdit, QTextEdit, QPushButton, QListWidget, QListWidgetItem, QComboBox,
    QSplitter, QLabel, QMessageBox, QInputDialog, QFileDialog, QDialog, QSpinBox, QCheckBox,
    QDialogButtonBox, QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea, QToolButton, QMenu, QGridLayout,
    QSizePolicy, QColorDialog, QFrame, QSystemTrayIcon, QCompleter)
from .theme import stylesheet
from .category_list import CategoryList, HAS_CHILDREN, COLLAPSED
from .icons import application_icon, navigation_icon, entry_icon
from .preferences import Preferences

from . import model
from .crypto import Access, recovery_secret, validate_password, MIN_MASTER_PASSWORD, MAX_MASTER_PASSWORD
from . import __version__
from .errors import VaultError, InvalidVault
from .generator import GeneratorOptions, generate
from .importer import preview_legacy
from .session import Session
from .storage import Store, read_bounded

LABELS = {"title": "Название", "site": "Сайт", "username": "Логин", "email": "Почта",
          "phone": "Телефон", "password": "Пароль", "second_password": "Второй пароль (2FA)",
          "note": "Заметка"}


def button(text, callback, layout):
    widget = QPushButton(text)
    widget.clicked.connect(callback)
    layout.addWidget(widget)
    return widget


class NumberInput(QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lineEdit().setTextMargins(11, 0, 0, 0)


class WindowsEvents(QAbstractNativeEventFilter):
    def __init__(self, window):
        super().__init__()
        self.window = window

    def nativeEventFilter(self, event_type, message):
        if os.name == "nt":
            import ctypes
            from ctypes.wintypes import MSG
            msg = MSG.from_address(int(message))
            if (msg.message == 0x2B1 and msg.wParam == 7) or (msg.message == 0x218 and msg.wParam == 4):
                # Complete lock before Windows can suspend this message-processing thread.
                self.window.lock_vault()
        return False, 0


class Window(QMainWindow):
    def __init__(self, store):
        super().__init__()
        self.session = Session(store)
        self.preferences = Preferences(store.root)
        self._window_mode = self.preferences.window_mode
        self._restoring_window = False
        self._window_preference_error = False
        self.window_state_timer = QTimer(self)
        self.window_state_timer.setSingleShot(True)
        self.window_state_timer.timeout.connect(self.save_window_mode)
        self.collapsed_categories = set()
        self.tray = None
        self._pending_close_action = None
        self._force_quit = False
        self._close_remember = False
        self._asking_close = False
        from .sync_ui import SyncUI
        self.cloud = SyncUI(self)
        from .updates import UpdateChecker
        self.updates = UpdateChecker(self)
        self.selected_id = None
        self.dirty = False
        self.loading = False
        self.generator_options = asdict(GeneratorOptions())
        self.clipboard_secret = None
        self.last_activity = time.monotonic()
        self.setWindowTitle(f"Менеджер паролей — {__version__}")
        self.setWindowIcon(application_icon())
        self.resize(1220, 820)
        self.setMinimumSize(980, 640)
        self.setStyleSheet(stylesheet())
        self.clip_timer = QTimer(self)
        self.clip_timer.setSingleShot(True)
        self.clip_timer.timeout.connect(self.clear_clipboard)
        self.idle_timer = QTimer(self)
        self.idle_timer.timeout.connect(self.check_idle)
        self.idle_timer.start(1000)
        QApplication.instance().installEventFilter(self)
        self.native_filter = WindowsEvents(self)
        QApplication.instance().installNativeEventFilter(self.native_filter)
        if os.name == "nt":
            import ctypes
            from ctypes.wintypes import HWND, DWORD, BOOL
            register = ctypes.windll.wtsapi32.WTSRegisterSessionNotification
            register.argtypes, register.restype = [HWND, DWORD], BOOL
            self.wts_registered = bool(register(int(self.winId()), 0))
        self.show_locked()

    def toast(self, text, persistent=False):
        if not hasattr(self, "toast_label"):
            self.toast_label = QLabel(self)
            self.toast_label.setStyleSheet("QLabel { background: #292637; color: #ff9900; border: 1px solid #9b87f5; border-radius: 8px; padding: 14px 20px; }")
            self.toast_timer = QTimer(self)
            self.toast_timer.setSingleShot(True)
            self.toast_timer.timeout.connect(self.toast_label.hide)
        self.toast_timer.stop()
        self.toast_label.setText(text)
        self.toast_label.adjustSize()
        self.position_toast()
        self.toast_label.show()
        self.toast_label.raise_()
        if not persistent:
            self.toast_timer.start(6500)

    def position_toast(self):
        if hasattr(self, "toast_label"):
            self.toast_label.move(max(8, self.width() - self.toast_label.width() - 24), self.height() - self.toast_label.height() - 24)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.position_toast()

    def remember_window_mode(self):
        if not self.isVisible() or self.isMinimized() or self._restoring_window:
            return
        self._window_mode = "fullscreen" if self.isFullScreen() else "maximized" if self.isMaximized() else "normal"

    def save_window_mode(self):
        self.window_state_timer.stop()
        if self.preferences.window_mode == self._window_mode:
            return
        try:
            self.preferences.save_window_mode(self._window_mode)
            self._window_preference_error = False
        except OSError:
            if self.isVisible() and not self._window_preference_error:
                self.toast("Не удалось сохранить состояние окна. Проверьте доступ к папке приложения.")
            self._window_preference_error = True

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and hasattr(self, "window_state_timer") and self.isVisible() and not self.isMinimized() and not self._restoring_window:
            self.remember_window_mode()
            self.window_state_timer.start(200)

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, "window_state_timer") and not self._restoring_window:
            self.remember_window_mode()
            self.window_state_timer.start(200)

    def show_saved_window(self):
        self._restoring_window = True
        try:
            if self._window_mode == "fullscreen":
                self.showFullScreen()
            elif self._window_mode == "maximized":
                self.showMaximized()
            else:
                self.showNormal()
        finally:
            self._restoring_window = False

    def error(self, exception):
        message = str(exception) if isinstance(exception, VaultError) else "Операция не выполнена. Проверьте доступ к файлам и свободное место."
        QMessageBox.warning(self, "Операция не выполнена", message)

    def safe(self, operation):
        try:
            return operation()
        except (VaultError, OSError):
            self.error(sys.exception())
            return None

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.KeyPress, QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove, QEvent.Type.Wheel):
            self.last_activity = time.monotonic()
        return False

    def check_idle(self):
        if self.session.unlocked and time.monotonic() - self.last_activity >= self.session.document["settings"]["lock_minutes"] * 60:
            self.lock_vault()

    def replace_page(self, page):
        old = self.takeCentralWidget()
        if old:
            old.hide()
            old.deleteLater()
        self.setCentralWidget(page)

    def show_locked(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        brand = QLabel("Личное хранилище")
        brand.setObjectName("brand")
        layout.setContentsMargins(32, 24, 32, 24)
        layout.addWidget(brand)
        layout.addStretch()
        card = QWidget()
        card.setObjectName("lockCard")
        card.setFixedWidth(470)
        content = QVBoxLayout(card)
        content.setContentsMargins(38, 32, 38, 32)
        content.setSpacing(16)
        layout.addWidget(card, 0, Qt.AlignmentFlag.AlignHCenter)
        mark = QLabel("PM")
        mark.setObjectName("lockMark")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content.addWidget(mark)
        label = QLabel("Хранилище заблокировано" if self.session.store.exists else "Создать личное хранилище")
        label.setObjectName("sectionHeading")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content.addWidget(label)
        hint = QLabel("Ваши записи под защитой.\nВведите мастер-пароль, чтобы продолжить." if self.session.store.exists else "Все пароли в одном спокойном месте.\nСоздайте мастер-пароль для защиты записей.")
        hint.setObjectName("caption")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content.addWidget(hint)
        if not self.session.store.exists:
            self.vault_name = QLineEdit("Main")
            self.vault_name.setPlaceholderText("Название хранилища")
            self.vault_name.setMaxLength(100)
            content.addWidget(self.vault_name)
        self.master = QLineEdit()
        self.master.setEchoMode(QLineEdit.EchoMode.Password)
        self.master.setPlaceholderText(f"Мастер-пароль ({MIN_MASTER_PASSWORD}–{MAX_MASTER_PASSWORD} символов)")
        self.master.setMaxLength(MAX_MASTER_PASSWORD)
        content.addWidget(self.master)
        self.master.returnPressed.connect(lambda: self.safe(self.open_or_create))
        button("Разблокировать" if self.session.store.exists else "Создать хранилище", lambda: self.safe(self.open_or_create), content).setObjectName("primary")
        if self.session.store.exists:
            button("Восстановить доступ по ключу", lambda: self.safe(self.recover), content)
            button("Проверить резервную копию", lambda: self.safe(self.recover_backup), content)
        else:
            button("Открыть зашифрованный экспорт", lambda: self.safe(self.open_export), content)
            button("Восстановить доступ из файла", lambda: self.safe(lambda: self.open_export(recovery=True)), content)
        button("Все копии Google Drive", lambda: self.safe(self.cloud.browse_copies), content)
        if (self.session.store.root / "switched-vaults").exists():
            button("Архив прежних хранилищ", lambda: self.safe(self.cloud.browse_archive), content)
        layout.addStretch()
        foot = QLabel("Локальное хранилище  •  Google Drive приостановлен до разблокировки")
        foot.setObjectName("caption")
        foot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(foot)
        self.replace_page(page)
        self.master.setFocus()

    def ask_password(self, title):
        value, ok = QInputDialog.getText(self, title, title, QLineEdit.EchoMode.Password)
        if not ok:
            return None
        validate_password(value)
        return value

    def open_export(self, recovery=False):
        path, _ = QFileDialog.getOpenFileName(self, "Открыть зашифрованный экспорт", "", "Хранилище (*.pmvault)")
        if not path:
            return
        from .crypto import unlock
        secret = self.master.text()
        if recovery:
            secret, ok = QInputDialog.getText(self, "Восстановление из файла", "Ключ восстановления", QLineEdit.EchoMode.Password)
            if not ok:
                return
        access, doc = unlock(read_bounded(path), secret, recovery=recovery)
        model.validate(doc)
        if self.session.store.exists:
            raise VaultError("Локальное хранилище уже существует.")
        if recovery:
            new = self.ask_password("Новый мастер-пароль")
            if new is None:
                return
            if self.ask_password("Повторите новый мастер-пароль") != new:
                raise VaultError("Мастер-пароли не совпадают.")
            if not self.warn_exports():
                return
            access = access.change_password(new)
        self.session.store.commit(access, doc)
        self.session.access, self.session.document = access, doc
        self.master.clear()
        self.build_editor()

    def confirm_recovery(self, recovery):
        dialog = QDialog(self)
        dialog.setWindowTitle("Сохраните ключ восстановления отдельно")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Без мастер-пароля и этого ключа доступ восстановить невозможно.\nСохраните ключ отдельно от хранилища. Автоматической записи нет."))
        text = QLineEdit(recovery)
        text.setReadOnly(True)
        layout.addWidget(text)
        def save_key():
            path, _ = QFileDialog.getSaveFileName(dialog, "Сохраните отдельно от хранилища", "recovery-key.txt", "Текст (*.txt)")
            if not path or not text.text():
                return
            if Path(path).resolve().is_relative_to(self.session.store.root.resolve()):
                raise VaultError("Сохраните ключ вне каталога хранилища.")
            from .storage import write_fsynced
            write_fsynced(Path(path), (text.text() + "\n").encode("ascii"))
        button("Сохранить ключ в выбранный файл…", lambda: self.safe(save_key), layout)
        check = QCheckBox("Я сохранил(а) ключ в отдельном безопасном месте")
        layout.addWidget(check)
        actions = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        actions.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        check.toggled.connect(actions.button(QDialogButtonBox.StandardButton.Ok).setEnabled)
        actions.accepted.connect(dialog.accept)
        actions.rejected.connect(dialog.reject)
        layout.addWidget(actions)
        result = dialog.exec() == QDialog.DialogCode.Accepted
        text.clear()
        dialog.deleteLater()
        return result

    def open_or_create(self):
        password = self.master.text()
        created = not self.session.store.exists
        if self.session.store.exists:
            self.session.open(password)
        else:
            from .vault_names import validate_name
            name = validate_name(self.vault_name.text())
            validate_password(password)
            repeat = self.ask_password("Повторите мастер-пароль")
            if repeat is None:
                return
            if repeat != password:
                raise VaultError("Мастер-пароли не совпадают.")
            access, recovery = Access.create(password)
            if not self.confirm_recovery(recovery):
                return
            doc = model.new_document()
            doc["settings"]["vault_name"] = name
            self.session.store.commit(access, doc)
            self.session.access, self.session.document = access, doc
        self.master.clear()
        self.last_activity = time.monotonic()
        self.build_editor()
        if created:
            self.toast("Хранилище создано. Для облачной копии подключите Google Drive в настройках.")

    def recover(self):
        recovery, ok = QInputDialog.getText(self, "Восстановление", "Ключ восстановления", QLineEdit.EchoMode.Password)
        if not ok:
            return
        password = self.ask_password("Новый мастер-пароль")
        if password is None:
            return
        repeat = self.ask_password("Повторите новый мастер-пароль")
        if repeat != password:
            raise VaultError("Мастер-пароли не совпадают.")
        if not self.warn_exports():
            return
        self.session.access, self.session.document = self.session.store.recover(recovery, password)
        self.master.clear()
        self.build_editor()

    def recover_backup(self):
        paths = self.session.store.snapshots()
        index, ok = QInputDialog.getInt(self, "Резервные копии", "Номер копии (1 — предыдущая)", 1, 1, max(1, len(paths) - 1))
        if not ok or index >= len(paths):
            return
        password = self.master.text()
        access, doc = self.session.store.open(password, index=index)
        try:
            _, current = self.session.store.open(password)
        except InvalidVault:
            text = f"Копия читается, записей: {len(doc['entries'])}. Текущее состояние повреждено; сравнить поля невозможно.\nВсе исходные зашифрованные файлы будут сохранены отдельно в каталоге damaged. Восстановить выбранную копию?"
            if QMessageBox.question(self, "Повреждённое хранилище", text) != QMessageBox.StandardButton.Yes:
                return
            access, doc = self.session.store.recover_damaged(password, index)
        else:
            diff = model.backup_diff(current, doc)
            text = f"Добавится: {diff['added']}; исчезнет: {diff['removed']}; изменится: {diff['changed']}.\nСохранить текущее состояние и восстановить копию?"
            if QMessageBox.question(self, "Различия", text) != QMessageBox.StandardButton.Yes:
                return
            doc = self.session.store.restore_backup(access, current, index)
        self.session.access, self.session.document = access, doc
        self.master.clear()
        self.build_editor()

    def build_editor(self):
        try:
            self.preferences.save_last_opened_vault(self.session.access.header["vault_id"])
        except OSError:
            self.toast("Не удалось запомнить последнее открытое хранилище")
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        toolbar = QHBoxLayout()
        toolbar.addStretch()
        button("🔒 Заблокировать", self.lock_vault, toolbar)
        outer.addLayout(toolbar)
        split = QSplitter()
        split.setChildrenCollapsible(False)
        split.setHandleWidth(1)
        outer.addWidget(split, 1)
        left = QWidget()
        left.setObjectName("sidebar")
        left.setMinimumWidth(205)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(16, 25, 16, 18)
        ll.setSpacing(10)
        brand = QLabel(self.session.document["settings"].get("vault_name", "Main"))
        brand.setTextFormat(Qt.TextFormat.PlainText)
        self.vault_title = brand
        brand.setObjectName("brand")
        ll.addWidget(brand)
        caption = QLabel("ЛИЧНОЕ ПРОСТРАНСТВО")
        caption.setObjectName("caption")
        ll.addWidget(caption)
        ll.addSpacing(12)
        self.categories = CategoryList()
        self.categories.toggleRequested.connect(lambda cid: self.safe(lambda: self.toggle_category(cid)))
        self.categories.moveRequested.connect(lambda cid, parent: self.safe(lambda: self.move_category(cid, parent)))
        self.categories.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.categories.customContextMenuRequested.connect(self.category_context_menu)
        ll.addWidget(self.categories)
        button("Настройки", lambda: self.safe(self.settings), ll)
        self.theme_button = QToolButton()
        self.theme_button.setObjectName("themeToggle")
        self.theme_button.setAccessibleName("Переключить тему")
        self.theme_button.setToolTip("Переключить тему")
        self.theme_button.clicked.connect(lambda: self.safe(self.toggle_theme))
        ll.addWidget(self.theme_button, 0, Qt.AlignmentFlag.AlignLeft)
        version = QLabel(f"Windows  ·  {__version__}")
        version.setObjectName("caption")
        ll.addWidget(version)
        split.addWidget(left)
        center = QWidget()
        center.setObjectName("entryColumn")
        center.setMinimumWidth(240)
        cl = QVBoxLayout(center)
        cl.setContentsMargins(14, 26, 14, 16)
        cl.setSpacing(16)
        list_title = QLabel("Записи")
        list_title.setObjectName("sectionHeading")
        cl.addWidget(list_title)
        button("+ Новая запись", lambda: self.safe(self.new_entry), cl).setObjectName("primary")
        self.empty_trash_button = button("Очистить корзину", lambda: self.safe(self.empty_trash), cl)
        self.empty_trash_button.setObjectName("danger")
        self.query = QLineEdit()
        self.query.setPlaceholderText("Поиск записей…")
        self.query.setClearButtonEnabled(True)
        cl.addWidget(self.query)
        self.entry_sort = QComboBox()
        self.entry_sort.setAccessibleName("Сортировка записей")
        self.entry_sort.addItem("По алфавиту (А–Я)", "title")
        self.entry_sort.addItem("По изменению (сначала новые)", "updated")
        self.entry_sort.setCurrentIndex(self.entry_sort.findData(self.preferences.entry_sort))
        self.entry_sort.currentIndexChanged.connect(lambda: self.safe(self.change_entry_sort))
        cl.addWidget(self.entry_sort)
        self.entries = QListWidget()
        self.entries.setObjectName("entryList")
        cl.addWidget(self.entries)
        self.entry_count = QLabel()
        self.entry_count.setObjectName("caption")
        cl.addWidget(self.entry_count)
        split.addWidget(center)
        right = QWidget()
        right.setMinimumWidth(450)
        editor = QVBoxLayout(right)
        editor.setContentsMargins(28, 24, 28, 26)
        editor.setSpacing(18)
        self.editor_heading = QLabel("Новая запись")
        self.editor_heading.setObjectName("heading")
        self.editor_heading.setTextFormat(Qt.TextFormat.PlainText)
        self.editor_heading.setWordWrap(True)
        editor.addWidget(self.editor_heading)
        subtitle = QLabel("Детали записи  /  Личное хранилище")
        subtitle.setObjectName("caption")
        editor.addWidget(subtitle)
        form = QGridLayout()
        form.setVerticalSpacing(14)
        form.setHorizontalSpacing(16)
        form.setColumnStretch(0, 1)
        form.setColumnStretch(1, 1)
        editor.addLayout(form)
        positions = {"title": (0, 0, 2), "site": (1, 0, 2), "username": (2, 0, 1),
                     "email": (2, 1, 1), "phone": (3, 0, 1), "password": (4, 0, 2),
                     "second_password": (5, 0, 2), "old_passwords": (6, 0, 2), "note": (7, 0, 2)}
        self.field_form = form
        self.field_groups = {}
        def field(label, widget, row, column, span=1):
            container = QWidget()
            group = QVBoxLayout(container)
            group.setContentsMargins(0, 0, 0, 0)
            group.setSpacing(7)
            heading = QHBoxLayout()
            heading.addWidget(QLabel(label), 1)
            if widget in self.fields.values() and next(k for k, v in self.fields.items() if v is widget) in model.EXTRA_FIELDS:
                key = next(k for k, v in self.fields.items() if v is widget)
                plus = button("+", lambda checked=False, name=key: self.safe(lambda: self.add_extra_field(name)), heading)
                plus.setAccessibleName("Добавить: " + label)
                self.extra_buttons[key] = plus
            group.addLayout(heading)
            group.addWidget(widget)
            form.addWidget(container, row, column, 1, span)
            self.field_groups[widget] = (container, row, column, span)
        self.fields = {}
        self.editing = True
        self.extra_buttons = {}
        self.extra_widgets = {key: [] for key in model.EXTRA_FIELDS}
        self.secret_reveals = {}
        self.secret_copy_buttons = {}
        for key, label in LABELS.items():
            widget = QTextEdit() if key == "note" else QLineEdit()
            if key in model.SECRET_FIELDS:
                widget.setEchoMode(QLineEdit.EchoMode.Password)
            if isinstance(widget, QLineEdit):
                widget.setMaxLength(100_000)
                widget.setPlaceholderText(label)
            else:
                widget.setFixedHeight(90)
            widget.textChanged.connect(self.mark_dirty)
            self.fields[key] = widget
            if key in model.SUGGESTION_FIELDS:
                completer = QCompleter([], widget)
                completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
                completer.setFilterMode(Qt.MatchFlag.MatchContains)
                widget.setCompleter(completer)
                completer.activated[str].connect(widget.setText)
            field(label, widget, *positions[key])
            if key == "second_password":
                controls = QHBoxLayout()
                self.secret_copy_buttons[key] = button("Копировать", lambda checked=False, field=key: self.copy_password(field), controls)
                self.field_groups[widget][0].layout().addLayout(controls)
        self.record_category = QComboBox()
        self.record_category.currentIndexChanged.connect(self.mark_dirty)
        field("Категория", self.record_category, 3, 1)
        self.reveal = QCheckBox("Показать пароль")
        self.reveal.toggled.connect(self.reveal_passwords)
        options = QHBoxLayout()
        options.addWidget(self.reveal)
        options.addStretch()
        self.advanced = QPushButton("Продвинутые настройки")
        self.advanced.setObjectName("advancedOptions")
        self.advanced.setCheckable(True)
        self.advanced.toggled.connect(lambda _: self.set_editing(self.editing))
        options.addWidget(self.advanced)
        editor.addLayout(options)
        self.paste_button = button("Вставить пароли из буфера обмена (по строкам)", lambda: self.safe(self.paste_other_passwords), editor)
        actions = QHBoxLayout()
        self.save_button = button("Сохранить", lambda: self.safe(self.save), actions)
        self.save_button.setObjectName("primary")
        self.edit_button = button("Редактировать", self.edit_entry, actions)
        self.copy_button = button("Копировать пароль", lambda: self.copy_password(), actions)
        self.generate_button = button("Сгенерировать", lambda: self.safe(lambda: self.generator_dialog(True)), actions)
        editor.addLayout(actions)
        deleted_actions = QHBoxLayout()
        self.trash_button = button("В корзину", lambda: self.safe(self.delete_entry), deleted_actions)
        self.trash_button.setObjectName("danger")
        self.restore_button = button("Восстановить", lambda: self.safe(self.restore_entry), deleted_actions)
        self.purge_button = button("Удалить навсегда", lambda: self.safe(self.purge_entry), deleted_actions)
        self.purge_button.setObjectName("danger")
        editor.addLayout(deleted_actions)
        editor.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(right)
        split.addWidget(scroll)
        split.setSizes([218, 290, 710])
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 0)
        split.setStretchFactor(2, 1)
        self.status = QLabel(self.cloud.status)
        self.status.setObjectName("status")
        self.status.setFixedHeight(38)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        outer.addWidget(self.status)
        self.replace_page(page)
        self.selected_id = None
        self.dirty = False
        self.refresh_categories()
        self.categories.currentRowChanged.connect(lambda _: self.safe(self.navigate_filter))
        self.query.textChanged.connect(lambda _: self.safe(self.navigate_filter))
        self.entries.currentItemChanged.connect(lambda current, previous: self.safe(lambda: self.select_entry(current, previous)))
        self.clear_editor()
        self.refresh_entries()
        self.apply_theme()
        drafts = self.session.document["drafts"]
        if drafts and QMessageBox.question(self, "Черновик", "Продолжить сохранённый локальный черновик?") == QMessageBox.StandardButton.Yes:
            key = next(iter(drafts))
            draft = drafts[key]
            self.selected_id = key if key in self.session.document["entries"] else None
            self.fill_editor(draft)
            self.set_editing(True)
            self.dirty = True
        self.updates.schedule()

    def category_context_menu(self, position):
        if not self.leave_editor():
            return
        item = self.categories.itemAt(position)
        cid = item.data(Qt.ItemDataRole.UserRole) if item else None
        if item:
            self.categories.setCurrentItem(item)
        menu = self.category_menu(cid)
        menu.exec(self.categories.viewport().mapToGlobal(position))
        menu.deleteLater()

    def category_menu(self, cid=None):
        menu = QMenu(self)
        menu.addAction("Создать категорию").triggered.connect(lambda: self.safe(self.add_category))
        if cid in self.session.document["categories"]:
            menu.addAction("Создать подкатегорию").triggered.connect(lambda: self.safe(lambda: self.add_category(parent_id=cid)))
            destinations = menu.addMenu("Переместить в…")
            excluded = model.category_descendants(self.session.document, cid)
            targets = [(None, "Верхний уровень")]
            targets.extend((key, model.category_path(self.session.document, key))
                           for key, _, _ in model.category_rows(self.session.document) if key not in excluded)
            for parent, label in targets:
                action = destinations.addAction(label)
                action.setEnabled(self.session.document.get("category_parents", {}).get(cid) != parent)
                action.triggered.connect(lambda checked=False, target=parent: self.safe(lambda: self.move_category(cid, target)))
            menu.addSeparator()
            for label, callback in [("Переименовать", self.rename_category), ("Поменять цвет", self.color_category), ("Удалить категорию", self.remove_category)]:
                menu.addAction(label).triggered.connect(lambda checked=False, op=callback: self.safe(op))
        return menu

    def set_editing(self, editing):
        self.editing = editing
        for widget in self.fields.values():
            widget.setReadOnly(not editing)
        visible_row = 0
        for widget, (container, row, column, span) in sorted(self.field_groups.items(), key=lambda item: item[1][1:3]):
            self.field_form.removeWidget(container)
            if self.password_only and widget not in (self.fields["password"], self.fields["note"]):
                container.hide()
                continue
            if widget is self.fields["second_password"] and not self.advanced.isChecked():
                container.hide()
                continue
            populated = bool(widget.currentData()) if widget is self.record_category else bool((widget.toPlainText() if isinstance(widget, QTextEdit) else widget.text()).strip())
            container.setVisible(editing or populated)
            if editing:
                self.field_form.addWidget(container, row, column, 1, span)
            elif populated:
                self.field_form.addWidget(container, visible_row, 0, 1, 2)
                visible_row += 1
        has_password = bool(self.fields["password"].text().strip())
        self.reveal.setVisible(editing or has_password)
        self.copy_button.setVisible(editing or has_password)
        self.record_category.setEnabled(editing)
        self.save_button.setVisible(editing)
        self.generate_button.setVisible(editing)
        self.edit_button.setVisible(bool(self.selected_id) and not editing and not self.session.document["entries"][self.selected_id]["deleted_at"])
        self.advanced.setVisible(not self.password_only)
        self.paste_button.setVisible(self.password_only)
        for key, control in self.extra_buttons.items():
            control.setVisible(editing and self.advanced.isChecked() and not self.password_only)
        for items in self.extra_widgets.values():
            for container, widget in items:
                container.setVisible(self.advanced.isChecked() and not self.password_only and (editing or bool(widget.text())))
                widget.setReadOnly(not editing)

    def reveal_passwords(self, visible):
        mode = QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        for key in ("password", "second_password"):
            self.fields[key].setEchoMode(mode)
            for _, widget in self.extra_widgets[key]:
                widget.setEchoMode(mode)

    def add_extra_field(self, key, value=""):
        items = self.extra_widgets[key]
        if len(items) >= 100:
            raise VaultError("Можно добавить до 100 дополнительных полей каждого типа.")
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.addWidget(QLabel(f"{LABELS[key]} №{len(items) + 2}"))
        widget = QLineEdit(value)
        widget.setMaxLength(100_000)
        if key in model.SECRET_FIELDS:
            widget.setEchoMode(QLineEdit.EchoMode.Normal if self.reveal.isChecked() else QLineEdit.EchoMode.Password)
        widget.textChanged.connect(self.mark_dirty)
        layout.addWidget(widget)
        if key in model.SECRET_FIELDS:
            button("Копировать", lambda: self.copy_secret_value(widget.text()), layout)
        self.field_groups[self.fields[key]][0].layout().addWidget(container)
        items.append((container, widget))
        widget.setReadOnly(not self.editing)
        if not self.loading:
            self.mark_dirty()
            widget.setFocus()

    def copy_secret_value(self, text):
        QApplication.clipboard().setText(text)
        self.clipboard_secret = text
        self.clip_timer.start(300_000)

    def paste_other_passwords(self):
        if not self.leave_editor():
            return
        ids = self.session.mutate(lambda doc: model.paste_passwords(doc, QApplication.clipboard().text()))
        self.clear_editor()
        self.refresh_entries()
        self.status.setText(f"Добавлено паролей: {len(ids)}")

    def edit_entry(self):
        if self.selected_id and not self.session.document["entries"][self.selected_id]["deleted_at"]:
            self.set_editing(True)
            self.fields["password" if self.password_only else "title"].setFocus()

    def action_menu(self, title, actions, layout):
        control = QToolButton()
        control.setText(title)
        control.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        control.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(control)
        for label, callback in actions:
            menu.addAction(label).triggered.connect(lambda checked=False, op=callback: self.safe(op))
        control.setMenu(menu)
        layout.addWidget(control)
        return control

    def mark_dirty(self, *args):
        if not self.loading:
            self.dirty = True
            title = model.password_title(self.fields["note"].toPlainText()) if self.password_only else self.fields["title"].text() or "Новая запись"
            self.editor_heading.setText(title)

    def refresh_categories(self, selected=None):
        self.loading = True
        theme = self.session.document["settings"]["theme"]
        dark = theme == "dark" or (theme == "system" and QGuiApplication.styleHints().colorScheme() != Qt.ColorScheme.Light)
        icon_color = "#a09cb0" if dark else "#706a7c"
        current = self.categories.currentItem()
        selected = selected if selected is not None else current.data(Qt.ItemDataRole.UserRole) if current else "all"
        self.categories.blockSignals(True)
        self.categories.clear()
        rows = model.category_rows(self.session.document)
        ids = set(self.session.document["categories"])
        self.categories.category_ids = ids
        self.collapsed_categories.intersection_update(ids)
        parents = self.session.document.get("category_parents", {})
        has_children = set(parents.values())
        hidden = set()
        for cid, name, depth in rows:
            if parents.get(cid) in self.collapsed_categories or parents.get(cid) in hidden:
                hidden.add(cid)
        for name, data in [("Все записи", "all"), ("Без категории", None), ("Прочие пароли", "other-passwords"), *[(('    ' * depth + '• ' if depth else '') + name, cid) for cid, name, depth in rows], ("Корзина", "trash")]:
            if self.categories.count() == 3:
                heading = QListWidgetItem("Категории")
                heading.setData(Qt.ItemDataRole.UserRole, "category-heading")
                heading.setFlags(Qt.ItemFlag.NoItemFlags)
                heading.setForeground(QColor(icon_color))
                self.categories.addItem(heading)
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, data)
            if data in ("all", None, "other-passwords", "trash"):
                item.setIcon(navigation_icon({"all": "key", None: "folder", "other-passwords": "asterisk", "trash": "trash"}[data], icon_color))
            if data in self.session.document["categories"]:
                item.setForeground(QColor(self.session.document["settings"].get("category_colors", {}).get(data, self.session.document["settings"].get("accent_color", "#8864cb"))))
                item.setData(HAS_CHILDREN, data in has_children)
                item.setData(COLLAPSED, data in self.collapsed_categories)
                item.setToolTip(model.category_path(self.session.document, data))
            self.categories.addItem(item)
            if data in hidden:
                item.setHidden(True)
            if data == selected:
                self.categories.setCurrentItem(item)
        if self.categories.currentItem() is None:
            self.categories.setCurrentRow(0)
        self.categories.blockSignals(False)
        self.record_category.clear()
        self.record_category.addItem("Без категории", None)
        for cid, name, depth in rows:
            self.record_category.addItem(model.category_path(self.session.document, cid), cid)
        self.loading = False

    def toggle_category(self, cid):
        if cid not in self.session.document["categories"]:
            return
        current = self.categories.currentItem()
        selected = current.data(Qt.ItemDataRole.UserRole) if current else "all"
        hiding_selected = cid not in self.collapsed_categories and selected != cid and selected in model.category_descendants(self.session.document, cid)
        if hiding_selected and not self.leave_editor():
            return
        if cid in self.collapsed_categories:
            self.collapsed_categories.remove(cid)
        else:
            self.collapsed_categories.add(cid)
        self.refresh_categories(cid if hiding_selected else selected)
        if hiding_selected:
            self.clear_editor()
            self.refresh_entries()

    def move_category(self, cid, parent_id):
        if not self.session.unlocked or not self.leave_editor():
            return False
        if self.session.document.get("category_parents", {}).get(cid) == parent_id:
            return False
        self.session.mutate(lambda doc: model.move_category(doc, cid, parent_id))
        self.collapsed_categories.discard(parent_id)
        self.refresh_categories(cid)
        self.clear_editor()
        self.refresh_entries()
        return True

    def change_entry_sort(self):
        self.preferences.save_entry_sort(self.entry_sort.currentData())
        self.refresh_entries()

    def refresh_entries(self):
        if not self.session.unlocked:
            return
        self.entries.blockSignals(True)
        self.entries.clear()
        item = self.categories.currentItem()
        category = item.data(Qt.ItemDataRole.UserRole) if item else "all"
        self.empty_trash_button.setVisible(category == "trash")
        self.empty_trash_button.setEnabled(any(e["deleted_at"] for e in self.session.document["entries"].values()))
        entries = model.search(self.session.document, self.query.text(), "all" if category == "trash" else category, category == "trash")
        collator = QCollator(QLocale("ru_RU"))
        collator.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        entries.sort(key=lambda entry: (collator.sortKey(entry["title"]), entry["id"]))
        if self.entry_sort.currentData() == "updated":
            entries.sort(key=lambda entry: entry["updated_at"], reverse=True)
        for entry in entries:
            cid = entry["category"]
            category_name = self.session.document["categories"].get(cid, "Без категории")
            if entry.get("entry_type") == "password":
                category_name = "Прочие пароли"
            item = QListWidgetItem(entry["title"])
            badge = entry_icon("*" if entry.get("entry_type") == "password" else entry["title"], self.session.document["settings"].get("accent_color", "#8864cb"))
            item.setIcon(badge)
            color = self.session.document["settings"].get("category_colors", {}).get(cid, self.session.document["settings"].get("accent_color", "#8864cb")) if cid else None
            if category == "all" and color:
                item.setForeground(QColor(color))
            item.setToolTip(category_name)
            item.setData(Qt.ItemDataRole.UserRole, entry["id"])
            self.entries.addItem(item)
            if category == "all":
                row = QWidget()
                row.setStyleSheet("background: transparent;")
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(10, 7, 10, 7)
                mark = QLabel()
                mark.setPixmap(badge.pixmap(28, 28))
                mark.setFixedSize(28, 28)
                mark.setAccessibleName("Значок записи")
                row_layout.addWidget(mark)
                labels = QVBoxLayout()
                row_layout.addLayout(labels, 1)
                labels.setSpacing(3)
                title = QLabel(entry["title"])
                title.setTextFormat(Qt.TextFormat.PlainText)
                if color:
                    title.setStyleSheet("color: " + color + "; background: transparent;")
                subtitle = QLabel(category_name)
                subtitle.setTextFormat(Qt.TextFormat.PlainText)
                subtitle.setObjectName("caption")
                subtitle.setStyleSheet("font-size: 11px; background: transparent;")
                labels.addWidget(title)
                labels.addWidget(subtitle)
                row.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                row.ensurePolished()
                item.setSizeHint(row.sizeHint() + QSize(0, 6))
                item.setText("")
                item.setIcon(QIcon())
                item.setData(Qt.ItemDataRole.AccessibleTextRole, entry["title"])
                self.entries.setItemWidget(item, row)
            if entry["id"] == self.selected_id:
                self.entries.setCurrentItem(item)
        self.entries.blockSignals(False)
        self.entry_count.setText(f"Записей: {self.entries.count()}")

    def values(self):
        values = {**{key: widget.toPlainText() if isinstance(widget, QTextEdit) else widget.text() for key, widget in self.fields.items()},
                "category": self.record_category.currentData()}
        values["old_passwords"] = ""
        additional = {key: [widget.text() for _, widget in items] for key, items in self.extra_widgets.items() if items}
        if additional:
            values["additional_fields"] = additional
        if self.password_only:
            values.update(entry_type="password", category=None, title=model.password_title(values["note"]))
        return values

    def fill_editor(self, values):
        self.loading = True
        self.password_only = values.get("entry_type") == "password"
        self.reveal.setChecked(False)
        for items in self.extra_widgets.values():
            for container, widget in items:
                widget.clear()
                container.setParent(None)
                container.deleteLater()
            items.clear()
        for reveal in self.secret_reveals.values():
            reveal.setChecked(False)
        for key, widget in self.fields.items():
            widget.setPlainText(values.get(key, "")) if isinstance(widget, QTextEdit) else widget.setText(values.get(key, ""))
            if key in model.SUGGESTION_FIELDS:
                widget.completer().model().setStringList(model.suggestions(self.session.document, key))
        additional = model.additional_fields(values)
        for key, items in additional.items():
            for value in items:
                self.add_extra_field(key, value)
        self.advanced.setChecked(bool(values.get("second_password") or any(additional.values())))
        self.reveal_passwords(False)
        self.record_category.setCurrentIndex(max(0, self.record_category.findData(values.get("category"))))
        self.editor_heading.setText(values.get("title") or ("Прочий пароль" if self.password_only else "Новая запись"))
        deleted = bool(values.get("deleted_at"))
        self.trash_button.setVisible(bool(self.selected_id) and not deleted)
        self.restore_button.setVisible(deleted)
        self.purge_button.setVisible(deleted)
        self.loading = False
        self.dirty = False
        self.set_editing(not self.selected_id)

    def clear_editor(self):
        self.selected_id = None
        item = self.categories.currentItem()
        cid = item.data(Qt.ItemDataRole.UserRole) if item else None
        self.fill_editor({"category": cid if cid in self.session.document["categories"] else None,
                          "entry_type": "password" if cid == "other-passwords" else "account"})

    def leave_editor(self):
        if not self.dirty:
            return True
        result = QMessageBox.question(self, "Незавершённые изменения", "Сохранить изменения?", QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        if result == QMessageBox.StandardButton.Cancel:
            return False
        if result == QMessageBox.StandardButton.Save:
            self.save()
        elif self.session.document["drafts"]:
            self.session.mutate(lambda doc: doc["drafts"].clear())
        self.dirty = False
        return True

    def select_entry(self, current, previous):
        if not self.leave_editor():
            self.entries.blockSignals(True)
            self.entries.setCurrentItem(previous)
            self.entries.blockSignals(False)
            return
        if current:
            self.selected_id = current.data(Qt.ItemDataRole.UserRole)
            self.fill_editor(self.session.document["entries"][self.selected_id])

    def navigate_filter(self):
        if self.leave_editor():
            self.clear_editor()
            self.refresh_entries()

    def new_entry(self):
        if self.leave_editor():
            self.clear_editor()
            self.fields["password" if self.password_only else "title"].setFocus()

    def save(self):
        if self.selected_id and self.session.document["entries"][self.selected_id]["deleted_at"]:
            raise VaultError("Сначала восстановите запись из корзины.")
        values = self.values()
        eid = self.selected_id
        def operation(doc):
            result = model.save_entry(doc, values, eid)
            doc["drafts"].clear()
            return result
        self.selected_id = self.session.mutate(operation)
        self.dirty = False
        self.status.setText("Сохранено локально")
        self.set_editing(False)
        # Preserve list item lifetime during a selection-change signal.
        QTimer.singleShot(0, self.refresh_entries)

    def delete_entry(self):
        if self.selected_id and self.leave_editor():
            self.session.mutate(lambda doc: model.trash(doc, self.selected_id))
            self.clear_editor()
            self.refresh_entries()

    def restore_entry(self):
        if self.selected_id:
            self.session.mutate(lambda doc: model.restore(doc, self.selected_id))
            self.clear_editor()
            self.refresh_entries()

    def purge_entry(self):
        if self.selected_id and QMessageBox.question(self, "Удаление", "Удалить запись из актуального состояния навсегда? Старые копии могут её содержать.") == QMessageBox.StandardButton.Yes:
            self.session.mutate(lambda doc: model.purge(doc, self.selected_id))
            self.clear_editor()
            self.refresh_entries()

    def empty_trash(self):
        if not self.leave_editor():
            return
        count = sum(bool(entry["deleted_at"]) for entry in self.session.document["entries"].values())
        if not count:
            return
        if QMessageBox.question(self, "Очистить корзину", f"Удалить все записи из корзины ({count}) навсегда? Поиск не ограничивает очистку. Прежние резервные копии могут содержать эти записи.") != QMessageBox.StandardButton.Yes:
            return
        self.session.mutate(model.empty_trash)
        self.clear_editor()
        self.refresh_entries()

    def add_category(self, parent_id=None):
        if not self.leave_editor():
            return
        name, ok = QInputDialog.getText(self, "Категория", "Название")
        if ok:
            self.session.mutate(lambda doc: model.category(doc, name, parent_id=parent_id))
            self.refresh_categories()
            self.clear_editor()
            self.refresh_entries()

    def rename_category(self):
        item = self.categories.currentItem()
        cid = item.data(Qt.ItemDataRole.UserRole) if item else None
        if cid not in self.session.document["categories"] or not self.leave_editor():
            return
        name, ok = QInputDialog.getText(self, "Категория", "Новое название", text=self.session.document["categories"][cid])
        if ok:
            self.session.mutate(lambda doc: model.category(doc, name, cid))
            self.refresh_categories()
            self.clear_editor()
            self.refresh_entries()

    def remove_category(self):
        item = self.categories.currentItem()
        cid = item.data(Qt.ItemDataRole.UserRole) if item else None
        if cid in self.session.document["categories"] and self.leave_editor():
            if QMessageBox.question(self, "Категория", "Удалить категорию? Её записи перейдут в «Без категории», подкатегории сохранятся на уровень выше.") != QMessageBox.StandardButton.Yes:
                return
            self.session.mutate(lambda doc: model.delete_category(doc, cid))
            self.refresh_categories()
            self.clear_editor()
            self.refresh_entries()

    def color_category(self):
        item = self.categories.currentItem()
        cid = item.data(Qt.ItemDataRole.UserRole) if item else None
        if cid not in self.session.document["categories"] or not self.leave_editor():
            return
        color = QColorDialog.getColor(QColor(self.session.document["settings"].get("category_colors", {}).get(cid, self.session.document["settings"].get("accent_color", "#8864cb"))), self, "Цвет категории")
        if color.isValid() and self.session.unlocked:
            self.session.mutate(lambda doc: doc["settings"].setdefault("category_colors", {}).update({cid: color.name()}))
            self.refresh_categories()
            self.clear_editor()
            self.refresh_entries()

    def lock_vault(self):
        self.cloud.pause()
        if not self.session.unlocked:
            self.master.clear()
            for dialog in self.findChildren(QDialog):
                dialog.reject()
            if hasattr(self, "toast_label"):
                self.toast_label.hide()
            return
        if hasattr(self, "toast_label"):
            self.toast_label.hide()
        try:
            if self.dirty:
                values, key = self.values(), self.selected_id or "new"
                self.session.mutate(lambda doc: doc["drafts"].update({key: values}))
        except (VaultError, OSError):
            # Lock takes priority over leaving secrets visible after disk failure.
            failed = True
        else:
            failed = False
        self.loading = True
        self.entries.blockSignals(True)
        self.categories.blockSignals(True)
        self.record_category.blockSignals(True)
        for widget in self.fields.values():
            if isinstance(widget, QLineEdit) and widget.completer():
                widget.completer().popup().hide()
                widget.completer().model().setStringList([])
            widget.clear()
        for items in self.extra_widgets.values():
            for _, widget in items:
                widget.clear()
            items.clear()
        # Nested modal event loops must not keep secrets visible after session lock.
        for dialog in self.findChildren(QDialog):
            for widget in dialog.findChildren(QLineEdit):
                widget.clear()
            for widget in dialog.findChildren(QTextEdit):
                widget.clear()
            for widget in dialog.findChildren(QTableWidget):
                widget.clear()
            dialog.reject()
        self.entries.clear()
        self.categories.clear()
        self.editor_heading.clear()
        self.record_category.clear()
        self.clear_clipboard()
        self.session.lock()
        self.selected_id = None
        self.dirty = False
        self.fields = {}
        self.show_locked()
        self.loading = False
        if failed:
            QMessageBox.warning(self, "Черновик не сохранён", "Не удалось записать черновик. Хранилище заблокировано; незавершённый ввод утрачен. Проверьте диск.")

    def copy_password(self, field="password"):
        text = self.fields[field].text()
        if text:
            self.clipboard_secret = text
            QApplication.clipboard().setText(text)
            self.clip_timer.start(5 * 60 * 1000)

    def clear_clipboard(self):
        if self.clipboard_secret is not None and QApplication.clipboard().text() == self.clipboard_secret:
            QApplication.clipboard().clear()
        self.clipboard_secret = None
        self.clip_timer.stop()

    def generator_dialog(self, into_editor=False):
        dialog = QDialog(self)
        dialog.setWindowTitle("Генератор паролей")
        form = QFormLayout(dialog)
        saved = self.generator_options
        length, count = NumberInput(), NumberInput()
        length.setRange(8, 128)
        length.setValue(saved["length"])
        count.setRange(1, 100)
        count.setValue(saved["count"])
        form.addRow("Длина", length)
        form.addRow("Количество", count)
        checks = {}
        for key, label in [("lower", "a–z"), ("upper", "A–Z"), ("digits", "0–9"), ("symbols", "Спецсимволы"), ("exclude_similar", "Исключить похожие")]:
            box = QCheckBox(label)
            box.setChecked(saved[key])
            checks[key] = box
            form.addRow(box)
        output = QTextEdit()
        output.setReadOnly(True)
        form.addRow(output)
        def run():
            options = GeneratorOptions(length.value(), count.value(), **{k: v.isChecked() for k, v in checks.items()})
            passwords = generate(options)
            self.generator_options = asdict(options)
            output.setPlainText("\n".join(passwords))
        actions = QHBoxLayout()
        button("Сгенерировать", lambda: self.safe(run), actions)
        if into_editor:
            def use():
                if output.toPlainText():
                    self.fields["password"].setText(output.toPlainText().splitlines()[0])
                    dialog.accept()
            button("Вставить первый", use, actions)
        button("Закрыть", dialog.reject, actions)
        form.addRow(actions)
        dialog.exec()
        output.clear()
        dialog.deleteLater()

    def import_json(self):
        if not self.leave_editor():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Импорт старого JSON", "", "JSON (*.json)")
        if not path:
            return
        rows = preview_legacy(read_bounded(path))
        dialog = QDialog(self)
        dialog.setWindowTitle("Предпросмотр импорта — пароли скрыты")
        dialog.resize(800, 450)
        layout = QVBoxLayout(dialog)
        table = QTableWidget(len(rows), 5)
        keys = ["title", "username", "email", "phone", "password"]
        table.setHorizontalHeaderLabels([LABELS[k] for k in keys])
        for i, row in enumerate(rows):
            for j, key in enumerate(keys):
                item = QTableWidgetItem("••••••" if key == "password" and row[key] else row[key])
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(i, j, item)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(table)
        actions = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        actions.accepted.connect(dialog.accept)
        actions.rejected.connect(dialog.reject)
        layout.addWidget(actions)
        if dialog.exec() == QDialog.DialogCode.Accepted and self.session.unlocked:
            def operation(doc):
                for row in rows:
                    model.save_entry(doc, row)
            self.session.mutate(operation)
            self.clear_editor()
            self.refresh_entries()
        table.clear()
        dialog.deleteLater()

    def export_filename(self):
        import re
        name = self.session.document["settings"].get("vault_name", "Main")
        return re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name).rstrip('. ') + "-vault-export.pmvault"

    def export(self):
        if not self.leave_editor():
            return
        destination, _ = QFileDialog.getSaveFileName(self, "Зашифрованный экспорт", self.export_filename(), "Хранилище (*.pmvault)")
        if destination:
            self.session.store.export(destination)

    def backups(self):
        if not self.leave_editor():
            return
        count = len(self.session.store.snapshots())
        if count < 2:
            raise VaultError("Предыдущих состояний пока нет.")
        index, ok = QInputDialog.getInt(self, "Восстановление данных", "Номер копии (1 — предыдущая)", 1, 1, count - 1)
        if not ok:
            return
        prior = model.validate(self.session.access.decode(read_bounded(self.session.store.snapshots()[index])))
        diff = model.backup_diff(self.session.document, prior)
        text = f"Добавится записей: {diff['added']}; исчезнет: {diff['removed']}; изменится: {diff['changed']}.\nКатегории изменятся: {'да' if diff['categories_changed'] else 'нет'}.\nТекущее состояние будет сохранено как резервное. Восстановить?"
        if QMessageBox.question(self, "Различия", text) == QMessageBox.StandardButton.Yes:
            self.session.document = self.session.store.restore_backup(self.session.access, self.session.document, index)
            self.refresh_categories()
            self.clear_editor()
            self.refresh_entries()

    def warn_exports(self):
        return QMessageBox.question(self, "Изменение доступа", "Защита восьми управляемых копий будет обновлена. Экспорты, скачанные файлы и сохранённые исходники в damaged/sync-blocked не меняются и могут требовать прежних секретов. Продолжить?") == QMessageBox.StandardButton.Yes

    def resolve_conflicts(self):
        from .sync import SyncEngine
        from .sync_state import conflicts
        if not self.leave_editor(): return
        metadata = self.session.document["sync"]
        pending = conflicts(metadata["state"]) if metadata else {}
        if not pending:
            QMessageBox.information(self, "Конфликты", "Неразрешённых конфликтов нет.")
            return
        key = next(iter(pending))
        color_conflict = key.startswith("category_color:")
        variants = pending[key]
        dialog = QDialog(self)
        dialog.setWindowTitle("Выберите вариант — остальные сохраняются до подтверждения")
        dialog.resize(720, 600)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Ни время изменения, ни это устройство не выбирают победителя автоматически."))
        if color_conflict:
            cid = key.split(":")[1]
            layout.addWidget(QLabel("Цвет категории: " + model.category_path(self.session.document, cid)))
        choices = QListWidget()
        layout.addWidget(choices)
        details = QTextEdit()
        details.setReadOnly(True)
        layout.addWidget(details)
        reveal = QCheckBox("Показать пароль выбранного варианта")
        layout.addWidget(reveal)
        dots = sorted(variants)
        for i, dot in enumerate(dots):
            value = variants[dot]
            label = (("Цвет по умолчанию" if color_conflict else "Удалённая категория") if value is None else value if isinstance(value, str)
                     else "Окончательное удаление" if "purged_at" in value
                     else value["title"] + (" (в корзине)" if value["deleted_at"] else ""))
            choices.addItem(f"Вариант {i + 1}: {label}")
        def show():
            index = choices.currentRow()
            if index < 0: return
            value = variants[dots[index]]
            if isinstance(value, dict) and "title" in value:
                text = "\n\n".join(f"{label}: {('••••••' if field in model.SECRET_FIELDS and not reveal.isChecked() else content)}" for field, label, content in model.display_fields(value, LABELS))
            elif isinstance(value, dict):
                text = "Окончательно удалено: " + value["purged_at"]
            else:
                text = value or ("Цвет по умолчанию" if color_conflict else "Категория удалена; записи сохраняются.")
            details.setPlainText(text)
        choices.currentRowChanged.connect(lambda _: show())
        reveal.toggled.connect(lambda _: show())
        choices.setCurrentRow(0)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted and self.session.unlocked:
            SyncEngine(self.session).resolve(key, dots[choices.currentRow()])
            self.refresh_categories()
            self.clear_editor()
            self.refresh_entries()
            self.status.setText("Вариант сохранён; изменение ожидает синхронизации.")
        details.clear()
        choices.clear()
        dialog.deleteLater()

    def merge_encrypted(self):
        from .crypto import unlock
        from .sync import SyncEngine
        if not self.leave_editor() or self.cloud.busy:
            return
        source, _ = QFileDialog.getOpenFileName(self, "Объединить зашифрованную версию", str(self.session.store.root / "sync-blocked"), "Хранилище (*.pmvault)")
        if not source: return
        blob = read_bounded(source)
        password = self.ask_password("Мастер-пароль выбранной версии")
        if password is None: return
        foreign, payload = unlock(blob, password)
        same = foreign.header["vault_id"] == self.session.access.header["vault_id"]
        options = ["Перенести изменения, оставить текущий доступ"]
        if same: options.append("Перенести изменения и принять доступ выбранной версии")
        choice, ok = QInputDialog.getItem(self, "Доступ после объединения", "Действие", options, editable=False)
        if not ok or not self.session.unlocked: return
        if QMessageBox.question(self, "Подтверждение объединения", "Обе версии разблокированы. Исходники будут сохранены отдельно зашифрованными. Конфликты останутся до выбора варианта. Объединить?") != QMessageBox.StandardButton.Yes:
            return
        SyncEngine(self.session).import_unlocked(blob, foreign, payload, adopt_access=choice == options[-1] and len(options) > 1)
        self.cloud.refresh_view()
        self.status.setText("Версии объединены локально. Проверьте конфликты перед синхронизацией.")

    def settings(self):
        if not self.leave_editor():
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Настройки хранилища")
        dialog.setMinimumWidth(540)
        dialog.resize(600, 740)
        outer = QVBoxLayout(dialog)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(12)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        values = self.session.document["settings"]
        def separator():
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setObjectName("settingsSeparator")
            layout.addWidget(line)
        def action(label, callback):
            control = button(label, lambda: self.safe(callback), layout)
            control.setObjectName("settingsAction")
            return control
        general_heading = QLabel("Общие")
        general_heading.setObjectName("sectionHeading")
        layout.addWidget(general_heading)
        general = QFormLayout()
        theme = QComboBox()
        theme.setObjectName("settingsTheme")
        for label, key in [("Системная", "system"), ("Светлая", "light"), ("Тёмная", "dark")]:
            theme.addItem(label, key)
        theme.setCurrentIndex(theme.findData(values["theme"]))
        minutes = NumberInput()
        minutes.setRange(1, 1440)
        minutes.setValue(values["lock_minutes"])
        customization = QLabel("Кастомизация")
        customization.setObjectName("sectionHeading")
        layout.addWidget(customization)
        appearance = QFormLayout()
        appearance.addRow("Тема", theme)
        accent = QPushButton(values.get("accent_color", "#8864cb"))
        accent.setObjectName("settingsAccent")
        def choose_accent():
            color = QColorDialog.getColor(QColor(accent.text()), dialog, "Основной цвет интерфейса")
            if color.isValid():
                accent.setText(color.name())
                accent.setStyleSheet(f"border: 2px solid {color.name()};")
        accent.clicked.connect(choose_accent)
        appearance.addRow("Основной цвет", accent)
        reset_accent = QPushButton("Фиолетовый по умолчанию")
        reset_accent.clicked.connect(lambda: accent.setText("#8864cb"))
        appearance.addRow("", reset_accent)
        layout.addLayout(appearance)
        general.addRow("Автоблокировка, минут", minutes)
        close_action = QComboBox()
        close_action.setObjectName("closeActionSetting")
        for label, key in [("Спрашивать каждый раз", "ask"), ("Закрывать в трей", "tray"), ("Полностью закрывать", "quit")]:
            close_action.addItem(label, key)
        close_action.setCurrentIndex(close_action.findData(self.preferences.close_action))
        general.addRow("При закрытии окна", close_action)
        layout.addLayout(general)
        separator()
        action("Мастер-пароль и ключ восстановления…", self.security_settings)
        separator()
        action("Google Drive — Действия", self.cloud.menu)
        action("Все копии Google Drive", self.cloud.browse_copies)
        if (self.session.store.root / "switched-vaults").exists():
            action("Архив прежних хранилищ", self.cloud.browse_archive)
        drive_status = QLabel()
        drive_status.setObjectName("driveConnectionStatus")
        layout.addWidget(drive_status)
        sync_now = action("Синхронизировать сейчас", self.cloud.sync)
        def update_status():
            if not self.session.unlocked:
                dialog.reject()
                return
            status, color = self.cloud.connection_status()
            drive_status.setText(status)
            drive_status.setStyleSheet("color: " + color + "; background: transparent; padding: 5px;")
            sync_now.setEnabled(self.cloud.connection.exists and not self.cloud.busy)
        update_status()
        status_timer = QTimer(dialog)
        status_timer.timeout.connect(update_status)
        status_timer.start(500)
        auto = QCheckBox("Автоматическая синхронизация Google Drive")
        auto.setChecked(bool(values.get("sync_minutes", 5)))
        layout.addWidget(auto)
        sync = NumberInput()
        sync.setRange(1, 1440)
        sync.setValue(values.get("sync_minutes", 5) or 5)
        sync.setEnabled(auto.isChecked())
        auto.toggled.connect(sync.setEnabled)
        form = QFormLayout()
        form.addRow("Интервал в минутах", sync)
        layout.addLayout(form)
        separator()
        name = QLineEdit(values.get("vault_name", "Main"))
        name.setMaxLength(100)
        name_form = QFormLayout()
        name_form.addRow("Имя хранилища", name)
        layout.addLayout(name_form)
        for label, callback in [("Импорт JSON", self.import_json), ("Экспорт", self.export), ("Резервные копии", self.backups), ("Конфликты синхронизации", self.resolve_conflicts), ("Объединить файл", self.merge_encrypted)]:
            action(label, callback)
        separator()
        check_updates = QCheckBox("Проверять обновления при запуске")
        check_updates.setChecked(values.get("check_updates", True))
        layout.addWidget(check_updates)
        action("Проверить обновления", lambda: self.updates.check(manual=True))
        layout.addStretch()
        def save_settings():
            if not self.session.unlocked:
                return
            from .vault_names import validate_name
            vault_name = validate_name(name.text())
            self.session.mutate(lambda doc: doc["settings"].update(vault_name=vault_name, theme=theme.currentData(), accent_color=accent.text(), lock_minutes=minutes.value(), sync_minutes=sync.value() if auto.isChecked() else 0, check_updates=check_updates.isChecked()))
            self.preferences.save_close_action(close_action.currentData())
            self.cloud.reset_schedule()
            self.apply_theme()
            self.refresh_categories()
            self.refresh_entries()
            self.vault_title.setText(vault_name)
            dialog.accept()
        button("Сохранить", lambda: self.safe(save_settings), layout).setObjectName("primary")
        dialog.exec()

    def security_settings(self):
        if not self.leave_editor():
            return
        choice, ok = QInputDialog.getItem(self, "Настройки", "Выберите действие", ["Тема", "Автоблокировка", "Синхронизация", "Сменить мастер-пароль", "Заменить ключ восстановления"], editable=False)
        if not ok:
            return
        if choice == "Тема":
            theme, ok = QInputDialog.getItem(self, "Тема", "Тема", ["Системная", "Светлая", "Тёмная"], editable=False)
            if ok:
                self.session.mutate(lambda doc: doc["settings"].update(theme={"Системная": "system", "Светлая": "light", "Тёмная": "dark"}[theme]))
                self.apply_theme()
        elif choice == "Автоблокировка":
            minutes, ok = QInputDialog.getInt(self, "Автоблокировка", "Минуты бездействия", self.session.document["settings"]["lock_minutes"], 1, 1440)
            if ok:
                self.session.mutate(lambda doc: doc["settings"].update(lock_minutes=minutes))
        elif choice == "Синхронизация":
            minutes, ok = QInputDialog.getInt(self, "Синхронизация Google Drive", "Интервал в минутах (0 — только вручную)", self.session.document["settings"].get("sync_minutes", 5), 0, 1440)
            if ok:
                self.session.mutate(lambda doc: doc["settings"].update(sync_minutes=minutes))
                self.cloud.reset_schedule()
        else:
            if self.cloud.busy:
                self.cloud.pause()
                self.status.setText("Обмен останавливается. Повторите смену секрета после завершения сетевого запроса.")
                return
            current = self.ask_password("Текущий мастер-пароль")
            if current is None or not self.warn_exports():
                return
            if choice == "Сменить мастер-пароль":
                new = self.ask_password("Новый мастер-пароль")
                if new is None:
                    return
                repeat = self.ask_password("Повторите новый мастер-пароль")
                if new != repeat:
                    raise VaultError("Мастер-пароли не совпадают.")
                self.session.access = self.session.store.change_password(self.session.access, self.session.document, current, new)
            else:
                recovery = recovery_secret()
                if self.confirm_recovery(recovery):
                    self.session.access = self.session.store.rotate_recovery(self.session.access, self.session.document, current, recovery)
            if self.session.store.cleanup():
                QMessageBox.warning(self, "Очистка не завершена", "Новый доступ записан, но часть старых зашифрованных файлов пока не удалена. Старый доступ к ним может сохраняться. Повторите очистку после устранения ошибки диска.")

    def toggle_theme(self):
        dark = self._dark_theme
        self.session.mutate(lambda doc: doc["settings"].update(theme="light" if dark else "dark"))
        self.apply_theme()

    def apply_theme(self):
        theme = self.session.document["settings"]["theme"]
        QGuiApplication.styleHints().setColorScheme({"system": Qt.ColorScheme.Unknown, "light": Qt.ColorScheme.Light, "dark": Qt.ColorScheme.Dark}[theme])
        dark = theme == "dark" or (theme == "system" and QGuiApplication.styleHints().colorScheme() != Qt.ColorScheme.Light)
        self._dark_theme = dark
        self.setStyleSheet(stylesheet(dark, self.session.document["settings"].get("accent_color", "#8864cb")))
        self.theme_button.setIcon(navigation_icon("sun" if dark else "moon", "#a09cb0" if dark else "#706a7c"))
        muted = "#a09cb0" if dark else "#706a7c"
        for index in range(self.categories.count()):
            item = self.categories.item(index)
            kind = item.data(Qt.ItemDataRole.UserRole)
            if kind in ("all", None, "other-passwords", "trash"):
                item.setIcon(navigation_icon({"all": "key", None: "folder", "other-passwords": "asterisk", "trash": "trash"}[kind], muted))
            elif kind == "category-heading":
                item.setForeground(QColor(muted))

    def choose_close_action(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Закрытие приложения")
        dialog.setObjectName("closeChoice")
        dialog.setMinimumWidth(420)
        layout = QVBoxLayout(dialog)
        tray_available = QSystemTrayIcon.isSystemTrayAvailable()
        layout.addWidget(QLabel("Закрыть в трей или полностью?" if tray_available else "Системный трей недоступен. Закрыть приложение полностью?"))
        note = QLabel("В трее хранилище будет заблокировано. Для возвращения нажмите значок замка рядом с часами." if tray_available else "Можно полностью выйти или отменить закрытие.")
        note.setWordWrap(True)
        layout.addWidget(note)
        remember = QCheckBox("Не спрашивать больше")
        remember.setObjectName("rememberCloseAction")
        layout.addWidget(remember)
        controls = QHBoxLayout()
        chosen = []
        def select(value):
            chosen.append(value)
            dialog.accept()
        tray = button("В трей", lambda: select("tray"), controls)
        tray.setEnabled(tray_available)
        tray.setObjectName("primary")
        tray.setAutoDefault(False)
        tray.setDefault(tray_available)
        close = button("Закрыть", lambda: select("quit"), controls)
        close.setAutoDefault(False)
        cancel = button("Отмена", dialog.reject, controls)
        cancel.setAutoDefault(False)
        cancel.setDefault(not tray_available)
        layout.addLayout(controls)
        self._asking_close = True
        try:
            accepted = dialog.exec() == QDialog.DialogCode.Accepted
        finally:
            self._asking_close = False
        return (chosen[0], remember.isChecked()) if accepted and chosen else (None, False)

    def ensure_tray(self):
        if self.tray is not None:
            return
        self.tray = QSystemTrayIcon(application_icon(), self)
        self.tray.setToolTip("Password Manager")
        menu = QMenu(self)
        menu.addAction("Открыть").triggered.connect(self.restore_from_tray)
        menu.addAction("Заблокировать").triggered.connect(self.lock_vault)
        menu.addSeparator()
        menu.addAction("Выйти").triggered.connect(self.quit_application)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.restore_from_tray() if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick) else None)

    def restore_from_tray(self):
        self.show_saved_window()
        self.raise_()
        self.activateWindow()
        if self.tray is not None:
            self.tray.hide()

    def quit_application(self):
        self._force_quit = True
        self._pending_close_action = "quit"
        self.close()

    def closeEvent(self, event):
        if self._asking_close:
            event.ignore()
            return
        if self._pending_close_action is None:
            action = "quit" if self._force_quit else self.preferences.close_action
            if action == "ask":
                action, self._close_remember = self.choose_close_action()
            if action is None:
                event.ignore()
                return
            self._pending_close_action = action
        if self._pending_close_action == "tray" and not QSystemTrayIcon.isSystemTrayAvailable():
            self._pending_close_action = None
            self._close_remember = False
            action, remember = self.choose_close_action()
            if action != "quit":
                event.ignore()
                return
            self._pending_close_action = "quit"
            self._close_remember = remember
        if self.updates.busy:
            self.lock_vault()
            self.updates.cancel.set()
            event.ignore()
            QTimer.singleShot(200, self.close)
            return
        if self.cloud.busy:
            self.lock_vault()
            self.cloud.pause()
            event.ignore()
            QTimer.singleShot(200, self.close)
            return
        if self.session.unlocked:
            try:
                if not self.leave_editor():
                    self._pending_close_action = None
                    self._force_quit = False
                    self._close_remember = False
                    event.ignore()
                    return
            except (VaultError, OSError):
                self.error(sys.exception())
                self._pending_close_action = None
                event.ignore()
                return
        if self._close_remember:
            try:
                self.preferences.save_close_action(self._pending_close_action)
            except OSError:
                self.error(sys.exception())
                self._pending_close_action = None
                self._close_remember = False
                event.ignore()
                return
            self._close_remember = False
        self.remember_window_mode()
        self.save_window_mode()
        if self._pending_close_action == "tray":
            self.lock_vault()
            self.ensure_tray()
            QApplication.instance().setQuitOnLastWindowClosed(False)
            self.tray.show()
            self._restoring_window = True
            try:
                self.hide()
            finally:
                self._restoring_window = False
            self._pending_close_action = None
            event.ignore()
            return
        self.clear_clipboard()
        self.cloud.pause()
        self.session.lock()
        if os.name == "nt":
            import ctypes
            from ctypes.wintypes import HWND, BOOL
            unregister = ctypes.windll.wtsapi32.WTSUnRegisterSessionNotification
            unregister.argtypes, unregister.restype = [HWND], BOOL
            unregister(int(self.winId()))
        self.session.store.close()
        if self.tray is not None:
            self.tray.hide()
        QApplication.instance().setQuitOnLastWindowClosed(True)
        event.accept()


def configure_app(app):
    app.setApplicationName("PersonalPasswordManager")
    app.setWindowIcon(application_icon())
    if os.name == "nt":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Ramaifs.PasswordManager")
    app.setStyle("Fusion")
    translator = QTranslator(app)
    if translator.load("qtbase_ru", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)
    app._russian_translator = translator


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from .smoke import run
        return run(Path(sys.argv[2]))
    app = QApplication(sys.argv)
    configure_app(app)
    from .paths import data_root
    root = data_root()
    try:
        store = Store(root)
        window = Window(store)
    except (VaultError, OSError) as error:
        QMessageBox.critical(None, "Менеджер паролей", str(error) if isinstance(error, VaultError) else "Не удалось открыть каталог данных.")
        return 1
    # Never allow Qt callback tracebacks to dump locals or user input.
    def exception_hook(kind, error, traceback):
        window.error(error)
    sys.excepthook = exception_hook
    window.show_saved_window()
    return app.exec()
