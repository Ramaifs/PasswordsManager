import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox, QLineEdit, QDialog, QVBoxLayout, QTextEdit

from password_manager.app import Window
from password_manager.storage import Store

PASSWORD = "GUI fictional password phrase"


def test_other_passwords_editor_only_has_password_and_note_and_reopens(window):
    from PySide6.QtCore import Qt
    from password_manager import model
    item = next(window.categories.item(i) for i in range(window.categories.count()) if window.categories.item(i).data(Qt.ItemDataRole.UserRole) == 'other-passwords')
    window.categories.setCurrentItem(item)
    window.new_entry()
    visible = [key for key, widget in window.fields.items() if not window.field_groups[widget][0].isHidden()]
    assert visible == ['password', 'note']
    assert window.field_groups[window.record_category][0].isHidden()
    window.fields['password'].setText('Other password fixture')
    window.fields['note'].setPlainText('Door lock')
    assert window.editor_heading.text() == 'Door lock'
    window.save()
    eid = window.selected_id
    record = window.session.store.open(PASSWORD)[1]['entries'][eid]
    assert record['entry_type'] == 'password' and record['title'] == 'Door lock'
    window.refresh_entries()
    assert window.entries.count() == 1
    window.entries.setCurrentRow(0)
    window.edit_entry()
    assert [key for key, widget in window.fields.items() if not window.field_groups[widget][0].isHidden()] == ['password', 'note']
    window.fields['note'].setPlainText('Updated door lock')
    window.lock_vault()
    assert window.session.store.open(PASSWORD)[1]['drafts'][eid]['entry_type'] == 'password'


def test_autocomplete_uses_vault_values_and_clears_when_locked(window):
    from password_manager import model
    values = {'email':'fixture@example.invalid', 'phone':'+79991234567', 'username':'fixture-user', 'site':'example.invalid'}
    window.session.mutate(lambda doc: model.save_entry(doc, {'title':'Existing', **values}))
    window.new_entry()
    completers = []
    for field, value in values.items():
        completer = window.fields[field].completer()
        completers.append(completer)
        assert completer.model().stringList() == [value]
        completer.setCompletionPrefix(value[:3])
        assert completer.currentCompletion() == value
        completer.activated.emit(value)
        assert window.fields[field].text() == value
    assert window.fields['password'].completer() is None
    window.dirty = False
    window.lock_vault()
    for completer in completers:
        assert completer.model().stringList() == []


def test_search_box_filters_records_by_formatted_phone(window):
    from password_manager import model
    from PySide6.QtCore import Qt
    first = window.session.mutate(lambda doc: model.save_entry(doc, {'title': 'Phone account', 'phone': '+7 (999) 123-45-67'}))
    window.session.mutate(lambda doc: model.save_entry(doc, {'title': 'Other account', 'phone': '+1 (212) 555-0000'}))
    window.refresh_entries()
    window.query.setText('+7999')
    assert window.entries.count() == 1
    assert window.entries.item(0).data(Qt.ItemDataRole.UserRole) == first
    window.query.setText('+7999000')
    assert window.entries.count() == 0
    window.query.clear()
    assert window.entries.count() == 2


