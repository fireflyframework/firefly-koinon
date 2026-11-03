// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
/** A single read-only observation loop. Scope owners remain responsible for aborting stale reads. */
export class UploadObservationLoop {
  private timer?: ReturnType<typeof setTimeout>;
  private running = false;
  private disposed = false;
  private delay = 0;
  private failures = 0;
  private epoch = 0;
  constructor(
    private readonly ports: {
      active(): boolean;
      visible(): boolean;
      interval?(): number;
      read(): Promise<void | boolean>;
    },
  ) {}
  update() {
    if (this.disposed || this.running) return;
    if (!this.ports.active()) {
      clearTimeout(this.timer);
      this.timer = undefined;
      return;
    }
    const delay = this.failures
      ? Math.min(60000, 30000 * 2 ** (this.failures - 1))
      : this.ports.visible()
        ? Math.max(5000, Math.min(60000, this.ports.interval?.() ?? 5000))
        : 30000;
    if (this.timer && delay === this.delay) return;
    clearTimeout(this.timer);
    this.delay = delay;
    this.timer = setTimeout(() => void this.tick(), delay);
  }
  private async tick() {
    this.timer = undefined;
    if (this.disposed || !this.ports.active()) return;
    this.running = true;
    const epoch = this.epoch;
    try {
      const success = await this.ports.read();
      if (epoch === this.epoch) this.failures = success === false ? Math.min(this.failures + 1, 4) : 0;
    } catch {
      if (epoch === this.epoch) this.failures = Math.min(this.failures + 1, 4);
    } finally {
      this.running = false;
      this.update();
    }
  }
  reset() {
    ++this.epoch;
    this.failures = 0;
    clearTimeout(this.timer);
    this.timer = undefined;
    this.update();
  }
  dispose() {
    this.disposed = true;
    clearTimeout(this.timer);
    this.timer = undefined;
  }
}
