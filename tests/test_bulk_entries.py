from copy import deepcopy
import uuid
import pytest
from password_manager import model, sync_state
from password_manager.crypto import Access, unlock
from password_manager.errors import VaultError, InvalidVault


def test_bulk_color_category_preserves_password_type_and_syncs():
    doc = model.new_document()
    category = model.category(doc, 'Work')
    first = model.save_entry(doc, {'title':'Account', 'password':'SECRET-FIXTURE'})
    second = model.save_entry(doc, {'entry_type':'password', 'password':'OTHER-SECRET', 'note':'31'})
    untouched = model.save_entry(doc, {'title':'Untouched'})
    before = deepcopy(doc['entries'][untouched])
    model.bulk_edit(doc, [first, second], 'color', '#12ab34')
    model.bulk_edit(doc, [first, second], 'category', category)
    model.validate(doc)
    assert doc['entries'][second]['entry_type'] == 'password'
    assert len(model.search(doc, category_id=category)) == 2
    assert [record['id'] for record in model.search(doc, category_id=None)] == [untouched]
    assert len(model.search(doc, category_id='other-passwords')) == 1
    assert doc['entries'][untouched] == before
    model.save_entry(doc, {key: doc['entries'][first].get(key, '') for key in model.FIELDS}, first)
    assert doc['entries'][first]['color'] == '#12ab34'
    actor = str(uuid.uuid4())
    state = sync_state.seed(doc, actor)
    doc['sync'] = {'state':state, 'pending':None, 'published':None, 'seen':{}}
    access, _ = Access.create('Bulk test master')
    assert unlock(access.encode(doc), 'Bulk test master')[1]['entries'][second]['category'] == category
    assert sync_state.project(doc, state)['entries'][second]['color'] == '#12ab34'
    model.bulk_edit(doc, [first, second], 'color', None)
    assert all('color' not in doc['entries'][eid] for eid in [first, second])
    with pytest.raises(VaultError):
        model.bulk_edit(doc, [first], 'color', 'bad')
    doc['entries'][first]['color'] = 1
    with pytest.raises(InvalidVault):
        model.validate(doc)


def test_bulk_paste_continues_highest_active_number_without_counting_accounts():
    doc = model.new_document()
    model.save_entry(doc, {'title':'Account', 'note':'999'})
    model.save_entry(doc, {'entry_type':'password', 'password':'Existing', 'note':'31'})
    deleted = model.save_entry(doc, {'entry_type':'password', 'password':'Deleted', 'note':'100'})
    model.trash(doc, deleted)
    ids = model.paste_passwords(doc, ' FIRST \r\nSECOND\n')
    assert [doc['entries'][eid]['note'] for eid in ids] == ['32','33']
    again = model.paste_passwords(doc, 'THIRD')
    assert doc['entries'][again[0]]['note'] == '34'
    assert doc['entries'][ids[0]]['password'] == ' FIRST '