def test_extra_password_fields_mask_copy_save_reopen_and_lock(window, app):
    from password_manager.cloud_browser import CloudPreviewDialog
    window.new_entry()
    assert window.field_groups[window.fields['second_password']][0].isHidden()
    assert 'old_passwords' not in window.fields
    assert not window.advanced.isChecked()
    window.advanced.click()
    window.fields['title'].setText('Extra secrets')
    window.fields['password'].setText('PRIMARY-FICTIONAL-SECRET')
    window.fields['second_password'].setText('2FA-FICTIONAL-SECRET')
    for key in ['password', 'second_password', 'email', 'phone', 'site', 'username']:
        window.extra_buttons[key].click()
        widget = window.extra_widgets[key][0][1]
        widget.setText(key + '-ADDITIONAL-FIXTURE')
        if key in ['password', 'second_password']:
            assert widget.echoMode() == QLineEdit.EchoMode.Password
    window.reveal.setChecked(True)
    for key in ['password', 'second_password']:
        assert window.fields[key].echoMode() == QLineEdit.EchoMode.Normal
        assert window.extra_widgets[key][0][1].echoMode() == QLineEdit.EchoMode.Normal
    window.secret_copy_buttons['second_password'].click()
    assert QApplication.clipboard().text() == '2FA-FICTIONAL-SECRET'
    window.clear_clipboard()
    window.save()
    eid = window.selected_id
    opened = window.session.store.open(PASSWORD)[1]
    assert opened['entries'][eid]['additional_fields']['password'] == ['password-ADDITIONAL-FIXTURE']
    window.fill_editor(opened['entries'][eid])
    assert window.advanced.isChecked() and not window.reveal.isChecked()
    for key in ['password', 'second_password']:
        assert window.fields[key].echoMode() == QLineEdit.EchoMode.Password
        assert window.extra_widgets[key][0][1].echoMode() == QLineEdit.EchoMode.Password
    preview = CloudPreviewDialog(window, {'name': 'Fixture'}, window.session.access, opened)
    assert 'FICTIONAL-SECRET' not in preview.details.toPlainText()
    assert 'password-ADDITIONAL-FIXTURE' not in preview.details.toPlainText()
    preview.reveal.setChecked(True)
    assert '2FA-FICTIONAL-SECRET' in preview.details.toPlainText()
    assert 'password-ADDITIONAL-FIXTURE' in preview.details.toPlainText()
    preview.clear()
    preview.deleteLater()
    extra_widget = window.extra_widgets['password'][0][1]
    window.lock_vault()
    assert extra_widget.text() == ''
    assert not window.session.unlocked and not window.fields


def test_customization_saves_theme_and_accent(window, monkeypatch):
    from PySide6.QtWidgets import QPushButton, QComboBox
    def change(dialog):
        dialog.findChild(QComboBox, 'settingsTheme').setCurrentIndex(1)
        dialog.findChild(QPushButton, 'settingsAccent').setText('#007755')
        next(button for button in dialog.findChildren(QPushButton) if button.text() == 'Сохранить').click()
    monkeypatch.setattr(QDialog, 'exec', change)
    window.settings()
    saved = window.session.store.open(PASSWORD)[1]['settings']
    assert saved['theme'] == 'light' and saved['accent_color'] == '#007755'
    assert '#007755' in window.styleSheet()


def test_default_color_is_only_inside_color_picker(window, monkeypatch):
    from PySide6.QtWidgets import QPushButton, QColorDialog
    from PySide6.QtGui import QColor
    def choose(picker):
        reset = picker.findChild(QPushButton, 'accentColorDefault')
        assert reset.text() == 'по умолчанию'
        picker.setCurrentColor(QColor('#007755'))
        reset.click()
        assert picker.currentColor().name() == '#8864cb'
        return QDialog.DialogCode.Accepted
    def settings(dialog):
        assert not any(button.text() in ('по умолчанию', 'Фиолетовый по умолчанию') for button in dialog.findChildren(QPushButton))
        accent = dialog.findChild(QPushButton, 'settingsAccent')
        accent.setText('#007755')
        accent.click()
        assert accent.text() == '#8864cb'
        next(button for button in dialog.findChildren(QPushButton) if button.text() == 'Сохранить').click()
    monkeypatch.setattr(QDialog, 'exec', settings)
    monkeypatch.setattr(QColorDialog, 'exec', choose)
    window.settings()
    assert window.session.store.open(PASSWORD)[1]['settings']['accent_color'] == '#8864cb'


def test_category_sort_groups_paths_and_keeps_unsaved_editor(window):
    from password_manager import model
    from password_manager.preferences import Preferences
    from PySide6.QtCore import Qt
    def seed(doc):
        root = model.category(doc, 'Work')
        child = model.category(doc, 'Mail', parent_id=root)
        other = model.category(doc, 'Alpha')
        first = model.save_entry(doc, {'title':'Zulu', 'category':other})
        second = model.save_entry(doc, {'title':'Alpha', 'category':root})
        third = model.save_entry(doc, {'title':'Bravo', 'category':root})
        fourth = model.save_entry(doc, {'title':'Alpha', 'category':child})
        return [first, second, third, fourth]
    expected = window.session.mutate(seed)
    window.refresh_categories()
    window.refresh_entries()
    window.fields['note'].setPlainText('UNSAVED-SORT-FIXTURE')
    window.entry_sort.setCurrentIndex(window.entry_sort.findData('category'))
    assert [window.entries.item(i).data(Qt.ItemDataRole.UserRole) for i in range(window.entries.count())] == expected
    assert window.dirty and window.fields['note'].toPlainText() == 'UNSAVED-SORT-FIXTURE'
    assert Preferences(window.session.store.root).entry_sort == 'category'
    window.dirty = False


