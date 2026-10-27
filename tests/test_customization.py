from copy import deepcopy
from threading import Event
import hashlib
import uuid

import pytest

from password_manager import model, sync_state
from password_manager.crypto import Access, unlock, canonical
from password_manager.errors import InvalidVault, VaultError
from password_manager.session import Session
from password_manager.storage import Store
from password_manager.updates import download_release, release_versions


def test_additional_fields_encryption_search_sync_and_validation():
    doc = model.new_document()
    extra = {key: [key + '-EXTRA-SECRET'] for key in model.EXTRA_FIELDS}
    extra['phone'] = ['+7 (999) 456-12-34']
    eid = model.save_entry(doc, {'title': 'Fixture', 'additional_fields': extra})
    doc['settings']['accent_color'] = '#007755'
    model.validate(doc)
    assert model.search(doc, '+7999456')[0]['id'] == eid
    assert model.suggestions(doc, 'email') == extra['email']
    access, _ = Access.create('Customization fixture')
    encoded = access.encode(doc)
    assert b'EXTRA-SECRET' not in encoded
    opened = unlock(encoded, 'Customization fixture')[1]
    state = sync_state.seed(opened, str(uuid.uuid4()))
    opened['sync'] = {'state': state, 'pending': None, 'published': None, 'seen': {}}
    assert sync_state.project(opened, state)['entries'][eid]['additional_fields'] == extra
    for invalid in [[], {'password': 'text'}, {'password': [None]}, {'password': ['x'] * 101}, {'unknown': ['x']}]:
        broken = deepcopy(doc)
        broken['entries'][eid]['additional_fields'] = invalid
        with pytest.raises(InvalidVault):
            model.validate(broken)
        with pytest.raises(InvalidVault):
            sync_state.seed(broken, str(uuid.uuid4()))


def test_legacy_migration_preserves_secrets_and_creates_fresh_causal_values(tmp_path):
    store = Store(tmp_path / 'migration')
    password = 'Migration fixture master'
    doc = model.new_document()
    legacy = '  Legacy; password\nwith newline  '
    eid = model.save_entry(doc, {'title': 'Legacy', 'old_passwords': legacy, 'second_password': '2FA unchanged'})
    doc['drafts']['new'] = {**{key: '' for key in model.FIELDS}, 'old_passwords': legacy, 'category': None}
    state = sync_state.seed(doc, str(uuid.uuid4()))
    doc['sync'] = {'state': state, 'pending': None, 'published': None, 'seen': {}}
    before = canonical(state)
    access, _ = Access.create(password)
    store.commit(access, doc)
    session = Session(store)
    try:
        session.open(password)
        record = session.document['entries'][eid]
        assert record['old_passwords'] == ''
        assert record['additional_fields']['password'] == [legacy]
        assert record['second_password'] == '2FA unchanged'
        assert session.document['drafts']['new']['additional_fields']['password'] == [legacy]
        assert canonical(state) == before
        assert session.document['sync']['state'] != state
        assert store.open(password)[1] == session.document
        again = deepcopy(session.document)
        model.migrate_old_passwords(again)
        assert again == session.document
    finally:
        store.close()


def test_bulk_passwords_keep_spaces_and_stay_out_of_uncategorized():
    doc = model.new_document()
    normal = model.save_entry(doc, {'title': 'Normal'})
    ids = model.paste_passwords(doc, ' first \r\nsecond\n\nthird\r')
    assert [doc['entries'][eid]['password'] for eid in ids] == [' first ', 'second', 'third']
    assert [record['id'] for record in model.search(doc, category_id=None)] == [normal]
    assert len(model.search(doc, category_id='other-passwords')) == 3
    before = deepcopy(doc)
    with pytest.raises(VaultError):
        model.paste_passwords(doc, 'valid\n' + 'x' * 100001)
    assert doc == before


def test_release_list_and_verified_download_cancel_corruption(tmp_path):
    releases = [{'tag_name': 'v0.41', 'assets': [{'name': name} for name in ['PasswordsManager.exe', 'manifest.json']]},
                {'tag_name': 'v0.40', 'assets': []}, {'tag_name': '../bad', 'assets': []}]
    assert release_versions(fetch=lambda *a, **k: canonical(releases)) == [{'version': '0.41', 'tag': 'v0.41'}]
    installer = b'MZ-FICTIONAL-INSTALLER'
    manifest = {'version': '0.41', 'files': {'PasswordsManager.exe': {'bytes': len(installer), 'sha256': hashlib.sha256(installer).hexdigest()}}}
    def stream(url, **kwargs):
        assert url.startswith('https://github.com/Ramaifs/PasswordsManager/releases/download/v0.41/')
        yield canonical(manifest) if url.endswith('manifest.json') else installer
    result = download_release({'tag': 'v0.41'}, tmp_path, cancel=Event(), stream=stream)
    assert result['path'].read_bytes() == installer
    manifest['files']['PasswordsManager.exe']['sha256'] = '0' * 64
    with pytest.raises(VaultError):
        download_release({'tag': 'v0.41'}, tmp_path, cancel=Event(), stream=stream)
    assert result['path'].read_bytes() == installer
    assert not list(tmp_path.rglob('*.partial'))
    cancel = Event()
    cancel.set()
    with pytest.raises(VaultError):
        download_release({'tag': 'v0.41'}, tmp_path, cancel=cancel, stream=stream)
    with pytest.raises(VaultError):
        download_release({'tag': '../bad'}, tmp_path, cancel=Event(), stream=stream)
