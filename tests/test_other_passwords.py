from copy import deepcopy
import uuid

import pytest

from password_manager import model, sync_state
from password_manager.crypto import Access, unlock
from password_manager.errors import VaultError, InvalidVault


def test_password_only_filter_encryption_sync_and_trash():
    doc = model.new_document()
    normal = model.save_entry(doc, {'title': 'Ordinary account', 'password': 'Normal'})
    eid = model.save_entry(doc, {'entry_type': 'password', 'password': 'ONLY-PASSWORD-FIXTURE', 'note': 'Замок на двери\nПодробности'})
    assert doc['entries'][eid]['title'] == 'Замок на двери'
    assert [e['id'] for e in model.search(doc, category_id='other-passwords')] == [eid]
    assert len(model.search(doc)) == 2
    state = sync_state.seed(doc, str(uuid.uuid4()))
    doc['sync'] = {'state':state, 'pending':None, 'published':None, 'seen':{}}
    assert sync_state.project(doc, state)['entries'][eid]['entry_type'] == 'password'
    access, _ = Access.create('Other password fixture')
    blob = access.encode(model.validate(doc))
    assert b'ONLY-PASSWORD-FIXTURE' not in blob
    assert unlock(blob, 'Other password fixture')[1]['entries'][eid]['note'] == 'Замок на двери\nПодробности'
    model.trash(doc, eid)
    assert model.search(doc, category_id='other-passwords') == []
    model.restore(doc, eid)
    assert model.search(doc, 'password-fixture', 'other-passwords')[0]['id'] == eid
    assert doc['entries'][normal].get('entry_type') is None


def test_password_only_rejects_extra_identity_fields_and_empty_password():
    doc = model.new_document()
    for extra in [{'username':'user'}, {'email':'mail@example.invalid'}, {'second_password':'secret'}, {'entry_type':'unknown'}, {'password':''}]:
        values = {'entry_type':'password', 'password':'Fixture', **extra}
        with pytest.raises(VaultError):
            model.save_entry(doc, values)
        assert doc['entries'] == {}
    eid = model.save_entry(doc, {'entry_type':'password', 'password':'Fixture'})
    assert doc['entries'][eid]['title'] == 'Пароль'
    invalid = deepcopy(doc); invalid['entries'][eid]['phone'] = '+7999'
    with pytest.raises(InvalidVault):
        model.validate(invalid)


def test_suggestions_reuse_active_values_and_never_offer_passwords():
    doc = model.new_document()
    first = model.save_entry(doc, {'title':'One', 'email':'Name@example.invalid', 'phone':'+7999', 'username':'Login', 'site':'example.invalid', 'password':'Secret'})
    model.save_entry(doc, {'title':'Duplicate', 'email':'name@example.invalid'})
    deleted = model.save_entry(doc, {'title':'Deleted', 'email':'gone@example.invalid'})
    model.trash(doc, deleted)
    assert model.suggestions(doc, 'email') == ['Name@example.invalid']
    assert model.suggestions(doc, 'phone') == ['+7999']
    assert model.suggestions(doc, 'username') == ['Login']
    assert model.suggestions(doc, 'site') == ['example.invalid']
    assert model.suggestions(doc, 'password') == []
