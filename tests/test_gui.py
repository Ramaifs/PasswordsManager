import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox, QLineEdit, QDialog, QVBoxLayout, QTextEdit

from password_manager.app import Window
from password_manager.storage import Store

PASSWORD = "GUI fictional password phrase"

def test_sidebar_context_actions_and_nested_categories(window):
    from password_manager import model
    from PySide6.QtWidgets import QPushButton, QToolButton
    root = window.session.mutate(lambda doc: model.category(doc, 'Work'))
    child = window.session.mutate(lambda doc: model.category(doc, 'Mail', parent_id=root))
    window.refresh_categories()
    assert window.categories.item(3).data(__import__('PySide6').QtCore.Qt.ItemDataRole.UserRole) == child
    assert '> ' in window.categories.item(3).text()
    assert [action.text() for action in window.category_menu().actions()] == ['Создать категорию']
    labels = [action.text() for action in window.category_menu(root).actions()]
    assert all(label in labels for label in ['Создать подкатегорию','Переименовать','Поменять цвет','Удалить категорию'])
    sidebar = window.categories.parentWidget()
    buttons = [button.text() for button in sidebar.findChildren(QPushButton)]
    assert buttons == ['Настройки']
    assert not sidebar.findChildren(QToolButton)


def test_all_entries_category_color_caption_and_named_export(window):
    from password_manager import model
    from PySide6.QtWidgets import QLabel
    from PySide6.QtCore import Qt
    cid = window.session.mutate(lambda doc: model.category(doc, 'Работа'))
    window.session.mutate(lambda doc: doc['settings'].update(vault_name='Main', category_colors={cid: '#24aabb'}))
    window.session.mutate(lambda doc: model.save_entry(doc, {'title': 'Почта', 'category': cid}))
    window.refresh_categories()
    window.categories.setCurrentRow(0)
    window.refresh_entries()
    item = window.entries.item(0)
    assert item.foreground().color().name() == '#24aabb'
    assert [label.text() for label in window.entries.itemWidget(item).findChildren(QLabel)] == ['Почта', 'Работа']
    window.show()
    QApplication.processEvents()
    assert all(label.height() >= label.fontMetrics().height() for label in window.entries.itemWidget(item).findChildren(QLabel))
    assert window.export_filename() == 'Main-vault-export.pmvault'
    window.session.mutate(lambda doc: model.delete_category(doc, cid))
    window.refresh_entries()
    assert window.entries.item(0).toolTip() == 'Без категории'


def test_settings_order_separators_and_google_status(window, monkeypatch):
    from PySide6.QtWidgets import QPushButton, QFrame
    from types import SimpleNamespace
    from password_manager.sync import state_id
    from password_manager.sync_state import seed
    def inspect(dialog):
        labels = [button.text() for button in dialog.findChildren(QPushButton)]
        assert labels.index('Google Drive — Действия') < labels.index('Синхронизировать сейчас')
        assert dialog.findChild(QLabel, 'driveConnectionStatus').text() == 'Google Drive — не подключен'
        assert dialog.findChild(__import__('PySide6').QtWidgets.QComboBox, 'settingsTheme') is not None
        assert len([line for line in dialog.findChildren(QFrame) if line.objectName() == 'settingsSeparator']) >= 3
        assert next(b for b in dialog.findChildren(QPushButton) if b.text().startswith('Мастер-пароль')).objectName() == 'settingsAction'
    from PySide6.QtWidgets import QLabel
    monkeypatch.setattr(QDialog, 'exec', inspect)
    window.settings()
    monkeypatch.setattr(window.cloud, 'connection', SimpleNamespace(exists=True))
    assert 'Требует' in window.cloud.connection_status()[0]
    state = seed(window.session.document, window.session.actor)
    window.session.document['sync'] = {'state': state, 'pending': None, 'published': state_id(window.session.access, state), 'seen': {}}
    assert window.cloud.connection_status() == ('Google Drive — Подключен', '#2a9d59')


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, tmp_path, monkeypatch):
    store = Store(tmp_path / "gui")
    widget = Window(store)
    widget.updates.scheduled = True
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.No)
    widget.session.access, widget.session.document, _ = store.create(PASSWORD)
    widget.build_editor()
    yield widget
    widget.dirty = False
    widget.close()
    app.processEvents()


