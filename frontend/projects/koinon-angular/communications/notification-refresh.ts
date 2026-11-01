// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { Injectable, signal } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class KoinonNotificationRefresh {
  private readonly changes = signal(0);
  readonly revision = this.changes.asReadonly();

  invalidate() {
    this.changes.update((value) => value + 1);
  }
}
