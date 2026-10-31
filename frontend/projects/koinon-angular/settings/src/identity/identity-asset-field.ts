// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {
  Component,
  ChangeDetectionStrategy,
  Input,
  Output,
  EventEmitter,
  signal,
} from '@angular/core';
import { KoinonIcon, KoinonTextPipe } from '@fireflyframework/koinon-angular';
let nextAsset = 0;
@Component({
  selector: 'ffk-identity-asset',
  imports: [KoinonIcon, KoinonTextPipe],
  templateUrl: './identity-asset-field.html',
  styleUrl: './identity-asset-field.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonIdentityAssetField {
  @Input() label = '';
  @Input() hint = '';
  @Input() value: string | null = null;
  @Input() fallback = '';
  @Input() dark = false;
  @Input() square = false;
  @Input() disabled = false;
  @Input() busy = false;
  @Output() fileSelected = new EventEmitter<File>();
  @Output() removed = new EventEmitter<void>();
  readonly id = 'identity-asset-' + ++nextAsset;
  readonly dimensions = signal('');
  readonly dragging = signal(false);
  readonly failed = signal('');
  imageLoaded(event: Event) {
    const image = event.target as HTMLImageElement;
    this.dimensions.set(image.naturalWidth + ' × ' + image.naturalHeight + ' px');
  }
  select(event: Event) {
    const input = event.target as HTMLInputElement,
      file = input.files?.[0];
    input.value = '';
    if (file && !this.disabled) this.fileSelected.emit(file);
  }
  drop(event: DragEvent) {
    event.preventDefault();
    this.dragging.set(false);
    if (this.disabled) return;
    const file = event.dataTransfer?.files?.[0];
    if (file) this.fileSelected.emit(file);
  }
  drag(event: DragEvent) {
    if (this.disabled) return;
    event.preventDefault();
    this.dragging.set(true);
  }
}
