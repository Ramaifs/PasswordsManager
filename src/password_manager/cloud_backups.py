"""Ordering and grouping of encrypted Google Drive copies."""
from datetime import datetime, timezone
import re


def backup_time(copy):
    for value in (copy.get("modifiedAt"), copy.get("createdAt")):
        try:
            moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if moment.tzinfo is not None:
                return moment.timestamp()
        except (ValueError, TypeError, AttributeError):
            pass
    match = re.search(r"-Backup-(\d{4}-\d\d-\d\d)-(\d\d:\d\d:\d\d)\.pmvault$", copy.get("name", ""))
    if match:
        try:
            return datetime.fromisoformat(match[1] + "T" + match[2]).replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            pass
    return float("-inf")


def ordered_copies(copies):
    return sorted(copies, key=lambda copy: (-backup_time(copy), copy.get("name", ""), copy["id"]))


def group_copies(copies, last_vault=None):
    ordered = ordered_copies(copies)
    latest = next((copy for copy in ordered if last_vault and copy.get("vaultId") == last_vault), None)
    return latest, [copy for copy in ordered if latest is None or copy["id"] != latest["id"]]


def display_time(copy):
    stamp = backup_time(copy)
    return "Время неизвестно" if stamp == float("-inf") else datetime.fromtimestamp(stamp, timezone.utc).strftime("%d.%m.%Y %H:%M:%S UTC")
