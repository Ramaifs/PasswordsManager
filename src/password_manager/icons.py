"""The same lock mark used by the website and the Windows executable."""
from pathlib import Path

from PySide6.QtGui import QIcon


def application_icon():
    return QIcon(str(Path(__file__).with_name("assets") / "app.ico"))
