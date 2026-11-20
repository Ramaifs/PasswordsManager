import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from types import SimpleNamespace
import pytest
from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QPushButton
from password_manager.app import Window, NumberInput
from password_manager.storage import Store
from password_manager.sync import digest


@pytest.fixture
def window(tmp_path):
    app = QApplication.instance() or QApplication([])
    widget = Window(Store(tmp_path / 'vault'))
    widget.updates.scheduled = True
    widget.preferences.close_action = 'quit'
    widget.session.access, widget.session.document, _ = widget.session.store.create('Fictional 042 password')
    widget.build_editor()
    yield widget
    widget.dirty = False
    widget.quit_application()
    app.processEvents()


def test_remote_check_prompts_before_applying_and_decline_blocks_auto_sync(window, monkeypatch):
    cloud = window.cloud
    monkeypatch.setattr(cloud, 'connection', SimpleNamespace(exists=True))
    remote = {'fixture-version': b'ciphertext fixture'}
    monkeypatch.setattr(cloud, 'transport_factory', lambda *a: SimpleNamespace(fetch=lambda: remote))
    monkeypatch.setattr(cloud, '_start', lambda operation, callback: callback(operation()))
    applied = []
    monkeypatch.setattr(cloud, '_received', lambda transport, values: applied.append(values))
    monkeypatch.setattr(cloud, 'confirm_remote_changes', lambda remote: False)
    before = window.session.document.copy()
    cloud.check_remote_changes()
    assert window.session.document == before and not applied
    monkeypatch.setattr(cloud, 'sync', lambda: pytest.fail('Declined cloud version auto applied'))
    cloud.auto_sync()
    monkeypatch.setattr(cloud, 'confirm_remote_changes', lambda remote: True)
    cloud.check_remote_changes()
    assert applied == [remote]


def test_seen_remote_versions_do_not_prompt(window, monkeypatch):
    cloud = window.cloud
    monkeypatch.setattr(cloud, 'connection', SimpleNamespace(exists=True))
    window.session.document['sync'] = {'seen': {'known': {'digest': digest(b'ciphertext')}}}
    monkeypatch.setattr(cloud, 'transport_factory', lambda *a: SimpleNamespace(fetch=lambda: {'known': b'ciphertext'}))
    monkeypatch.setattr(cloud, '_start', lambda operation, callback: callback(operation()))
    monkeypatch.setattr(cloud, 'confirm_remote_changes', lambda remote: pytest.fail('Known version prompted'))
    cloud.check_remote_changes()


def test_wheel_requires_click_and_loses_permission_on_focus_out(window):
    control = NumberInput(window)
    control.setRange(1, 1440)
    control.setValue(5)
    control.show()
    window.show()
    QApplication.processEvents()
    def wheel():
        event = QWheelEvent(QPointF(10, 10), QPointF(10, 10), QPoint(), QPoint(0, 120), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
        QApplication.sendEvent(control, event)
    control.setFocus()
    wheel()
    assert control.value() == 5
    QTest.mouseClick(control.lineEdit(), Qt.MouseButton.LeftButton)
    wheel()
    assert control.value() == 6
    control.clearFocus()
    QApplication.processEvents()
    wheel()
    assert control.value() == 6


def test_deletion_category_opens_actions_and_keeps_updates_below(window, monkeypatch):
    from PySide6.QtWidgets import QCheckBox
    actions = ['Удалить облачные версии', 'Удалить локальное сохранение', 'Удалить приложение']
    opened = []
    def inspect(dialog):
        buttons = dialog.findChildren(QPushButton)
        labels = [button.text() for button in buttons]
        if dialog.objectName() == 'deletionSettings':
            opened.append(dialog.windowTitle())
            assert labels[:3] == actions
            assert all(button.objectName() == 'danger' for button in buttons[:3])
            return
        assert not set(actions).intersection(labels), 'Deletion actions leaked into the main settings list'
        category = next(button for button in buttons if button.text() == 'Удаление/Отключение')
        assert category.objectName() == 'danger'
        assert labels.index('Объединить файл') < labels.index(category.text()) < labels.index('Проверить обновления') < labels.index('Сохранить')
        updates = next(box for box in dialog.findChildren(QCheckBox) if box.text() == 'Проверять обновления при запуске')
        assert category.parentWidget().layout().indexOf(category) < category.parentWidget().layout().indexOf(updates)
        updates.setChecked(False)
        category.click()
        assert opened == ['Удаление/Отключение']
        next(button for button in buttons if button.text() == 'Сохранить').click()
    monkeypatch.setattr(QDialog, 'exec', inspect)
    window.settings()
    assert window.session.document['settings']['check_updates'] is False
    window.toast('Синхронизация выполнена!')
    assert '#48bf7b' in window.toast_label.styleSheet()
    window.toast('Синхронизация..')
    assert '#ff9900' in window.toast_label.styleSheet()


def test_local_delete_removes_generations_but_keeps_settings_and_other_files(tmp_path):
    store = Store(tmp_path / 'local')
    store.create('Fictional 042 password')
    (store.root / 'preferences.json').write_text('{}')
    (store.root / 'user-file.txt').write_text('keep')
    store.delete_local_save()
    assert not store.exists
    assert not list(store.root.glob('*/0.pmvault'))
    assert (store.root / 'preferences.json').exists()
    assert (store.root / 'user-file.txt').exists()
    assert store._lock is not None
    store.close()