def test_crud_lock_draft_and_resume(window, monkeypatch):
    window.fields["title"].setText("GUI test record")
    window.fields["email"].setText("gui@example.invalid")
    window.fields["password"].setText("GUI-SECRET-MARKER")
    window.save()
    eid = window.selected_id
    assert window.session.store.open(PASSWORD)[1]["entries"][eid]["email"] == "gui@example.invalid"
    assert window.fields["password"].echoMode() == QLineEdit.EchoMode.Password
    window.fields["note"].setPlainText("DRAFT-MARKER")
    window.lock_vault()
    assert not window.session.unlocked and window.session.document is None
    assert window.session.store.open(PASSWORD)[1]["drafts"][eid]["note"] == "DRAFT-MARKER"
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    window.master.setText(PASSWORD)
    window.open_or_create()
    assert window.fields["note"].toPlainText() == "DRAFT-MARKER" and window.dirty
    assert window.selected_id == eid


def test_clipboard_timer_preserves_new_content(window, monkeypatch):
    class Clipboard:
        content = ""
        def text(self): return self.content
        def setText(self, value): self.content = value
        def clear(self): self.content = ""
    clipboard = Clipboard()
    monkeypatch.setattr(QApplication, "clipboard", lambda: clipboard)
    window.fields["password"].setText("copied-fictional-password")
    window.copy_password()
    assert window.clip_timer.interval() == 300_000
    clipboard.setText("replacement")
    window.clear_clipboard()
    assert clipboard.text() == "replacement"
    window.copy_password()
    window.clear_clipboard()
    assert clipboard.text() == ""


def test_sync_schedule_default_custom_disabled_and_manual(window, monkeypatch):
    from types import SimpleNamespace
    import password_manager.sync_ui as sync_ui
    clock = [100.0]
    monkeypatch.setattr(sync_ui, "monotonic", lambda: clock[0])
    window.cloud.connection = SimpleNamespace(exists=True)
    calls = []
    def sync():
        calls.append(clock[0])
        window.cloud.reset_schedule()
    monkeypatch.setattr(window.cloud, "sync", sync)
    window.cloud.reset_schedule()
    clock[0] += 299
    window.cloud.auto_sync()
    assert calls == []
    clock[0] += 1
    window.cloud.auto_sync()
    assert len(calls) == 1
    window.session.document["settings"]["sync_minutes"] = 0
    clock[0] += 3600
    window.cloud.auto_sync()
    assert len(calls) == 1
    window.cloud.sync()
    assert len(calls) == 2
    window.session.document["settings"]["sync_minutes"] = 2
    clock[0] += 119
    window.cloud.auto_sync()
    assert len(calls) == 2
    clock[0] += 1
    window.cloud.auto_sync()
    assert len(calls) == 3


def test_empty_trash_is_one_commit_ignores_search_and_preserves_active(window, monkeypatch):
    from password_manager import model
    ids = []
    def seed(doc):
        for title in ('active', 'matches-only-one', 'hidden-trash'):
            eid = model.save_entry(doc, {'title': title})
            ids.append(eid)
        for eid in ids[1:]:
            model.trash(doc, eid)
    window.session.mutate(seed)
    window.refresh_categories()
    window.categories.setCurrentRow(window.categories.count() - 1)
    window.query.setText('matches-only-one')
    window.empty_trash()
    assert len(window.session.document['entries']) == 3  # cancelled
    revision = window.session.document['revision']
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Yes)
    window.empty_trash()
    assert set(window.session.document['entries']) == {ids[0]}
    assert set(window.session.document['tombstones']) == set(ids[1:])
    assert window.session.document['revision'] == revision + 1
    assert set(window.session.store.open(PASSWORD)[1]['entries']) == {ids[0]}


def test_generator_does_not_write_vault_or_request_sync(window, monkeypatch):
    from PySide6.QtWidgets import QPushButton
    observed = []
    before = window.session.document
    def forbidden(*args, **kwargs):
        raise AssertionError('Generator must not save the vault or synchronize')
    monkeypatch.setattr(window.session, 'mutate', forbidden)
    monkeypatch.setattr(window.cloud, 'sync', forbidden)
    def run_dialog(dialog):
        next(button for button in dialog.findChildren(QPushButton) if button.text() == 'Сгенерировать').click()
        observed.append(dialog.findChild(QTextEdit).toPlainText())
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(QDialog, 'exec', run_dialog)
    window.generator_dialog()
    assert len(observed[0]) == 20
    assert window.session.document is before


