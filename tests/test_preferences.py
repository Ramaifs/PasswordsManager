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
    assert json.loads((tmp_path / 'preferences.json').read_text()) == {'close_action': 'ask', 'window_mode': 'normal'}
    assert not list(tmp_path.glob('*.tmp'))
    for invalid in ['bad', None, []]:
        with pytest.raises(VaultError):
            first.save_close_action(invalid)
    assert Preferences(tmp_path).close_action == 'ask'


def test_damaged_or_oversized_preferences_default_to_question(tmp_path):
    for data in [b'broken', b'[]', b'{"close_action": []}', b' ' * 1025]:
        (tmp_path / 'preferences.json').write_bytes(data)
        assert Preferences(tmp_path).close_action == 'ask'


def test_window_state_and_close_action_survive_each_others_updates(tmp_path):
    preferences = Preferences(tmp_path)
    preferences.save_close_action('tray')
    for mode in ['maximized', 'fullscreen', 'normal']:
        preferences.save_window_mode(mode)
        loaded = Preferences(tmp_path)
        assert loaded.window_mode == mode and loaded.close_action == 'tray'
    preferences.save_window_mode('maximized')
    preferences.save_close_action('quit')
    assert Preferences(tmp_path).window_mode == 'maximized'
    assert Preferences(tmp_path).close_action == 'quit'
    for mode in ['minimized', 'bad', None, []]:
        with pytest.raises(VaultError):
            preferences.save_window_mode(mode)
    assert Preferences(tmp_path).window_mode == 'maximized'


def test_legacy_preferences_and_invalid_window_mode(tmp_path):
    (tmp_path/'preferences.json').write_text('{"close_action":"tray"}')
    assert Preferences(tmp_path).window_mode == 'normal'
    (tmp_path/'preferences.json').write_text('{"close_action":"tray","window_mode":"bad"}')
    assert Preferences(tmp_path).window_mode == 'normal'
    assert Preferences(tmp_path).close_action == 'tray'
