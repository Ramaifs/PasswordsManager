"""Non-secret application preferences available before vault unlock."""
import json
import os
from pathlib import Path
import uuid

from .errors import VaultError

CLOSE_ACTIONS = {"ask", "tray", "quit"}
WINDOW_MODES = {"normal", "maximized", "fullscreen"}


class Preferences:
    def __init__(self, root):
        self.path = Path(root) / "preferences.json"
        self.close_action = "ask"
        self.window_mode = "normal"
        try:
            with self.path.open("rb") as stream:
                data = stream.read(1025)
            value = json.loads(data)
            if len(data) <= 1024 and isinstance(value, dict):
                action, mode = value.get("close_action"), value.get("window_mode")
                if isinstance(action, str) and action in CLOSE_ACTIONS:
                    self.close_action = action
                if isinstance(mode, str) and mode in WINDOW_MODES:
                    self.window_mode = mode
        except (OSError, ValueError, TypeError, AttributeError):
            pass

    def save_close_action(self, action):
        if not isinstance(action, str) or action not in CLOSE_ACTIONS:
            raise VaultError("Неизвестное действие при закрытии приложения.")
        self._save(action, self.window_mode)

    def save_window_mode(self, mode):
        if not isinstance(mode, str) or mode not in WINDOW_MODES:
            raise VaultError("Неизвестное состояние окна.")
        self._save(self.close_action, mode)

    def _save(self, action, mode):
        temporary = self.path.with_name("preferences-" + uuid.uuid4().hex + ".tmp")
        try:
            with temporary.open("x", encoding="utf-8") as stream:
                json.dump({"close_action": action, "window_mode": mode}, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
        self.close_action = action
        self.window_mode = mode