def test_ctrl_shift_selection_bulk_actions_and_delete_only_selected(window, monkeypatch):
    from password_manager import model
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    ids = window.session.mutate(lambda doc: [model.save_entry(doc, {'title':f'Fixture {index:02}'}) for index in range(5)])
    category = window.session.mutate(lambda doc: model.category(doc, 'Batch category'))
    window.refresh_categories()
    window.refresh_entries()
    window.show()
    QApplication.processEvents()
    viewport = window.entries.viewport()
    def click(index, modifier=Qt.KeyboardModifier.NoModifier):
        QTest.mouseClick(viewport, Qt.MouseButton.LeftButton, modifier, window.entries.visualItemRect(window.entries.item(index)).center())
        QApplication.processEvents()
    click(0)
    click(2, Qt.KeyboardModifier.ControlModifier)
    selected = lambda: {item.data(Qt.ItemDataRole.UserRole) for item in window.entries.selectedItems()}
    assert selected() == {ids[0], ids[2]}
    click(4, Qt.KeyboardModifier.ShiftModifier)
    chosen = selected()
    assert {ids[2], ids[3], ids[4]} <= chosen
    window.change_entries(list(chosen), 'color', '#12ab34')
    assert selected() == chosen
    window.change_entries(list(chosen), 'category', category)
    records = window.session.store.open(PASSWORD)[1]['entries']
    assert all(records[eid].get('color') == '#12ab34' and records[eid]['category'] == category for eid in chosen)
    assert all('color' not in records[eid] and records[eid]['category'] is None for eid in set(ids) - chosen)
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Yes)
    menu = window.entry_menu(list(chosen))
    next(action for action in menu.actions() if action.text() == 'Удалить пароли').trigger()
    assert {eid for eid, record in window.session.document['entries'].items() if record['deleted_at']} == chosen


def test_minus_removes_only_extra_field_renumbers_and_both_primary_copy_buttons_remain(window):
    from PySide6.QtWidgets import QPushButton, QLabel
    window.fields['title'].setText('Extra deletion fixture')
    window.fields['password'].setText('PRIMARY-FIXTURE')
    window.advanced.click()
    for value in ['REMOVE-ME', 'KEEP-ME']:
        window.add_extra_field('password', value)
    first = window.extra_widgets['password'][0][0]
    first.findChild(QPushButton, 'extraRemove').click()
    assert len(window.extra_widgets['password']) == 1
    container, control = window.extra_widgets['password'][0]
    assert control.text() == 'KEEP-ME'
    assert container.findChild(QLabel, 'extraFieldLabel').text() == 'Пароль №2'
    assert window.copy_button.text() == 'Копировать пароль'
    window.secret_copy_buttons['password'].click()
    assert QApplication.clipboard().text() == 'PRIMARY-FIXTURE'
    window.clear_clipboard()
    window.save()
    saved = window.session.store.open(PASSWORD)[1]['entries'][window.selected_id]
    assert saved['additional_fields']['password'] == ['KEEP-ME']


def test_extra_only_password_remains_visible_and_revealable(window):
    window.fields['title'].setText('Additional secret only')
    window.advanced.click()
    window.add_extra_field('password', 'EXTRA-ONLY-FIXTURE')
    window.save()
    assert not window.field_groups[window.fields['password']][0].isHidden()
    assert not window.reveal.isHidden()
    window.reveal.setChecked(True)
    assert window.extra_widgets['password'][0][1].echoMode() == QLineEdit.EchoMode.Normal


