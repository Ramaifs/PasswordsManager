import {test} from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import path from 'node:path';
import {newDocument, validateDocument, trackChanges} from '../dist/core.js';
import {seed, project, merge} from '../dist/sync.js';
import {categoryRows, visibleCategoryRows, moveCategory, descendants, removeCategory} from '../dist/categories.js';

function fixture() {
  const doc = newDocument(), a = crypto.randomUUID(), b = crypto.randomUUID(), c = crypto.randomUUID();
  doc.categories = {[a]:'Work', [b]:'Accounts', [c]:'Mail'};
  doc.category_parents = {[b]:a, [c]:b};
  return {doc, a, b, c};
}

test('folding hides descendants without modifying data; moving keeps branches and prevents cycles', () => {
  const { doc, a, b, c } = fixture();
  const before = structuredClone(doc);
  assert.deepEqual(visibleCategoryRows(doc, new Set([a])).map(row => row.id), [a]);
  assert.deepEqual(doc, before);
  assert.equal(visibleCategoryRows(doc)[0].hasChildren, true);
  moveCategory(doc, b, null);
  assert.deepEqual(categoryRows(doc).map(row => row.depth), [0, 0, 1]);
  assert.equal(doc.category_parents[c], b);
  moveCategory(doc, b, a);
  assert.deepEqual(doc, before);
  for (const [id, parent] of [[a, c], [b, b], ['missing', a]]) {
    assert.throws(() => moveCategory(doc, id, parent));
    assert.deepEqual(doc, before);
  }
});
test('nested tree, subtree filter, delete promotion and legacy migration', () => {
  const {doc,a,b,c} = fixture();
  assert.deepEqual(categoryRows(doc).map(row=>row.depth), [0,1,2]);
  assert.equal(categoryRows(doc)[2].path, 'Work / Accounts / Mail');
  assert(descendants(doc,a).has(c));
  removeCategory(doc,b); assert.equal(doc.category_parents[c],a);
  removeCategory(doc,a); assert.deepEqual(doc.category_parents,{}); assert(doc.categories[c]);
  validateDocument(doc);
  const old = newDocument(); delete old.category_parents; validateDocument(old); assert.deepEqual(old.category_parents,{});
});
test('parent metadata survives JS to Python and Python to JS causal projection', () => {
  const {doc} = fixture(), actor = crypto.randomUUID();
  const state = seed(doc,actor);
  doc.sync = {state,pending:null,published:null,seen:{}};
  const python = process.env.PM_TEST_PYTHON || path.resolve('../../.venv/Scripts/python.exe');
  const code = 'import json,sys; from password_manager import model,sync_state; d=json.load(sys.stdin); model.validate(d); d=sync_state.project(d,d["sync"]["state"]); print(json.dumps(d))';
  const result = spawnSync(python,['-c',code],{input:JSON.stringify(doc),encoding:'utf8',env:{...process.env,PYTHONPATH:path.resolve('../../src')}});
  assert.equal(result.status,0,result.stderr);
  const returned = JSON.parse(result.stdout); validateDocument(returned);
  assert.deepEqual(returned.category_parents,doc.category_parents);
  assert.deepEqual(project(returned,returned.sync.state).category_parents,doc.category_parents);
});
test('concurrent parent cycle is normalized identically without deleting categories', () => {
  const doc = newDocument(), a=crypto.randomUUID(), b=crypto.randomUUID(), actor=crypto.randomUUID(), other=crypto.randomUUID();
  doc.categories = {[a]:'A',[b]:'B'}; doc.sync={state:seed(doc,actor),pending:null,published:null,seen:{}};
  const left=structuredClone(doc),right=structuredClone(doc);
  left.category_parents[a]=b; right.category_parents[b]=a;
  trackChanges(doc,left,actor);trackChanges(doc,right,other);
  assert.deepEqual(project(doc,merge(left.sync.state,right.sync.state)).category_parents,{});
  assert.equal(Object.keys(project(doc,merge(right.sync.state,left.sync.state)).categories).length,2);
  doc.category_parents={[a]:b,[b]:a};assert.throws(()=>validateDocument(doc));
});
