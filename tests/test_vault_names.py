from datetime import datetime, timezone
from copy import deepcopy

import pytest

from password_manager import model
from password_manager.errors import InvalidVault, VaultError
from password_manager.vault_names import backup_name, validate_name


def test_named_backup_and_old_document_compatibility():
    assert backup_name('Main', datetime(2026, 10, 25, 15, 21, 50, tzinfo=timezone.utc)) == 'Main-Backup-2026-10-25-15:21:50.pmvault'
    doc = model.new_document()
    model.validate(doc)
    doc['settings']['vault_name'] = 'Личное'
    model.validate(doc)
    for value in ['', '  ', 'x' * 101, 'bad\nname', 5]:
        with pytest.raises(VaultError):
            validate_name(value)
        invalid = deepcopy(doc)
        invalid['settings']['vault_name'] = value
        with pytest.raises(InvalidVault):
            model.validate(invalid)
