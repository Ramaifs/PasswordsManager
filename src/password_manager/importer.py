"""All-or-nothing legacy preview; errors contain neither field names nor values."""
from .crypto import parse, MAX_FILE
from .errors import VaultError, InvalidVault

MAPPING = {"Username": "username", "Email": "email", "Phone": "phone", "Password": "password"}


def preview_legacy(data: bytes) -> list[dict]:
    try:
        if len(data) > MAX_FILE:
            raise InvalidVault()
        root = parse(data)
        if not isinstance(root, dict) or not root:
            raise InvalidVault()
        rows = []
        for platform, accounts in root.items():
            if not isinstance(platform, str) or not platform.strip() or not isinstance(accounts, list) or not accounts:
                raise InvalidVault()
            for account in accounts:
                if not isinstance(account, dict) or set(account) - MAPPING.keys():
                    raise InvalidVault()
                if any(not isinstance(v, str) for v in account.values()):
                    raise InvalidVault()
                rows.append({"title": platform, **{new: account.get(old, "") for old, new in MAPPING.items()},
                             "site": "", "note": "", "category": None})
        return rows
    except InvalidVault:
        raise VaultError("Импорт отменён: неверная схема, повторяющиеся ключи или неизвестные поля. Источник не изменён.") from None
