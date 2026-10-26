"""Frozen/source smoke harness. Own temporary vault, no desktop/Drive/real clipboard."""
import json
from pathlib import Path
import tempfile
import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QFontDatabase

from . import __version__, model
from .app import Window, configure_app
from .storage import Store
from .generator import generate
from .crypto import Access, unlock, validate_password
from .errors import VaultError


def run(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    font = Path("C:/Windows/Fonts/segoeui.ttf")
    if font.exists():
        QFontDatabase.addApplicationFont(str(font))
        app.setFont(QFont("Segoe UI", 10))
    configure_app(app)
    results = {"version": __version__, "level": "offscreen smoke", "frozen": bool(getattr(sys, "frozen", False)),
               "executable": sys.executable, "checks": []}
    try:
        try:
            validate_password("1234567")
        except VaultError:
            results["checks"].append("seven-character-master-rejected")
        else:
            raise AssertionError("Seven characters must be rejected")
        old_access, _ = Access.create("Legacy fictional master phrase")
        assert unlock(old_access.encode(model.new_document()), "Legacy fictional master phrase")[1] == model.new_document()
        results["checks"].append("legacy-long-master-compatibility")
        if results["frozen"]:
            import argon2, cryptography, PySide6
            base = Path(sys._MEIPASS).resolve()
            for module in (argon2, cryptography, PySide6):
                assert Path(module.__file__).resolve().is_relative_to(base)
            results["checks"].append("dependencies-from-bundle")
        if sys.platform == "win32":
            import ctypes
            results["non_admin"] = not bool(ctypes.windll.shell32.IsUserAnAdmin())
        with tempfile.TemporaryDirectory(prefix="pm-smoke-") as temporary:
            store = Store(Path(temporary) / "vault")
            window = Window(store)
            assert not window.windowIcon().isNull()
            assert window.windowIcon().pixmap(32, 32).width() == 32
            results["checks"].append("packaged-application-lock-icon")
            window.updates.scheduled = True  # Offline fixture: no GitHub request.
            master = "тест1234"
            window.session.access, window.session.document, recovery = store.create(master)
            results["checks"].append("eight-character-master")
            window.build_editor()
            window.fields["title"].setText("Демонстрационный сервис")
            window.fields["site"].setText("https://example.invalid")
            window.fields["username"].setText("fictional-user")
            window.fields["email"].setText("demo@example.invalid")
            window.fields["password"].setText(generate()[0])
            window.fields["note"].setPlainText("Вымышленные данные для проверки сборки.")
            window.save()
            eid = window.selected_id
            assert store.open(master)[1]["entries"][eid]["email"] == "demo@example.invalid"
            results["checks"].append("gui-save-reopen")
            assert store.open(recovery, recovery=True)[1]["entries"][eid]["username"] == "fictional-user"
            results["checks"].append("recovery")
            window.refresh_entries()
            window.entries.setCurrentRow(0)
            window.show()
            app.processEvents()
            assert window.grab().save(str(output / "desktop-demo.png"))
            window.session.document["settings"]["theme"] = "light"
            window.apply_theme()
            app.processEvents()
            assert window.grab().save(str(output / "desktop-light.png"))
            window.session.document["settings"]["theme"] = "dark"
            window.apply_theme()
            window.resize(980, 640)
            app.processEvents()
            assert window.grab().save(str(output / "desktop-compact.png"))
            window.resize(1220, 820)
            results["checks"].append("qt-widgets-platform-render")
            window.lock_vault()
            assert not window.session.unlocked
            app.processEvents()
            assert window.grab().save(str(output / "desktop-locked.png"))
            window.master.setText(master)
            window.open_or_create()
            results["checks"].append("lock-unlock")
            window.dirty = False
            window.quit_application()
            app.processEvents()
        results["success"] = True
    except Exception:
        results["success"] = False
    (output / "smoke-result.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if results["success"] else 1
