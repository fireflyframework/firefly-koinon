// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { Injectable, signal } from '@angular/core';
// The page shares presentation ownership only after each result has been authorized.
@Injectable()
export class KoinonEvidenceGroups {
  private readonly groups = signal(new Map<string, readonly object[]>());
  claim(key: string, owner: object) {
    this.groups.update((groups) => {
      const rows = groups.get(key) ?? [];
      if (rows.includes(owner)) return groups;
      return new Map(groups).set(key, [...rows, owner]);
    });
  }
  visible(key: string, owner: object) {
    return this.groups().get(key)?.[0] === owner;
  }
  release(key: string, owner: object) {
    this.groups.update((groups) => {
      const rows = (groups.get(key) ?? []).filter((row) => row !== owner);
      const updated = new Map(groups);
      if (rows.length) updated.set(key, rows);
      else updated.delete(key);
      return updated;
    });
  }
}
