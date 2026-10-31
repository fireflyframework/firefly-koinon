// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { Component, Input, Output, EventEmitter, ChangeDetectionStrategy } from '@angular/core';
import { KoinonButton, KoinonTextPipe, KoinonValuePipe } from '@fireflyframework/koinon-angular';
import type { ModelOptionField, ModelOptionValues } from './model-options';
@Component({
  selector: 'ffk-model-options-form',
  imports: [KoinonButton, KoinonTextPipe, KoinonValuePipe],
  templateUrl: './model-options-form.html',
  styleUrl: './model-options-form.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonModelOptionsForm {
  @Input() fields: ModelOptionField[] = [];
  @Input() values: ModelOptionValues = {};
  @Input() errors: Record<string, string> = {};
  @Output() valuesChanged = new EventEmitter<ModelOptionValues>();
  text(name: string) {
    const value = this.values[name];
    return typeof value === 'string' ? value : '';
  }
  optionLabel(field: ModelOptionField, value: string) {
    return field.name === 'output_mode'
      ? value === 'native' ? 'Native JSON' : 'Default structured output'
      : value;
  }
  list(name: string) {
    const value = this.values[name];
    return Array.isArray(value) ? value : [];
  }
  set(name: string, value: string | string[]) {
    this.valuesChanged.emit({ ...this.values, [name]: value });
  }
  add(name: string) {
    this.set(name, [...this.list(name), '']);
  }
  remove(name: string, index: number) {
    this.set(
      name,
      this.list(name).filter((_, position) => position !== index),
    );
  }
  setItem(name: string, index: number, value: string) {
    this.set(
      name,
      this.list(name).map((item, position) => (position === index ? value : item)),
    );
  }
  hiddenErrors() {
    return Object.entries(this.errors).filter(
      ([name]) => !this.fields.some((field) => field.name === name),
    );
  }
}