def test_bulk_clipboard_and_additional_draft_reopen(window, monkeypatch):
    from PySide6.QtCore import Qt
    window.fields['title'].setText('Draft with extras')
    window.advanced.click()
    window.extra_buttons['password'].click()
    window.extra_widgets['password'][0][1].setText('DRAFT-EXTRA-FIXTURE')
    window.lock_vault()
    assert window.session.store.open(PASSWORD)[1]['drafts']['new']['additional_fields']['password'] == ['DRAFT-EXTRA-FIXTURE']
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Yes)
    window.master.setText(PASSWORD)
    window.open_or_create()
    assert window.extra_widgets['password'][0][1].text() == 'DRAFT-EXTRA-FIXTURE'
    assert window.advanced.isChecked()
    window.dirty = False
    window.session.mutate(lambda doc: doc['drafts'].clear())
    other = next(window.categories.item(i) for i in range(window.categories.count()) if window.categories.item(i).data(Qt.ItemDataRole.UserRole) == 'other-passwords')
    window.categories.setCurrentItem(other)
    QApplication.clipboard().setText(' fixture-one \nfixture-two\r\nfixture-three')
    window.paste_button.click()
    assert window.entries.count() == 3
    assert window.session.store.open(PASSWORD)[1]['entries'] == window.session.document['entries']
    QApplication.clipboard().clear()


