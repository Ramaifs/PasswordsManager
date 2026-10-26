import pytest
from password_manager.updates import latest_release, version_tuple, API
from password_manager.crypto import canonical
from password_manager.errors import VaultError
from password_manager.http_client import HttpError

def test_stable_versions_and_exact_github_origin():
    calls = []
    def fetch(method, url, **kwargs):
        calls.append((method,url,kwargs))
        return canonical({'tag_name':'v0.10.0', 'draft':False, 'prerelease':False, 'html_url':'https://attacker.invalid/'})
    value = latest_release(current='0.9.9', fetch=fetch)
    assert value['available'] and value['url'] == 'https://github.com/Ramaifs/PasswordsManager/releases/tag/v0.10.0'
    assert calls[0][1] == API and 'Authorization' not in calls[0][2]['headers']
    assert not latest_release(current='0.10.0', fetch=fetch)['available']
    assert not latest_release(current='1.0.0', fetch=fetch)['available']

def test_no_releases_network_errors_and_invalid_tags():
    def missing(*args, **kwargs): raise HttpError(404)
    assert latest_release(fetch=missing) == {'available':False, 'unpublished':True}
    def failed(*args, **kwargs): raise HttpError(403)
    with pytest.raises(VaultError): latest_release(fetch=failed)
    for tag in ['v1.0.0-beta', '../bad', 'v1', None, 'v1.2.3/../../bad']:
        with pytest.raises(VaultError): version_tuple(tag)
    with pytest.raises(VaultError): latest_release(fetch=lambda *a, **k: canonical({'tag_name':'v9.0.0','prerelease':True}))
