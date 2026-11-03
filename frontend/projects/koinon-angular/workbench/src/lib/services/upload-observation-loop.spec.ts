// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { afterEach, expect, it, vi } from 'vitest';
import { UploadObservationLoop } from './upload-observation-loop';
afterEach(() => vi.useRealTimers());
it('has one read in flight, backs off when hidden, and stops on authority loss or disposal', async () => {
  vi.useFakeTimers();
  let active = true,
    visible = true,
    finish!: () => void;
  const read = vi.fn(
    () =>
      new Promise<void>((resolve) => {
        finish = resolve;
      }),
  );
  const loop = new UploadObservationLoop({ active: () => active, visible: () => visible, read });
  loop.update();
  await vi.advanceTimersByTimeAsync(5000);
  expect(read).toHaveBeenCalledTimes(1);
  loop.update();
  await vi.advanceTimersByTimeAsync(60000);
  expect(read).toHaveBeenCalledTimes(1);
  visible = false;
  finish();
  await Promise.resolve();
  await Promise.resolve();
  await vi.advanceTimersByTimeAsync(29999);
  expect(read).toHaveBeenCalledTimes(1);
  await vi.advanceTimersByTimeAsync(1);
  expect(read).toHaveBeenCalledTimes(2);
  active = false;
  loop.update();
  finish();
  await Promise.resolve();
  await Promise.resolve();
  await vi.advanceTimersByTimeAsync(60000);
  expect(read).toHaveBeenCalledTimes(2);
  active = true;
  loop.update();
  loop.dispose();
  await vi.advanceTimersByTimeAsync(60000);
  expect(read).toHaveBeenCalledTimes(2);
});
