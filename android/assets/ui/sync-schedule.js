// Elapsed-time scheduling; no publication is triggered by record edits.
export const DEFAULT_SYNC_MINUTES = 5;
export function syncMinutes(settings) { return settings.sync_minutes ?? DEFAULT_SYNC_MINUTES; }
export class SyncSchedule {
  constructor(clock = () => Date.now()) { this.clock = clock; this.reset(DEFAULT_SYNC_MINUTES); }
  reset(minutes) { this.minutes = minutes; this.lastAttempt = this.clock(); }
  due(minutes) {
    if (minutes !== this.minutes) { this.reset(minutes); return false; }
    return minutes > 0 && this.clock() - this.lastAttempt >= minutes * 60000;
  }
}
