"""Vault display names and human-readable Drive backup names."""
from datetime import datetime, timezone
import re

from .errors import VaultError


def validate_name(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 100 or any(ord(c) < 32 for c in value):
        raise VaultError("Название хранилища должно содержать от 1 до 100 символов без управляющих знаков.")
    return value.strip()


def backup_name(name, moment=None):
    name = re.sub(r'[<>:"/\\|?*]', '_', validate_name(name))
    stamp = (moment or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime('%Y-%m-%d-%H:%M:%S')
    return f"{name}-Backup-{stamp}.pmvault"