def test_update_dialog_downloads_and_enables_install_without_launch(window, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QPushButton, QComboBox
    from PySide6.QtTest import QTest
    import password_manager.updates as updates
    import time
    calls = []
    def download(release, root, **kwargs):
        calls.append(release)
        kwargs['progress'](1, 1)
        return {'path': tmp_path / 'fixture.exe', 'sha256': '0' * 64, 'version': release['version']}
    monkeypatch.setattr(updates, 'download_release', download)
    def inspect(dialog):
        dialog.show()
        versions = dialog.findChild(QComboBox, 'updateVersions')
        assert versions.count() == 2
        install = dialog.findChild(QPushButton, 'installUpdate')
        assert not install.isEnabled()
        next(button for button in dialog.findChildren(QPushButton) if button.text() == 'Скачать').click()
        deadline = time.monotonic() + 3
        while window.updates.busy and time.monotonic() < deadline:
            QApplication.processEvents()
            QTest.qWait(10)
        QApplication.processEvents()
        assert install.isEnabled()
        assert calls == [{'tag': 'v0.41', 'version': '0.41'}]
        versions.setCurrentIndex(1)
        assert not install.isEnabled() and window.updates.downloaded is None
        dialog.reject()
    monkeypatch.setattr(QDialog, 'exec', inspect)
    window.updates.show_versions([{'tag': 'v0.41', 'version': '0.41'}, {'tag': 'v0.40', 'version': '0.40'}])


def test_new_entry_uses_selected_category_and_subcategory(window):
    from password_manager import model
    from PySide6.QtCore import Qt
    root = window.session.mutate(lambda doc: model.category(doc, 'Work'))
    child = window.session.mutate(lambda doc: model.category(doc, 'Mail', parent_id=root))
    window.refresh_categories()
    for cid in [root, child, 'all', None, 'trash']:
        item = next(window.categories.item(i) for i in range(window.categories.count()) if window.categories.item(i).data(Qt.ItemDataRole.UserRole) == cid)
        window.categories.setCurrentItem(item)
        window.new_entry()
        assert window.record_category.currentData() == (cid if cid in (root, child) else None)
        assert not window.dirty
    window.refresh_categories(child)
    window.new_entry()
    window.fields['title'].setText('Inherited category')
    window.save()
    assert window.session.store.open(PASSWORD)[1]['entries'][window.selected_id]['category'] == child


def test_sort_preserves_unsaved_editor_and_selection(window):
    from password_manager import model
    from PySide6.QtCore import Qt
    from password_manager.preferences import Preferences
    def seed(doc):
        a = model.save_entry(doc, {'title': 'Яндекс'})
        b = model.save_entry(doc, {'title': 'Альфа'})
        doc['entries'][a]['updated_at'] = '2026-10-27T12:00:00Z'
        doc['entries'][b]['updated_at'] = '2026-10-26T12:00:00Z'
        return a, b
    a, b = window.session.mutate(seed)
    window.refresh_entries()
    ids = lambda: [window.entries.item(i).data(Qt.ItemDataRole.UserRole) for i in range(window.entries.count())]
    assert ids() == [b, a]
    window.entries.setCurrentRow(1)
    window.set_editing(True)
    window.fields['note'].setPlainText('Unsaved note')
    window.entry_sort.setCurrentIndex(1)
    assert ids() == [a, b]
    assert window.entries.currentItem().data(Qt.ItemDataRole.UserRole) == a
    assert window.selected_id == a and window.dirty
    assert window.fields['note'].toPlainText() == 'Unsaved note'
    assert Preferences(window.session.store.root).entry_sort == 'updated'
    window.dirty = False


def test_category_move_menu_excludes_descendants_and_keeps_subtree(window):
    from password_manager import model
    root = window.session.mutate(lambda doc: model.category(doc, 'Work'))
    child = window.session.mutate(lambda doc: model.category(doc, 'Mail', parent_id=root))
    other = window.session.mutate(lambda doc: model.category(doc, 'Personal'))
    window.refresh_categories()
    menu = window.category_menu(root)
    targets = next(action.menu() for action in menu.actions() if action.text() == 'Переместить в…')
    assert [a.text() for a in targets.actions()] == ['Верхний уровень', 'Personal']
    targets.actions()[1].trigger()
    assert window.session.document['category_parents'][root] == other
    assert window.session.document['category_parents'][child] == root
    menu = window.category_menu(root)
    targets = next(action.menu() for action in menu.actions() if action.text() == 'Переместить в…')
    targets.actions()[0].trigger()
    assert root not in window.session.document['category_parents']


def test_cloud_list_preview_export_and_last_opened_marker(window, monkeypatch, tmp_path):
    from password_manager.cloud_browser import CloudCopiesDialog, CloudPreviewDialog
    from password_manager.crypto import Access, unlock
    from password_manager import model
    from PySide6.QtWidgets import QLabel, QFrame, QFileDialog
    identity = window.session.access.header['vault_id']
    copies = [
        {'id':'old', 'vaultId':identity, 'name':'Old', 'modifiedAt':'2026-10-26T10:00:00Z'},
        {'id':'new', 'vaultId':identity, 'name':'New', 'modifiedAt':'2026-10-26T12:00:00Z'},
        {'id':'other', 'vaultId':'other', 'name':'Other', 'modifiedAt':'2026-10-26T13:00:00Z'},
    ]
    chooser = CloudCopiesDialog(window, copies, identity)
    assert chooser.findChild(QLabel, 'lastOpenedHeading').text() == 'Последнее открытое хранилище'
    assert [r.property('copyId') for r in chooser.findChildren(QFrame) if r.property('copyId')] == ['new', 'other', 'old']
    chooser.deleteLater()
    access, _ = Access.create('Preview fictional password')
    doc = model.new_document()
    model.save_entry(doc, {'title':'Cloud record', 'password':'PREVIEW-SECRET'})
    preview = CloudPreviewDialog(window, copies[1], access, doc)
    assert 'PREVIEW-SECRET' not in preview.details.toPlainText()
    preview.reveal.setChecked(True)
    assert 'PREVIEW-SECRET' in preview.details.toPlainText()
    exported = tmp_path / 'preview.pmvault'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(exported), ''))
    preview.export()
    assert unlock(exported.read_bytes(), 'Preview fictional password')[1] == doc
    preview.clear()
    preview.deleteLater()
    before = window.session.store.snapshots()[0].read_bytes()
    monkeypatch.setattr(window, 'ask_password', lambda *args: 'Preview fictional password')
    monkeypatch.setattr(CloudPreviewDialog, 'exec', lambda self: self.reject())
    window.cloud.preview_copy(copies[1], access.encode(doc))
    assert window.session.store.snapshots()[0].read_bytes() == before
    from password_manager.preferences import Preferences
    assert Preferences(window.session.store.root).last_opened_vault == access.header['vault_id']


