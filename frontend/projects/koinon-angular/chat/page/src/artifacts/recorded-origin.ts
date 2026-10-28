// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { KoinonTextPipe } from '@fireflyframework/koinon-angular';
import type { NativeReadOrigin } from '@fireflyframework/koinon-sdk';
const FIELDS: readonly (readonly [keyof NativeReadOrigin, string])[] = [
  ['original_filename', 'Original file'],
  ['sheet_or_json_path', 'Sheet or JSON path'],
  ['connection_name', 'Original connection'],
  ['database', 'Original database'],
  ['schema', 'Original schema'],
  ['table', 'Original table'],
];
@Component({
  selector: 'ffk-recorded-origin',
  imports: [KoinonTextPipe],
  template: `
    <h4>{{ heading | ffkText }}</h4>
    @if (hasFacts()) {
      <dl>
        @for (row of rows(); track row.key) {
          <dt>{{ row.label | ffkText }}</dt>
          <dd>{{ row.value }}</dd>
        }
      </dl>
    } @else if (origin?.connection_id) {
      <p>{{ 'Connection reference recorded.' | ffkText }}</p>
    } @else {
      <p>{{ 'Original source identity was not recorded.' | ffkText }}</p>
    }
  `,
  styleUrl: './recorded-origin.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonRecordedOrigin {
  @Input() heading = 'Recorded source origin';
  @Input() origin: NativeReadOrigin | null | undefined = null;
  hasFacts() {
    return this.rows().length > 0;
  }
  rows() {
    return FIELDS.flatMap(([key, label]) => {
      const value = this.origin?.[key];
      return typeof value === 'string' && value.trim() ? [{ key, label, value }] : [];
    });
  }
}
