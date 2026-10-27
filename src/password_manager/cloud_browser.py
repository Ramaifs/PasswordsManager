"""Owned native dialogs for browsing ciphertext copies and inspecting a decoded copy."""
import re
import time
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame, QListWidget, QTextEdit, QCheckBox, QFileDialog)

from .cloud_backups import group_copies, display_time
from . import model
from .storage import export_blob


class CloudCopiesDialog(QDialog):
    def __init__(self, window, copies, last_vault):
        super().__init__(window)
        self.setObjectName("cloudCopies")
        self.setWindowTitle("Копии в Google Drive")
        self.resize(820, 640)
        self.selected_copy = None
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Новые копии показаны первыми. Время сохранения указано в UTC."))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        rows = QVBoxLayout(content)
        latest, others = group_copies(copies, last_vault)
        if latest:
            heading = QLabel("Последнее открытое хранилище")
            heading.setObjectName("lastOpenedHeading")
            heading.setProperty("accentHeading", True)
            rows.addWidget(heading)
            self.add_copy(rows, latest, pinned=True)
        if others:
            rows.addWidget(QLabel("Все резервные копии"))
            for copy in others:
                self.add_copy(rows, copy)
        if not copies:
            rows.addWidget(QLabel("В Google Drive пока нет доступных копий хранилищ."))
        rows.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        close = QPushButton("Закрыть")
        close.clicked.connect(self.reject)
        layout.addWidget(close)

    def add_copy(self, layout, copy, pinned=False):
        row = QFrame()
        row.setObjectName("lastOpenedCopy" if pinned else "cloudCopy")
        row.setProperty("copyId", copy["id"])
        if pinned:
            row.setProperty("accentPanel", True)
        line = QHBoxLayout(row)
        labels = QVBoxLayout()
        for value in [copy.get("vaultName") or copy.get("name") or "Хранилище", display_time(copy), copy.get("name", "")]:
            label = QLabel(value)
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            labels.addWidget(label)
        line.addLayout(labels, 1)
        open_button = QPushButton("Открыть")
        def select():
            self.selected_copy = copy
            self.accept()
        open_button.clicked.connect(select)
        line.addWidget(open_button)
        layout.addWidget(row)


class CloudPreviewDialog(QDialog):
    def __init__(self, window, copy, access, document):
        super().__init__(window)
        self.window, self.access, self.document = window, access, document
        self.switch_requested = False
        self.setObjectName("cloudPreview")
        self.setWindowTitle("Просмотр копии Google Drive")
        self.resize(850, 680)
        layout = QVBoxLayout(self)
        title = QLabel(document["settings"].get("vault_name") or copy.get("vaultName") or "Хранилище")
        title.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(title)
        layout.addWidget(QLabel(display_time(copy)))
        layout.addWidget(QLabel("Просмотр копии · изменения доступны после переключения"))
        self.entries = QListWidget()
        self.records = sorted(document["entries"].values(), key=lambda entry: entry["title"].casefold())
        for entry in self.records:
            self.entries.addItem(entry["title"] + (" · В корзине" if entry["deleted_at"] else ""))
        layout.addWidget(self.entries, 1)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        layout.addWidget(self.details, 1)
        self.reveal = QCheckBox("Показать пароль выбранной записи")
        layout.addWidget(self.reveal)
        self.entries.currentRowChanged.connect(self.show_record)
        self.reveal.toggled.connect(self.show_record)
        controls = QHBoxLayout()
        export = QPushButton("Экспорт .pmvault")
        export.clicked.connect(lambda: window.safe(self.export))
        switch = QPushButton("Переключиться на эту копию")
        switch.setObjectName("primary")
        switch.clicked.connect(self.request_switch)
        close = QPushButton("Закрыть")
        close.clicked.connect(self.reject)
        for button in (export, switch, close):
            controls.addWidget(button)
        layout.addLayout(controls)
        if self.records:
            self.entries.setCurrentRow(0)
        self.idle_timer = QTimer(self)
        self.idle_timer.timeout.connect(self.check_idle)
        self.idle_timer.start(1000)

    def check_idle(self):
        if self.document and time.monotonic() - self.window.last_activity >= self.document["settings"]["lock_minutes"] * 60:
            self.window.lock_vault()

    def show_record(self, *_):
        index = self.entries.currentRow()
        if not 0 <= index < len(self.records):
            self.details.clear()
            return
        entry = self.records[index]
        labels = [("title", "Название"), ("site", "Сайт"), ("username", "Логин"), ("email", "Почта"), ("phone", "Телефон"), ("password", "Пароль"), ("second_password", "Второй пароль (2FA)"), ("old_passwords", "Старые пароли"), ("note", "Заметка")]
        labels = dict((field, label) for field, label in labels if field != "old_passwords")
        lines = [label + ": " + ("••••••" if field in model.SECRET_FIELDS and not self.reveal.isChecked() else value) for field, label, value in model.display_fields(entry, labels)]
        lines.append("Категория: " + (model.category_path(self.document, entry["category"]) if entry["category"] else "Без категории"))
        self.details.setPlainText("\n\n".join(lines))

    def export(self):
        name = re.sub(r'[<>:"/\\|?*]', '_', self.document["settings"].get("vault_name", "Main"))
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт копии", name + "-vault-export.pmvault", "Хранилище (*.pmvault)")
        if path:
            export_blob(path, self.access.encode(self.document))
            self.window.toast("Зашифрованная копия экспортирована")

    def request_switch(self):
        self.switch_requested = True
        self.accept()

    def clear(self):
        self.idle_timer.stop()
        self.details.clear()
        self.entries.clear()
        self.records = []
        self.document = self.access = None