def test_switch_cloud_copy_preserves_previous_vault_and_rebuilds_editor(window, monkeypatch):
    from password_manager.crypto import Access, unlock
    from password_manager import model
    original = window.session.store.snapshots()[0].read_bytes()
    access, _ = Access.create('New cloud fictional password')
    doc = model.new_document()
    eid = model.save_entry(doc, {'title':'Switched cloud record'})
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.No)
    window.cloud.switch_to_copy(access, doc)
    assert window.session.store.snapshots()[0].read_bytes() == original
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Yes)
    window.cloud.switch_to_copy(access, doc)
    assert window.session.access.header['vault_id'] == access.header['vault_id']
    assert window.entries.count() == 1
    assert window.session.document['entries'][eid]['title'] == 'Switched cloud record'
    archived = next((window.session.store.root / 'switched-vaults').glob('*/0.pmvault'))
    assert archived.read_bytes() == original
    assert unlock(archived.read_bytes(), PASSWORD)[1]['entries'] == {}


@pytest.mark.parametrize('mode', ['normal', 'maximized', 'fullscreen'])
def test_window_mode_survives_minimize_tray_and_restart(window, app, monkeypatch, mode):
    from types import SimpleNamespace
    from PySide6.QtWidgets import QSystemTrayIcon
    from PySide6.QtTest import QTest
    from password_manager.preferences import Preferences
    window.show_saved_window()
    getattr(window, {'normal': 'showNormal', 'maximized': 'showMaximized', 'fullscreen': 'showFullScreen'}[mode])()
    QTest.qWait(250)
    assert window._window_mode == mode
    window.showMinimized()
    app.processEvents()
    window.save_window_mode()
    assert Preferences(window.session.store.root).window_mode == mode
    window.preferences.close_action = 'tray'
    monkeypatch.setattr(QSystemTrayIcon, 'isSystemTrayAvailable', lambda: True)
    monkeypatch.setattr(window, 'ensure_tray', lambda: setattr(window, 'tray', SimpleNamespace(show=lambda: None, hide=lambda: None)))
    window.close()
    assert not window.isVisible()
    window.restore_from_tray()
    app.processEvents()
    assert not window.isMinimized()
    assert window.isFullScreen() == (mode == 'fullscreen')
    assert window.isMaximized() == (mode == 'maximized')
    window.quit_application()
    restored = Window(Store(window.session.store.root))
    restored.updates.scheduled = True
    try:
        restored.show_saved_window()
        QTest.qWait(250)
        assert restored._window_mode == mode
        assert restored.isFullScreen() == (mode == 'fullscreen')
        assert restored.isMaximized() == (mode == 'maximized')
    finally:
        restored.quit_application()


def test_close_dialog_enter_defaults_to_tray(window, monkeypatch):
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QPushButton, QSystemTrayIcon
    monkeypatch.setattr(QSystemTrayIcon, 'isSystemTrayAvailable', lambda: True)
    def enter():
        dialog = QApplication.activeModalWidget()
        buttons = dialog.findChildren(QPushButton)
        assert [b.text() for b in buttons] == ['В трей', 'Закрыть', 'Отмена']
        assert [b.text() for b in buttons if b.isDefault()] == ['В трей']
        assert buttons[0].objectName() == 'primary'
        QTest.keyClick(dialog, Qt.Key.Key_Return)
    QTimer.singleShot(0, enter)
    assert window.choose_close_action() == ('tray', False)


