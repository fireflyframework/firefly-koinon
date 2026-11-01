// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { activityWindow, defaultActivityDates } from '../../../../activity/window/window';
it('uses complete past UTC days and rejects future, reversed and impossible dates', () => {
  const now = new Date('2026-10-31T15:00:00Z');
  expect(defaultActivityDates(now)).toEqual({ start: '2026-10-24', end: '2026-10-31' });
  expect(activityWindow('2026-10-24', '2026-10-31', 'Europe/Madrid', now)).toEqual({
    start_at: '2026-10-24T00:00:00.000Z',
    end_at: '2026-10-31T00:00:00.000Z',
    time_zone: 'Europe/Madrid',
  });
  for (const [start, end] of [
    ['2026-10-31', '2026-11-01'],
    ['2026-10-31', '2026-10-31'],
    ['2026-02-30', '2026-03-01'],
  ])
    expect(activityWindow(start, end, 'UTC', now)).toBeNull();
});
