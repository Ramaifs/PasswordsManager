import { test } from 'node:test';
import assert from 'node:assert/strict';
import { SyncSchedule, syncMinutes } from '../dist/sync-schedule.js';
import { newDocument, validateDocument } from '../dist/core.js';

test('default five minutes, custom interval, disabled mode, delayed background and manual reset', () => {
  let now = 1000;
  const schedule = new SyncSchedule(() => now);
  assert.equal(syncMinutes({}), 5);
  now += 299999; assert.equal(schedule.due(5), false);
  now++; assert.equal(schedule.due(5), true);
  schedule.reset(5); assert.equal(schedule.due(5), false);
  now += 600000; assert.equal(schedule.due(5), true);
  assert.equal(schedule.due(2), false); // changed interval starts a fresh deadline
  now += 120000; assert.equal(schedule.due(2), true);
  schedule.reset(0); now += 86400000; assert.equal(schedule.due(0), false);
  schedule.reset(0); assert.equal(schedule.due(0), false); // manual action works outside scheduler
  for (const minutes of [0, 1, 5, 1440]) {
    const doc = newDocument(); doc.settings.sync_minutes = minutes; validateDocument(doc);
  }
  for (const minutes of [-1, 1441, 2.5, true, '5', null]) {
    const doc = newDocument(); doc.settings.sync_minutes = minutes; assert.throws(() => validateDocument(doc));
  }
});
