from copy import deepcopy

import pytest

from password_manager import model


@pytest.mark.parametrize('field', model.FIELDS)
def test_search_finds_text_in_every_record_field_without_modifying_document(field):
    doc = model.new_document()
    eid = model.save_entry(doc, {'title': 'Account', field: 'Начало ИСКОМЫЙ конец'})
    model.save_entry(doc, {'title': 'Other'})
    before = deepcopy(doc)
    result = model.search(doc, '  искомый  ')
    assert [e['id'] for e in result] == [eid]
    result[0]['title'] = 'Changed result'
    assert doc == before


@pytest.mark.parametrize('query', ['+7', '+7999', '9991234567', '+7 999 123-45-67', '(999) 123', '  +7 (999) 123-45-67  '])
def test_search_matches_phone_with_different_formatting(query):
    doc = model.new_document()
    eid = model.save_entry(doc, {'title': 'Account', 'phone': '+7 (999) 123-45-67'})
    model.save_entry(doc, {'title': 'Other', 'phone': '+1 (212) 555-0000'})
    assert [e['id'] for e in model.search(doc, query)] == [eid]


def test_phone_search_keeps_category_trash_and_legacy_record_boundaries():
    doc = model.new_document()
    root = model.category(doc, 'Root')
    child = model.category(doc, 'Child', parent_id=root)
    active = model.save_entry(doc, {'title': 'Active', 'phone': '+7 (999) 123-45-67', 'category': child})
    outside = model.save_entry(doc, {'title': 'Outside', 'phone': '+79991234567'})
    deleted = model.save_entry(doc, {'title': 'Deleted', 'phone': '+79991234567', 'category': root})
    model.trash(doc, deleted)
    for field in model.OPTIONAL_FIELDS:
        del doc['entries'][active][field]
    assert [e['id'] for e in model.search(doc, '+7999', root)] == [active]
    assert [e['id'] for e in model.search(doc, '+7999', root, deleted=True)] == [deleted]
    assert {e['id'] for e in model.search(doc, '  ')} == {active, outside}
    assert model.search(doc, '+7-no-match') == []
    assert model.search(doc, '---') == []


@pytest.mark.parametrize('number', ['+79991234567', '+7 (999) 123-45-67'])
def test_search_finds_number_in_note_without_phone_field(number):
    doc = model.new_document()
    eid = model.save_entry(doc, {'title': 'Account', 'note': 'Контакт: ' + number})
    assert [e['id'] for e in model.search(doc, '+7999')] == [eid]
