from copy import deepcopy
import uuid
import pytest
from password_manager import model, sync_state
from password_manager.errors import InvalidVault, VaultError

def test_nested_filter_deletion_and_legacy_migration():
    doc = model.new_document()
    root = model.category(doc, 'Work')
    child = model.category(doc, 'Accounts', parent_id=root)
    leaf = model.category(doc, 'Mail', parent_id=child)
    eid = model.save_entry(doc, {'title':'Mail account', 'category':leaf})
    assert [row[2] for row in model.category_rows(doc)] == [0,1,2]
    assert [entry['id'] for entry in model.search(doc, category_id=root)] == [eid]
    with pytest.raises(VaultError): model.category(doc, 'Work', root, parent_id=leaf)
    model.delete_category(doc, child)
    assert doc['category_parents'][leaf] == root
    assert doc['entries'][eid]['category'] == leaf
    model.delete_category(doc, root)
    assert doc['category_parents'] == {} and leaf in doc['categories']
    model.validate(doc)
    legacy = model.new_document(); del legacy['category_parents']
    assert model.validate(legacy)['category_parents'] == {}

def test_parent_register_sync_and_concurrent_cycle_is_deterministic():
    doc = model.new_document()
    a, b = model.category(doc, 'A'), model.category(doc, 'B')
    first, second = str(uuid.uuid4()), str(uuid.uuid4())
    state = sync_state.seed(doc, first)
    left, right = deepcopy(state), deepcopy(state)
    sync_state.write(left, first, 'category_parent:' + a, b)
    sync_state.write(right, second, 'category_parent:' + b, a)
    merged = sync_state.merge(left, right)
    doc['sync'] = {'state':merged, 'pending':None, 'published':None, 'seen':{}}
    assert sync_state.project(doc, merged)['category_parents'] == {}
    assert sync_state.project(doc, sync_state.merge(right, left))['category_parents'] == {}
    sync_state.write(left, first, 'category_parent:' + a, None)
    assert sync_state.project(doc, left)['category_parents'] == {}

def test_hierarchy_validation_and_parent_rename():
    doc = model.new_document()
    a = model.category(doc, 'A'); b = model.category(doc, 'B', parent_id=a)
    model.category(doc, 'Renamed', b)
    assert doc['category_parents'][b] == a
    doc['category_parents'][a] = b
    with pytest.raises(InvalidVault): model.validate(doc)
    doc['category_parents'] = {b: str(uuid.uuid4())}
    with pytest.raises(InvalidVault): model.validate(doc)


def test_move_category_keeps_subtree_entries_and_rejects_cycles_without_mutation():
    doc = model.new_document()
    a = model.category(doc, 'Work')
    b = model.category(doc, 'Mail', parent_id=a)
    c = model.category(doc, 'Personal')
    eid = model.save_entry(doc, {'title': 'Account', 'category': b})
    model.move_category(doc, a, c)
    assert model.category_path(doc, b) == 'Personal / Work / Mail'
    assert doc['entries'][eid]['category'] == b
    before = deepcopy(doc)
    for source, target in [(c, b), (a, a), (str(uuid.uuid4()), c)]:
        with pytest.raises(VaultError):
            model.move_category(doc, source, target)
        assert doc == before
    model.move_category(doc, a)
    assert a not in doc['category_parents'] and doc['category_parents'][b] == a
    model.validate(doc)
