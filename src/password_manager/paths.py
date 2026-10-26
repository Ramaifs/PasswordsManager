"""Installed builds keep data in AppData; portable builds use their own directory."""
import os
from pathlib import Path
import sys


def data_root():
    executable = Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False) and (executable / "portable.flag").is_file():
        return executable / "data"
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local" / "share"))) / "PersonalPasswordManager"
