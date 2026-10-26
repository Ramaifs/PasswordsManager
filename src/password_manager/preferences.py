"""Non-secret application preferences available before vault unlock."""
import json
import os
from pathlib import Path
import uuid

from .errors import VaultError

CLOSE_ACTIONS = {"ask", "tray", "quit"}


class Preferences:
    def __init__(self, root):
        self.path = Path(root) / "preferences.json"
        self.close_action = "ask"
        try:
            with self.path.open("rb") as stream:
                data = stream.read(1025)
            value = json.loads(data)
            if len(data) <= 1024 and value.get("close_action") in CLOSE_ACTIONS:
                self.close_action = value["close_action"]
        except (OSError, ValueError, TypeError, AttributeError):
            pass

    def save_close_action(self, action):
        if not isinstance(action, str) or action not in CLOSE_ACTIONS:
            raise VaultError("Неизвестное действие при закрытии приложения.")
        temporary = self.path.with_name("preferences-" + uuid.uuid4().hex + ".tmp")
        try:
            with temporary.open("x", encoding="utf-8") as stream:
                json.dump({"close_action": action}, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
        self.close_action = action
