// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  ElementRef,
  Injector,
  afterNextRender,
  Component,
  PendingTasks,
  effect,
  untracked,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { KoinonButton, KoinonTextPipe, KoinonPagination } from '@fireflyframework/koinon-angular';
import { KoinonOrganizationDirectory } from '@fireflyframework/koinon-angular/workbench';
import type { OrganizationPerson } from '@fireflyframework/koinon-sdk';
import { KoinonOrganizationUnitBrowser } from './organization-unit-browser';
@Component({
  selector: 'ffk-organization-structure',
  imports: [
    FormsModule,
    KoinonButton,
    KoinonTextPipe,
    KoinonPagination,
    KoinonOrganizationUnitBrowser,
  ],
  providers: [KoinonOrganizationDirectory],
  templateUrl: './organization-structure.html',
  styleUrl: './organization-directory.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonOrganizationStructure {
  readonly s = inject(KoinonOrganizationDirectory);
  private readonly tasks = inject(PendingTasks);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly injector = inject(Injector);
  private focusBranch() {
    afterNextRender(
      () => {
        const element = this.host.nativeElement;
        const target =
          element.querySelector<HTMLElement>('.branch-path [aria-current]') ||
          element.querySelector<HTMLElement>('.branch-path button');
        target?.focus();
      },
      { injector: this.injector },
    );
  }
  readonly tab = signal<'units' | 'reports'>('units');
  readonly path = signal<OrganizationPerson[]>([]);
  query = '';
  private appliedQuery = '';
  constructor() {
    effect(() => {
      this.s.contextIdentity();
      untracked(() => {
        this.path.set([]);
        this.query = '';
        this.appliedQuery = '';
        if (!this.s.denied() && this.tab() === 'reports') this.tasks.run(() => this.load());
      });
    });
  }
  apply() {
    this.appliedQuery = this.query;
    return this.load();
  }
  load(page = 1) {
    const manager = this.path().at(-1);
    return manager?.id
      ? this.s.loadReports(manager.id, page)
      : this.s.loadPeople({ q: this.appliedQuery, page });
  }
  async open(person: OrganizationPerson) {
    if (!person.id || this.path().length >= 32) return;
    this.path.update((path) => [...path, person]);
    const loaded = await this.load();
    this.focusBranch();
    return loaded;
  }
  async back(index: number) {
    this.path.update((path) => path.slice(0, index));
    const loaded = await this.load();
    this.focusBranch();
    return loaded;
  }
}