def test_number_input_and_navigation_icons(window, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QSpinBox
    from password_manager import model
    def inspect():
        dialog = QApplication.activeModalWidget()
        numbers = dialog.findChildren(QSpinBox)
        assert len(numbers) == 2
        assert all(n.lineEdit().textMargins().left() == 11 for n in numbers)
        dialog.reject()
    from PySide6.QtCore import QTimer
    QTimer.singleShot(0, inspect)
    window.settings()
    for index in [0, 1, window.categories.count() - 1]:
        assert not window.categories.item(index).icon().isNull()
    heading = window.categories.item(3)
    assert heading.text() == 'Категории'
    assert not (heading.flags() & Qt.ItemFlag.ItemIsSelectable)
    cid = window.session.mutate(lambda doc: model.category(doc, 'Work'))
    window.refresh_categories()
    window.record_category.setCurrentIndex(window.record_category.findData(cid))
    window.theme_button.click()
    first = window.session.document['settings']['theme']
    window.theme_button.click()
    assert window.session.document['settings']['theme'] != first
    assert window.record_category.currentData() == cid
    window.session.mutate(lambda doc: model.save_entry(doc, {'title': 'Почта'}))
    window.categories.setCurrentRow(1)
    window.refresh_entries()
    assert not window.entries.item(0).icon().isNull()

def test_sidebar_context_actions_and_nested_categories(window):
    from password_manager import model
    from PySide6.QtWidgets import QPushButton, QToolButton
    root = window.session.mutate(lambda doc: model.category(doc, 'Work'))
    child = window.session.mutate(lambda doc: model.category(doc, 'Mail', parent_id=root))
    window.refresh_categories()
    assert window.categories.item(5).data(__import__('PySide6').QtCore.Qt.ItemDataRole.UserRole) == child
    assert '• ' in window.categories.item(5).text()
    assert [action.text() for action in window.category_menu().actions()] == ['Создать категорию']
    labels = [action.text() for action in window.category_menu(root).actions()]
    assert all(label in labels for label in ['Создать подкатегорию','Переименовать','Поменять цвет','Удалить категорию'])
    sidebar = window.categories.parentWidget()
    buttons = [button.text() for button in sidebar.findChildren(QPushButton)]
    assert buttons == ['Настройки']
    assert [b.objectName() for b in sidebar.findChildren(QToolButton)] == ['themeToggle']


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
    assert [label.text() for label in window.entries.itemWidget(item).findChildren(QLabel)] == ['', 'Почта', 'Работа']
    window.show()
    QApplication.processEvents()
    assert all(label.height() >= label.fontMetrics().height() for label in window.entries.itemWidget(item).findChildren(QLabel))
    assert window.export_filename() == 'Main-vault-export.pmvault'
    window.session.mutate(lambda doc: model.delete_category(doc, cid))
    window.refresh_entries()
    assert window.entries.item(0).toolTip() == 'Без категории'


def test_category_arrow_click_drag_drop_and_root_move(window):
    from PySide6.QtCore import Qt, QMimeData, QPointF
    from PySide6.QtGui import QDropEvent
    from PySide6.QtTest import QTest
    from password_manager import model
    from password_manager.category_list import MIME
    a = window.session.mutate(lambda doc: model.category(doc, 'Work'))
    b = window.session.mutate(lambda doc: model.category(doc, 'Mail', parent_id=a))
    c = window.session.mutate(lambda doc: model.category(doc, 'Personal'))
    window.refresh_categories()
    window.show()
    QApplication.processEvents()
    def item(cid):
        return next(window.categories.item(i) for i in range(window.categories.count()) if window.categories.item(i).data(Qt.ItemDataRole.UserRole) == cid)
    assert '• ' in item(b).text() and '> ' not in item(b).text()
    rect = window.categories.visualItemRect(item(a))
    QTest.mouseClick(window.categories.viewport(), Qt.MouseButton.LeftButton, pos=rect.topRight() + __import__('PySide6').QtCore.QPoint(-18, rect.height() // 2))
    assert item(b).isHidden() and a in window.collapsed_categories
    rect = window.categories.visualItemRect(item(a))
    QTest.mouseClick(window.categories.viewport(), Qt.MouseButton.LeftButton, pos=rect.topRight() + __import__('PySide6').QtCore.QPoint(-18, rect.height() // 2))
    assert not item(b).isHidden()
    class Drop(QDropEvent):
        def source(self):
            return window.categories
    mime = QMimeData()
    mime.setData(MIME, a.encode('ascii'))
    target = window.categories.visualItemRect(item(c)).center()
    event = Drop(QPointF(target), Qt.DropAction.MoveAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    window.categories.dropEvent(event)
    assert event.isAccepted()
    assert window.session.document['category_parents'][a] == c
    assert window.session.document['category_parents'][b] == a
    assert window.session.store.open(PASSWORD)[1]['category_parents'][a] == c
    assert window.move_category(a, None)
    assert a not in window.session.document['category_parents']


def test_close_to_tray_remembers_choice_locks_and_restores(window, monkeypatch):
    from types import SimpleNamespace
    from PySide6.QtWidgets import QSystemTrayIcon
    from password_manager.preferences import Preferences
    events = []
    window.preferences.close_action = 'ask'
    monkeypatch.setattr(window, 'choose_close_action', lambda: ('tray', True))
    monkeypatch.setattr(QSystemTrayIcon, 'isSystemTrayAvailable', lambda: True)
    fake_tray = SimpleNamespace(show=lambda: events.append('show'), hide=lambda: events.append('hide'))
    monkeypatch.setattr(window, 'ensure_tray', lambda: setattr(window, 'tray', fake_tray))
    window.show()
    window.close()
    assert not window.isVisible() and not window.session.unlocked
    assert events == ['show']
    assert window.session.store._lock is not None
    assert Preferences(window.session.store.root).close_action == 'tray'
    window.restore_from_tray()
    assert window.isVisible() and events[-1] == 'hide'
    assert window.master.text() == ''


def test_close_choice_dialog_and_full_exit_saved(window, monkeypatch):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QPushButton, QCheckBox
    from password_manager.preferences import Preferences
    window.preferences.close_action = 'ask'
    def choose():
        dialog = QApplication.activeModalWidget()
        assert dialog.objectName() == 'closeChoice'
        box = dialog.findChild(QCheckBox, 'rememberCloseAction')
        assert not box.isChecked()
        box.setChecked(True)
        next(b for b in dialog.findChildren(QPushButton) if b.text() == 'Закрыть').click()
    QTimer.singleShot(0, choose)
    window.close()
    assert window.session.store._lock is None
    assert Preferences(window.session.store.root).close_action == 'quit'


def test_close_cancel_and_network_retry_ask_only_once(window, monkeypatch):
    window.preferences.close_action = 'ask'
    monkeypatch.setattr(window, 'choose_close_action', lambda: (None, False))
    window.show()
    window.close()
    assert window.isVisible() and window.session.unlocked
    calls = []
    monkeypatch.setattr(window, 'choose_close_action', lambda: (calls.append(True) or 'quit', False))
    window.cloud.worker = object()
    window.close()
    assert calls == [True] and window.session.store._lock is not None
    window.cloud.worker = None
    window.close()
    assert calls == [True] and window.session.store._lock is None


def test_general_settings_changes_remembered_close_action(window, monkeypatch):
    from PySide6.QtWidgets import QComboBox, QPushButton
    from password_manager.preferences import Preferences
    def save(dialog):
        selection = dialog.findChild(QComboBox, 'closeActionSetting')
        selection.setCurrentIndex(selection.findData('tray'))
        next(b for b in dialog.findChildren(QPushButton) if b.text() == 'Сохранить').click()
    monkeypatch.setattr(QDialog, 'exec', save)
    window.settings()
    assert Preferences(window.session.store.root).close_action == 'tray'


def test_unavailable_tray_offers_exit_without_hiding_or_trapping(window, monkeypatch):
    from PySide6.QtWidgets import QSystemTrayIcon
    window.preferences.close_action = 'tray'
    monkeypatch.setattr(QSystemTrayIcon, 'isSystemTrayAvailable', lambda: False)
    monkeypatch.setattr(window, 'choose_close_action', lambda: (None, False))
    window.show()
    window.close()
    assert window.isVisible() and window.session.unlocked
    monkeypatch.setattr(window, 'choose_close_action', lambda: ('quit', False))
    window.close()
    assert window.session.store._lock is None


def test_window_uses_website_lock_icon(window):
    from pathlib import Path
    import struct
    icon = Path(__file__).resolve().parents[1] / 'src/password_manager/assets/app.ico'
    source = Path(__file__).resolve().parents[1] / 'web/password-manager/dist/icon.svg'
    assert icon.with_suffix('.svg').read_bytes() == source.read_bytes()
    assert struct.unpack_from('<HHH', icon.read_bytes()) == (0, 1, 10)
    assert not window.windowIcon().isNull()
    assert window.windowIcon().pixmap(32, 32).width() == 32


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
    widget.preferences.close_action = "quit"
    widget.updates.scheduled = True
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.No)
    widget.session.access, widget.session.document, _ = store.create(PASSWORD)
    widget.build_editor()
    yield widget
    widget.dirty = False
    widget.quit_application()
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
        widget.quit_application()
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
        widget.quit_application()
        app.processEvents()
