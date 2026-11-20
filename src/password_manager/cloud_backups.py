"""Ordering and grouping of encrypted Google Drive copies."""
from collections import Counter
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


WEEKDAYS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
MONTHS = ("янв.", "февр.", "мар.", "апр.", "мая", "июн.", "июл.", "авг.", "сент.", "окт.", "нояб.", "дек.")


def display_time(copy, seconds=False):
    stamp = backup_time(copy)
    if stamp == float("-inf"):
        return "Время неизвестно"
    date = datetime.fromtimestamp(stamp, timezone.utc)
    clock = date.strftime("%H:%M:%S" if seconds else "%H:%M")
    return f"{WEEKDAYS[date.weekday()]}, {date.day} {MONTHS[date.month - 1]} {date.year}, {clock} UTC"


def copy_times(copies):
    minutes = {copy["id"]: backup_time(copy) // 60 for copy in copies}
    counts = Counter(minutes.values())
    return {copy["id"]: display_time(copy, counts[minutes[copy["id"]]] > 1) for copy in copies}
