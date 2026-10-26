import json
import pytest
from password_manager.preferences import Preferences
from password_manager.errors import VaultError


def test_close_preference_survives_restart_and_can_return_to_ask(tmp_path):
    first = Preferences(tmp_path)
    assert first.close_action == 'ask'
    for action in ['tray', 'quit', 'ask']:
        first.save_close_action(action)
        assert Preferences(tmp_path).close_action == action
    assert json.loads((tmp_path / 'preferences.json').read_text()) == {'close_action': 'ask'}
    assert not list(tmp_path.glob('*.tmp'))
    for invalid in ['bad', None, []]:
        with pytest.raises(VaultError):
            first.save_close_action(invalid)
    assert Preferences(tmp_path).close_action == 'ask'


def test_damaged_or_oversized_preferences_default_to_question(tmp_path):
    for data in [b'broken', b'[]', b'{"close_action": []}', b' ' * 1025]:
        (tmp_path / 'preferences.json').write_bytes(data)
        assert Preferences(tmp_path).close_action == 'ask'
