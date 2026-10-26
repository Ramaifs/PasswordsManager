class VaultError(Exception):
    """Safe, user-facing error; never include input or secrets."""


class InvalidVault(VaultError):
    def __init__(self):
        super().__init__("Неверный секрет или повреждённое хранилище.")


class StorageError(VaultError):
    def __init__(self):
        super().__init__("Не удалось сохранить данные. Последнее подтверждённое состояние сохранено.")
