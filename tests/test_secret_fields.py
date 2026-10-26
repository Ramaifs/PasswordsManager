from copy import deepcopy
import uuid

import pytest

from password_manager import model, sync_state
from password_manager.crypto import Access, unlock, canonical
from password_manager.errors import InvalidVault


def test_all_password_fields_and_drafts_are_encrypted_and_recoverable():
    access, recovery = Access.create('Secret fields fixture')
    doc = model.new_document()
    secrets = {'password': 'PRIMARY-FICTIONAL-MARKER', 'second_password': 'SECOND-FICTIONAL-MARKER',
               'old_passwords': 'OLD-FICTIONAL-MARKER; previous password'}
    eid = model.save_entry(doc, {'title': 'Account', **secrets})
    doc['drafts']['new'] = {**{f: '' for f in model.FIELDS}, **secrets, 'category': None}
    blob = access.encode(model.validate(doc))
    for secret in secrets.values():
        assert secret.encode() not in blob
    for key, recovery_mode in [('Secret fields fixture', False), (recovery, True)]:
        opened = unlock(blob, key, recovery=recovery_mode)[1]
        assert all(opened['entries'][eid][f] == value for f, value in secrets.items())
        assert all(opened['drafts']['new'][f] == value for f, value in secrets.items())


def test_legacy_records_drafts_and_causal_values_stay_byte_identical():
    doc = model.new_document()
    eid = model.save_entry(doc, {'title': 'Legacy account'})
    for field in model.OPTIONAL_FIELDS:
        del doc['entries'][eid][field]
    doc['drafts']['new'] = {f: '' for f in model.FIELDS if f not in model.OPTIONAL_FIELDS}
    doc['drafts']['new']['category'] = None
    actor = str(uuid.uuid4())
    state = sync_state.seed(doc, actor)
    doc['sync'] = {'state': state, 'pending': None, 'published': None, 'seen': {}}
    before = canonical(doc)
    model.validate(doc)
    sync_state.validate(state)
    assert canonical(doc) == before
    assert sync_state.merge(state, deepcopy(state)) == state
    updated = deepcopy(doc)
    values = {f: doc['entries'][eid].get(f, '') for f in model.FIELDS}
    values.update(second_password='New second password', old_passwords='Old password')
    model.save_entry(updated, values, eid)
    sync_state.track(doc, updated, actor)
    merged = sync_state.merge(state, updated['sync']['state'])
    projected = sync_state.project(doc, merged)
    assert projected['entries'][eid]['second_password'] == 'New second password'
    assert projected['entries'][eid]['old_passwords'] == 'Old password'


@pytest.mark.parametrize('field', ['second_password', 'old_passwords'])
@pytest.mark.parametrize('value', [None, 123, [], 'x' * 100001], ids=['null', 'number', 'array', 'too-long'])
def test_optional_secrets_reject_invalid_values_in_records_drafts_and_sync(field, value):
    doc = model.new_document()
    eid = model.save_entry(doc, {'title': 'Account'})
    doc['entries'][eid][field] = value
    with pytest.raises(InvalidVault):
        model.validate(doc)
    with pytest.raises(InvalidVault):
        sync_state.seed(doc, str(uuid.uuid4()))
    doc['entries'][eid][field] = ''
    doc['drafts']['new'] = {**{f: '' for f in model.FIELDS}, 'category': None, field: value}
    with pytest.raises(InvalidVault):
        model.validate(doc)
