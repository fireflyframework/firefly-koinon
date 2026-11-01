// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { SessionClock } from './session-clock';

it('uses server time and monotonic elapsed time instead of the browser wall clock', () => {
  const clock = new SessionClock();
  expect(
    clock.observe(
      { server_time: '2026-11-01T10:00:00Z', expires_at: '2026-11-01T10:02:00Z' },
      1000,
      1200,
    ),
  ).toBe(true);
  expect(clock.remaining(1200)).toBe(120);
  expect(clock.remaining(61200)).toBe(60);
  expect(clock.remaining(121200)).toBe(0);
});
it('never extends the same observed deadline or fabricates one for an old/custom backend', () => {
  const clock = new SessionClock();
  clock.observe({ server_time: '2026-11-01T10:00:00Z', expires_at: '2026-11-01T10:02:00Z' }, 0, 0);
  clock.observe(
    { server_time: '2026-11-01T10:00:00Z', expires_at: '2026-11-01T10:02:00Z' },
    10000,
    10000,
  );
  expect(clock.remaining(10000)).toBe(110);
  expect(
    clock.observe({ server_time: '2026-11-01T10:01:00Z', expires_at: null }, 10000, 10000),
  ).toBe(false);
  expect(clock.remaining(10000)).toBe(null);
  expect(clock.observe({}, 0, 0)).toBe(false);
  expect(
    clock.observe({ server_time: '2026-11-01T10:00:00', expires_at: '2026-11-01T10:02:00' }, 0, 0),
  ).toBe(false);
  expect(clock.observe({ server_time: 'invalid', expires_at: '2026-11-01T10:02:00Z' }, 0, 0)).toBe(
    false,
  );
});
it('accepts a genuinely new server deadline only from a fresh observation', () => {
  const clock = new SessionClock();
  clock.observe({ server_time: '2026-11-01T10:00:00Z', expires_at: '2026-11-01T10:02:00Z' }, 0, 0);
  clock.observe(
    { server_time: '2026-11-01T10:01:00Z', expires_at: '2026-11-01T10:31:00Z' },
    60000,
    60000,
  );
  expect(clock.remaining(60000)).toBe(1800);
  clock.clear();
  expect(clock.remaining(60000)).toBe(null);
});