def test_idle_and_modal_cleanup(window):
    dialog = QDialog(window)
    layout = QVBoxLayout(dialog)
    secret = QTextEdit("MODAL-SECRET")
    layout.addWidget(secret)
    window.last_activity -= 31 * 60
    window.check_idle()
    assert not window.session.unlocked and secret.toPlainText() == ""
    assert window.centralWidget().findChildren(QLineEdit)[0].text() == ""


def test_failed_save_keeps_memory_and_editor(window, monkeypatch):
    from password_manager.errors import StorageError
    window.fields["title"].setText("unsaved")
    before = window.session.document
    def fail(*args): raise StorageError()
    monkeypatch.setattr(window.session.store, "commit", fail)
    with pytest.raises(StorageError):
        window.save()
    assert window.session.document is before and window.dirty


@pytest.mark.parametrize("recovery", [False, True])
def test_open_export_in_empty_profile(app, tmp_path, monkeypatch, recovery):
    from PySide6.QtWidgets import QFileDialog, QInputDialog
    from password_manager.crypto import Access
    from password_manager import model
    access, key = Access.create(PASSWORD)
    doc = model.new_document()
    eid = model.save_entry(doc, {"title": "export fixture", "email": "export@example.invalid"})
    exported = tmp_path / "fixture.pmvault"
    original = access.encode(doc)
    exported.write_bytes(original)
    store = Store(tmp_path / "new-profile")
    widget = Window(store)
    try:
        monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(exported), ""))
        monkeypatch.setattr(QInputDialog, "getText", lambda *args: (key, True))
        monkeypatch.setattr(widget, "ask_password", lambda *args: "new fictional master phrase")
        monkeypatch.setattr(widget, "warn_exports", lambda: True)
        widget.master.setText(PASSWORD if not recovery else "")
        widget.open_export(recovery=recovery)
        password = "new fictional master phrase" if recovery else PASSWORD
        assert store.open(password)[1]["entries"][eid]["email"] == "export@example.invalid"
        assert store.open(key, recovery=True)[1]["entries"][eid]["title"] == "export fixture"
        assert exported.read_bytes() == original
    finally:
        widget.dirty = False
        widget.close()
        app.processEvents()


def test_sync_worker_never_applies_after_lock(window, app):
    from threading import Event
    from PySide6.QtCore import QThread
    from PySide6.QtTest import QTest
    release = Event()
    applied = []
    window.cloud._start(lambda: (release.wait(2), b"encrypted")[1], lambda result: applied.append(result))
    window.lock_vault()
    release.set()
    deadline = __import__('time').monotonic() + 5
    while window.cloud.busy and __import__('time').monotonic() < deadline:
        app.processEvents()
        QTest.qWait(10)
    assert not window.cloud.busy and not applied and not window.session.unlocked


def test_sync_callback_runs_on_gui_thread(window, app):
    from PySide6.QtCore import QThread
    from PySide6.QtTest import QTest
    observed = []
    window.cloud._start(lambda: b"encrypted", lambda _: observed.append(QThread.currentThread() == app.thread()))
    deadline = __import__('time').monotonic() + 5
    while window.cloud.busy and __import__('time').monotonic() < deadline:
        app.processEvents()
        QTest.qWait(10)
    assert observed == [True]


@pytest.mark.skipif(os.name != "nt", reason="Windows native message structure")
@pytest.mark.parametrize("message,parameter", [(0x2B1, 7), (0x218, 4)])
def test_native_notifications_lock_before_return(window, message, parameter):
    import ctypes
    from ctypes.wintypes import MSG
    event = MSG()
    event.message, event.wParam = message, parameter
    window.native_filter.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(event))
    assert not window.session.unlocked


def test_create_with_eight_character_master(app, tmp_path, monkeypatch):
    store = Store(tmp_path / "eight-character-gui")
    widget = Window(store)
    try:
        assert widget.master.placeholderText() == "Мастер-пароль (8–128 символов)"
        monkeypatch.setattr(widget, "ask_password", lambda *args: "12345678")
        monkeypatch.setattr(widget, "confirm_recovery", lambda *args: True)
        widget.master.setText("12345678")
        widget.open_or_create()
        assert widget.session.unlocked
        assert store.open("12345678")[1] == widget.session.document
    finally:
        widget.dirty = False
        widget.close()
        app.processEvents()
