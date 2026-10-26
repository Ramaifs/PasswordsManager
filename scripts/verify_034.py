"""Own fictional offscreen fixtures: views, settings, colors, Drive and paths."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from pathlib import Path
import json
import sys
import tempfile
import time
from types import SimpleNamespace
from PySide6.QtWidgets import QApplication, QDialog, QSpinBox, QPushButton, QCheckBox, QMessageBox, QInputDialog
from PySide6.QtTest import QTest
from password_manager.app import Window
from password_manager import model
from password_manager.storage import Store
from password_manager.sync_state import seed
from password_manager.paths import data_root
from password_manager.oauth import config

app = QApplication([])
class Checks(list):
    def append(self, item):
        super().append(item)
        print('PASS:', item, flush=True)
checks = Checks()
password = 'Fictional verification master'
def drain(window):
    deadline = time.monotonic() + 10
    while window.cloud.busy and time.monotonic() < deadline:
        app.processEvents()
        QTest.qWait(10)
    assert not window.cloud.busy
with tempfile.TemporaryDirectory(prefix='pm-034-') as temporary:
    window = Window(Store(Path(temporary) / 'original'))
    window.updates.scheduled = True
    window.session.access, window.session.document, _ = window.session.store.create(password)
    window.build_editor()
    window.fields['title'].setText('Fictional record')
    window.fields['password'].setText('Fictional secret')
    window.save()
    eid = window.selected_id
    assert all(field.isReadOnly() for field in window.fields.values())
    window.edit_entry()
    assert all(not field.isReadOnly() for field in window.fields.values())
    window.fields['note'].setPlainText('Edited note')
    window.save()
    assert window.session.store.open(password)[1]['entries'][eid]['note'] == 'Edited note'
    checks.append('view-edit-save-and-reopen-encrypted-vault')
    cid = window.session.mutate(lambda doc: model.category(doc, 'Fictional category'))
    def color(doc):
        doc['settings']['category_colors'] = {cid:'#12ab34'}
        doc['entries'][eid]['category'] = cid
    window.session.mutate(color)
    assert window.session.store.open(password)[1]['settings']['category_colors'][cid] == '#12ab34'
    window.refresh_categories()
    assert window.categories.item(2).foreground().color().name() == '#12ab34'
    window.fill_editor(window.session.document['entries'][eid])
    original_values = window.values()
    window.edit_entry()
    for key, field in window.fields.items():
        field.setPlainText('') if key == 'note' else field.setText('Main' if key == 'title' else '')
    window.save()
    visible = [key for key, field in window.fields.items() if not window.field_groups[field][0].isHidden()]
    assert visible == ['title'] and not window.field_groups[window.record_category][0].isHidden()
    assert window.reveal.isHidden() and window.copy_button.isHidden()
    window.edit_entry()
    assert all(not group[0].isHidden() for group in window.field_groups.values())
    window.fill_editor(original_values)
    window.edit_entry()
    window.save()
    checks.append('sparse-view-only-title-and-category-edit-shows-all-fields')
    window.session.mutate(lambda doc: model.delete_category(doc, cid))
    assert window.session.document['entries'][eid]['category'] is None
    assert cid not in window.session.document['settings']['category_colors']
    checks.append('category-color-persist-render-delete-keeps-record')
    original_exec = QDialog.exec
    def inspect_settings(dialog):
        buttons = dialog.findChildren(QPushButton)
        assert buttons[-1].text() == 'Сохранить'
        assert buttons[0].text() == 'Синхронизировать сейчас'
        assert dialog.findChildren(QCheckBox)[0].isChecked()
        dialog.findChildren(QSpinBox)[0].setValue(7)
        buttons[-1].click()
        return 0
    QDialog.exec = inspect_settings
    window.settings()
    QDialog.exec = original_exec
    assert window.session.document['settings']['sync_minutes'] == 7
    checks.append('settings-sync-up-top-save-bottom-checkbox-right')
    class Transport:
        remote = {}
        def __init__(self, *args): pass
        def fetch(self): return dict(self.remote)
        def publish(self, version, blob): self.remote[version] = blob; return blob
        def delete(self, version): self.remote.pop(version, None)
    window.cloud.connection = SimpleNamespace(exists=True)
    window.cloud.transport_factory = Transport
    window.cloud.sync()
    assert window.toast_label.text() == 'Синхронизация..'
    drain(window)
    assert window.toast_label.text() == 'Синхронизация выполнена!'
    assert '#ff9900' in window.toast_label.styleSheet()
    checks.append('real-qt-workers-encrypted-sync-progress-and-completion-toast')
    def fail(): raise OSError('fictional IO error')
    window.cloud._start(fail, lambda value: None)
    drain(window)
    assert window.toast_label.text() != 'Синхронизация выполнена!'
    checks.append('sync-failure-shows-error')
    QInputDialog.getItem = lambda parent, title, label, values, **kw: (values[0], True)
    restored = Window(Store(Path(temporary) / 'restored'))
    restored.updates.scheduled = True
    restored.cloud.connection = SimpleNamespace(exists=True)
    restored.cloud.transport_factory = Transport
    restored.master.setText(password)
    restored.cloud.open_from_drive()
    drain(restored)
    assert restored.session.unlocked
    assert restored.session.store.open(password)[1]['entries'][eid]['password'] == 'Fictional secret'
    checks.append('locked-screen-drive-open-master-password-decrypt-merge')
    wrong = Window(Store(Path(temporary) / 'wrong-password'))
    wrong.cloud.connection = SimpleNamespace(exists=True)
    wrong.cloud.transport_factory = Transport
    wrong.master.setText('wrong fictional password')
    wrong.cloud.open_from_drive()
    drain(wrong)
    assert not wrong.session.unlocked and not wrong.session.store.exists
    checks.append('drive-open-wrong-master-keeps-local-profile-empty')
    wrong.close()
    restored.lock_vault()
    restored.close()
    window.clear_editor()
    assert any(b.text() == '🔒 Заблокировать' for b in window.findChildren(QPushButton))
    window.lock_vault()
    assert not window.session.unlocked
    window.close()
    checks.append('global-lock-with-no-record-selected')
    app.processEvents()
    from password_manager import paths
    original_executable = sys.executable
    sys.executable = str(Path(temporary) / 'PasswordManager.exe')
    sys.frozen = True
    assert data_root().name == 'PersonalPasswordManager'
    (Path(temporary) / 'portable.flag').write_text('')
    assert data_root() == Path(temporary) / 'data'
    del sys.frozen
    sys.executable = original_executable
    checks.append('installed-appdata-and-marker-based-portable-paths')
    config(Path('src/password_manager/google-desktop.json'))
    checks.append('bundled-desktop-oauth-config-valid-no-browser-login-performed')
report = {'success':True, 'level':'source Qt offscreen / own fictional fixtures / fake Drive', 'checks':checks}
Path('artifacts/verification-034.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
