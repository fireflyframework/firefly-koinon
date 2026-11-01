// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
export interface BrowserSession {
  subject?: string;
  authenticated?: boolean;
  expires_at?: string | null;
  authenticated_at?: string | null;
  server_time?: string;
}

export function sessionInstant(value: string | null | undefined): number {
  return typeof value === 'string' && /T.*(?:Z|[+-]\d{2}:\d{2})$/.test(value)
    ? Date.parse(value)
    : NaN;
}

/** An advisory server observation. It never derives lifetime from cookies or browser wall time. */
export class SessionClock {
  private deadline: number | null = null;
  private observedExpiry: number | null = null;
  observe(value: BrowserSession, started: number, received: number): boolean {
    const expiry = sessionInstant(value.expires_at);
    const server = sessionInstant(value.server_time);
    if (!Number.isFinite(expiry) || !Number.isFinite(server)) {
      this.clear();
      return false;
    }
    const deadline = received + Math.max(0, expiry - server - Math.max(0, received - started));
    this.deadline =
      expiry === this.observedExpiry && this.deadline !== null
        ? Math.min(this.deadline, deadline)
        : deadline;
    this.observedExpiry = expiry;
    return true;
  }
  remaining(now: number): number | null {
    return this.deadline === null ? null : Math.max(0, Math.ceil((this.deadline - now) / 1000));
  }
  clear(): void {
    this.deadline = this.observedExpiry = null;
  }
}
